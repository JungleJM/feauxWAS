# PheWAS Tutorial Assets

Start here:

- `control-matching-tutorial.md`: plain-English guide to HaT controls, matching variables, MatchIt usage, and YAML structure.
- `hat-control-recipe.yaml`: fill-in recipe that points to parquet files with alias-based column references like `p.PatientSex`.
- `make_synthetic_hat_parquets.py`: regenerates the fake parquet examples.
- `synthetic_parquets/`: fake HaT cases, non-HaT pools, candidate-control ratio files, diagnosis events, and example 4:1 matches.
- `why-and-how-for-phewas.md`: the earlier PheWAS overview moved into this tutorial folder.
- `matchit_example.R`: runnable MatchIt example using the synthetic match-ready cohort.
- `prepare_phewas_inputs.py`: turns the matched cohort and diagnosis events into pheauxWAS CSVs, dropping the HaT code and keeping one time window (pre/post/all index).

Regenerate synthetic files:

``` bash
python3 tutorial/make_synthetic_hat_parquets.py
```

Run the MatchIt example from the repo root:

``` bash
Rscript tutorial/matchit_example.R
```

Prepare inputs and run the PheWAS, once per window (`pre`, then `post`):

``` bash
python3 tutorial/prepare_phewas_inputs.py \
  --cohort tutorial/synthetic_parquets/matchit_4to1_matched.parquet \
  --events tutorial/synthetic_parquets/diagnosis_events.parquet \
  --window pre --lookback-years 3 --out-dir tutorial/work

python3 pheauxWAS/pheauxWAS.py \
  --people tutorial/work/hat_people_matched.csv --id-col Patient_ID \
  --predictors HaT_Flag \
  --covars AgeAtIndex Sex Race Ethnicity YearsBeforeIndex ClinicVisitCountPreIndex \
  --sex-col Sex \
  --events tutorial/work/hat_diagnosis_events_pre.csv --events-id-col Patient_ID \
  --code-col DiagnosisCode --vocab-col Vocabulary --date-col DiagnosisDate \
  --map phecode/phecodeX_ICD_CM_map_flat.csv --definitions phecode/phecodeX_info.csv \
  --out tutorial/results/hat_phewas_pre
```

The Python scripts need `pandas` and `pyarrow` (for example `uv run --with pandas --with pyarrow python ...`).