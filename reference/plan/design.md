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
Cosmos (on the VM)                                  this repo
  hat_ pull ─┐
             ├─► one row per patient ──► MatchIt 4:1 ──► prepare_phewas_inputs.py ──► pheauxWAS
  ctrl_ pull ┘   (cases + ~50× pool)     (matched ~30k)   (drop D89.44, pick window)    (per phecode)
                                              │
                                              └─► ctrl_ diagnoses pulled for the matched only (D16)
```

### Cases And Controls

| | Cases | Controls |
|------------------|------------------------------|------------------------------|
| Who | D89.44 on 2+ distinct dates (D4) | No D89.44 at any date (D5) |
| Index date | First D89.44 | A sampled completed outpatient face-to-face encounter in a case quarter (D6) |
| Age at index | `AgeKey` of the index diagnosis → `DurationDim.Years` | `AgeKey` of the index encounter → `DurationDim.Years` |
| Neither | Patients with exactly one D89.44 | |

Eligibility for both: at least 2 clinic-visit days in the 365 days before index (D8).

### Derived Fields

Built in Python from the pulled tables, one row per patient:

| Field | From |
|------------------------------------|------------------------------------|
| `IndexDate` | A DateKey (`YYYYMMDD` integer), converted to a date |
| `IndexYear`, `IndexQuarter` | The index date: year `key / 10000`, month `(key / 100) % 100`, quarter `(month - 1) / 3 + 1` |
| `ObservationStartDate`, `ObservationEndDate` | First and last encounter `DateKey`; the end also no later than `DeathDate` |
| `YearsBeforeIndex`, `YearsAfterIndex` | Index minus observation start; observation end minus index. |
| `ClinicVisitCountPreIndex` | Distinct `DateKey`s with `IsOutpatientFaceToFaceVisit = 1`, completed, in the 365 days before index (D8) |
| `ClinicVisitCountPostIndex` | The same, after index |
| `Race` | `FirstRace`, with blank / unknown / refused / other grouped into one level (D10) |
| `Sex` | `ReliableSex` (D10), as Male / Female for pheauxWAS's sex-specific phecodes |
| Case rule | Count of distinct D89.44 dates in the diagnoses |

Not collected: diagnosis count before index, problem-list count (D9).

### Matching

MatchIt, 4 controls per case, without replacement (D7):

``` r
matchit(HaT_Flag ~ AgeAtIndex + YearsBeforeIndex + YearsAfterIndex +
          log1p(ClinicVisitCountPreIndex) + Race + Ethnicity,
        method = "nearest", distance = "glm",
        exact = ~ Sex + IndexQuarter,
        ratio = 4, replace = FALSE, caliper = 0.2, std.caliper = TRUE)
```

Balance: standardized mean difference under 0.1 for every variable (`cobalt::love.plot`). Unmatched cases are reviewed: if quarter is too strict, year is the fallback.

### The PheWAS

`tutorial/prepare_phewas_inputs.py` turns the matched cohort and the diagnoses into pheauxWAS's CSVs:

- keeps only events for patients in the matched cohort;
- drops the exposure codes, D89.44 by default (D11);
- keeps one window relative to each patient's index: `pre` (with `--lookback-years 3`, the primary analysis), `post` (sensitivity) or `all`. The index day is in neither pre nor post (D12).

pheauxWAS then fits, for each phecode with at least 20 cases, `phecode ~ HaT_Flag + AgeAtIndex + Sex + Race + Ethnicity + YearsBeforeIndex + ClinicVisitCountPreIndex`, as ordinary logistic regression on the matched cohort (D13). A person is a phecode case with the code on 2+ distinct dates; one-date people are excluded from that phecode.

------------------------------------------------------------------------

## The Cosmos Pull

`reference/HaT_PheWAS_intake.yaml` is a Telescope intake, project "HaT PheWAS", built from dictionary tables (D18). It is validated with Telescope's `makeYaml.py --validate` and run on the VM by Telescope. Window 1990-01-01 to 2026-06-01, all history, with the analysis window applied in Python (D23); ICD-10-CM only (D15); Dual (Cosmos and SneakPeek); 2,000 patients per chunk.

| Table | Rows | From | Joins | Where |
|------------------|------------------|------------------|------------------|------------------|
| `hat_Patients` (PK) | One per patient with any D89.44, at the first | DiagnosisEventFact `def` | DiagnosisTerminologyDim `dt` on `DiagnosisKey`; PatientDim `p` on `DurableKey`; LEFT DurationDim `dur` on `AgeKey` | live rows; date window; `dt.Type = 'ICD-10-CM'`, `dt.Value = 'D89.44'`; `p.IsCurrent`, `IsValid`, `UseInCosmosAnalytics_X` |
| `hat_Encounters` | One per encounter | EncounterFact `ef` | the PK on `PatientDurableKey` | live rows; date window |
| `hat_Diagnoses` | One per diagnosis event and code (D17) | DiagnosisEventFact `def` | the PK; DiagnosisTerminologyDim | live rows; date window; ICD-10-CM |

`hat_Patients` carries index (date, diagnosis event, encounter, code, age) and demographics (`Sex`, `ReliableSex`, `FirstRace`, `MultiRacial`, `Ethnicity`, `BirthDate`, `DeathDate`). It is everyone with any D89.44, so it is also the control exclusion list (D5); the 2-date rule is applied in Python. `hat_Encounters` carries the date, status, type and the outpatient, ED and admission flags. `hat_Diagnoses` carries date, code, vocabulary, event and encounter keys, and the diagnosis's `Type` and `Status`.

DurationDim is a LEFT JOIN so that a missing age does not push a patient's index to a later D89.44. Not pulled: ProblemListFact (D9); EdVisitFact and HospitalAdmissionFact, which EncounterFact's flags cover.

`reference/plan/profile_queries.sql` holds aggregate SSMS queries that size the cohort and show column values before the pull; each says what to look for.

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

`tutorial/` runs the whole method on synthetic data. `README.md` lists the files and commands; `control-matching-tutorial.md` and `why-and-how-for-phewas.md` explain the method in plain English; `hat-control-recipe.yaml` describes the study in one place.

``` text
make_synthetic_hat_parquets.py ─► synthetic_parquets/ (200 cases, 10,000 non-HaT)
matchit_example.R              ─► matchit_4to1_matched.parquet, balance plot
prepare_phewas_inputs.py       ─► work/hat_people_matched.csv, work/hat_diagnosis_events_<window>.csv
pheauxWAS.py                   ─► results/hat_phewas_<window>_*
```

The synthetic cases carry the real D89.44 and events before and after index, with a larger post-index enrichment, so the exposure-code problem and the window difference both show (D19). The `example_4to1_*` files are a greedy illustration; the match is MatchIt's (D20).

## Environments

| | Mac | VM |
|------------------|------------------------------|------------------------------|
| Python | pandas and pyarrow through `uv run --with pandas --with pyarrow`; the repo venv has numpy | from the bundle |
| R | MatchIt, arrow, cobalt, dplyr (installed by `matchit_example.R` if missing) | |
| Cosmos | none | SSMS and Telescope |
