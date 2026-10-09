# pheauxWAS Design

What exists, as built: the tools, the HaT study design, the Cosmos pull and the tutorial.

Three documents, one job each, so a fact lives in exactly one place:

| Document | Answers |
|------------------------------------|------------------------------------|
| `design.md` | What it is, and how it behaves. Describes the repo and the study as they stand. |
| `decisions.md` | Why, what was rejected, and what it cost. Append-only, numbered. |
| `roadmap.md` | What is unbuilt, unverified, or undecided. The only place status lives. |

When this document and the code or study disagree, one of them is wrong. Fix whichever is wrong in the same commit. Working rules are in `.claude/CLAUDE.md`; what is still being discussed is in `docs/plan/tasklist.md` (D1).

------------------------------------------------------------------------

## The Study

The HaT PheWAS asks which diagnoses, across the whole phenome, are more or less common in patients with hereditary alpha tryptasemia (HaT) than in similar patients without known HaT. It is a discovery study: an association among similarly observable patients, not proof that HaT causes a phenotype.

``` text
Cosmos (on the VM)                 build_group_parquet.py           MatchIt 10:1     prepare_phewas_inputs.py      pheauxWAS
  hat_ pull  (4 tables) ─► hat_group.parquet     + _diagnoses ─┐
  ctrl_ pull (4 tables) ─► control_group.parquet + _diagnoses ─┴─► matched cohort ─► drop D89.44, pick window ─► per phecode
```

### Cases And Controls

| | Cases | Controls |
|------------------|------------------------------|------------------------------|
| Who | D89.44 on at least one date (D24, settled by D42: a D89.44 needs a genetic test) | No D89.44 at any date (D5) |
| Index date | First D89.44 (D4) | One random completed Office Visit or Follow-Up from 2021-10-01 on (D30, D31) |
| Age at index | `AgeKey` of the index diagnosis → `DurationDim.Years` | `AgeKey` of the index encounter → `DurationDim.Years` |

Eligibility for both: at least 2 clinic-visit days in the 365 days before index (D8). Counts from the profile queries, 2026-10-01: 5,967 HaT patients, 3,693 of them with D89.44 on 2+ dates.

### The Group Files

`study/build_group_parquet.py` turns each pull into `<group>_group.parquet`, one row per patient, and `<group>_group_diagnoses.parquet`, one row per patient, ICD-10-CM code and date (D29). Its README lists every column and each step; It reads the diagnoses a few million rows at a time and keeps each kept diagnosis as one packed 64-bit key (patient, code, day), with text tested and tidied once per distinct value: the control pull's 92 million diagnoses ran out of memory as a table. A diagnosis of a patient not in `<p>_Patients` is dropped and counted in the report. `--selftest` checks the date parsing and the diagnosis reading against the plain per-row version, and that the memory per diagnosis row stays small. The study's choices it applies:

- diagnoses with a ruled-out or error `DiagnosisStatus` are dropped, then collapsed to one row per patient, code and date;
- a case's index is their first D89.44 surviving that filter (D4, D24); a control's is the sampled clinic visit (D30), and a control with any D89.44 is dropped;
- `Sex` is `ReliableSex`, else `Sex` (D25); unknown race and ethnicity values (blank, `*`-prefixed) are one `Unknown` level (D10);
- observation runs from the first to the last completed encounter, capped at death and the data's end;
- `ClinicVisits365Before` counts days with a completed Office Visit or Follow-Up in the year before index (D8, D31);
- eligible for matching: at least 2 such days, a usable sex, and for cases an index from 2021-10-01 on;
- also kept, for describing the cases: D89.44 date count (the 2+ sensitivity analysis), the first earlier D89.4x code, and baseline serum tryptase (components 2287 and 59082, ng/mL).

Not used: diagnosis count before index, problem-list count (D9).

### Matching

MatchIt, 10 controls per case, without replacement (D7, D32), on the eligible patients of both groups:

