#!/usr/bin/env python3
r"""Match, then run the PheWAS with every tool, each into its own folder (D33-D36).

On the VM, from the pheauxWAS folder, everything is one short command (D36, D37):

    python phewas check     is everything here? Python packages, R and its packages, the files
    python phewas match     MatchIt -> runs\matching\
    python phewas balance   what to judge in the match: SMDs over 0.1, unmatched cases, controls per case
    python phewas sheet     one page: where the study stands and the next step (match prints it too)
    python phewas results   one page on one PheWAS run, e.g. python phewas results pre (pre and post print it too)
    python phewas pre       the PheWAS, 3 years before index -> runs\pre_3y\
    python phewas post      the PheWAS, after index -> runs\post\
    python phewas review    one page for the reviewers: tryptase, utilization, background ORs,
                            the mast-cell neoplasm subgroup, prevalence in each group -> runs\review\
    python phewas cluster   one page: the strongest associations, consistent in both windows -> runs\cluster\
    python phewas pvalues   p and q for every phecode the reports cite -> runs\pvalues\pvalues.txt
    python phewas all       move the last run to runs\archive\, then pre, post, review and cluster,
                            every page in one file -> runs\all_results.txt
    python phewas update    unpack the newest *bundle*.py in this folder over these scripts
    python phewas vscode    point VSCodium's terminal and R extension at the newest R, in every folder

phewas (no extension) just runs this file; `python phewas --check` works too. In the repo
these scripts live in study/ (D41) and run from there or the repo root; on the VM they sit
at the root of the pheauxWAS folder, unpacked from bundles/phewas_vm_runner_bundle.py.
Each run folder holds:
    inputs/               the windowed people and events (prepare_phewas_inputs.py)
    pheauxwas/            the study's PheWAS: phecodeX, the study's rules
    pyphewas/             pyPheWAS 2a8fff1 on the same events: Phecode 1.2, its rules
    pheauxwas_phecode12/  pheauxWAS on pyPheWAS's map and rules (D34)
    comparison/           pheauxwas_phecode12 against pyphewas, phecode by phecode
    run_log.txt           every command, how long it took, and how it ended

Every path has a default for the VM's layout (D35); --help on each command lists
them, and `run` takes any window. A finished run folder is never overwritten; an
unfinished one is renamed *_unfinished_<time> and the run starts again. pyPheWAS
is skipped, with a message, if its packages are missing. Rscript is looked for
on the PATH and then in C:\Program Files\R.
"""

from __future__ import annotations

import argparse
import glob
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# abspath, not resolve(): resolve() turns a mapped drive (Z:) into its \\server path.
HERE = Path(os.path.abspath(__file__)).parent
R_PACKAGES = ["MatchIt", "arrow", "cobalt", "dplyr"]
COVARIATES = ["AgeAtIndex", "Sex", "Race", "Ethnicity", "YearsBeforeIndex", "ClinicVisits365Before"]


def covariates_for(window: str) -> list[str]:
    """The regression covariates for a window. Windows that count diagnoses after index
    also adjust for follow-up after index (D40): it was the one variable just over
    SMD 0.1 after matching, and more follow-up means more chances to be coded."""
    return COVARIATES + (["YearsAfterIndex"] if window in ("post", "all") else [])
PYPHEWAS = "pyPheWAS-2a8fff1"


def pyphewas_dir(root: Path) -> Path:
    """pyPheWAS: vendor/ in the repo (D41), the root itself on the VM."""
    for d in (root / "vendor" / PYPHEWAS, root / PYPHEWAS):
        if d.is_dir():
            return d
    return root / PYPHEWAS
PYPHEWAS_MIN_CASES = 5           # pyPhewasPipeline's --reg_thresh default


def phecode_definitions(root: Path) -> list[Path]:
    """phecodeX's labels and its sex file. The sex file marks the 320 male- or female-only
    phecodes; without it pheauxWAS analyses those in both sexes (found 2026-10-08, D45)."""
    sex = next((p for p in (root / "phecode" / "phecodeX_R_sex.csv",
                            root / "phecode" / "R_CSVs" / "phecodeX_R_sex.csv") if p.exists()),
               root / "phecode" / "phecodeX_R_sex.csv")
    return [need(root / "phecode" / "phecodeX_info.csv", "phecodeX definitions"),
            need(sex, "phecodeX sex file (phecode/phecodeX_R_sex.csv; python phewas update unpacks it)")]


def definitions_args(root: Path) -> list:
    """pheauxWAS's --definitions takes one file per flag."""
    return [x for d in phecode_definitions(root) for x in ("--definitions", d)]


def sex_unrestricted(root: Path, results: Path) -> list[str]:
    """Sex-specific phecodes in a results file that were analysed without their sex
    restriction: should be none."""
    import pandas as pd
    sx = pd.read_csv(phecode_definitions(root)[1], dtype=str)
    only = set(sx.loc[(sx["male_only"].str.upper() == "TRUE") | (sx["female_only"].str.upper() == "TRUE"), "phecode"])
    r = pd.read_csv(results, dtype={"sex_restriction": str})
    bad = r[r["phecode"].isin(only) & r["sex_restriction"].fillna("").str.strip().eq("") & (r["n_total"] > 0)]
    return sorted(bad["phecode"])


def die(msg: str) -> None:
    raise SystemExit(f"run_phewas.py: {msg}")


def need(path: Path, what: str) -> Path:
    if not path.exists():
        die(f"{what} not found: {path}. Run from the repo root, or give its path (see --help).")
    return path


def finished(folder: Path) -> bool:
    log = folder / "run_log.txt"
    return log.exists() and "\nfinished " in log.read_text(encoding="utf-8", errors="replace")


def fresh(folder: Path, top: bool = False) -> Path:
    """A new, empty folder. For a run's top folder (top=True): a finished one
    stops the run; an unfinished one (a failed try) is renamed out of the way."""
    if folder.exists() and top and not finished(folder):
        aside = folder.with_name(f"{folder.name}_unfinished_{time.strftime('%Y%m%d_%H%M%S')}")
        folder.rename(aside)
        print(f"an earlier, unfinished try was moved to {aside.name}")
    if folder.exists():
        die(f"{folder} already exists and finished; nothing is overwritten. Give the run another "
            f"--name (match: --out), or move the old folder away.")
    folder.mkdir(parents=True)
    return folder


def find_rscript(given: str | None) -> str:
    """Rscript: as given, else on the PATH, else the newest under C:\\Program Files\\R."""
    if given:
        if not (shutil.which(given) or Path(given).exists()):
            die(f"--rscript {given} not found.")
        return given
    on_path = shutil.which("Rscript")
    if on_path:
        return on_path
    roots = [os.environ.get(v, "") for v in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA")]
    found = sorted(f for r in roots if r for f in glob.glob(os.path.join(r, "R", "R-*", "bin", "Rscript.exe"))
                   + glob.glob(os.path.join(r, "Programs", "R", "R-*", "bin", "Rscript.exe")))
    if found:
        return found[-1]
    die("Rscript not found on the PATH or under Program Files\\R. Is R installed? If it is, find "
        "Rscript.exe and run: python phewas match --rscript \"<its full path>\"")


class Log:
    """run_log.txt: each command, its time and its ending; each step's own
    output goes to <folder>/console.txt as it also prints here."""

    def __init__(self, path: Path):
        self.path = path
        self.write(f"started {time.strftime('%Y-%m-%d %H:%M:%S')}  python {platform.python_version()}  "
                   f"{platform.platform()}\n  {' '.join(sys.argv)}")

    def write(self, text: str) -> None:
        print(text)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def step(self, name: str, cmd: list, console: Path, env: dict | None = None) -> bool:
        self.write(f"\n== {name}\n  {subprocess.list2cmdline([str(c) for c in cmd])}")
        start = time.time()
        with open(console, "a", encoding="utf-8") as out:
            try:
                proc = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, errors="replace", env=env)
            except OSError as e:
                self.write(f"  FAILED: could not start {cmd[0]}: {e}")
                return False
            for line in proc.stdout:
                sys.stdout.write(line)
                out.write(line)
            proc.wait()
        took = time.time() - start
        ok = proc.returncode == 0
        self.write(f"  {'done' if ok else f'FAILED (exit {proc.returncode}); see {console}'} in {took / 60:.1f} min")
        return ok


