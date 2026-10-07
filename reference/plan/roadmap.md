# Roadmap

What is unbuilt, unverified, or undecided. The only document that carries status: `design.md` describes what exists, `decisions.md` why.

When an item here is built, delete it from this file and describe the result in `design.md`. When it is decided, record the decision in `decisions.md`.

------------------------------------------------------------------------

## Where Things Stand

| Part | State |
|------------------------------------|------------------------------------|
| pheauxWAS 1.1.1 and pyPheWAS 2a8fff1 | Built; pheauxWAS `--selftest` passes (2026-10-06), with the separation fix (design.md) |
| `run_phewas.py` (D33–D37) | Built; run end to end on the synthetic data under the VM's pandas 2.2.3 and numpy 2.1.3: the study run matches the tutorial's results, and the Phecode 1.2 bridge agrees with pyPheWAS within 0.002 in beta. On a 67,000-person, 4.3-million-event copy, pheauxWAS took 8 s and pyPheWAS 1.5 min. On the VM, `match` first failed to start Rscript (2026-10-06); the runner now finds it itself |
| Tutorial, remade on Cosmos-shaped synthetic pulls: generator, builder, MatchIt 10:1, `prepare_phewas_inputs.py`, pheauxWAS pre and post | Built and run end to end on the Mac (2026-10-03): 328 of 350 eligible synthetic cases matched, to 2,471 controls |
| Study design (D4–D13, D24–D26) | Decided; the case rule (D24) and index (D4) are provisional, pending the user's attending (`Attending Questions.md`) |
| `hat_` pull | Run on the VM, 2026-10-02 (D28): `hat_Patients`, `hat_Encounters`, `hat_Diagnoses`, `hat_Labs`, as parquets there |
| Profile queries (`tutorial/pulling-cohorts/profile_queries.sql`) | All run (2026-10-03); 7 folded into 2 |
| `build_group_parquet.py` | Built; run on both real pulls on the VM (2026-10-06), writing `hat_phewas_parquets/` and `control_phewas_parquets/`. The control pull ran out of memory until diagnoses were read in chunks (design.md). The two reports haven't been reviewed here yet |
| `ctrl_` pull (`ctrl_PheWAS_intake.yaml`) | Run on the VM (2026-10-06): 5,969 hat keys uploaded; `ctrl_Patients` 300,000, `ctrl_Encounters` 29,822,443, `ctrl_Diagnoses` 92,143,391, `ctrl_Labs` 948. About 4 hours in all |

------------------------------------------------------------------------

## Next, In Order

1.  **Review the two group reports** (`hat_group_report.txt`, `control_group_report.txt`): status spellings, units, who isn't eligible; then the three choices in the task list.
2.  **Update and check the VM**: `python phewas update`, then `python phewas check` (Python and R packages, Rscript, files). Without pyPheWAS's packages the runner skips it and says so.
3.  **Match on the VM** (`python phewas match`, run 2026-10-07), then judge it from `python phewas sheet`: balance, unmatched cases, and how many cases got fewer than 10 controls.
4.  **Run the PheWAS**: `python phewas pre`, then `python phewas post` (D12).

------------------------------------------------------------------------

## Open Problems

- **Questions for the user's attending**: the index date and the case rule, in `Attending Questions.md`. Their answers may change D4 and D24.
- **Sensitivity analyses** beyond post-index: high-utilization controls, symptom-adjacent controls (allergic, GI or immune diagnoses, no known HaT), and negative-control phenotypes. None designed.
- **Conditional logistic regression** within matched sets, as a check on D13. pheauxWAS does not do it.
- **Unverified on real data:** that the 3-year lookback (D12) leaves enough events per phecode to reach 20 cases.