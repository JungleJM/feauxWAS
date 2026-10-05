# PheWAS Tutorial

The method, end to end, on synthetic data shaped like the real Cosmos pulls. Start with `control-matching-tutorial.md`, which runs every step in order.

- `control-matching-tutorial.md`: the walkthrough: pulls, one row per patient, matching, PheWAS inputs, PheWAS.
- `why-and-how-for-phewas.md`: what a PheWAS is, the two tools (pheauxWAS and pyPheWAS), and their options.
- `make_synthetic_cosmos_parquets.py`: writes the fake pulls to `synthetic_cosmos/hat/` and `synthetic_cosmos/ctrl/`.
- `adapting-cosmos/`: the script that turns a pull into a group's parquets, its walkthrough, and the control pull's YAML. This is what runs on the VM.
- `matchit_example.R`: MatchIt, 10 controls per case.
- `prepare_phewas_inputs.py`: drops the exposure code and keeps one time window, for pheauxWAS.
- `pulling-cohorts/`: the HaT pull's intake and the SSMS profile queries.
- `work/`, `results/`: what the steps write.

The Python scripts need pandas and pyarrow, for example `uv run --with pandas --with pyarrow python ...`.