def match(args) -> None:
    root = args.root
    hat = need(args.hat or root / "hat_phewas_parquets" / "hat_group.parquet", "hat group file")
    control = need(args.control or root / "control_phewas_parquets" / "control_group.parquet",
                   "control group file")
    script = need(HERE / "matchit_example.R", "matchit_example.R (beside run_phewas.py)")
    rscript = find_rscript(args.rscript)
    out = fresh(args.out or root / "runs" / "matching", top=True)
    log = Log(out / "run_log.txt")
    ok = log.step("MatchIt, 10 controls per case (D7, D32)", [rscript, script, hat, control, out],
                  out / "matching_log.txt")
    if not ok:
        die(f"matching failed; its output is in {out / 'matching_log.txt'}. Run python phewas check.")
    log.write(f"\nfinished {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    if args.out is None:
        sheet(args)


def pyphewas_inputs(inputs: Path, events_name: str, folder: Path, covars: list[str]) -> None:
    """pyPheWAS's group.csv and icds.csv, from the same people and events."""
    import pandas as pd
    people = pd.read_csv(inputs / "people_matched.csv", parse_dates=["BirthDate", "ObservationEndDate"],
                         usecols=["PatientDurableKey", "HaT_Flag", *covars, "BirthDate", "ObservationEndDate"])
    years = lambda later, birth: (later - birth).dt.days / 365.25
    group = people[["PatientDurableKey", "HaT_Flag"] + covars].rename(columns={"PatientDurableKey": "id"})
    group["MaxAgeAtVisit"] = years(people["ObservationEndDate"], people["BirthDate"])
    group.to_csv(folder / "group.csv", index=False)

    birth = people.set_index("PatientDurableKey")["BirthDate"]
    with open(folder / "icds.csv", "w", newline="", encoding="utf-8") as f:
        for i, ev in enumerate(pd.read_csv(inputs / events_name, parse_dates=["DiagnosisDate"],
                                           usecols=["PatientDurableKey", "DiagnosisCode", "DiagnosisDate"],
                                           chunksize=2_000_000)):
            pd.DataFrame({"id": ev["PatientDurableKey"],
                          "ICD_CODE": ev["DiagnosisCode"],
                          "ICD_TYPE": 10,
                          "AgeAtICD": years(ev["DiagnosisDate"], ev["PatientDurableKey"].map(birth))}
                         ).to_csv(f, index=False, header=i == 0)


def missing_modules(python: str, env: dict) -> str:
    """'' when pyPheWAS imports here, else the import error."""
    r = subprocess.run([python, "-c", "import pyPheWAS.pyPhewasCorev2"], capture_output=True, text=True, env=env)
    return "" if r.returncode == 0 else (r.stderr.strip().splitlines() or ["unknown error"])[-1]


def run(args) -> None:
    root, py = args.root, sys.executable
    if args.window != "pre" and args.lookback_years:
        die("--lookback-years applies to --window pre only.")
    name = args.name or (f"pre_{args.lookback_years:g}y" if args.window == "pre" and args.lookback_years
                         else args.window)
    cohort = need(args.cohort or root / "runs" / "matching" / "matched_cohort.parquet",
                  "matched cohort (run 'match' first)")
    diagnoses = [need(args.hat_diagnoses or root / "hat_phewas_parquets" / "hat_group_diagnoses.parquet",
                      "hat diagnoses file"),
                 need(args.control_diagnoses
                      or root / "control_phewas_parquets" / "control_group_diagnoses.parquet",
                      "control diagnoses file")]
    pheauxwas = need(root / "pheauxWAS" / "pheauxWAS.py", "pheauxWAS.py")
    phecode_map = need(root / "phecode" / "phecodeX_ICD_CM_map_flat.csv", "phecodeX map")
    definitions = definitions_args(root)
    prepare = need(HERE / "prepare_phewas_inputs.py", "prepare_phewas_inputs.py (beside run_phewas.py)")
    pyp = pyphewas_dir(root)
    if not args.skip_pyphewas:
        need(pyp / "bin" / "pyPhewasPipeline", "pyPheWAS (or pass --skip-pyphewas)")

    run_dir = fresh((args.runs or root / "runs") / name, top=True)
    log = Log(run_dir / "run_log.txt")
    failed = []

    # 1. One window of the matched cohort, exposure codes dropped.
    inputs = fresh(run_dir / "inputs")
    window = ["--window", args.window] + (["--lookback-years", str(args.lookback_years)]
                                         if args.lookback_years else [])
    if not log.step("inputs: matched patients, one window, D89.44 dropped",
                    [py, prepare, "--cohort", cohort, "--diagnoses", *diagnoses, *window,
                     "--out-dir", inputs], inputs / "console.txt"):
        die("preparing the inputs failed; nothing else was run.")
    people, events = inputs / "people_matched.csv", inputs / f"diagnosis_events_{args.window}.csv"
    covars = covariates_for(args.window)
    log.write(f"  covariates: {' + '.join(covars)}")
    common = ["--people", people, "--id-col", "PatientDurableKey", "--predictors", "HaT_Flag",
              "--covars", *covars, "--events", events, "--events-id-col", "PatientDurableKey",
              "--code-col", "DiagnosisCode", "--vocab-col", "Vocabulary", "--date-col", "DiagnosisDate"]

    # 2. The study's PheWAS.
    out = fresh(run_dir / "pheauxwas")
    if not log.step("pheauxWAS: phecodeX, the study's rules",
                    [py, pheauxwas, *common, "--sex-col", "Sex", "--map", phecode_map,
                     *definitions, "--out", out / f"hat_phewas_{name}"], out / "console.txt"):
        failed.append("pheauxwas")
    else:
        bad = sex_unrestricted(root, out / f"hat_phewas_{name}_results.csv")
        log.write("  sex restriction: " + ("applied to every sex-specific phecode" if not bad else
                  f"NOT APPLIED to {len(bad)} sex-specific phecodes (e.g. {', '.join(bad[:5])})"))
        if bad:
            failed.append("sex restriction")

    # 3. The bridge: pheauxWAS on pyPheWAS's map, with pyPheWAS's rules (D34).
    out = fresh(run_dir / "pheauxwas_phecode12")
    bridge = out / f"hat_phewas_{name}_phecode12"
    if not log.step("pheauxWAS on Phecode 1.2, pyPheWAS's rules",
                    [py, pheauxwas, *common,
                     "--map", need(pyp / "pyPheWAS" / "resources" / "phecode_map_v1_2_icd10_beta.csv",
                                   "pyPheWAS's Phecode 1.2 map"), "ICD10CM",
                     "--map-code-col", "ICD10", "--map-phecode-col", "PheCode",
                     "--min-code-count", "1", "--no-exclusions", "--no-rollup", "--no-sex-restriction",
                     "--min-cases", str(PYPHEWAS_MIN_CASES), "--firth", "never", "--out", bridge],
                    out / "console.txt"):
        failed.append("pheauxwas_phecode12")

    # 4. pyPheWAS, unmodified, on the same events.
    if args.skip_pyphewas:
        log.write("\n== pyPheWAS: skipped (--skip-pyphewas)")
    else:
        out = fresh(run_dir / "pyphewas")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(
            [str(pyp)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])))
        problem = missing_modules(py, env)
        if problem:
            log.write(f"\n== pyPheWAS: skipped, it does not import here: {problem}\n"
                      f"  Install statsmodels, matplotlib and tqdm for this Python, then rerun with "
                      f"another --name; pheauxWAS's results above stand.")
            failed.append("pyphewas (packages)")
        else:
            log.write("\n== pyPheWAS inputs: group.csv and icds.csv from the same people and events")
            pyphewas_inputs(inputs, events.name, out, covars)
            ok = log.step("pyPheWAS 2a8fff1: Phecode 1.2, its rules, L1-penalized",
                          [py, pyp / "bin" / "pyPhewasPipeline", "--phenotype", "icds.csv", "--group", "group.csv",
                           "--reg_type", "log", "--covariates", "+".join(covars), "--target", "HaT_Flag",
                           "--path", out, "--postfix", name], out / "console.txt", env=env)
            if not args.keep_feature_matrices:
                # Two text copies of the patient-by-phecode matrix, gigabytes each.
                for f in out.glob("*feature_matrix_*.csv"):
                    f.unlink()
                log.write("  removed pyPheWAS's feature-matrix CSVs (--keep-feature-matrices keeps them)")
            regressions = out / f"regressions_{name}.csv"
            if not ok:
                failed.append("pyphewas")
                if regressions.exists():
                    log.write(f"  its regressions were written before it stopped: {regressions.name} "
                              f"(pandas 3 breaks its plots; pandas 2.2 does not)")

            # 5. The bridge against pyPheWAS.
            if regressions.exists() and "pheauxwas_phecode12" not in failed:
                out = fresh(run_dir / "comparison")
                if not log.step("compare: pheauxWAS on Phecode 1.2 against pyPheWAS",
                                [py, pheauxwas, "--compare", Path(f"{bridge}_results.csv"),
                                 regressions,
                                 "--compare-predictor", "HaT_Flag", "--out", out / f"compare_{name}"],
                                out / "console.txt"):
                    failed.append("comparison")

    log.write(f"\nfinished {time.strftime('%Y-%m-%d %H:%M:%S')}: "
              + (f"FAILED or skipped: {', '.join(failed)}" if failed else "every step done")
              + f"\n  {run_dir}")
    print()
    if args.runs is None:
        print("\n".join(run_sheet(run_dir)))
        print(f"\n(this run's sheet: {run_dir / 'sheet.txt'}; the whole study: python phewas sheet)")
    if failed:
        sys.exit(1)


def check(args) -> None:
    """Everything the other commands need, one line each."""
    root, bad = args.root, 0
    def line(ok: bool, what: str, detail: str = "") -> None:
        nonlocal bad
        bad += not ok
        print(f"  {'ok     ' if ok else 'MISSING'}  {what}  {detail}")
    print(f"python {platform.python_version()} ({sys.executable}), in {root}")
    for mod in ["numpy", "pandas", "pyarrow", "statsmodels", "matplotlib", "tqdm", "scipy"]:
        try:
            line(True, mod, getattr(__import__(mod), "__version__", ""))
        except Exception as e:
            line(False, mod, f"({type(e).__name__}){' - pyPheWAS needs it' if mod in ('statsmodels', 'matplotlib', 'tqdm', 'scipy') else ''}")
    line((pyphewas_dir(root) / "bin" / "pyPhewasPipeline").exists(), "pyPheWAS", str(pyphewas_dir(root)))
    for rel in ["pheauxWAS/pheauxWAS.py", "phecode/phecodeX_ICD_CM_map_flat.csv", "phecode/phecodeX_info.csv",
                "phecode/phecodeX_R_sex.csv", "hat_phewas_parquets/hat_group.parquet",
                "hat_phewas_parquets/hat_group_diagnoses.parquet", "control_phewas_parquets/control_group.parquet",
                "control_phewas_parquets/control_group_diagnoses.parquet"]:
        line((root / rel).exists(), rel)
    for rel in ["prepare_phewas_inputs.py", "matchit_example.R"]:
        line((HERE / rel).exists(), rel)
    try:
        rscript = find_rscript(args.rscript)
        line(True, "Rscript", rscript)
        code = "for (p in c(%s)) cat(p, if (requireNamespace(p, quietly = TRUE)) 'ok' else 'MISSING', '\\n')" % (
            ", ".join(f"'{p}'" for p in R_PACKAGES))
        r = subprocess.run([rscript, "-e", code], capture_output=True, text=True)
        for ln in r.stdout.split("\n"):
            if ln.strip():
                pkg, state = ln.split()[:2]
                line(state == "ok", f"R package {pkg}")
    except SystemExit as e:
        line(False, "Rscript", str(e))
    print("\nall present" if not bad else f"\n{bad} missing")