``` r
matchit(HaT_Flag ~ AgeAtIndex + YearsBeforeIndex + YearsAfterIndex +
          log1p(ClinicVisits365Before) + Race + Ethnicity,
        method = "nearest", distance = "glm",
        exact = ~ Sex + IndexQuarter,
        ratio = 10, replace = FALSE, caliper = 0.2, std.caliper = TRUE)
```

Balance: standardized mean difference under 0.1 for every variable (`cobalt::love.plot`). Unmatched cases are reviewed: if quarter is too strict, year is the fallback.

`study/matchit_example.R` runs it. With no arguments it matches the tutorial's synthetic groups into `tutorial/work/`; given `<hat_group.parquet> <control_group.parquet> <out folder>` it matches those. For the study, `run_phewas.py match` passes the VM's files and writes `runs/matching/`.

### The PheWAS

`study/prepare_phewas_inputs.py` turns the matched cohort and both groups' diagnosis files into pheauxWAS's CSVs:

- keeps only diagnoses of patients in the matched cohort, reading only their rows from each file and testing the exposure codes once per distinct code (the control file holds about 90 million rows);
- drops the exposure codes, D89.44 by default (D11);
- keeps one window relative to each patient's index: `pre` (with `--lookback-years 3`, the primary analysis), `post` (sensitivity) or `all`. The index day is in neither pre nor post (D12).

pheauxWAS then fits, for each phecode with at least 20 cases, `phecode ~ HaT_Flag + AgeAtIndex + Sex + Race + Ethnicity + YearsBeforeIndex + ClinicVisits365Before`, as ordinary logistic regression on the matched cohort (D13). The post and all windows add `YearsAfterIndex` (D40). A person is a phecode case with the code on 2+ distinct dates; one-date people are excluded from that phecode.

**The runner** (`study/run_phewas.py`, D33–D38, D41) runs all of this with the VM's paths as defaults; on the VM it is typed as `python phewas <command>` (`phewas`, an extensionless Python file beside it, runs it; `--check` works as well as `check`):

