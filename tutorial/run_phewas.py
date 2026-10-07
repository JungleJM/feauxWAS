#!/usr/bin/env python3
r"""Match, then run the PheWAS with every tool, each into its own folder (D33-D36).

On the VM, from the pheauxWAS folder, everything is one short command (D36, D37):

    python phewas check     is everything here? Python packages, R and its packages, the files
    python phewas match     MatchIt -> runs\matching\
    python phewas balance   what to judge in the match: SMDs over 0.1, unmatched cases, controls per case
    python phewas sheet     one page: where the study stands and the next step (match, pre, post print it too)
    python phewas pre       the PheWAS, 3 years before index -> runs\pre_3y\
    python phewas post      the PheWAS, after index -> runs\post\
    python phewas update    unpack the newest *bundle*.py in this folder over these scripts
    python phewas vscode    point VSCodium's terminal and R extension at the newest R, in every folder

phewas (no extension) just runs this file; `python phewas --check` works too.
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
PYPHEWAS = "pyPheWAS-2a8fff1"
PYPHEWAS_MIN_CASES = 5           # pyPhewasPipeline's --reg_thresh default


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


def pyphewas_inputs(inputs: Path, events_name: str, folder: Path) -> None:
    """pyPheWAS's group.csv and icds.csv, from the same people and events."""
    import pandas as pd
    people = pd.read_csv(inputs / "people_matched.csv", parse_dates=["BirthDate", "ObservationEndDate"],
                         usecols=["PatientDurableKey", "HaT_Flag", *COVARIATES, "BirthDate", "ObservationEndDate"])
    years = lambda later, birth: (later - birth).dt.days / 365.25
    group = people[["PatientDurableKey", "HaT_Flag"] + COVARIATES].rename(columns={"PatientDurableKey": "id"})
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
    phecode_info = need(root / "phecode" / "phecodeX_info.csv", "phecodeX definitions")
    prepare = need(HERE / "prepare_phewas_inputs.py", "prepare_phewas_inputs.py (beside run_phewas.py)")
    pyp = root / PYPHEWAS
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
    common = ["--people", people, "--id-col", "PatientDurableKey", "--predictors", "HaT_Flag",
              "--covars", *COVARIATES, "--events", events, "--events-id-col", "PatientDurableKey",
              "--code-col", "DiagnosisCode", "--vocab-col", "Vocabulary", "--date-col", "DiagnosisDate"]

    # 2. The study's PheWAS.
    out = fresh(run_dir / "pheauxwas")
    if not log.step("pheauxWAS: phecodeX, the study's rules",
                    [py, pheauxwas, *common, "--sex-col", "Sex", "--map", phecode_map,
                     "--definitions", phecode_info, "--out", out / f"hat_phewas_{name}"], out / "console.txt"):
        failed.append("pheauxwas")

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
            pyphewas_inputs(inputs, events.name, out)
            ok = log.step("pyPheWAS 2a8fff1: Phecode 1.2, its rules, L1-penalized",
                          [py, pyp / "bin" / "pyPhewasPipeline", "--phenotype", "icds.csv", "--group", "group.csv",
                           "--reg_type", "log", "--covariates", "+".join(COVARIATES), "--target", "HaT_Flag",
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
        sheet(args)
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
    for rel in ["pheauxWAS/pheauxWAS.py", "phecode/phecodeX_ICD_CM_map_flat.csv", "phecode/phecodeX_info.csv",
                f"{PYPHEWAS}/bin/pyPhewasPipeline", "hat_phewas_parquets/hat_group.parquet",
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
                + ", ".join(f"{r['variable']} {r['SMD']:+.2f}" for _, r in over.iterrows()))]
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
                         f"[{x['OR_lower95']:.3g}-{x['OR_upper95']:.3g}]  q {x['q_fdr']:.2g}  cases {int(x['n_cases']):,}"
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


def sheet(args) -> None:
    """One page: everything needed to judge where the study stands, and the next step."""
    root, lines = args.root, [f"pheauxWAS one-sheet, {time.strftime('%Y-%m-%d %H:%M')}", ""]
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
    elif not f["over"].empty or len(f["gone"]) > 0.1 * f["eligible"]:
        nxt = "send this sheet: balance or unmatched cases need a decision before the PheWAS"
    elif "pre_3y" not in names:
        nxt = "python phewas pre"
    elif "post" not in names:
        nxt = "python phewas post"
    else:
        nxt = "send this sheet: results ready to review"
    lines += [f"NEXT: {nxt}", "Copy this whole sheet into the chat."]
    text = "\n".join(lines)
    print(text)
    runs.mkdir(exist_ok=True)
    (runs / "sheet.txt").write_text(text + "\n", encoding="utf-8")


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
    sub.add_parser("pre", parents=[common], help="the 3 years before index (D12): run --window pre --lookback-years 3")
    sub.add_parser("post", parents=[common], help="after index: run --window post")
    r = sub.add_parser("run", parents=[common], help="any one window, every tool")
    r.add_argument("--window", choices=["pre", "post", "all"], required=True)
    r.add_argument("--lookback-years", type=float, help="with --window pre: the years before index (study: 3)")
    commands = {"check", "update", "vscode", "match", "balance", "sheet", "pre", "post", "run"}
    argv = [a[2:] if a.startswith("--") and a[2:] in commands else a for a in sys.argv[1:]]
    args = ap.parse_args(argv)

    if args.root is None:
        args.root = HERE if (HERE / "pheauxWAS").is_dir() else Path.cwd()
    args.root = Path(os.path.abspath(args.root))
    if args.command == "pre":
        args.command, args.window, args.lookback_years = "run", "pre", 3.0
    elif args.command == "post":
        args.command, args.window, args.lookback_years = "run", "post", None
    {"check": check, "update": update, "vscode": vscode, "match": match, "balance": balance, "sheet": sheet,
     "run": run}[args.command](args)


if __name__ == "__main__":
    main()
