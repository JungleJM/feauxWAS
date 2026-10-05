# Roadmap

What is unbuilt, unverified, or undecided. The only document that carries status: `design.md` describes what exists, `decisions.md` why.

When an item here is built, delete it from this file and describe the result in `design.md`. When it is decided, record the decision in `decisions.md`.

------------------------------------------------------------------------

## Where Things Stand

| Part | State |
|------------------------------------|------------------------------------|
| pheauxWAS 1.1.0 and pyPheWAS 2a8fff1 | Built; pheauxWAS `--selftest` passes (2026-10-01). The comparison against pyPheWAS on real-shaped data was not rerun |
| Tutorial, remade on Cosmos-shaped synthetic pulls: generator, builder, MatchIt 10:1, `prepare_phewas_inputs.py`, pheauxWAS pre and post | Built and run end to end on the Mac (2026-10-03): 328 of 350 eligible synthetic cases matched, to 2,471 controls |
| Study design (D4–D13, D24–D26) | Decided; the case rule (D24) and index (D4) are provisional, pending the user's attending (`Attending Questions.md`) |
| `hat_` pull | Run on the VM, 2026-10-02 (D28): `hat_Patients`, `hat_Encounters`, `hat_Diagnoses`, `hat_Labs`, as parquets there |
| Profile queries (`tutorial/pulling-cohorts/profile_queries.sql`) | All run (2026-10-03); 7 folded into 2 |
| `build_group_parquet.py` | Built; run on the synthetic pulls under the VM's pandas 2.2.3, pyarrow 22 and numpy 2.1.3. Not yet run on the real `hat_` pull |
| `ctrl_` pull (`ctrl_PheWAS_intake.yaml`) | Written; passes Telescope's validator (one expected warning) and its dry run renders the intended sampling SQL. Not yet run |

------------------------------------------------------------------------

## Next, In Order

1.  **Build the hat group on the VM**: `build_group_parquet.py` beside the `hat_` parquets; read `hat_group_report.txt` (task list).
2.  **Run the `ctrl_` pull**, with `hat_patient_keys.parquet` beside its intake. If the pool comes back under 300,000, raise `pool_permille`.
3.  **Build the control group** the same way.
4.  **Match** with MatchIt on the real groups; check balance, unmatched cases, and how many cases got fewer than 10 controls.
5.  **Run the PheWAS**: pre with a 3-year lookback, then post (D12).

------------------------------------------------------------------------

## Open Problems

- **Questions for the user's attending**: the index date and the case rule, in `Attending Questions.md`. Their answers may change D4 and D24.
- **Sensitivity analyses** beyond post-index: high-utilization controls, symptom-adjacent controls (allergic, GI or immune diagnoses, no known HaT), and negative-control phenotypes. None designed.
- **Conditional logistic regression** within matched sets, as a check on D13. pheauxWAS does not do it.
- **Unverified on real data:** that the 3-year lookback (D12) leaves enough events per phecode to reach 20 cases.