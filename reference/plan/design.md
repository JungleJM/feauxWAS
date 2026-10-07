# pheauxWAS Design

What exists, as built: the tools, the HaT study design, the Cosmos pull and the tutorial.

Three documents, one job each, so a fact lives in exactly one place:

| Document | Answers |
|------------------------------------|------------------------------------|
| `design.md` | What it is, and how it behaves. Describes the repo and the study as they stand. |
| `decisions.md` | Why, what was rejected, and what it cost. Append-only, numbered. |
| `roadmap.md` | What is unbuilt, unverified, or undecided. The only place status lives. |

When this document and the code or study disagree, one of them is wrong. Fix whichever is wrong in the same commit. Working rules are in `.claude/CLAUDE.md`; what is still being discussed is in `reference/plan/tasklist.md` (D1).

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
| Who | D89.44 on at least one date (D24); 2+ dates as a sensitivity analysis | No D89.44 at any date (D5) |
| Index date | First D89.44 (D4) | A sampled completed Office Visit in a case quarter (D6, D26) |
| Age at index | `AgeKey` of the index diagnosis → `DurationDim.Years` | `AgeKey` of the index encounter → `DurationDim.Years` |

Eligibility for both: at least 2 clinic-visit days in the 365 days before index (D8). Counts from the profile queries, 2026-10-01: 5,967 HaT patients, 3,693 of them with D89.44 on 2+ dates.

### The Group Files

`tutorial/adapting-cosmos/build_group_parquet.py` turns each pull into `<group>_group.parquet`, one row per patient, and `<group>_group_diagnoses.parquet`, one row per patient, ICD-10-CM code and date (D29). Its README lists every column and each step; It reads the diagnoses a few million rows at a time and keeps each kept diagnosis as one packed 64-bit key (patient, code, day), with text tested and tidied once per distinct value: the control pull's 92 million diagnoses ran out of memory as a table. A diagnosis of a patient not in `<p>_Patients` is dropped and counted in the report. `--selftest` checks the date parsing and the diagnosis reading against the plain per-row version, and that the memory per diagnosis row stays small. The study's choices it applies:

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

### The PheWAS

`tutorial/prepare_phewas_inputs.py` turns the matched cohort and both groups' diagnosis files into pheauxWAS's CSVs:

- keeps only diagnoses of patients in the matched cohort;
- drops the exposure codes, D89.44 by default (D11);
- keeps one window relative to each patient's index: `pre` (with `--lookback-years 3`, the primary analysis), `post` (sensitivity) or `all`. The index day is in neither pre nor post (D12).

pheauxWAS then fits, for each phecode with at least 20 cases, `phecode ~ HaT_Flag + AgeAtIndex + Sex + Race + Ethnicity + YearsBeforeIndex + ClinicVisits365Before`, as ordinary logistic regression on the matched cohort (D13). A person is a phecode case with the code on 2+ distinct dates; one-date people are excluded from that phecode.

------------------------------------------------------------------------

## The Cosmos Pull

The `hat_` pull ran on the VM on 2026-10-02 (D28). `tutorial/pulling-cohorts/HaT_PheWAS_intake.yaml` is the Telescope intake, and `reference/hat_cosmos_blueprint.yaml` the blueprint as run: project "HaT PheWAS", window 2015-01-01 to 2026-06-01, ICD-10-CM only (D15), Dual (Cosmos and SneakPeek), 1,000 patients per chunk. Every table takes every column its Cosmos tables offer; what to drop is decided in Python.

| Table | Rows | From | Joins | Where |
|------------------|------------------|------------------|------------------|------------------|
| `hat_Patients` (PK) | One per patient with any D89.44, at the first | DiagnosisEventFact `def` | DiagnosisTerminologyDim `dt` on `DiagnosisKey`; PatientDim `p` on `DurableKey`; LEFT DurationDim `dur` on `AgeKey` | live rows; date window; `dt.Type = 'ICD-10-CM'`, `dt.Value = 'D89.44'`; `p.IsCurrent`, `IsValid`, `UseInCosmosAnalytics_X` |
| `hat_Encounters` | One per encounter | EncounterFact `ef` | the PK on `PatientDurableKey`; LEFT DepartmentDim `dep` on `DepartmentKey` | live rows; date window |
| `hat_Diagnoses` | One per diagnosis event and code (D17) | DiagnosisEventFact `def` | the PK; DiagnosisTerminologyDim | live rows; date window; ICD-10-CM |
| `hat_Labs` | One per tryptase result | LabComponentResultFact `lcrf` | the PK; LEFT LabComponentDim `lcd` | live rows; date window on `PrioritizedDateKey`; the eight tryptase `LabComponentKey`s |