def update(args) -> None:
    """Unpack the newest *bundle*.py in this folder over the scripts here."""
    bundles = sorted(args.root.glob("*bundle*.py"), key=lambda p: p.stat().st_mtime)
    if not bundles:
        die(f"no *bundle*.py in {args.root}; copy the bundle there first.")
    b = bundles[-1]
    print(f"unpacking {b.name} (newest of {len(bundles)}); check its PACK_ID starts as I said:")
    if subprocess.run([sys.executable, b, "info"]).returncode:
        die(f"{b.name} failed its own integrity check; nothing was unpacked.")
    sys.exit(subprocess.run([sys.executable, b, "unpack", args.root, "--force"]).returncode)


def match_facts(root: Path, cohort: Path | None = None) -> dict:
    """What to judge in the match, from the files match wrote."""
    import numpy as np
    import pandas as pd
    matched = pd.read_parquet(need(cohort or root / "runs" / "matching" / "matched_cohort.parquet",
                                   "matched cohort (run match first)"))
    hat = pd.read_parquet(need(root / "hat_phewas_parquets" / "hat_group.parquet", "hat group file"))
    eligible = hat[hat["EligibleForMatching"] == 1]

    # Standardized mean differences as MatchIt's summary() computes them: treated mean
    # minus weighted control mean, over the treated SD among all eligible cases.
    def columns(df: pd.DataFrame) -> pd.DataFrame:
        x = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce")
                          for c in ["AgeAtIndex", "YearsBeforeIndex", "YearsAfterIndex"]})
        x["log1p(ClinicVisits365Before)"] = np.log1p(pd.to_numeric(df["ClinicVisits365Before"], errors="coerce"))
        for c in ["Race", "Ethnicity", "Sex"]:
            for level in sorted(pd.concat([matched[c], eligible[c]]).dropna().astype(str).unique()):
                x[f"{c} {level}"] = (df[c].astype(str) == level).astype(float)
        return x
    xt_all, xm = columns(eligible), columns(matched)
    t = matched["HaT_Flag"].astype(int) == 1
    w = pd.to_numeric(matched["weights"], errors="coerce")
    rows = []
    for c in xm.columns:
        binary = set(xt_all[c].dropna().unique()) <= {0.0, 1.0}
        p = xt_all[c].mean()
        sd = np.sqrt(p * (1 - p)) if binary else xt_all[c].std()
        mt = xm.loc[t, c].mean()
        mc = np.average(xm.loc[~t, c], weights=w[~t]) if (~t).any() else np.nan
        rows.append((c, mt, mc, (mt - mc) / sd if sd > 0 else 0.0))
    smd = pd.DataFrame(rows, columns=["variable", "HaT mean", "control mean", "SMD"])
    gone = eligible[~eligible["PatientDurableKey"].isin(matched.loc[t, "PatientDurableKey"])]
    per = matched[~t].groupby("subclass", observed=True).size().reindex(
        matched.loc[t, "subclass"].unique(), fill_value=0)
    return {"smd": smd, "over": smd[smd["SMD"].abs() > 0.1], "eligible": len(eligible), "gone": gone,
            "cases": int(t.sum()), "controls": int((~t).sum()), "per": per}


def match_lines(f: dict, detail: bool) -> list[str]:
    smd, over, per, gone = f["smd"], f["over"], f["per"], f["gone"]
    big = smd.loc[smd["SMD"].abs().idxmax()]
    lines = [f"MATCHING: {f['cases']:,} of {f['eligible']:,} eligible cases matched to {f['controls']:,} controls",
             f"  balance: largest SMD {big['variable']} {abs(big['SMD']):.3f} -> "
             + ("all under 0.1, OK" if over.empty else f"{len(over)} OVER 0.1: "
                + ", ".join(f"{r['variable']} {r['SMD']:+.3f}" for _, r in over.iterrows())
                + ("  (YearsAfterIndex: adjusted for in post, D40)" if "YearsAfterIndex" in set(over["variable"]) else ""))]
    by_q = gone["IndexQuarter"].astype(str).value_counts().head(3) if len(gone) else None
    lines.append(f"  unmatched cases: {len(gone):,} ({len(gone) / max(f['eligible'], 1):.1%})"
                 + (", most in " + ", ".join(f"{q} ({n})" for q, n in by_q.items()) if by_q is not None else ""))
    counts = per.value_counts().sort_index(ascending=False)
    lines.append(f"  controls per case (asked 10): mean {per.mean():.1f}; "
                 + "  ".join(f"{k}:{n}" for k, n in counts.items()) + "  (controls:cases)")
    if detail:
        lines.append("  every variable's SMD (should be under 0.1; sex and quarter are exact):")
        lines += [f"    {r['variable']:<45} {r['SMD']:+.3f}" for _, r in smd.iterrows()]
    return lines


def balance(args) -> None:
    """After match: SMDs, unmatched cases and controls per case, one sheet."""
    lines = match_lines(match_facts(args.root, args.cohort), detail=True)
    text = "\n".join(lines)
    print(text)
    (args.root / "runs" / "matching" / "balance.txt").write_text(text + "\n", encoding="utf-8")


def group_lines(root: Path) -> list[str]:
    import pandas as pd
    lines = ["GROUPS"]
    for name, rel in [("hat", "hat_phewas_parquets/hat_group.parquet"),
                      ("control", "control_phewas_parquets/control_group.parquet")]:
        path = root / rel
        if not path.exists():
            lines.append(f"  {name}: MISSING {rel}")
            continue
        g = pd.read_parquet(path, columns=["EligibleForMatching", "ClinicVisits365Before", "Sex",
                                           "IndexBeforeD8944Existed"])
        lines.append(f"  {name}: {len(g):,} patients, {int(g['EligibleForMatching'].sum()):,} eligible; not: "
                     f"{int((g['ClinicVisits365Before'] < 2).sum()):,} under 2 clinic visits, "
                     f"{int(g['Sex'].isna().sum()):,} no sex, "
                     f"{int(g['IndexBeforeD8944Existed'].sum()):,} indexed before 2021-10")
    return lines


def run_lines(run_dir: Path) -> list[str]:
    """One run folder: what each tool found."""
    import pandas as pd
    name = run_dir.name
    lines = [f"PHEWAS {name}" + ("" if finished(run_dir) else "  (UNFINISHED: see its run_log.txt)")]
    log = (run_dir / "inputs" / "console.txt")
    if log.exists():
        kept = [l.strip() for l in log.read_text(errors="replace").splitlines() if "rows kept in window" in l]
        people = [l.split()[1] for l in log.read_text(errors="replace").splitlines() if l.startswith("people:")]
        if kept:
            lines.append(f"  inputs: {people[0] if people else '?'} people, {kept[0].split(' rows')[0]} diagnoses in window")
    res = run_dir / "pheauxwas" / f"hat_phewas_{name}_results.csv"
    if res.exists():
        r = pd.read_csv(res)
        tested = r[r["p"].notna()]
        bon = tested[tested["bonferroni"].astype(str).str.upper() == "TRUE"]
        lines.append(f"  pheauxWAS (phecodeX): {len(tested):,} phecodes tested, {len(bon):,} Bonferroni-significant, "
                     f"{int((tested['q_fdr'] < 0.05).sum()):,} FDR<0.05; {int((tested['model'] == 'firth').sum()):,} by Firth")
        for _, x in tested.sort_values("p").head(8).iterrows():
            lines.append(f"    {x['phecode']:<10} {str(x['description'])[:38]:<38} OR {x['OR']:>7.3g} "
                         f"[{x['OR_lower95']:.3g}-{x['OR_upper95']:.3g}]  q {fmt_p(x['q_fdr'])}  cases {int(x['n_cases']):,}"
                         + ("  (Firth)" if x["model"] == "firth" else ""))
    else:
        lines.append("  pheauxWAS: no results")
    comp = next(iter((run_dir / "comparison").glob("*_summary.txt")), None) if (run_dir / "comparison").exists() else None
    if comp:
        keep = [" ".join(l.split()) for l in comp.read_text(errors="replace").splitlines()
                if l.strip().startswith(("phecodes in both", "beta:", "same direction"))]
        lines.append("  pyPheWAS vs pheauxWAS on Phecode 1.2 (should agree): " + "; ".join(keep))
    elif (run_dir / "pyphewas").exists():
        lines.append("  pyPheWAS: no comparison (see run_log.txt)")
    else:
        lines.append("  pyPheWAS: skipped")
    return lines


def fmt_p(v) -> str:
    """A p or q value; 0 means it underflowed below about 1e-300, not that it is zero."""
    return "<1e-300" if v == 0 else f"{v:.2g}"


ADJACENT_WORDS = ("mast", "immune mechanism", "serum enzyme", "myeloid", "tryptase", "anaphyla")