| Command | Does |
|---|---|
| `check` | lists what is present and missing: Python packages, Rscript and MatchIt, arrow, cobalt, dplyr, the files |
| `match` | MatchIt into `runs/matching/` |
| `balance` | the match on a page: every variable's standardized mean difference (as MatchIt's `summary()` computes it), unmatched cases by quarter, controls per case; also `runs/matching/balance.txt` |
| `sheet` | one page on the whole study and the next command, in `runs/sheet.txt`; `match` prints it when it finishes (D38). A YearsAfterIndex SMD over 0.1 does not hold up the next step (D40) |
| `results` | one page on one PheWAS run (`results pre`, `results post`; default the latest), in `runs/<run>/sheet.txt`; `pre` and `post` print it when they finish: the model, inputs (HaT and controls, diagnoses, D89.44 rows removed), phecodes tested and significant (higher and lower in HaT), Firth count, FDR hits by category, the top 20 and the top 5 lower in HaT, phecodes whose names suggest the HaT workup, and the cross-check with separated phecodes (|beta| > 10) set apart |
| `pre` | the 3 years before index into `runs/pre_3y/` (`run --window pre --lookback-years 3`) |
| `post` | after index into `runs/post/` |
| `review` | one page for the reviewers, after `pre` and `post` (D43), in `runs/review/review.txt`: tryptase on record and ≥ 8 ng/mL in each group, D89.44 on 2+ dates; ED visits and admissions (not matched on) beside clinic visits; the median OR across all tested phecodes, the non-significant ones and ten proposed negative controls; HaT patients with mast-cell neoplasm codes (D47.0x, C96.2x), by code, and their urticaria, anaphylaxis, insect allergy, flushing, POTS, hypermobility and fracture codes beside other HaT and controls; each key phecode's prevalence in HaT and controls beside its OR; and the ICD codes behind hypermobility, insect allergy, anaphylaxis, CA_125 and GE_978. It reruns pheauxWAS on each run's inputs into `runs/review/<run>/` for the group counts and checks the betas match. Counts of 1–10 show as `<11` |
| `all` | the whole study after matching, in one command (D45): `selftest`, then moves the last run's `pre_3y`, `post`, `review`, `cluster` and `sheet.txt` (not `matching`) to `runs/archive/run_<when it started>/`, then `pre`, `post`, `review` and `cluster`, and writes every page (the study sheet, both results sheets, the review page and every cluster row) to `runs/all_results.txt`, besides each step's own files |
| `pvalues` | p (Wald, or penalized likelihood-ratio under Firth) and FDR q, before and after index, for every phecode the reports cite: the cluster in its order, the diagnosis-related families, the lower-in-HaT phecodes and `GI_527`; Bonferroni marked; every row in one file, `runs/pvalues/pvalues.txt` (`pvalues 2` prints one 45-line page) (D47). Reads each run's results file; nothing is refitted. Also `runs/pvalues/all_phecodes_p_q.csv`: every tested phecode's OR, CI, p and q in both windows |
| `selftest` | checks the runner's phecodeX wiring on a made-up cohort: a female-only phecode (GU_615) coded in both sexes is analysed in women only, and the run's sex check catches it when the sex file is left out (D45) |
| `cluster` | one page, after `pre` and `post` (D44), in `runs/cluster/cluster.txt`: phecodes with FDR < 0.05 in both windows and an OR at least twice that window's median, exposure-adjacent families (GE_969, BI_180, SS_823, CA_120, CA_125) left out, children under their parents, each with its OR, 95% CI and HaT % / control % in both windows; then the five strongest lower in HaT in both windows. The full list is `runs/cluster/cluster.csv`. Uses `review`'s reruns (running them if needed) |
| `update` | unpacks the newest `*bundle*.py` in the folder over the scripts |
| `vscode` | points VSCodium (and VS Code, if installed) at the newest R in its user settings (`%APPDATA%\VSCodium\User\settings.json`, every folder): the terminal's PATH, the R extension (`r.rpath.windows`, `r.rterm.windows`) and Code Runner; keeps other settings and backs the old file up |

`run --window <w>` takes any window. `Rscript` is found on the PATH or under `Program Files\R`, and paths keep their mapped drive letter. Each PheWAS run folder holds:

| Folder | What |
|---|---|
| `inputs/` | `prepare_phewas_inputs.py`'s people and windowed events |
| `pheauxwas/` | the study's PheWAS: phecodeX, the rules above |
| `pheauxwas_phecode12/` | pheauxWAS on pyPheWAS's Phecode 1.2 ICD-10 map with pyPheWAS's rules: one code makes a case, no exclusions, no rollup, no sex limits, 5 cases, no Firth (D34) |
| `pyphewas/` | pyPheWAS's `pyPhewasPipeline`, unmodified, on the same events: `group.csv` (with `MaxAgeAtVisit` = age at `ObservationEndDate`) and `icds.csv` (`AgeAtICD` from `DiagnosisDate` and `BirthDate`); target `HaT_Flag`, the same covariates. Its two feature-matrix CSVs are deleted unless `--keep-feature-matrices` |
| `comparison/` | `pheauxWAS.py --compare` of `pheauxwas_phecode12` against `pyphewas` |
| `run_log.txt` | every command, its time and its ending; each folder has its step's `console.txt` |

A finished run folder stops the run; an unfinished one (a failed try) is renamed `<name>_unfinished_<time>`. pyPheWAS is skipped with a message when it does not import (statsmodels, matplotlib, tqdm); the runner then exits 1, after the pheauxWAS runs. On the synthetic data the bridge and pyPheWAS agree to within 0.002 in beta on every phecode both test.

------------------------------------------------------------------------

## The Cosmos Pull

