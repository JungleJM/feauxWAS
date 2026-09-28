# PheWAS Tutorial Assets

Start here:

- `control-matching-tutorial.md`: plain-English guide to HaT controls, matching variables, MatchIt usage, and YAML structure.
- `hat-control-recipe.yaml`: fill-in recipe that points to parquet files with alias-based column references like `p.PatientSex`.
- `make_synthetic_hat_parquets.py`: regenerates the fake parquet examples.
- `synthetic_parquets/`: fake HaT cases, non-HaT pools, candidate-control ratio files, diagnosis events, and example 4:1 matches.
- `why-and-how-for-phewas.md`: the earlier PheWAS overview moved into this tutorial folder.
- `matchit_example.R`: runnable MatchIt example using the synthetic match-ready cohort.

Regenerate synthetic files:

```bash
python3 tutorial/make_synthetic_hat_parquets.py
```

Run the MatchIt example from the repo root:

```bash
Rscript tutorial/matchit_example.R
```
