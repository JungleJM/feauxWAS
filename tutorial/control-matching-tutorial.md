# HaT Control Matching Tutorial

This folder is a working sketch of what to collect before a HaT PheWAS. The synthetic parquets are fake, but the columns are deliberately shaped like a real extraction plan from a large medical database.

## Files In `synthetic_parquets`

- `hat_patients.parquet`: known HaT cases, one row per patient.
- `non_hat_patient_pool.parquet`: patients with no known HaT diagnosis, before matching.
- `candidate_controls_4x.parquet`, `candidate_controls_8x.parquet`, `candidate_controls_20x.parquet`, `candidate_controls_50x.parquet`: increasingly large candidate control pools sampled from eligible non-HaT patients.
- `match_ready_cohort.parquet`: HaT cases plus eligible non-HaT controls in one table, ready for MatchIt.
- `example_4to1_matches.parquet`: example case-control links from a simple greedy match (an illustration of the file shape, not MatchIt).
- `example_4to1_matched_cohort.parquet`: the cohort from that greedy match. The real matched cohort is `matchit_4to1_matched.parquet`, written by `matchit_example.R`.
- `index_events.parquet`: the case diagnosis date or control pseudo-index date.
- `diagnosis_events.parquet`: fake ICD-10-CM events for PheWAS, both before and after the index date. HaT cases also carry the real HaT code, `D89.44`.
- `data_dictionary.csv`: short column explanations.

Regenerate them with:

``` bash
python3 tutorial/make_synthetic_hat_parquets.py
```

## Must-Haves For Control Selection

- Patient ID: a stable identifier present in patient, event, and diagnosis tables.
- HaT flag: `1` for known HaT cases, `0` for no known HaT diagnosis.
- Sex: use exact matching or exact strata.
- Index date: HaT diagnosis/index date for cases; pseudo-index date for controls.
- Age at index: use matching/caliper or strong covariate adjustment.
- Observation time before index: require enough pre-index history, usually at least 1-2 years.
- Observation time after index: require enough follow-up if post-index outcomes are included.
- Utilization before index: clinic visits (in Cosmos, distinct dates with an outpatient face-to-face encounter). Not diagnosis count: in a pre-index PheWAS those diagnoses are the outcomes, and balancing on them removes part of the signal.
- Race and ethnicity: adjust or balance if available and usable.
- Diagnosis-event table: one row per ICD event, with patient ID, code, vocabulary, and date.
- Repeat-diagnosis information: enough to require repeated diagnosis codes for case definitions and phenotypes.

## Good Optional Variables

- Index year or index quarter: exact match on calendar time when possible.
- ED visit and hospital admission counts, kept separate from clinic visits.
- Prior mast-cell-related diagnosis flag: useful sensitivity variable, but be careful because it may partly mediate HaT recognition.
- Medication or lab proxies: only if available broadly enough and not caused by the exposure definition.
- Data-source/system flag: ideal if available, but you said physical location/source details are not available.

## What I Would Use First

Use exact matching on:

- `Sex`
- `IndexQuarter`, meaning same 3-month calendar period

Then use nearest-neighbor or propensity-score matching on:

- `AgeAtIndex`
- `YearsBeforeIndex`
- `YearsAfterIndex`
- `ClinicVisitCountPreIndex`
- `Race`
- `Ethnicity`

I would start with a large control candidate pool, probably 20x or 50x the HaT case count if the database supports it. Then match down to 4:1 or 8:1. Larger final ratios are not automatically better: after about 4-8 controls per case, the gain in precision can be small, and poor extra controls can make balance worse.

## Plain-English Matching Workflow

First, define the cases. Every known HaT patient gets `HaT_Flag = 1` and an `IndexDate`, usually the first reliable HaT diagnosis date or cohort-entry date.

Second, define the possible controls. These are not proven non-HaT; they are "no known HaT diagnosis." Remove anyone with a HaT diagnosis code or cohort flag. Require enough observation before the pseudo-index date, enough follow-up after it if needed, and enough clinical contact that they had a reasonable chance to accumulate diagnoses.

Third, assign each control a pseudo-index date. A simple approach is to sample or choose an eligible encounter date so the control index-date distribution resembles the case index-date distribution. The synthetic parquets use index quarter to represent the "same 3-month period" idea.

Fourth, create a match-ready table with cases and candidate controls in one row-per-patient file. That table should contain the exposure flag, exact-match variables, and balancing variables.

Fifth, run matching. For a first pass, match within exact sex and exact index quarter. Within those strata, find controls with similar age, observation time, and utilization. After matching, inspect balance. If age, utilization, race, or observation time are still imbalanced, tighten calipers, add exact strata, or lower the match ratio.

Sixth, prepare the PheWAS inputs with `prepare_phewas_inputs.py` (next section).

Seventh, use the matched cohort as the population table for the PheWAS. The PheWAS still creates phecode-specific outcome cases and controls internally; the matching step only defines the fairer HaT-vs-non-HaT study population.

## Preparing The PheWAS Inputs

pheauxWAS tests every event it is given. Two decisions must be made before the events reach it:

**Remove the exposure codes.** The code that defines HaT, `D89.44`, maps to phecode `GE_969.4` "Hereditary alpha tryptasemia". If it stays in, every case has it and no control does, so it comes back as the top hit (in the synthetic data: OR ≈ 100,000, p ≈ 10⁻¹⁷⁴), along with its parent `GE_969`. It is circular and says nothing. Drop every code used to define the cases.