`hat_Patients` is everyone with any D89.44: every case (D24) and the control exclusion list (D5). Its index columns are prefixed `Index`; it also carries every PatientDim column. `hat_Encounters` carries `DepartmentSpecialty` and the site's `SiteFullyUsableInCosmos…` dates. `hat_Labs`' eight components and what each measures are in the blueprint's description; only 2287 (and maybe 59082) are baseline serum tryptase in ng/mL.

**The `ctrl_` pull** (`tutorial/adapting-cosmos/ctrl_PheWAS_intake.yaml`, D30) has the same fact tables and columns, with `ctrl_Patients` as the PK: one random completed Office Visit or Follow-Up per patient from 2021-10-01 (the pseudo-index), excluding the uploaded `hat_patient_keys.parquet`. A hash of the patient key keeps about 1% of patients (`pool_permille: 10`), and `smallset` with `stop_at_for_pk_table: 300000` and `random_pk_sample` caps the pool at 300,000 in a reproducible hash order. Not yet run.

DurationDim is a LEFT JOIN so that a missing age does not push a patient's index to a later D89.44. Not pulled: ProblemListFact (D9); EdVisitFact and HospitalAdmissionFact, which EncounterFact's flags cover.

`tutorial/pulling-cohorts/profile_queries.sql` holds aggregate SSMS queries that size the cohort and show column values before a pull; each says what to look for.

### The Data Dictionary

`reference/DataDictionary.yaml` is a copy of Telescope's `reference/datadictionary.yaml` (D2), never edited here. To sync it after Telescope's changes:

``` bash
cp /Users/jmath/Documents/code/telescope/reference/datadictionary.yaml reference/DataDictionary.yaml
```

Then validate the intake again.

------------------------------------------------------------------------

## The Tools

**pheauxWAS** (`pheauxWAS/pheauxWAS.py`, 1.1.0): one Python file needing only numpy. It maps ICD events to phecodes (rolling child phecodes up to parents), defines cases, exclusions and controls for each phecode, fits logistic regression (Firth when separation is detected, `--firth auto`), corrects with Bonferroni and FDR, and writes a results CSV, an SVG Manhattan plot and a run log with the SHA-256 of the script and every input. Vocabulary values are normalized (`ICD-10-CM` reads as `ICD10CM`). It has no option to drop a phecode or to window events by date: both are done before it (`prepare_phewas_inputs.py`). `--make-test-data`, `--compare` and `--selftest` build and check a cross-tool synthetic dataset.

**pyPheWAS** (`pyPheWAS-2a8fff1/`): the published package at commit 2a8fff1, with lookup, model and plot steps and its own control matcher (`maximizeControls`). Used to cross-check pheauxWAS.

**Phecodes** (`phecode/`): the phecodeX map (`phecodeX_ICD_CM_map_flat.csv`, ICD-10-CM and ICD-9-CM) and definitions (`phecodeX_info.csv`). Latin-1 encoded.

**Bundling** (`bundling/make_bundle.py`): packs the repo into one file for the VM; the command is in the root `readme.md`.

------------------------------------------------------------------------

## The Tutorial

`tutorial/` runs the whole method on synthetic data shaped like the real pulls: the same table and column names, keeping only the columns the builder reads. `control-matching-tutorial.md` walks through it; `why-and-how-for-phewas.md` explains PheWAS and the two tools. It teaches the method and points here for the study's own choices (D27).

``` text
make_synthetic_cosmos_parquets.py      ─► synthetic_cosmos/hat/, synthetic_cosmos/ctrl/ (400 cases, 16,000 pool)
adapting-cosmos/build_group_parquet.py ─► hat_group.parquet, control_group.parquet (+ _diagnoses), in each folder
matchit_example.R                      ─► work/matched_cohort.parquet, balance plot
prepare_phewas_inputs.py               ─► work/people_matched.csv, work/diagnosis_events_<window>.csv
pheauxWAS.py                           ─► results/hat_phewas_<window>_*
```

The synthetic cases carry the real D89.44 (single-date cases among them), earlier D89.40 codes, ruled-out diagnoses, cancelled visits, IgE tryptase rows, and more diagnoses after index than before, so each step has something to show (D19).

------------------------------------------------------------------------

## Environments

| | Mac | VM |
|------------------|------------------------------|------------------------------|
| Python | pandas and pyarrow through `uv run --with pandas --with pyarrow`; the repo venv has numpy | from the bundle |
| R | MatchIt, arrow, cobalt, dplyr (installed by `matchit_example.R` if missing) | |
| Cosmos | none | SSMS and Telescope |
