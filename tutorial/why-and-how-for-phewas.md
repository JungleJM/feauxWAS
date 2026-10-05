# Why and How for the pheWAS function

## Short Answer

A PheWAS asks: for one exposure or case label, which diagnoses across the whole medical phenome are more or less common after accounting for covariates? In this repo, the exposure might be hereditary alpha tryptasemia (HaT) status, carrier status in synthetic data, or any binary case/control column.

This is related to "doing a bunch of odds ratios," but the important difference is that a real PheWAS standardizes the workflow: ICD codes are mapped into phecodes, repeated/ambiguous diagnoses are handled consistently, related phecodes can be excluded from controls, covariates are included in every model, many tests are corrected with Bonferroni/FDR, and outputs are designed for phenome-wide review rather than one-off symptom tables.

## What The Two Tools Do

`pheauxWAS` is the lightweight single-file Python implementation in this repo. It needs only Python and `numpy`. It maps ICD events to phecodes, rolls child phecodes up to parents by default, defines phecode-specific cases and controls, fits logistic regression for each phecode, uses Firth regression when separation is detected, then writes a results CSV, SVG Manhattan plot, and run log.

`pyPheWAS` is the larger published package. It splits the workflow into lookup, model, and plot steps. It can also prepare data, define case/control groups from ICD codes, censor by event age, and match controls. It uses `pandas`, `statsmodels`, and plotting libraries.

For a HaT study, use the binary HaT case/control indicator as the exposure/target, and test each phecode as an outcome:

``` text
phecode ~ HaT_status + age + sex + race + ancestry/PCs + utilization covariates
```

The exponentiated HaT coefficient is an odds ratio for that phecode, adjusted for the listed covariates.

## Controls

There are two different "control" ideas here.

First, the study-level controls are people without known HaT who come from the same source population as the HaT cohort. The cleanest starting design is:

- Cases: patients with known HaT or a validated HaT cohort flag.
- Candidate controls: patients eligible to have been observed in the same health system and time window, without the HaT flag.
- Caveat: untested controls may include undiagnosed HaT. State this explicitly as exposure misclassification.
- Matching/covariates: match or adjust on sex, age or birth year, race/ethnicity, ancestry PCs if available, calendar/index year, length of record, encounter density, site/system, and possibly testing opportunity.

Second, each phecode regression creates outcome-level controls. For a given phecode, cases are people who meet the diagnosis count rule for that phecode. Controls are the remaining study people, after removing ambiguous one-code patients and, in `pheauxWAS` default mode, people with related exclusion phecodes or impossible sex-specific codes.

For HaT, I would not pick arbitrary random controls from the whole database unless the source population is well defined. Pull candidate controls from the same VM data universe using the same basic eligibility criteria as cases, assign each control an index date comparable to case diagnosis/index date, require enough observation before/after that date, then match or adjust. Random sampling is fine after those restrictions.

## Synthetic Data Commands

From the repo root:

``` bash
python3 pheauxWAS/pheauxWAS.py --selftest
```

Generate a synthetic cross-tool dataset:

``` bash
python3 pheauxWAS/pheauxWAS.py --make-test-data test_data --test-n 20000 --test-seed 2024
```

Then run these commands from inside `test_data`:

``` bash
cd test_data
```

Run `pheauxWAS` with its standard settings:

``` bash
python3 "../pheauxWAS/pheauxWAS.py" \
  --people pheauxwas/people.csv \
  --predictors carrier \
  --covars age sex \
  --sex-col sex \
  --events pheauxwas/events.csv \
  --map pheauxwas/map_icd10cm_testcodes.csv \
  --definitions pheauxwas/definitions_testcodes.csv \
  --out results/pheauxwas_standard
```

Run `pheauxWAS` in a mode closer to `pyPheWAS`:

``` bash
python3 "../pheauxWAS/pheauxWAS.py" \
  --people pyphewas/group.csv \
  --id-col id \
  --predictors genotype \
  --covars AGE SEX \
  --events pyphewas/icds.csv \
  --code-col ICD_CODE \
  --vocab-col ICD_TYPE \
  --map pheauxwas/map_icd10cm_testcodes.csv \
  --min-code-count 1 \
  --no-exclusions \
  --no-rollup \
  --no-sex-restriction \
  --min-cases 6 \
  --firth never \
  --out results/pheauxwas_pyphewas_mode
```

Run `pyPheWAS` using the local unpacked folder:

``` bash
export PYTHONPATH="../pyPheWAS-2a8fff1"
python3 ../pyPheWAS-2a8fff1/bin/pyPhewasPipeline \
  --phenotype icds.csv \
  --group group.csv \
  --reg_type log \
  --covariates AGE+SEX \
  --path pyphewas \
  --postfix test
```

Compare outputs:

``` bash
python3 "../pheauxWAS/pheauxWAS.py" \
  --compare results/pheauxwas_pyphewas_mode_results.csv pyphewas/regressions_test.csv \
  --compare-predictor genotype \
  --truth truth.csv \
  --out results/compare_vs_pyphewas
```

## Real Data In The VM

The tools expect delimited files, not parquet. For the HaT study, `adapting-cosmos/build_group_parquet.py` turns each Cosmos pull into a group's patient and diagnosis parquets, `matchit_example.R` matches them, and `prepare_phewas_inputs.py` writes pheauxWAS's CSVs: it drops the exposure code and keeps one time window, which pheauxWAS can't do itself. The commands, in order, are in `control-matching-tutorial.md`; what the HaT study itself chose is in `reference/plan/design.md`.