The `hat_` pull ran on the VM on 2026-10-02 (D28). `study/pulls/HaT_PheWAS_intake.yaml` is the Telescope intake, and `reference/hat_cosmos_blueprint.yaml` the blueprint as run: project "HaT PheWAS", window 2015-01-01 to 2026-06-01, ICD-10-CM only (D15), Dual (Cosmos and SneakPeek), 1,000 patients per chunk. Every table takes every column its Cosmos tables offer; what to drop is decided in Python.

| Table | Rows | From | Joins | Where |
|------------------|------------------|------------------|------------------|------------------|
| `hat_Patients` (PK) | One per patient with any D89.44, at the first | DiagnosisEventFact `def` | DiagnosisTerminologyDim `dt` on `DiagnosisKey`; PatientDim `p` on `DurableKey`; LEFT DurationDim `dur` on `AgeKey` | live rows; date window; `dt.Type = 'ICD-10-CM'`, `dt.Value = 'D89.44'`; `p.IsCurrent`, `IsValid`, `UseInCosmosAnalytics_X` |
| `hat_Encounters` | One per encounter | EncounterFact `ef` | the PK on `PatientDurableKey`; LEFT DepartmentDim `dep` on `DepartmentKey` | live rows; date window |
| `hat_Diagnoses` | One per diagnosis event and code (D17) | DiagnosisEventFact `def` | the PK; DiagnosisTerminologyDim | live rows; date window; ICD-10-CM |
| `hat_Labs` | One per tryptase result | LabComponentResultFact `lcrf` | the PK; LEFT LabComponentDim `lcd` | live rows; date window on `PrioritizedDateKey`; the eight tryptase `LabComponentKey`s |

`hat_Patients` is everyone with any D89.44: every case (D24) and the control exclusion list (D5). Its index columns are prefixed `Index`; it also carries every PatientDim column. `hat_Encounters` carries `DepartmentSpecialty` and the site's `SiteFullyUsableInCosmos…` dates. `hat_Labs`' eight components and what each measures are in the blueprint's description; only 2287 (and maybe 59082) are baseline serum tryptase in ng/mL.

**The `ctrl_` pull** (`study/pulls/ctrl_PheWAS_intake.yaml`, D30) has the same fact tables and columns, with `ctrl_Patients` as the PK: one random completed Office Visit or Follow-Up per patient from 2021-10-01 (the pseudo-index), excluding the uploaded `hat_patient_keys.parquet`. A hash of the patient key keeps about 1% of patients (`pool_permille: 10`), and `smallset` with `stop_at_for_pk_table: 300000` and `random_pk_sample` caps the pool at 300,000 in a reproducible hash order. Run on the VM 2026-10-06 (counts in the roadmap).

DurationDim is a LEFT JOIN so that a missing age does not push a patient's index to a later D89.44. Not pulled: ProblemListFact (D9); EdVisitFact and HospitalAdmissionFact, which EncounterFact's flags cover.

`study/pulls/profile_queries.sql` holds aggregate SSMS queries that size the cohort and show column values before a pull; each says what to look for.

### The Data Dictionary

`reference/DataDictionary.yaml` is a copy of Telescope's `reference/datadictionary.yaml` (D2), never edited here. To sync it after Telescope's changes:

``` bash
cp /Users/jmath/Documents/code/telescope/reference/datadictionary.yaml reference/DataDictionary.yaml
```

Then validate the intake again.

------------------------------------------------------------------------

## The Tools

