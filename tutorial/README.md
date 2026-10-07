# PheWAS Tutorial

The method, end to end, on synthetic data shaped like the real Cosmos pulls. Start with `control-matching-tutorial.md`, which runs every step in order.

- `control-matching-tutorial.md`: the walkthrough: pulls, one row per patient, matching, PheWAS inputs, PheWAS.
- `why-and-how-for-phewas.md`: what a PheWAS is, the two tools (pheauxWAS and pyPheWAS), and their options.
- `make_synthetic_cosmos_parquets.py`: writes the fake pulls to `synthetic_cosmos/hat/` and `synthetic_cosmos/ctrl/`.
- `synthetic_cosmos/`: the fake pulls, and the group files built from them.
- `work/`, `results/`: what the steps write.

The scripts the steps run are the study's own, in `../study/` (what runs on the VM): `build_group_parquet.py`, `matchit_example.R`, `prepare_phewas_inputs.py` and `run_phewas.py`. Run the commands from the repo root.

The Python scripts need pandas and pyarrow, for example `uv run --with pandas --with pyarrow python ...`.