def run_sheet(run_dir: Path) -> list[str]:
    """One page on one run, from its files: inputs, the study's results, the cross-check.
    Also written to <run>/sheet.txt."""
    import numpy as np
    import pandas as pd
    name = run_dir.name
    window = "3 years before index" if name.startswith("pre") else ("after index" if name.startswith("post") else name)
    log_text = (run_dir / "run_log.txt").read_text(errors="replace") if (run_dir / "run_log.txt").exists() else ""
    covars = next((l.split(":", 1)[1].strip() for l in log_text.splitlines() if l.strip().startswith("covariates:")),
                  None) or " + ".join(covariates_for("post" if name.startswith("post") else "pre"))   # runs before covariates were logged
    L = [f"RESULTS {name}: {window}" + ("" if finished(run_dir) else "  (UNFINISHED: see run_log.txt)"),
         f"  model: phecode ~ HaT_Flag + {covars}"]

    people = run_dir / "inputs" / "people_matched.csv"
    console = run_dir / "inputs" / "console.txt"
    if people.exists():
        hat = pd.read_csv(people, usecols=["HaT_Flag"])["HaT_Flag"]
        text = console.read_text(errors="replace") if console.exists() else ""
        kept = next((l.split()[0] for l in text.splitlines() if "rows kept in window" in l), "?")
        dropped = next((l.split()[0] for l in text.splitlines() if "dropped as exposure codes" in l), "?")
        L.append(f"INPUTS: {len(hat):,} people ({int(hat.sum()):,} HaT, {int((hat == 0).sum()):,} controls); "
                 f"{int(kept):,} diagnoses in window; {int(dropped):,} D89.44 rows removed" if kept.isdigit()
                 and dropped.isdigit() else f"INPUTS: {len(hat):,} people")

    res = run_dir / "pheauxwas" / f"hat_phewas_{name}_results.csv"
    if not res.exists():
        return L + ["PHEAUXWAS: no results file"]
    r = pd.read_csv(res)
    t = r[r["p"].notna()].copy()
    fdr = t[t["q_fdr"] < 0.05]
    bon = t[t["bonferroni"].astype(str).str.upper() == "TRUE"]
    risk = lambda d: f"{int((d['OR'] > 1).sum()):,} higher in HaT / {int((d['OR'] < 1).sum()):,} lower"
    L += ["PHEAUXWAS (phecodeX, the study's result)",
          f"  {len(t):,} phecodes tested; {len(r) - len(t):,} not tested (under 20 cases, or no fit)",
          f"  Bonferroni {len(bon):,} ({risk(bon)}); FDR<0.05 {len(fdr):,} ({risk(fdr)})",
          f"  Firth (separation found) {int((t['model'] == 'firth').sum()):,}, of which FDR<0.05 "
          f"{int((fdr['model'] == 'firth').sum()):,}"]
    cats = fdr["category"].fillna("?").value_counts().head(8)
    L.append("  FDR hits by category: " + ", ".join(f"{c} {n}" for c, n in cats.items()))

    def row(x) -> str:
        return (f"    {x['phecode']:<10} {str(x['description'])[:34]:<34} OR {x['OR']:>6.3g} "
                f"[{x['OR_lower95']:.3g}-{x['OR_upper95']:.3g}] q {fmt_p(x['q_fdr']):>7} "
                f"cases {int(x['n_cases']):>6,}" + (" F" if x["model"] == "firth" else ""))
    L.append("  TOP 20 by p (F = Firth):")
    L += [row(x) for _, x in t.sort_values(["p", "q_fdr"]).head(20).iterrows()]
    low = fdr[fdr["OR"] < 1].sort_values("p").head(5)
    if len(low):
        L.append("  TOP 5 LOWER in HaT (FDR<0.05):")
        L += [row(x) for _, x in low.iterrows()]
    adj = t[t["description"].astype(str).str.lower().str.contains("|".join(ADJACENT_WORDS))]
    if len(adj):
        L.append("  POSSIBLY PART OF THE HaT WORKUP (by name; read as exposure-adjacent): "
                 + ", ".join(f"{x['phecode']} OR {x['OR']:.3g}" for _, x in adj.sort_values("p").head(8).iterrows()))

    comp = next(iter((run_dir / "comparison").glob("*_compare.csv")), None) if (run_dir / "comparison").exists() else None
    if comp is None:
        L.append("CROSS-CHECK: " + ("pyPheWAS skipped" if not (run_dir / "pyphewas").exists() else "no comparison; see run_log.txt"))
    else:
        c = pd.read_csv(comp)
        a, b = c["pheauxWAS beta"], c["pyPheWAS beta"]
        both = c[a.notna() & b.notna()]
        a, b = both["pheauxWAS beta"], both["pyPheWAS beta"]
        diff = (b - a).abs()
        sep = (a.abs() > 10) | (b.abs() > 10)
        ok = both[~sep]
        r_all = np.corrcoef(a, b)[0, 1] if len(both) > 2 else float("nan")
        r_ok = np.corrcoef(ok["pheauxWAS beta"], ok["pyPheWAS beta"])[0, 1] if len(ok) > 2 else float("nan")
        L += ["CROSS-CHECK: pyPheWAS vs pheauxWAS on Phecode 1.2 with pyPheWAS's rules (should agree)",
              f"  {len(both):,} phecodes in both; same direction {int((np.sign(a) == np.sign(b)).sum()):,}; "
              f"median |beta diff| {diff.median():.4f}; correlation {r_all:.3f}",
              f"  {int(sep.sum()):,} separated (|beta| > 10 in either: unpenalized ML vs pyPheWAS's L1 penalty differ "
              f"by design); without them: correlation {r_ok:.3f}, max |diff| {(diff[~sep].max() if (~sep).any() else 0):.3f}"]
        worst = both[~sep].assign(d=diff[~sep]).sort_values("d", ascending=False).head(3)
        if len(worst):
            L.append("  largest differences (not separated): " + "; ".join(
                f"{x['phecode']} {x['pheauxWAS beta']:.2f} vs {x['pyPheWAS beta']:.2f}" for _, x in worst.iterrows()))
    L.append("Read by q (FDR), not p. OR > 1: more common in HaT than in matched controls.")
    (run_dir / "sheet.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    return L


# python phewas review: the checks the 2026-10-08 review asked for, on one page.
KEY_PHECODES = ["DE_666", "SS_840.9", "NS_343.7", "MS_712.51", "DE_679.3", "SS_840.2", "SS_840.1", "RE_463",
                "RE_475", "GI_527", "MS_745", "GE_978", "GE_978.22", "BI_180.6", "SS_823.2", "CA_120.15"]
# Proposed negative-control outcomes, for discussion: no known link to HaT, mast cells or hypermobility.
NEGATIVE_CONTROLS = ["SO_371", "SO_390.4", "SO_387.2", "SO_387.4", "GI_518", "DE_670", "DE_672.21",
                     "CA_139.5", "GU_585", "GI_502.11"]
DRIVERS = [("pre_3y", "MS_712.51"), ("pre_3y", "SS_840.2"), ("pre_3y", "SS_840.9"), ("pre_3y", "CA_125"),
           ("pre_3y", "GE_978"), ("post", "GE_978")]
MAST_NEOPLASM = ("D47.0", "C96.2")       # mastocytosis and the other mast-cell neoplasms
PHENOTYPES = [("urticaria", "DE_666"), ("anaphylaxis", "SS_840.9"), ("insect allergy (Z91.03x)", "Z91.03"),
              ("flushing", "DE_679.3"), ("POTS", "NS_343.7"), ("hypermobility/EDS", "MS_712.51"),
              ("fractures", "MS_745")]


def masked(n) -> str:
    """A count, with 1-10 shown as <11 (Cosmos small-cell rule)."""
    n = int(n)
    return "<11" if 1 <= n <= 10 else f"{n:,}"


def pct(n, d) -> str:
    n, d = int(n), int(d)
    return "<11" if 1 <= n <= 10 else (f"{100 * n / d:.1f}%" if d else "-")


def review_rerun(root: Path, run_dir: Path) -> Path:
    """pheauxWAS again on a run's own inputs, into runs/review/<run>/: the same model, now
    with each phecode's cases and totals in HaT and in controls (pheauxWAS 1.2)."""
    import pandas as pd
    name = run_dir.name
    out = root / "runs" / "review" / name
    res = out / f"hat_phewas_{name}_results.csv"
    orig = run_dir / "pheauxwas" / f"hat_phewas_{name}_results.csv"
    if (res.exists() and "n_cases_exposed" in pd.read_csv(res, nrows=0).columns
            and (not orig.exists() or res.stat().st_mtime >= orig.stat().st_mtime)):
        return res
    events = next(iter(sorted((run_dir / "inputs").glob("diagnosis_events_*.csv"))), None)
    if events is None:
        die(f"{run_dir / 'inputs'} has no diagnosis_events_*.csv; rerun python phewas {name.split('_')[0]}.")
    window = events.stem.split("_")[-1]
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, need(root / "pheauxWAS" / "pheauxWAS.py", "pheauxWAS.py"),
           "--people", run_dir / "inputs" / "people_matched.csv", "--id-col", "PatientDurableKey",
           "--predictors", "HaT_Flag", "--covars", *covariates_for(window), "--events", events,
           "--events-id-col", "PatientDurableKey", "--code-col", "DiagnosisCode", "--vocab-col", "Vocabulary",
           "--date-col", "DiagnosisDate", "--sex-col", "Sex",
           "--map", root / "phecode" / "phecodeX_ICD_CM_map_flat.csv",
           *definitions_args(root), "--out", out / f"hat_phewas_{name}"]
    print(f"pheauxWAS on {name}'s inputs, for counts in each group (a minute or two) ...", flush=True)
    with open(out / "console.txt", "w", encoding="utf-8") as f:
        if subprocess.run([str(c) for c in cmd], stdout=f, stderr=subprocess.STDOUT).returncode:
            die(f"pheauxWAS failed on {name}; see {out / 'console.txt'}. Is pheauxWAS.py 1.2 or later "
                f"(python phewas update)?")
    bad = sex_unrestricted(root, res)
    if bad:
        die(f"sex restriction not applied to {len(bad)} sex-specific phecodes in {res} (e.g. {', '.join(bad[:5])}).")
    return res


def review(args) -> None:
    text = "\n".join(review_lines(args.root))
    print(text)
    (args.root / "runs" / "review").mkdir(parents=True, exist_ok=True)
    (args.root / "runs" / "review" / "review.txt").write_text(text + "\n", encoding="utf-8")


