# Roadmap

What is unbuilt, unverified, or undecided. The only document that carries status: `design.md` describes what exists, `decisions.md` why.

When an item here is built, delete it from this file and describe the result in `design.md`. When it is decided, record the decision in `decisions.md`.

------------------------------------------------------------------------

## Where Things Stand

| Part | State |
|------------------------------------|------------------------------------|
| pheauxWAS 1.1.0 and pyPheWAS 2a8fff1 | Built; pheauxWAS `--selftest` passes (2026-10-01). The comparison against pyPheWAS on real-shaped data was not rerun |
| Tutorial: synthetic data, MatchIt, `prepare_phewas_inputs.py` (with `--lookback-years`), pheauxWAS pre and post | Built and run end to end on the Mac (2026-10-01): 167 of 200 synthetic cases matched |
| Study design (D4–D13, D24–D26) | Decided; the case rule (D24) and index (D4) are provisional, pending the user's attending (`Attending Questions.md`) |
| `hat_` pull (`HaT_PheWAS_intake.yaml`) | Written; passes Telescope's validator against its dictionary. Not yet run |
| Profile queries (`profile_queries.sql`) | 1–6 run (2026-10-01); being rerun with 7–11 for whole results |
| One-row-per-patient builder (Python) | Not started |
| `ctrl_` pull | Not designed |

------------------------------------------------------------------------

## Next, In Order

1.  **Profile query results 7–11** (task list): the true first D89.44 before 2018, the gap from other D89.4x codes, every race and ethnicity value, every face-to-face encounter type, and the case count by number of D89.44 dates.
2.  **Run the `hat_` pull.** Copy `reference/HaT_PheWAS_intake.yaml` to Telescope's `YAMLs/temp/`, confirm `project_db`, and pull.
3.  **The one-row-per-patient builder**: Python that turns `hat_Patients`, `hat_Encounters` and `hat_Diagnoses` into the matching table (design.md, Derived Fields), with the case rule and the eligibility filter. Built and tested on synthetic data shaped like the pull first.
4.  **The `ctrl_` pull**: sampling per quarter (D6) and the patient-level fields for the \~50× pool (D16). How to sample at random per quarter in a Telescope pull is not worked out.
5.  **Match** with MatchIt on the real cohort; check balance and unmatched cases.
6.  **Pull `ctrl_` diagnoses** for the matched controls only (D16).
7.  **Run the PheWAS**: pre with a 3-year lookback, then post (D12).

------------------------------------------------------------------------

## Open Problems

- **Questions for the user's attending**: the index date and the case rule, in `Attending Questions.md`. Their answers may change D4 and D24.
- **Sensitivity analyses** beyond post-index: high-utilization controls, symptom-adjacent controls (allergic, GI or immune diagnoses, no known HaT), and negative-control phenotypes. None designed.
- **Conditional logistic regression** within matched sets, as a check on D13. pheauxWAS does not do it.
- **Unverified on real data:** that the 3-year lookback (D12) leaves enough events per phecode to reach 20 cases.