# Roadmap

What is unbuilt, unverified, or undecided. The only document that carries status: `design.md` describes what exists, `decisions.md` why.

When an item here is built, delete it from this file and describe the result in `design.md`. When it is decided, record the decision in `decisions.md`.

------------------------------------------------------------------------

## Where Things Stand

| Part | State |
|------------------------------------|------------------------------------|
| pheauxWAS 1.2.0 and pyPheWAS 2a8fff1 | Built; pheauxWAS `--selftest` passes (2026-10-08), with the separation fix and counts in each group (design.md) |
| `python phewas review` (D43), `cluster` (D44), `all` and `selftest` (D45) | Built; run on the VM 2026-10-08 with bundle 0d82f13b (`python phewas all`): self-test passed, sex restriction applied in both windows, the first run archived to `runs\archive\run_2026-10-07_0210` |
| `run_phewas.py` (D33–D37) | Built; run end to end on the synthetic data under the VM's pandas 2.2.3 and numpy 2.1.3: the study run matches the tutorial's results, and the Phecode 1.2 bridge agrees with pyPheWAS within 0.002 in beta. On a 67,000-person, 4.3-million-event copy, pheauxWAS took 8 s and pyPheWAS 1.5 min. On the VM, `match` first failed to start Rscript (2026-10-06); the runner now finds it itself |
| Matching and the PheWAS on the VM | Matched 2026-10-07: 3,911 of 4,144 eligible cases to 28,670 controls. Pre- and post-index PheWAS run (post adjusted for YearsAfterIndex, D40); results in `docs/phewasHistoryAndDecisions.md` and the 2026-10-07 review report. That run had no sex restriction (D45); rerun with it 2026-10-08, and the report and narrative now carry the rerun's numbers (482 / 858 pre, 514 / 865 post; Firth 387 and 390)
| Tutorial, remade on Cosmos-shaped synthetic pulls: generator, builder, MatchIt 10:1, `prepare_phewas_inputs.py`, pheauxWAS pre and post | Built and run end to end on the Mac (2026-10-03): 328 of 350 eligible synthetic cases matched, to 2,471 controls |
| Study design (D4–D13, D24–D26, D42) | Decided; the case rule is settled (D42); the index (D4) is provisional, pending the user's attending (`Attending Questions.md`) |
| `hat_` pull | Run on the VM, 2026-10-02 (D28): `hat_Patients`, `hat_Encounters`, `hat_Diagnoses`, `hat_Labs`, as parquets there |
| Profile queries (`study/pulls/profile_queries.sql`) | All run (2026-10-03); 7 folded into 2 |
| `build_group_parquet.py` | Built; run on both real pulls on the VM (2026-10-06), writing `hat_phewas_parquets/` and `control_phewas_parquets/`. The control pull ran out of memory until diagnoses were read in chunks (design.md). The two reports haven't been reviewed here yet |
| `ctrl_` pull (`ctrl_PheWAS_intake.yaml`) | Run on the VM (2026-10-06): 5,969 hat keys uploaded; `ctrl_Patients` 300,000, `ctrl_Encounters` 29,822,443, `ctrl_Diagnoses` 92,143,391, `ctrl_Labs` 948. About 4 hours in all |

------------------------------------------------------------------------

## Next, In Order

1.  **p-values for the reports**: `python phewas update` (bundle cb9abfdc), then `python phewas pvalues`; send the pages of `runs\pvalues\pvalues.txt`. The p and q columns then go into both reports' tables, and the reports are re-rendered and republished (D47).
2.  **Review with the attending and a statistician**: the full and concise reports in `docs/reports/run2_2026-10-08/` (sent as PDF and Word); the full report's section 10 lists the questions. Their answers decide the sensitivity analyses and whether the primary model changes (D13).
3.  **Build the sensitivity analyses as `python phewas` commands**, once their definitions are agreed: all D89.4x (and possibly R74.8, D47.0x, C96.2x) removed from outcomes; cases with mast-cell neoplasm codes (D47.0x, C96.2x) removed; cases with D89.44 on 2+ dates, if still wanted as a robustness check (D42); conditional or weighted regression; controls with baseline tryptase over 8 ng/mL removed.
4.  **Review the two group reports** (`hat_group_report.txt`, `control_group_report.txt`): the DiagnosisStatus values dropped, units, who isn't eligible.

------------------------------------------------------------------------

## Open Problems


- **Criticisms of the design and analysis**: every one we can identify is in the full report (`docs/reports/run2_2026-10-08/`), section 8. The major ones: indication bias in the pre-index window, asymmetric index events, health-system and referral confounding (not matched or adjusted), residual healthcare intensity, and the outcome model ignoring the matched design (D13).

- **Questions for the user's attending**: the index date and the case rule, in `Attending Questions.md`. Their answers may change D4 and D24.
- **Sensitivity analyses** beyond post-index: high-utilization controls, symptom-adjacent controls (allergic, GI or immune diagnoses, no known HaT), and negative-control phenotypes. None designed.
- **Conditional logistic regression** within matched sets, as a check on D13. pheauxWAS does not do it.
- **Unverified on real data:** that the 3-year lookback (D12) leaves enough events per phecode to reach 20 cases.