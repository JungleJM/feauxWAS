# Cases, Controls And Matching: A Walkthrough

How a PheWAS of one exposure (here HaT) goes from Cosmos pulls to results, on synthetic data shaped exactly like the real pulls. Every file and column below has the name the real data has, so the same steps run on the VM. This explains the *method*; the HaT study's own choices, and why, are in `docs/plan/design.md` and `decisions.md`. The scripts are the study's own, in `study/`; run every command from the repo root.

``` text
tutorial/make_synthetic_cosmos_parquets.py   fake pulls             tutorial/synthetic_cosmos/hat/, …/ctrl/
study/build_group_parquet.py                 one row per patient    hat_group.parquet, control_group.parquet (+ _diagnoses)
study/matchit_example.R                      matching               tutorial/work/matched_cohort.parquet
study/prepare_phewas_inputs.py               exposure code, window  tutorial/work/people_matched.csv, …/diagnosis_events_<window>.csv
pheauxWAS/pheauxWAS.py                       one model per phecode  tutorial/results/hat_phewas_<window>_*
```

Run everything from the repo root. The Python scripts need pandas and pyarrow (`uv run --with pandas --with pyarrow python ...`); the R script installs what it needs.

## 1. The Pulls

``` bash
python3 tutorial/make_synthetic_cosmos_parquets.py
```

Each group is one Telescope pull of four tables, joined by `PatientDurableKey`:

| Table | One row per | Used for |
|--------------------|--------------------|--------------------------------|
| `hat_Patients` / `ctrl_Patients` | patient | `IndexDate` (a DateKey like `20230517`), `AgeAtIndex`, `Sex`, `ReliableSex`, `FirstRace`, `MultiRacial`, `Ethnicity`, `BirthDate`, `DeathDate` |
| `hat_Encounters` / `ctrl_Encounters` | encounter | `DateKey`, `DerivedEncounterStatus`, `DerivedEncounterType_X`, `IsEdVisit`, `IsHospitalAdmission` |
| `hat_Diagnoses` / `ctrl_Diagnoses` | diagnosis event | `DiagnosisDate`, `DiagnosisCode`, `Vocabulary`, `DiagnosisStatus` |
| `hat_Labs` / `ctrl_Labs` | lab result | `LabComponentKey`, `PrioritizedDateKey`, `NumericValue`, `Unit` |

A case's `IndexDate` is their first HaT diagnosis. A control has no diagnosis to anchor on, so the control pull gives each one a **pseudo-index date**: one random clinic visit, drawn from the same years as the cases. Comparing diagnoses "in the 3 years before index" then means the same thing for both groups.

The real pulls take every column Cosmos offers; the synthetic ones keep only these.

## 2. One Row Per Patient

``` bash
python3 study/build_group_parquet.py --dir tutorial/synthetic_cosmos/hat
python3 study/build_group_parquet.py --dir tutorial/synthetic_cosmos/ctrl
```

The builder turns each pull into two files: `<group>_group.parquet`, one row per patient, and `<group>_group_diagnoses.parquet`, one row per patient, code and date. `study/README.md` walks through each step. The columns that matter next:

| Column | What it is |
|------------------------|-----------------------------------------------|
| `HaT_Flag` | 1 for the hat group, 0 for controls |
| `IndexDate`, `IndexQuarter` | the index date, and its calendar quarter (`2023Q2`) |
| `AgeAtIndex`, `Sex`, `Race`, `Ethnicity` | demographics; unknown values grouped as `Unknown` |
| `YearsBeforeIndex`, `YearsAfterIndex` | record length on each side of index, from the first and last completed encounter |
| `ClinicVisits365Before` | days with a completed Office Visit or Follow-Up in the year before index |
| `EligibleForMatching` | 1 if the patient can be matched: two clinic visits in that year, a usable sex, and for cases an index from when the code existed |
| `HaTDateCount`, `EarlierMastCellCode`, `TryptaseMax` | for checking and describing the cases |

**Why clinic visits matter.** A patient who sees doctors more collects more diagnoses. HaT patients are often heavily worked up, so without balancing utilization, every diagnosis can look "associated with HaT". Visit counts are balanced; diagnosis counts are not, because before index those diagnoses are the outcomes being measured.

## 3. Matching

``` bash
Rscript study/matchit_example.R
```

The script stacks the two group files, keeps `EligibleForMatching == 1`, and matches:

``` r
matchit(HaT_Flag ~ AgeAtIndex + YearsBeforeIndex + YearsAfterIndex +
          log1p(ClinicVisits365Before) + Race + Ethnicity,
        data = cohort, method = "nearest", distance = "glm",
        exact = ~ Sex + IndexQuarter,
        ratio = 10, replace = FALSE, caliper = 0.2, std.caliper = TRUE)
```

How to read it:

- `HaT_Flag ~ ...` lists what should look alike between the groups; MatchIt fits a logistic model of being a case on them (the propensity score).
- `exact = ~ Sex + IndexQuarter`: a control must have the same sex and an index in the same 3-month period.
- `ratio = 10`: up to 10 controls per case, each used once (`replace = FALSE`).
- `caliper = 0.2, std.caliper = TRUE`: no control further than 0.2 standard deviations of the propensity score; a case with fewer than 10 close controls keeps fewer.

Then check it worked: `summary(match)` shows each variable's standardized mean difference, which should be under 0.1, and how many cases went unmatched; `work/matchit_balance_love_plot.png` draws the same. On the synthetic data, 328 of 350 eligible cases match, to 2,471 controls. If balance is poor or many cases go unmatched, the pool is too small for the busiest quarters, or quarter is too strict (year is the fallback).

The output, `work/matched_cohort.parquet`, is the matched patients with every group column, plus MatchIt's `distance`, `weights` and `subclass` (the matched set).

## 4. Preparing The PheWAS Inputs

``` bash
python3 study/prepare_phewas_inputs.py \
  --cohort tutorial/work/matched_cohort.parquet \
  --diagnoses tutorial/synthetic_cosmos/hat/hat_group_diagnoses.parquet \
              tutorial/synthetic_cosmos/ctrl/control_group_diagnoses.parquet \
  --window pre --lookback-years 3 \
  --out-dir tutorial/work
```

pheauxWAS tests every diagnosis it is given, so two things happen first:

- **The exposure code goes.** D89.44 maps to phecode `GE_969.4` "Hereditary alpha tryptasemia". Every case has it and no control does, so left in, it is a guaranteed, meaningless top hit, with its parent phecode.
- **One time window is kept**, by each diagnosis's `DaysFromIndex`. `pre` with `--lookback-years 3` keeps the 3 years before index, the same length for everyone: phenotypes present before HaT was diagnosed. `post` keeps what came after: larger effects there may be the workup that follows a diagnosis rather than HaT itself. The index day is in neither.

Run it once per window. The synthetic data plants both patterns: urticaria and fatigue before index, more and larger effects after.

## 5. The PheWAS

``` bash
python3 pheauxWAS/pheauxWAS.py \
  --people tutorial/work/people_matched.csv --id-col PatientDurableKey \
  --predictors HaT_Flag \
  --covars AgeAtIndex Sex Race Ethnicity YearsBeforeIndex ClinicVisits365Before \
  --sex-col Sex \
  --events tutorial/work/diagnosis_events_pre.csv --events-id-col PatientDurableKey \
  --code-col DiagnosisCode --vocab-col Vocabulary --date-col DiagnosisDate \
  --map phecode/phecodeX_ICD_CM_map_flat.csv --definitions phecode/phecodeX_info.csv --definitions phecode/R_CSVs/phecodeX_R_sex.csv \
  --out tutorial/results/hat_phewas_pre
```

For each phecode, a patient is a phecode case with its codes on 2 or more distinct dates; patients with one date are left out of that phecode, and so are those with related phecodes or the wrong sex for it. Phecodes with fewer than 20 cases are skipped. Each remaining phecode gets a logistic regression, `phecode ~ HaT_Flag + covariates`; the `OR` column is HaT's odds ratio, adjusted. Read results by `q_fdr` (or `bonferroni`), not raw `p`: hundreds of phecodes are tested.

Two caveats belong in any write-up. The matched sets are not used in the regression: it is ordinary adjusted logistic regression on a matched cohort, not conditional logistic regression. And controls are "no known HaT", not proven non-HaT.

## 6. All At Once: The Runner

`study/run_phewas.py` does steps 3–5 in two commands (on the VM, `python phewas match` and `python phewas pre`), and also runs pyPheWAS on the same events. Each tool writes to its own folder under `runs/`. On the VM its defaults are the real files, so it needs no paths. Here, give it the synthetic ones:

``` bash
python3 study/run_phewas.py match \
  --hat tutorial/synthetic_cosmos/hat/hat_group.parquet \
  --control tutorial/synthetic_cosmos/ctrl/control_group.parquet
python3 study/run_phewas.py pre \
  --hat-diagnoses tutorial/synthetic_cosmos/hat/hat_group_diagnoses.parquet \
  --control-diagnoses tutorial/synthetic_cosmos/ctrl/control_group_diagnoses.parquet
```

Read the balance in `runs/matching/` before the second command. `runs/pre_3y/` then holds `pheauxwas/` (the results above), `pyphewas/`, `pheauxwas_phecode12/` (pheauxWAS run the way pyPheWAS works, on its map), `comparison/` (the last two side by side; they should agree phecode for phecode) and `run_log.txt`. pyPheWAS needs statsmodels, matplotlib and tqdm; without them the runner skips it and says so.