def review_lines(root: Path) -> list[str]:
    """One page for the reviewers: case validity, utilization the match did not use, how far the
    whole phenome is shifted, the mast-cell neoplasm subgroup, prevalence in each group, and
    which ICD codes make up the phecodes in question. Also runs/review/review.txt."""
    import numpy as np
    import pandas as pd
    runs = {n: root / "runs" / n for n in ("pre_3y", "post") if finished(root / "runs" / n)}
    if "pre_3y" not in runs:
        die("no finished runs/pre_3y; run python phewas pre first.")
    cohort = pd.read_parquet(need(root / "runs" / "matching" / "matched_cohort.parquet", "matched cohort"))
    hat = cohort["HaT_Flag"].astype(int) == 1
    nh, nc = int(hat.sum()), int((~hat).sum())
    flag = cohort.set_index("PatientDurableKey")["HaT_Flag"].astype(int)
    L = [f"REVIEW CHECKS {time.strftime('%Y-%m-%d %H:%M')} (python phewas review); counts 1-10 shown as <11", ""]

    # 1. Cases.
    num = lambda c: pd.to_numeric(cohort[c], errors="coerce")
    tc, tmax = num("TryptaseCount").fillna(0), num("TryptaseMax")
    has_t, high = tc > 0, tmax >= 8
    L += [f"CASES: {nh:,} matched HaT, {nc:,} controls",
          f"  serum tryptase on record (any date): HaT {masked((hat & has_t).sum())} ({pct((hat & has_t).sum(), nh)}),"
          f" controls {masked((~hat & has_t).sum())} ({pct((~hat & has_t).sum(), nc)})",
          f"  highest >= 8 ng/mL, of those measured: HaT {masked((hat & high).sum())} "
          f"({pct((hat & high).sum(), (hat & has_t).sum())}), median {tmax[hat].median():.1f}; "
          f"controls {masked((~hat & high).sum())} ({pct((~hat & high).sum(), (~hat & has_t).sum())})",
          f"  D89.44 on 2+ dates: {masked((hat & (num('HaTDateCount') >= 2)).sum())} "
          f"({pct((hat & (num('HaTDateCount') >= 2)).sum(), nh)})", ""]

    # 2. Utilization the match did not use.
    L.append(f"UTILIZATION, year before index unless said   {'HaT':>23}  {'controls':>23}")
    for label, col in [("clinic visit days (matched on)", "ClinicVisits365Before"),
                       ("ED visit days (not matched on)", "EdVisits365Before"),
                       ("admissions (not matched on)", "Admissions365Before"),
                       ("clinic visit days, year AFTER index", "ClinicVisits365After")]:
        v = num(col).fillna(0)
        cell = lambda m: f"mean {v[m].mean():.2f}, any {pct((v[m] > 0).sum(), m.sum())}"
        L.append(f"  {label:<42} {cell(hat):>23}  {cell(~hat):>23}")
    L.append("")

    # 3. The whole phenome: the same model again, now with counts in each group.
    res = {n: pd.read_csv(review_rerun(root, d)) for n, d in runs.items()}
    tested = {n: r[r["p"].notna()] for n, r in res.items()}
    cols = list(runs)
    same = []
    for n, d in runs.items():
        orig = d / "pheauxwas" / f"hat_phewas_{n}_results.csv"
        if orig.exists():
            j = tested[n].merge(pd.read_csv(orig), on="phecode", suffixes=("", "_orig"))
            same.append(f"{n} max |beta diff| {(j['beta'] - j['beta_orig']).abs().max():.1e}")
    L.append("BACKGROUND: how far the whole phenome is shifted        " + "".join(f"{c:>10}" for c in cols))
    med = lambda v: f"{v.median():.2f}" if v.notna().any() else "-"
    stats = [("median OR, all tested phecodes", lambda t: med(t["OR"])),
             ("share with OR > 1", lambda t: f"{(t['OR'] > 1).mean():.0%}"),
             ("median OR, not significant (q >= 0.05)", lambda t: med(t.loc[t["q_fdr"] >= 0.05, "OR"])),
             ("median OR, negative controls (proposed)",
              lambda t: med(t.loc[t["phecode"].isin(NEGATIVE_CONTROLS), "OR"]))]
    for label, f in stats:
        L.append(f"  {label:<53}" + "".join(f"{f(tested[c]):>10}" for c in cols))
    info = pd.read_csv(root / "phecode" / "phecodeX_info.csv", encoding="latin-1", dtype=str,
                       usecols=["phecode", "phecode_string"]).set_index("phecode")["phecode_string"]
    name = lambda p: str(info.get(p, p))
    neg = []
    for p in NEGATIVE_CONTROLS:
        got = [tested[c].loc[tested[c]["phecode"] == p] for c in cols]
        neg.append(f"{name(p)[:16]} " + "/".join(f"{g['OR'].iloc[0]:.2f}" if len(g) else "-" for g in got))
    L += ["  negative controls, OR " + "/".join(cols) + ": " + "; ".join(neg[:5]),
          "    " + "; ".join(neg[5:]),
          "  (rerun matches the original: " + ("; ".join(same) or "original not found") + ")", ""]

    # 4. Events of both windows, codes normalized; the phecodeX map to name codes.
    m = pd.read_csv(root / "phecode" / "phecodeX_ICD_CM_map_flat.csv", encoding="latin-1", dtype=str,
                    usecols=["ICD", "vocabulary_id", "phecode"])
    m = m[m["vocabulary_id"] == "ICD10CM"]
    under = lambda q, p: q == p or (q.startswith(p) and ("." in p or q[len(p):len(p) + 1] == "."))
    def codes_for(p: str) -> set:
        if "_" not in p:                                    # an ICD prefix, e.g. Z91.03
            return {"prefix:" + p}
        return set(m.loc[[under(q, p) for q in m["phecode"]], "ICD"].str.strip().str.upper())
    def hits(ev: pd.DataFrame, codes: set) -> pd.Series:
        pre = [c[7:] for c in codes if c.startswith("prefix:")]
        cats = ev["code"].cat.categories
        keep = [c for c in cats if c in codes or any(c.startswith(x) for x in pre)]
        return ev["code"].isin(keep)
    events = {}
    for n, d in runs.items():
        f = next(iter(sorted((d / "inputs").glob("diagnosis_events_*.csv"))))
        ev = pd.read_csv(f, usecols=["PatientDurableKey", "DiagnosisCode", "DiagnosisDate"],
                         dtype={"DiagnosisCode": "category"})
        ev["code"] = ev["DiagnosisCode"].astype(str).str.strip().str.upper().astype("category")
        ev["hat"] = ev["PatientDurableKey"].map(flag).fillna(0).astype(int)
        events[n] = ev

    # 5. The mast-cell neoplasm subgroup.
    pre = events["pre_3y"]
    neo_pre = pre[pre["code"].astype(str).str.startswith(MAST_NEOPLASM)]
    every = pd.concat([e[["PatientDurableKey", "code", "hat"]] for e in events.values()])
    neo_any = every[every["code"].astype(str).str.startswith(MAST_NEOPLASM)]
    dates = neo_pre[neo_pre["hat"] == 1].groupby("PatientDurableKey")["DiagnosisDate"].nunique()
    neo_hat = set(neo_any.loc[neo_any["hat"] == 1, "PatientDurableKey"])
    span = "3y before to end" if "post" in events else "3y before index"
    L += [f"MAST-CELL NEOPLASM CODES (D47.0x, C96.2x) among the {nh:,} matched HaT",
          f"  HaT, 3y before index: {masked(len(dates))} ({pct(len(dates), nh)}), on 2+ dates "
          f"{masked((dates >= 2).sum())};  {span}: {masked(len(neo_hat))} ({pct(len(neo_hat), nh)})",
          f"  controls, {span}: {masked(neo_any.loc[neo_any['hat'] == 0, 'PatientDurableKey'].nunique())}"]
    h = neo_any[neo_any["hat"] == 1]
    by = h.assign(c=np.where(h["code"].astype(str).str.startswith("C96.2"), "C96.2x", h["code"].astype(str))
                  ).groupby("c")["PatientDurableKey"].nunique()
    d8941 = every[(every["hat"] == 1) & (every["code"] == "D89.41")]["PatientDurableKey"].nunique()
    L.append(f"  by code, HaT, {span}: " + "  ".join(f"{c} {masked(n)}" for c, n in by.items())
             + f";  D89.41 (monoclonal MCAS) {masked(d8941)}")
    L.append(f"  % with the code on >=1 date, 3y before index   {'HaT+neoplasm*':>13} {'HaT, none':>10} {'controls':>9}")
    in_neo = pre["PatientDurableKey"].isin(neo_hat)
    groups = [(pre["hat"] == 1) & in_neo, (pre["hat"] == 1) & ~in_neo, pre["hat"] == 0]
    sizes = [len(neo_hat), nh - len(neo_hat), nc]
    for label, p in PHENOTYPES:
        hit = hits(pre, codes_for(p))
        cells = [pct(pre.loc[hit & g, "PatientDurableKey"].nunique(), s) for g, s in zip(groups, sizes)]
        L.append(f"    {label:<44} {cells[0]:>13} {cells[1]:>10} {cells[2]:>9}")
    L.append(f"    * a mast-cell neoplasm code {span}")
    L.append("")

    # 6. Prevalence in each group: phecode cases over patients analysed, as the model counts them.
    L.append("PREVALENCE: the model's cases (2+ dates) over the patients it analysed, in each group")
    L.append(f"  {'':<10} {'':<30}" + "".join(f"{c + ':   HaT    ctrl      OR':>28}" for c in cols))
    for p in KEY_PHECODES:
        cells = []
        for c in cols:
            x = res[c].loc[res[c]["phecode"] == p]
            if not len(x):
                cells.append(f"{'not observed':>28}")
                continue
            x = x.iloc[0]
            orv = (f"{x['OR']:.3g}" if x["OR"] < 1000 else f"{x['OR']:,.0f}") if pd.notna(x["OR"]) else "nt"
            cells.append(f"{pct(x['n_cases_exposed'], x['n_total_exposed']):>14} "
                         f"{pct(x['n_cases_unexposed'], x['n_total_unexposed']):>6} {orv:>7}")
        L.append(f"  {p:<10} {name(p)[:30]:<30}" + "".join(cells))
    L.append("  (OR: adjusted, from the model; nt: not tested, under 20 cases)")
    L.append("")

    # 7. Which ICD codes make up the phecodes in question.
    L.append("WHAT CODES MAKE THESE PHECODES (patients with the code on >=1 date, HaT/controls; top 5)")
    for n, p in DRIVERS:
        if n not in events:
            continue
        ev = events[n]
        x = ev[hits(ev, codes_for(p))]
        if not len(x):
            L.append(f"  {n:<6} {p:<10} none")
            continue
        g = x.groupby(["code", "hat"], observed=True)["PatientDurableKey"].nunique().unstack(fill_value=0)
        g = g.reindex(columns=[1, 0], fill_value=0)
        g = g.assign(t=g.sum(axis=1)).sort_values("t", ascending=False).head(5)
        L.append(f"  {n:<6} {p:<10} " + "  ".join(f"{c} {masked(r[1])}/{masked(r[0])}" for c, r in g.iterrows()))
    L.append("Copy this whole page into the chat.")
    return L