`--min-code-count 2` counts distinct dates per person and phecode. The events file must therefore keep **every** diagnosis date, not one row per patient per code. A pull that deduplicates to the earliest event per code leaves everyone with a count of 1, and nobody becomes a phecode case.

## `pheauxWAS` Parameter Notes

- `--people`: one row per patient; must include the exposure and covariates.
- `--id-col`: patient ID in `--people`; auto-detected when names are obvious.
- `--predictors`: exposure columns; for HAT this is usually `hat`.
- `--covars`: adjustment variables included in every regression.
- `--sex-col`: needed for sex-specific phecode handling.
- `--events`: one row per diagnosis event.
- `--events-id-col`, `--code-col`, `--vocab-col`, `--date-col`: explicit event-table column names.
- `--map`: ICD-to-phecode map; can be repeated.
- `--definitions`: phecode labels, categories, sex restrictions, and exclusion ranges.
- `--min-code-count`: repeated diagnoses needed to call someone a case for a phecode; default is `2`.
- `--min-cases`: minimum number of phecode cases before testing; default is `20`.
- `--no-rollup`: do not roll child phecodes up to parent phecodes.
- `--no-exclusions`: allow all non-cases as controls for every phecode.
- `--firth`: `auto`, `always`, or `never`; `auto` is safest for sparse phecodes.
- `--out`: output prefix for result files.

## `pyPheWAS` CLI Shape

`pyPheWAS` usually wants:

- A phenotype file with `id`, `ICD_CODE`, `ICD_TYPE`, and `AgeAtICD`.
- A group file with `id`, a binary target such as `hat`, and covariates.

Single-command pipeline:

``` bash
export PYTHONPATH="pyPheWAS-2a8fff1"
python3 pyPheWAS-2a8fff1/bin/pyPhewasPipeline \
  --phenotype hat_icds.csv \
  --group hat_group.csv \
  --reg_type log \
  --target hat \
  --covariates sex+age_at_index+race+observation_years+encounter_count \
  --path work/pyphewas \
  --postfix hat \
  --reg_thresh 20 \
  --thresh_type fdr \
  --plot_format png
```

Separate steps, if you want more inspection:

``` bash
python3 pyPheWAS-2a8fff1/bin/pyPhewasLookup \
  --phenotype hat_icds.csv --group hat_group.csv --reg_type log \
  --path work/pyphewas --outfile hat_fm.csv

python3 pyPheWAS-2a8fff1/bin/pyPhewasModel \
  --feature_matrix hat_fm.csv --group hat_group.csv --reg_type log \
  --target hat --covariates sex+age_at_index+race+observation_years \
  --path work/pyphewas --outfile hat_regressions.csv --reg_thresh 20

python3 pyPheWAS-2a8fff1/bin/pyPhewasPlot \
  --statfile hat_regressions.csv --thresh_type fdr \
  --path work/pyphewas --outfile hat_fdr.png
```

For matching controls in `pyPheWAS`, build a group file with cases and candidate controls, then run:

``` bash
python3 pyPheWAS-2a8fff1/bin/maximizeControls \
  --input hat_group.csv \
  --condition hat \
  --keys "sex,age_at_index,index_year" \
  --deltas "0,2,1" \
  --goal 4 \
  --path work/pyphewas \
  --output hat_group_matched.csv
```

This tries to keep four controls per case, exactly matched on sex, within two years on age, and within one year on index year. If the match cannot be achieved, some cases may be dropped; inspect the matched-pairs output.

## QMD Versus Markdown

Use QMD if the report should run code, read result CSVs, calculate odds ratios, style tables, and embed plots automatically. Plain Markdown is fine for static notes, but it will not execute R or Python chunks by itself.

A QMD can still use Python chunks through Quarto/RStudio if Python is configured. A practical approach is:

1.  Use Python CLI tools to generate CSV/SVG/PNG outputs.
2.  Use the QMD to read those outputs in R or Python.
3.  Render tables and plots in the report.

Example QMD chunk:

```{r}
#| eval: false

library(readr)
library(dplyr)
library(knitr)

results <- read_csv("results/hat_phewas_results.csv")

results |>
  mutate(odds_ratio = exp(beta)) |>
  arrange(p) |>
  select(phecode, description, beta, odds_ratio, p, q) |>
  head(20) |>
  kable(digits = 3)
```

## Main Caveats To State

- Controls are "not known HaT," not "proven non-HaT," unless they were tested.
- Diagnosis-code phenotypes reflect healthcare contact and coding behavior.
- Matching reduces imbalance but can drop cases and reduce power.
- Adjustment for utilization is important because patients with more care have more opportunities to accumulate diagnoses.
- Multiple-testing correction is part of the interpretation; raw p-values alone are not enough.
- Codes used to define the exposure must be removed from the events, or the exposure's own phecode is a guaranteed hit.
- Say which time window was tested. Pre-index hits are closer to "part of the HaT phenotype"; post-index-only hits may be diagnostic workup.
- Matched sets are not used in the regression: it is adjusted logistic regression on a matched cohort, not conditional logistic regression.