**pheauxWAS** (`pheauxWAS/pheauxWAS.py`, 1.2.0): one Python file needing only numpy. It maps ICD events to phecodes (rolling child phecodes up to parents), defines cases, exclusions and controls for each phecode, fits logistic regression (Firth when separation is detected, `--firth auto`), corrects with Bonferroni and FDR, and writes a results CSV, an SVG Manhattan plot and a run log with the SHA-256 of the script and every input. Vocabulary values are normalized (`ICD-10-CM` reads as `ICD10CM`). It has no option to drop a phecode or to window events by date: both are done before it (`prepare_phewas_inputs.py`). Separation is also detected when the predictor is 0/1 and one of its four cells with the outcome is empty (a phecode whose cases are all exposed); ML's own checks can miss that, as they did for `BI_180` (all cases HaT, via the earlier D89.4x codes) on a 67,000-person copy of the synthetic data. An odds ratio or bound too large to write is written as `NA`. For a 0/1 predictor the results also give each phecode's cases and totals in each group (`n_cases_exposed`, `n_total_exposed`, `n_cases_unexposed`, `n_total_unexposed`), the last columns of the CSV. `--make-test-data`, `--compare` and `--selftest` build and check a cross-tool synthetic dataset.

**pyPheWAS** (`vendor/pyPheWAS-2a8fff1/`; at the root of the pheauxWAS folder on the VM): the published package at commit 2a8fff1, with lookup, model and plot steps and its own control matcher (`maximizeControls`). Used to cross-check pheauxWAS.

**Phecodes** (`phecode/`): the phecodeX map (`phecodeX_ICD_CM_map_flat.csv`, ICD-10-CM and ICD-9-CM) and definitions (`phecodeX_info.csv`). Latin-1 encoded. phecodeX's R files are in `phecode/R_CSVs/`; among them `phecodeX_R_sex.csv` (male_only, female_only; 320 sex-specific phecodes), which every study run passes to pheauxWAS as a second `--definitions` (D45). phecodeX defines no exclusion ranges, so pheauxWAS's run log warns that none were found; that is expected.

**Bundling** (`tools/make_bundle.py`): packs files into one self-verifying Python file (standard library only; `info`, `verify`, `unpack`, `check`). `python tools/build_vm_bundle.py` builds `bundles/phewas_vm_runner_bundle.py` from `study/phewas`, `study/run_phewas.py`, `study/prepare_phewas_inputs.py`, `study/matchit_example.R` (all at the bundle's top level), `pheauxWAS/pheauxWAS.py` and `phecode/phecodeX_R_sex.csv`: the layout of the pheauxWAS folder on the VM, where `python phewas update` unpacks it.

**Repo tools** (`tools/`): `setup_env.py` makes a local `.venv` from `requirements.txt` (which installs `vendor/pyPheWAS-2a8fff1` editable); `sync_github.py` and `sync_gitea.py` push the current branch to each remote.

------------------------------------------------------------------------

## The Tutorial

`tutorial/` runs the whole method on synthetic data shaped like the real pulls, with the study's own scripts from `study/`: the same table and column names, keeping only the columns the builder reads. `control-matching-tutorial.md` walks through it; `why-and-how-for-phewas.md` explains PheWAS and the two tools. It teaches the method and points here for the study's own choices (D27).

``` text
tutorial/make_synthetic_cosmos_parquets.py ─► tutorial/synthetic_cosmos/hat/, …/ctrl/ (400 cases, 16,000 pool)
study/build_group_parquet.py               ─► hat_group.parquet, control_group.parquet (+ _diagnoses), in each folder
study/matchit_example.R                    ─► tutorial/work/matched_cohort.parquet, balance plot
study/prepare_phewas_inputs.py             ─► tutorial/work/people_matched.csv, …/diagnosis_events_<window>.csv
pheauxWAS/pheauxWAS.py                     ─► tutorial/results/hat_phewas_<window>_*
```

The synthetic cases carry the real D89.44 (single-date cases among them), earlier D89.40 codes, ruled-out diagnoses, cancelled visits, IgE tryptase rows, and more diagnoses after index than before, so each step has something to show (D19).

------------------------------------------------------------------------

## Environments

| | Mac | VM |
|------------------|------------------------------|------------------------------|
| Python | pandas and pyarrow through `uv run --with pandas --with pyarrow`; the repo venv has numpy | from the bundle |
| R | MatchIt, arrow, cobalt, dplyr (installed by `matchit_example.R` if missing) | |
| Cosmos | none | SSMS and Telescope |