# python phewas cluster: the strongest, consistent associations, chosen by a stated rule (D44).
CLUSTER_FDR = 0.05            # significant in both windows
CLUSTER_FOLD = 2.0            # OR at least this many times the window's median OR (the background shift)
# Exposure-adjacent families (report §6.2): the HaT code's own, mast-cell activation, raised tryptase,
# and the haematological families that hold the mastocytosis codes.
CLUSTER_ADJACENT = ["GE_969", "BI_180", "SS_823", "CA_120", "CA_125"]
CLUSTER_MAX_LINES = 40


def phecode_parents(p: str) -> list[str]:
    """MS_712.51 -> MS_712.5, MS_712: the rollup pheauxWAS uses."""
    out = []
    while "." in p:
        p = p[:-1]
        if p.endswith("."):
            p = p[:-1]
        out.append(p)
    return out


def cluster(args) -> None:
    lines, csv_rows = cluster_lines(args.root, args.page)
    out = args.root / "runs" / "cluster"
    out.mkdir(parents=True, exist_ok=True)
    import pandas as pd
    pd.DataFrame(csv_rows).to_csv(out / "cluster.csv", index=False)
    text = "\n".join(lines)
    (out / "cluster.txt").write_text(text + "\n", encoding="utf-8")
    print(text)


