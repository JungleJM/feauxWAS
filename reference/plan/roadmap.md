# Roadmap

What is unbuilt, unverified, or undecided. The only document that carries status: `design.md` describes what exists, `decisions.md` why.

When an item here is built, delete it from this file and describe the result in `design.md`. When it is decided, record the decision in `decisions.md`.

------------------------------------------------------------------------

## Where Things Stand

| Part | State |
|------------------------------------|------------------------------------|
| pheauxWAS 1.1.0 and pyPheWAS 2a8fff1 | Built; pheauxWAS `--selftest` passes (2026-10-01). The comparison against pyPheWAS on real-shaped data was not rerun |
| Tutorial: synthetic data, MatchIt, `prepare_phewas_inputs.py` (with `--lookback-years`), pheauxWAS pre and post | Built and run end to end on the Mac (2026-10-01): 167 of 200 synthetic cases matched |
| Study design (D4–D13) | Decided |
| `hat_` pull (`HaT_PheWAS_intake.yaml`) | Written; passes Telescope's validator against its dictionary. Not yet run |
| Profile queries (`profile_queries.sql`) | Query 6 run (ICD-10-CM spelling, D15); 1–5 running |
| One-row-per-patient builder (Python) | Not started |
| `ctrl_` pull | Not designed |

------------------------------------------------------------------------

## Next, In Order

1.  **Profile query results 1–5** (task list). They size the cohort, give the sampling plan per quarter, count other D89.4x codes before index, and give the exact spellings of sex, race, ethnicity and encounter status.
2.  **Run the `hat_` pull.** Copy `reference/HaT_PheWAS_intake.yaml` to Telescope's `YAMLs/temp/`, confirm `project_db`, and pull.
3.  **The one-row-per-patient builder**: Python that turns `hat_Patients`, `hat_Encounters` and `hat_Diagnoses` into the matching table (design.md, Derived Fields), with the case rule and the eligibility filter. Built and tested on synthetic data shaped like the pull first.
4.  **The `ctrl_` pull**: sampling per quarter (D6) and the patient-level fields for the ~50× pool (D16). How to sample at random per quarter in a Telescope pull is not worked out.
5.  **Match** with MatchIt on the real cohort; check balance and unmatched cases.
6.  **Pull `ctrl_` diagnoses** for the matched controls only (D16).
7.  **Run the PheWAS**: pre with a 3-year lookback, then post (D12).

------------------------------------------------------------------------

## Open Problems

- **D89.4x before the first D89.44.** How many cases had D89.40 or D89.49 before their first D89.44 (profile query 3). A handful: ignore. A large share: revisit the index date (D4).
- **The date D89.44 entered ICD-10-CM** is believed to be October 2021, not checked; query 1's earliest first date will show it.
- **The completed-encounter status value** is unknown until query 5 (D8).
- **Sensitivity analyses** beyond post-index, from `Questions.md`: high-utilization controls, symptom-adjacent controls (allergic, GI or immune diagnoses, no known HaT), and negative-control phenotypes. None designed.
- **Conditional logistic regression** within matched sets, as a check on D13. pheauxWAS does not do it.
- **Unverified on real data:** that the 3-year lookback (D12) leaves enough events per phecode to reach 20 cases.
