# Run 3, 2026-10-09

The reports sent to the reviewers, with p-values. Same results as run 2 (the rerun with phecodeX's sex restriction, D45); what is new is the p and q values, read from the VM's results by `python phewas pvalues` and checked on the VM with `python phewas verify` (D47, D48).

- `HaT pheWAS full report 10-9.qmd`: the full report (also `.pdf`, `.docx`).
- `HaT pheWAS preliminary report 10-9.qmd`: the concise report, with the full findings table as its appendix (also `.pdf`, `.docx`).
- `HaT PheWAS all phecodes p and q.csv`: the supplementary file the reports cite: OR, 95% CI, p, q and Bonferroni for every tested phecode, both windows. No patient counts.
- `all_phecodes_p_q_transcribed.csv`, `pvalues_transcribed.txt`: the VM's `runs/pvalues/all_phecodes_p_q.csv` and `pvalues.txt`, transcribed from screenshots and confirmed identical on the VM (`python phewas verify`, 2026-10-09: every line and field identical).
- `pvalues_transcribed.csv`: the p and q of the phecodes the reports cite, by section, as used to build the tables.

Render from this folder with `quarto render "<file>.qmd"` (all formats; Word uses `../report-reference.docx`, PDF `../pdf-header.tex`).