def cluster_lines(root: Path, page: int | None) -> tuple[list[str], list[dict]]:
    """One page (page None: every row): phecodes significant in both windows with ORs well above the background shift,
    exposure-adjacent families left out, children under their parents. Also runs/cluster/."""
    import pandas as pd
    runs = {n: root / "runs" / n for n in ("pre_3y", "post")}
    missing = [n for n, d in runs.items() if not finished(d)]
    if missing:
        die(f"needs finished runs/pre_3y and runs/post; missing {', '.join(missing)}. Run python phewas pre / post.")
    res = {n: pd.read_csv(review_rerun(root, d)) for n, d in runs.items()}
    t = {n: r[r["p"].notna()].set_index("phecode") for n, r in res.items()}
    median = {n: x["OR"].median() for n, x in t.items()}
    cut = {n: CLUSTER_FOLD * m for n, m in median.items()}
    adjacent = lambda p: any(p == a or a in phecode_parents(p) for a in CLUSTER_ADJACENT)

    both = t["pre_3y"].join(t["post"], lsuffix="_pre", rsuffix="_post", how="inner")
    sig = (both["q_fdr_pre"] < CLUSTER_FDR) & (both["q_fdr_post"] < CLUSTER_FDR)
    keep = both[sig & (both["OR_pre"] >= cut["pre_3y"]) & (both["OR_post"] >= cut["post"])]
    dropped = sorted(p for p in keep.index if adjacent(p))
    keep = keep.drop(dropped)
    low = both[sig & (both["OR_pre"] < 1) & (both["OR_post"] < 1)].drop(
        [p for p in both.index if adjacent(p)], errors="ignore")

    # Families: a phecode goes under its nearest ancestor that is also in the cluster.
    head = {p: next((a for a in phecode_parents(p) if a in keep.index), None) for p in keep.index}
    roots = [p for p, h in head.items() if h is None]
    kids = {}
    for p, h in head.items():
        if h is not None:
            kids.setdefault(h, []).append(p)
    strength = lambda p: min(keep.loc[p, "OR_pre"], keep.loc[p, "OR_post"])
    family_strength = {}
    def best(p):
        family_strength[p] = max([strength(p)] + [best(k) for k in kids.get(p, [])])
        return family_strength[p]
    for r in roots:
        best(r)
    roots.sort(key=lambda p: -family_strength[p])

    def cells(p: str, w: str) -> str:
        x = keep.loc[p]
        s = "_pre" if w == "pre_3y" else "_post"
        prev = f"{pct(x['n_cases_exposed' + s], x['n_total_exposed' + s])}/{pct(x['n_cases_unexposed' + s], x['n_total_unexposed' + s])}"
        return f"{x['OR' + s]:>6.3g} [{x['OR_lower95' + s]:.3g}-{x['OR_upper95' + s]:.3g}] {prev:>13}"
    rows, csv_rows = [], []
    def walk(p: str, depth: int) -> None:
        x = keep.loc[p]
        label = ("  " * depth + ("- " if depth else "") + str(x["description_pre"]))[:40]
        rows.append(f"  {p:<11} {label:<40} {cells(p, 'pre_3y'):<34} {cells(p, 'post'):<34}")
        csv_rows.append({"phecode": p, "family": roots_of[p], "depth": depth, "description": x["description_pre"],
                         **{f"{c}{s}": x[f"{c}{s}"] for s in ("_pre", "_post")
                            for c in ("OR", "OR_lower95", "OR_upper95", "q_fdr", "n_cases_exposed", "n_total_exposed",
                                      "n_cases_unexposed", "n_total_unexposed")}})
        for k in sorted(kids.get(p, []), key=lambda k: -family_strength[k]):
            walk(k, depth + 1)
    roots_of = {}
    for r in roots:
        stack = [r]
        while stack:
            q = stack.pop()
            roots_of[q] = r
            stack += kids.get(q, [])
    for r in roots:
        walk(r, 0)

    L = [f"CLUSTER {time.strftime('%Y-%m-%d %H:%M')} (python phewas cluster); counts 1-10 shown as <11",
         f"  rule: FDR < {CLUSTER_FDR:g} in BOTH windows, and OR >= {CLUSTER_FOLD:g} x that window's median OR "
         f"(pre: {cut['pre_3y']:.2f} = {CLUSTER_FOLD:g} x {median['pre_3y']:.2f}; "
         f"post: {cut['post']:.2f} = {CLUSTER_FOLD:g} x {median['post']:.2f})",
         f"  {len(keep):,} phecodes in {len(roots):,} families; children indented under their parents; "
         f"families by their strongest member's smaller OR",
         f"  left out as exposure-adjacent ({', '.join(CLUSTER_ADJACENT)} families): "
         + (", ".join(dropped) if dropped else "none"),
         "",
         f"  {'phecode':<11} {'description':<40} {'pre_3y: OR [95% CI]  HaT%/ctrl%':<34} {'post: OR [95% CI]  HaT%/ctrl%':<34}"]
    pages = max(1, -(-len(rows) // CLUSTER_MAX_LINES))
    if page is None:
        L += rows
    else:
        page = min(max(1, page), pages)
        start = (page - 1) * CLUSTER_MAX_LINES
        L += rows[start:start + CLUSTER_MAX_LINES]
    if page is not None:
        L.append(f"  page {page} of {pages} (rows {start + 1}-{min(start + CLUSTER_MAX_LINES, len(rows))} of {len(rows)})"
             + (f"; next: python phewas cluster {page + 1}" if page < pages else "; all in runs\\cluster\\cluster.csv"))
    L += ["", f"LOWER IN HaT, FDR < {CLUSTER_FDR:g} in both windows: {len(low):,}; strongest 5 (OR pre / post):"]
    L += [f"  {p:<11} {str(x['description_pre'])[:40]:<40} {x['OR_pre']:.2f} / {x['OR_post']:.2f}"
          for p, x in low.assign(m=low[["OR_pre", "OR_post"]].max(axis=1)).sort_values("m").head(5).iterrows()]
    L.append("Copy this whole page into the chat.")
    return L, csv_rows


def selftest(args) -> int:
    """The runner's wiring of phecodeX, checked by its outcome: a female-only phecode
    (GU_615, endometriosis, N80.0) coded in women and in men must be analysed in women only,
    and the guard must catch it when the sex file is left out (D45)."""
    import csv
    import tempfile
    root = args.root
    tmp = Path(tempfile.mkdtemp(prefix="phewas_selftest_"))
    women = [f"P{i:04d}" for i in range(0, 600, 2)]
    with open(tmp / "people.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["PatientDurableKey", "HaT_Flag", "Sex", "AgeAtIndex"])
        for i in range(600):
            w.writerow([f"P{i:04d}", int(i % 5 == 0), "Female" if i % 2 == 0 else "Male", 30 + i % 40])
    with open(tmp / "events.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["PatientDurableKey", "DiagnosisCode", "Vocabulary", "DiagnosisDate"])
        for i in range(600):
            if i % 3 == 0:                                   # women and men alike
                w.writerows([[f"P{i:04d}", "N80.0", "ICD-10-CM", d] for d in ("2024-01-01", "2024-03-01")])
    def fit(defs: list, name: str) -> Path:
        out = tmp / name
        cmd = [sys.executable, need(root / "pheauxWAS" / "pheauxWAS.py", "pheauxWAS.py"),
               "--people", tmp / "people.csv", "--id-col", "PatientDurableKey", "--predictors", "HaT_Flag",
               "--covars", "AgeAtIndex", "--events", tmp / "events.csv", "--events-id-col", "PatientDurableKey",
               "--code-col", "DiagnosisCode", "--vocab-col", "Vocabulary", "--date-col", "DiagnosisDate",
               "--sex-col", "Sex", "--map", need(root / "phecode" / "phecodeX_ICD_CM_map_flat.csv", "phecodeX map"),
               *defs, "--no-hash", "--out", out]
        subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
        return Path(f"{out}_results.csv")
    import pandas as pd
    ok = True
    res = fit(definitions_args(root), "with_sex")
    row = pd.read_csv(res, dtype={"sex_restriction": str}).set_index("phecode").loc["GU_615"] if res.exists() else None
    good = row is not None and row["sex_restriction"] == "F" and int(row["n_total"]) == len(women) and not sex_unrestricted(root, res)
    print(f"{'PASS' if good else 'FAIL'}  female-only GU_615 analysed in women only "
          f"(n_total {None if row is None else int(row['n_total'])}, women {len(women)})")
    ok &= good
    res = fit(["--definitions", phecode_definitions(root)[0]], "without_sex")
    caught = res.exists() and "GU_615" in sex_unrestricted(root, res)
    print(f"{'PASS' if caught else 'FAIL'}  without the sex file, the guard catches it")
    ok &= caught
    shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


# python phewas all: archive the last run, then pre, post, review and cluster, into one file (D45).
RUN_OUTPUTS = ["pre_3y", "post", "review", "cluster", "sheet.txt", "all_results.txt"]


def run_stamp(runs: Path) -> str:
    """When the run in runs/ started, from pre_3y's run log, as 2026-10-08_0210."""
    log = runs / "pre_3y" / "run_log.txt"
    first = log.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0].split() if log.exists() else []
    if len(first) >= 3 and first[0] == "started":
        return f"{first[1]}_{first[2][:5].replace(':', '')}"
    return time.strftime("%Y-%m-%d_%H%M")


def archive(root: Path) -> Path | None:
    """Move the last run's outputs (not the matching, which every run shares) into
    runs/archive/run_<when it started>/."""
    runs = root / "runs"
    here = [runs / n for n in RUN_OUTPUTS if (runs / n).exists()]
    here += sorted(p for p in runs.glob("*_unfinished_*") if not p.name.startswith("matching"))
    if not here:
        return None
    dest = base = runs / "archive" / f"run_{run_stamp(runs)}"
    n = 1
    while dest.exists():
        n += 1
        dest = base.with_name(f"{base.name}_{n}")
    dest.mkdir(parents=True)
    for p in here:
        shutil.move(str(p), str(dest / p.name))
    (dest / "README.txt").write_text(
        "A finished study run, moved here by python phewas all before the next one.\n"
        "Its matched cohort is runs/matching (shared by every run, not copied).\n", encoding="utf-8")
    return dest


def study_all(args) -> None:
    """Archive the last run, run pre, post, review and cluster, and put every page into one
    file, runs/all_results.txt, beside each step's own files."""
    import pandas as pd
    root, runs = args.root, args.root / "runs"
    need(runs / "matching" / "matched_cohort.parquet", "matched cohort (run python phewas match first)")
    if selftest(args):                              # stop now, not after an hour, if phecodeX is wired wrong
        die("the self-test failed (above); nothing was moved or run.")
    moved = archive(root)
    print(f"the last run was moved to {moved}" if moved else "no earlier run to move")
    notes = []
    for window, lookback, name in [("pre", 3.0, "pre_3y"), ("post", None, "post")]:
        a = argparse.Namespace(**vars(args))
        a.window, a.lookback_years, a.name, a.runs = window, lookback, None, None
        print(f"\n######## {name} ########", flush=True)
        try:
            run(a)
        except SystemExit as e:
            res = runs / name / "pheauxwas" / f"hat_phewas_{name}_results.csv"
            if not (finished(runs / name) and res.exists()) or sex_unrestricted(root, res):
                raise
            notes.append(f"{name}: {e.code if isinstance(e.code, str) else 'a step after pheauxWAS failed'}; "
                         f"see runs/{name}/run_log.txt")
    print("\n######## review and cluster ########", flush=True)
    review_text = review_lines(root)
    (runs / "review" / "review.txt").write_text("\n".join(review_text) + "\n", encoding="utf-8")
    cluster_text, csv_rows = cluster_lines(root, None)
    (runs / "cluster").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(csv_rows).to_csv(runs / "cluster" / "cluster.csv", index=False)
    (runs / "cluster" / "cluster.txt").write_text("\n".join(cluster_text) + "\n", encoding="utf-8")
    study = sheet_lines(root)
    (runs / "sheet.txt").write_text("\n".join(study) + "\n", encoding="utf-8")

    sx = pd.read_csv(phecode_definitions(root)[1], dtype=str)
    n_sex = int(((sx["male_only"].str.upper() == "TRUE") | (sx["female_only"].str.upper() == "TRUE")).sum())
    drop = "Copy this whole"
    parts = [("THE STUDY", study), ("PRE-INDEX RESULTS (3 years before index; primary)", run_sheet(runs / "pre_3y")),
             ("POST-INDEX RESULTS (after index)", run_sheet(runs / "post")),
             ("REVIEW CHECKS", review_text), ("CLUSTER (every row)", cluster_text)]
    L = [f"HaT PheWAS: EVERY PAGE OF ONE RUN, {time.strftime('%Y-%m-%d %H:%M')} (python phewas all)",
         f"  sex restriction from {phecode_definitions(root)[1].name} ({n_sex:,} sex-specific phecodes), checked in both windows; "
         + ("earlier run moved to " + str(moved.relative_to(root)) if moved else "no earlier run")]
    L += [f"  NOTE {x}" for x in notes]
    for i, (title, lines) in enumerate(parts, 1):
        L += ["", "=" * 100, f"{i}. {title}", "=" * 100] + [l for l in lines if not l.startswith(drop)]
    L += ["", "End. Screenshot this file page by page and paste the pages into the chat."]
    (runs / "all_results.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nDONE: every page is in runs\\all_results.txt ({len(L):,} lines). Open it in VSCodium and "
          f"screenshot it page by page." + (f"\n{len(notes)} note(s) at its top." if notes else ""))


# python phewas pvalues: p and q for every phecode the reports cite, from the existing results (D47).
PVALUE_EXTRA = ["GI_527"]          # cited in the reports but below the cluster's cut-off
PVALUE_LINES = 45


def pvalues(args) -> None:
    """p and q values, before and after index, for the phecodes the reports cite: the cluster
    (in its order), the diagnosis-related families, the lower-in-HaT ones, and a few more.
    Nothing is refitted: it reads each run's results file. Also runs/pvalues/: every tested
    phecode's OR, CI, p and q in both windows."""
    import pandas as pd
    root = args.root
    runs = {n: root / "runs" / n for n in ("pre_3y", "post")}
    missing = [n for n, d in runs.items() if not finished(d)]
    if missing:
        die(f"needs finished runs/pre_3y and runs/post; missing {', '.join(missing)}.")
    res = {}
    for n, d in runs.items():
        r = pd.read_csv(need(d / "pheauxwas" / f"hat_phewas_{n}_results.csv", f"{n} results"))
        res[n] = r[r["p"].notna()].set_index("phecode")
    both = res["pre_3y"].join(res["post"], lsuffix="_pre", rsuffix="_post", how="outer")
    n_tested = {n: len(r) for n, r in res.items()}
    out = root / "runs" / "pvalues"
    out.mkdir(parents=True, exist_ok=True)
    cols = [f"{c}_{w}" for w in ("pre", "post") for c in ("OR", "OR_lower95", "OR_upper95", "p", "q_fdr", "bonferroni")]
    desc = both["description_pre"].fillna(both["description_post"])
    both.assign(description=desc)[["description"] + cols].sort_values("p_pre").to_csv(out / "all_phecodes_p_q.csv")

    # The phecodes the reports cite, in sections.
    _, cluster_rows = cluster_lines(root, None)
    order = [(r["phecode"], r["depth"]) for r in cluster_rows]
    adjacent = [p for p in both.index if any(p == a or a in phecode_parents(p) for a in CLUSTER_ADJACENT)]
    adjacent = sorted(adjacent, key=lambda p: both.loc[p, "p_pre"] if pd.notna(both.loc[p, "p_pre"]) else 1)
    lower_both = both[(both["q_fdr_pre"] < 0.05) & (both["q_fdr_post"] < 0.05)
                      & (both["OR_pre"] < 1) & (both["OR_post"] < 1)].sort_values("p_pre").index.tolist()
    lower_top = []
    for w in ("pre", "post"):
        lower_top += both[(both[f"q_fdr_{w}"] < 0.05) & (both[f"OR_{w}"] < 1)].sort_values(f"p_{w}").head(5).index.tolist()
    lower = list(dict.fromkeys(lower_both + lower_top))
    seen = {p for p, _ in order}
    extra = [p for p in PVALUE_EXTRA if p in both.index and p not in seen]
    sections = [("CLUSTER (report §6.3.1; children indented)", order),
                ("DIAGNOSIS-RELATED (report §6.2)", [(p, 0) for p in adjacent if p not in seen]),
                ("LOWER IN HaT (both windows, and each window's top 5)", [(p, 0) for p in lower if p not in seen]),
                ("ALSO CITED", [(p, 0) for p in extra])]

    def fp(v) -> str:
        return "-" if pd.isna(v) else ("<1e-300" if v == 0 else f"{v:.2g}")
    def fo(v) -> str:
        return "-" if pd.isna(v) else (f"{v:.3g}" if v < 1000 else f"{v:,.0f}")
    rows = []
    for title, items in sections:
        if not items:
            continue
        rows.append(f"{title}")
        for p, depth in items:
            x = both.loc[p]
            star = lambda w: "*" if str(x[f"bonferroni_{w}"]).upper() == "TRUE" else " "
            label = ("  " * depth + ("- " if depth else "") + str(desc.loc[p]))[:34]
            rows.append(f"  {p:<11} {label:<34} {fo(x['OR_pre']):>6} {fp(x['p_pre']):>8} {fp(x['q_fdr_pre']):>8}{star('pre')}"
                        f"  {fo(x['OR_post']):>6} {fp(x['p_post']):>8} {fp(x['q_fdr_post']):>8}{star('post')}")
    pages = max(1, -(-len(rows) // PVALUE_LINES))
    page = None if args.page is None else min(max(1, args.page), pages)
    L = [f"P VALUES {time.strftime('%Y-%m-%d %H:%M')} (python phewas pvalues); from the existing results, nothing refitted",
         "  p: Wald (logistic regression) or penalized likelihood-ratio (Firth); q: Benjamini-Hochberg FDR",
         f"  * Bonferroni-significant: p < 0.05/{n_tested['pre_3y']:,} = {0.05 / n_tested['pre_3y']:.2g} before index, "
         f"0.05/{n_tested['post']:,} = {0.05 / n_tested['post']:.2g} after; <1e-300: below what can be represented",
         "",
         f"  {'phecode':<11} {'description':<34} {'OR pre':>6} {'p pre':>8} {'q pre':>8}   {'OR post':>6} {'p post':>8} {'q post':>8}"]
    if page is None:
        L += rows
        L.append(f"  {len(rows):,} lines; every tested phecode: runs\\pvalues\\all_phecodes_p_q.csv")
    else:
        start = (page - 1) * PVALUE_LINES
        L += rows[start:start + PVALUE_LINES]
        L.append(f"  page {page} of {pages}" + (f"; next: python phewas pvalues {page + 1}" if page < pages else ""))
    L.append("Screenshot the whole file, page by page, and paste the pages into the chat.")
    text = "\n".join(L)
    name = "pvalues.txt" if page is None else f"pvalues_page{page}.txt"
    (out / name).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nDONE: everything is in runs\\pvalues\\{name}. Open it in VSCodium and screenshot it page by page.")


def results(args) -> None:
    """The one-sheet of one run (pre, post or a run folder's name; default: the latest)."""
    runs = args.root / "runs"
    dirs = [d for d in runs.glob("*") if (d / "inputs").is_dir() and "_unfinished_" not in d.name] if runs.exists() else []
    if not dirs:
        die("no PheWAS run yet; run python phewas pre first.")
    if args.name:
        want = {"pre": "pre_3y"}.get(args.name, args.name)
        dirs = [d for d in dirs if d.name == want]
        if not dirs:
            die(f"no run folder runs/{want}.")
    d = max(dirs, key=lambda d: d.stat().st_mtime)
    print("\n".join(run_sheet(d)))


def sheet(args) -> None:
    """One page: everything needed to judge where the study stands, and the next step."""
    text = "\n".join(sheet_lines(args.root))
    print(text)
    (args.root / "runs").mkdir(exist_ok=True)
    (args.root / "runs" / "sheet.txt").write_text(text + "\n", encoding="utf-8")


def sheet_lines(root: Path) -> list[str]:
    lines = [f"pheauxWAS one-sheet, {time.strftime('%Y-%m-%d %H:%M')}", ""]
    lines += group_lines(root) + [""]
    runs = root / "runs"
    matched = (runs / "matching" / "matched_cohort.parquet").exists()
    f = None
    if matched:
        f = match_facts(root)
        lines += match_lines(f, detail=False) + [""]
    else:
        lines += ["MATCHING: not run yet", ""]
    run_dirs = sorted(d for d in runs.glob("*") if (d / "inputs").is_dir()
                      and "_unfinished_" not in d.name) if runs.exists() else []
    for d in run_dirs:
        lines += run_lines(d) + [""]
    names = {d.name for d in run_dirs if finished(d)}
    if any("MISSING" in l for l in lines[:6]):
        nxt = "build the missing group files (build_group_parquet.py), then python phewas match"
    elif not matched:
        nxt = "python phewas match"
    elif (not f["over"][f["over"]["variable"] != "YearsAfterIndex"].empty
          or len(f["gone"]) > 0.1 * f["eligible"]):
        nxt = "send this sheet: balance or unmatched cases need a decision before the PheWAS"
    elif "pre_3y" not in names:
        nxt = "python phewas pre"
    elif "post" not in names:
        nxt = "python phewas post"
    else:
        nxt = "send this sheet: results ready to review"
    lines += [f"NEXT: {nxt}", "Copy this whole sheet into the chat."]
    return lines


def user_settings_files() -> list[Path]:
    """VSCodium's and VS Code's user settings.json (all folders), for each one installed."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        die("APPDATA is not set, so VSCodium's settings could not be found.")
    found = [Path(appdata) / app / "User" / "settings.json" for app in ("VSCodium", "Code")
             if (Path(appdata) / app).is_dir()]
    if not found:
        die(f"neither VSCodium nor VS Code has settings under {appdata}. Open VSCodium once, then "
            f"run python phewas vscode again.")
    return found


def point_at_r(path: Path, rscript: Path) -> None:
    """Set the terminal PATH, the R extension and Code Runner in one settings.json."""
    import json
    r_bin = rscript.parent
    r_exe = r_bin / ("R.exe" if rscript.suffix.lower() == ".exe" else "R")
    settings = {}
    if path.exists():
        text = path.read_text(encoding="utf-8")
        try:
            settings = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError:
            # settings.json may hold comments; drop whole-line // comments and try again
            try:
                settings = json.loads("\n".join(l for l in text.splitlines() if not l.strip().startswith("//")))
            except json.JSONDecodeError as e:
                die(f"{path} could not be read ({e}); nothing was changed. Fix or move it, then run "
                    f"python phewas vscode again.")
        stamp, n = time.strftime('%Y%m%d_%H%M%S'), 1
        backup = path.with_name(f"settings_before_phewas_{stamp}.json")
        while backup.exists():                     # never overwrite an earlier backup
            n += 1
            backup = path.with_name(f"settings_before_phewas_{stamp}_{n}.json")
        backup.write_text(text, encoding="utf-8")
        print(f"backed up {path} to {backup.name}")
    env = settings.setdefault("terminal.integrated.env.windows", {})
    old_path = env.get("PATH", "${env:PATH}")
    # drop this R and any other R's bin folder already there, keep everything else
    kept = [p for p in old_path.split(";") if p and p != str(r_bin)
            and not (p.rstrip("\\").lower().endswith("\\bin") and "\\r-" in p.lower())]
    env["PATH"] = ";".join([str(r_bin)] + kept)
    settings["r.rpath.windows"] = str(r_exe)
    settings["r.rterm.windows"] = str(r_exe)
    settings.setdefault("code-runner.executorMap", {})["r"] = f'& "{rscript}"'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=4) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def vscode(args) -> None:
    """Point VSCodium (and VS Code, if installed) at the newest R, for every folder."""
    rscript = Path(find_rscript(args.rscript))
    for path in user_settings_files():
        point_at_r(path, rscript)
    print(f"R: {rscript}\n  terminal PATH starts with {rscript.parent}; the R extension and Code Runner use "
          f"this R, in every folder.\nOpen a new terminal (the + in the terminal panel) for the PATH to apply.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path,
                    help="the pheauxWAS folder, holding the tools and the group folders "
                         "(default: this script's folder if pheauxWAS/ is there, else the current one)")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="is everything here?").add_argument(
        "--rscript", help="the Rscript program, if not found by itself")
    sub.add_parser("update", help="unpack the newest *bundle*.py here")
    sub.add_parser("sheet", help="one page: where the study stands and the next step")
    sub.add_parser("review", help="one page for the reviewers, after pre and post: tryptase, utilization, "
                                  "background ORs, mast-cell neoplasm subgroup, prevalence in each group")
    sub.add_parser("cluster", help="one page, after pre and post: phecodes significant in both windows with "
                                   "ORs well above the background, grouped by family (cluster 2: the next page)"
                   ).add_argument("page", nargs="?", type=int, default=1)
    sub.add_parser("results", help="one page on one PheWAS run (pre, post or its folder name; default the latest)"
                   ).add_argument("name", nargs="?")
    sub.add_parser("balance", help="after match: SMDs over 0.1, unmatched cases, controls per case").add_argument(
        "--cohort", type=Path, help="default: runs/matching/matched_cohort.parquet")
    sub.add_parser("vscode", help="point VSCodium's terminal and R extension at the newest R").add_argument(
        "--rscript", help="the Rscript program, if not found by itself")

    m = sub.add_parser("match", help="MatchIt on the two group files")
    m.add_argument("--hat", type=Path, help="default: hat_phewas_parquets/hat_group.parquet")
    m.add_argument("--control", type=Path, help="default: control_phewas_parquets/control_group.parquet")
    m.add_argument("--out", type=Path, help="default: runs/matching")
    m.add_argument("--rscript", help="the Rscript program, if not found by itself")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--name", help="the run folder's name (default: pre_3y, post or all)")
    common.add_argument("--cohort", type=Path, help="default: runs/matching/matched_cohort.parquet")
    common.add_argument("--hat-diagnoses", type=Path,
                        help="default: hat_phewas_parquets/hat_group_diagnoses.parquet")
    common.add_argument("--control-diagnoses", type=Path,
                        help="default: control_phewas_parquets/control_group_diagnoses.parquet")
    common.add_argument("--runs", type=Path, help="where run folders go (default: runs)")
    common.add_argument("--skip-pyphewas", action="store_true", help="run pheauxWAS only")
    common.add_argument("--keep-feature-matrices", action="store_true",
                        help="keep pyPheWAS's feature-matrix CSVs (gigabytes on the real data)")
    sub.add_parser("pvalues", help="p and q values for every phecode the reports cite, from the existing results, "
                   "all in runs/pvalues/pvalues.txt (pvalues 2: one page only)").add_argument("page", nargs="?", type=int)
    sub.add_parser("selftest", help="check the runner's phecodeX wiring (sex restriction) on a small made-up cohort")
    sub.add_parser("all", parents=[common], help="move the last run to runs/archive/, then pre, post, review "
                   "and cluster; every page in runs/all_results.txt")
    sub.add_parser("pre", parents=[common], help="the 3 years before index (D12): run --window pre --lookback-years 3")
    sub.add_parser("post", parents=[common], help="after index: run --window post")
    r = sub.add_parser("run", parents=[common], help="any one window, every tool")
    r.add_argument("--window", choices=["pre", "post", "all"], required=True)
    r.add_argument("--lookback-years", type=float, help="with --window pre: the years before index (study: 3)")
    commands = {"check", "update", "vscode", "match", "balance", "sheet", "results", "review", "cluster", "all", "selftest", "pvalues", "pre", "post", "run"}
    argv = [a[2:] if a.startswith("--") and a[2:] in commands else a for a in sys.argv[1:]]
    args = ap.parse_args(argv)

    if args.root is None:
        # the folder holding pheauxWAS/: this script's own on the VM, its parent in the repo (study/, D41)
        args.root = next((d for d in (HERE, HERE.parent) if (d / "pheauxWAS").is_dir()), Path.cwd())
    args.root = Path(os.path.abspath(args.root))
    if args.command == "pre":
        args.command, args.window, args.lookback_years = "run", "pre", 3.0
    elif args.command == "post":
        args.command, args.window, args.lookback_years = "run", "post", None
    {"check": check, "update": update, "vscode": vscode, "match": match, "balance": balance, "sheet": sheet, "results": results,
     "review": review, "cluster": cluster, "all": study_all, "run": run, "pvalues": pvalues,
     "selftest": lambda a: sys.exit(selftest(a))}[args.command](args)


if __name__ == "__main__":
    main()