**Choose a time window.** Each event is kept or dropped based on its date relative to the patient's index date:

- `pre`: before index. These are phenotypes present before HaT was diagnosed. Use this as the primary analysis, with `--lookback-years 3` so every patient gets the same 3-year window.
- `post`: after index. HaT patients are worked up after diagnosis, so post-index hits can be surveillance rather than biology. Use it as a sensitivity analysis.
- `all`: every event.

The index day is in neither `pre` nor `post`, since codes entered on the diagnosis day are usually part of the HaT workup.

``` bash
python3 tutorial/prepare_phewas_inputs.py \
  --cohort tutorial/synthetic_parquets/matchit_4to1_matched.parquet \
  --events tutorial/synthetic_parquets/diagnosis_events.parquet \
  --window pre --lookback-years 3 \
  --out-dir tutorial/work
```

It writes `tutorial/work/hat_people_matched.csv` and `tutorial/work/hat_diagnosis_events_pre.csv`. Run it once per window, then run pheauxWAS on each events file. The synthetic data is built so the windows differ: urticaria and fatigue are enriched before index, and after index the effects are larger and abdominal pain and anxiety join them. That is the pattern a surveillance effect would produce.

**Matched sets are not used in the regression.** MatchIt writes a `subclass` column (the matched set). pheauxWAS ignores it and runs ordinary logistic regression, adjusted for the covariates, on the matched cohort. This is common and defensible, but say so in the methods. A conditional logistic regression within matched sets is the stricter alternative.

## MatchIt In R

MatchIt's default `matchit()` call does 1:1 nearest-neighbor matching on a propensity score estimated with logistic regression. For this use case, I would be more explicit: exact-match sex and index quarter, estimate propensity from age/observation/utilization/race/ethnicity, and request a fixed control ratio.

Install/read parquet:

``` r
install.packages(c("MatchIt", "arrow", "cobalt", "dplyr"))

library(MatchIt)
library(arrow)
library(cobalt)
library(dplyr)

cohort <- read_parquet("tutorial/synthetic_parquets/match_ready_cohort.parquet") |>
  mutate(
    HaT_Flag = as.integer(HaT_Flag),
    Sex = factor(Sex),
    Race = factor(Race),
    Ethnicity = factor(Ethnicity),
    IndexQuarter = factor(IndexQuarter)
  )
```

Practical first-pass match:

``` r
m1 <- matchit(
  HaT_Flag ~ AgeAtIndex +
    YearsBeforeIndex +
    YearsAfterIndex +
    log1p(ClinicVisitCountPreIndex) +
    Race +
    Ethnicity,
  data = cohort,
  method = "nearest",
  distance = "glm",
  exact = ~ Sex + IndexQuarter,
  ratio = 4,
  replace = FALSE,
  caliper = 0.2,
  std.caliper = TRUE
)

summary(m1)
love.plot(m1, threshold = 0.1)
matched <- match.data(m1)
write_parquet(matched, "tutorial/synthetic_parquets/matchit_4to1_matched.parquet")
```

How to read that:

- `HaT_Flag ~ ...` tells MatchIt which variables predict being a HaT case. These are the variables you want balanced.
- `method = "nearest"` means each case is matched to nearest controls.
- `distance = "glm"` estimates a logistic-regression propensity score.
- `exact = ~ Sex + IndexQuarter` means controls must have the same sex and same 3-month calendar period.
- `ratio = 4` asks for four controls per case.
- `replace = FALSE` prevents the same control from being reused.
- `caliper = 0.2, std.caliper = TRUE` prevents very distant propensity matches.
- `summary(m1)` and `love.plot()` tell you whether matching worked.

If exact quarter is too strict, relax `IndexQuarter` to `IndexYear` or remove exact calendar matching and add a caliper on index time. If too few controls match, try `ratio = 2`, allow replacement, or increase the candidate pool.

MatchIt also supports Mahalanobis matching and Mahalanobis matching within propensity-score calipers. The official docs note that `exact` performs matching within exact strata, and that `mahvars` can specify which variables use Mahalanobis distance when the distance is a propensity score. See:

- <https://search.r-project.org/CRAN/refmans/MatchIt/html/matchit.html>
- <https://search.r-project.org/CRAN/refmans/MatchIt/html/method_nearest.html>
- <https://stat.ethz.ch/CRAN/web/packages/MatchIt/vignettes/matching-methods.html>

## YAML Recipe

The file `hat-control-recipe.yaml` is meant to be filled in with your real parquet paths and column names. It uses aliases so you can write `p.PatientSex` instead of a long path. The convention is:

``` text
alias.ColumnName
```

For example, if your patient parquet is aliased as `p`, and sex is stored in `PatientSex`, use `p.PatientSex`.

The wrapper should:

1.  Load the listed parquet aliases.
2.  Resolve every `alias.column` reference.
3.  Build a match-ready cohort.
4.  Apply eligibility filters.
5.  Run MatchIt in R.
6.  Write a matched patient parquet and a matched-pairs parquet.
7.  Apply the `phewas_prep` block (drop exposure codes, pick the window) and export CSVs for `pheauxWAS`.

That wrapper does not exist yet. For now, run `matchit_example.R` and `prepare_phewas_inputs.py` by hand.

Start with the synthetic paths in the YAML, then replace them with your VM parquet paths.