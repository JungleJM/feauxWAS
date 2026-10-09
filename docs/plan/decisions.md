# Decisions

Why things are the way they are. `design.md` says what the repo and the study *are*; this says what was chosen, what was rejected, and what it cost. What is still undecided lives in `roadmap.md`.

Entries are grouped, numbered stably, and never renumbered. A reversed decision keeps its entry and gains a **Superseded by** line, because the reasoning that led to the wrong answer is usually the reasoning that will lead there again.

------------------------------------------------------------------------

## Method

### D1. Three plan documents and a self-cleaning task list

**Context.** The study was being worked out in a task list of questions, answers and tables (`reference/tasks.md`, then `reference/plan/taslklist.md`). Settled answers and open questions sat side by side, so what was decided was hard to find.

**Decision.** Follow the Telescope project's practice. `design.md` (what is), `decisions.md` (why), `roadmap.md` (status and next) are the only design documents, and a fact lives in one of them only. `reference/plan/tasklist.md` holds only what is under discussion, answered topic by topic (D22); what is settled moves into the three documents and is deleted from it. The working rules are in `.claude/CLAUDE.md`.

**Consequences.** The task list stays short. Settled answers from the first round (D4–D18) were moved out on 2026-10-01.

### D2. Telescope's data dictionary is the source of truth

**Context.** This repo had its own copy of the Cosmos data dictionary, older than Telescope's (DurationDim, ProblemListFact and the lab tables had since been checked against their Cosmos pages there). Telescope validates the pull against its own copy.

**Decision.** `reference/DataDictionary.yaml` is a copy of Telescope's `reference/datadictionary.yaml`, replaced whole when Telescope's changes. It is never edited here.

**Rejected.** A symlink (breaks on the VM and in the bundle) and a git submodule (pulls in the whole Telescope repo for one file).

**Cost.** The copy can fall behind; the sync is a manual `cp` (design.md, The Data Dictionary).

### D3. Study decisions come from this repo; Telescope is used for its format

**Context.** On 2026-09-30 Telescope recipes from other studies (`PatientWithDx`, `OtherDiagnoses`) were read to interpret a note, and their details leaked into this repo's reference files.

**Decision.** What to match on, which diagnoses count and how the study is designed are decided from this repo and the user. Telescope is used for how a pull YAML is written, its validator and its data dictionary. The HaT pull is built from dictionary tables, not from Telescope recipes (D18).

### D21. Task-list replies are GitHub alert blocks, not Quarto callouts

**Amends D1.**

**Context.** The task list began as `tasklist.qmd` with Quarto callouts (`::: {.callout-note title="🟦 Claude"}`). VS Code's built-in preview does not render them, and does not preview a `.qmd` as markdown at all, so the user saw raw `:::` lines.

**Decision.** The task list is `reference/plan/tasklist.md`. Claude's reply is a `> [!NOTE]` block (blue) headed `**Claude: <topic>**`; the user's is a `> [!IMPORTANT]` block (purple) headed `**Your response**`. Every line starts with `>`.

**Rejected.** Code blocks: visually distinct, but they render no bold, lists or tables, do not wrap, and invite code.

**Consequences.** A viewer without alert support still shows them as quote blocks.

**Superseded by D22**: the user's editor escapes `[!NOTE]` on save.

### D22. Task-list replies are bordered Quarto boxes

**Amends D1; supersedes D21.**

**Context.** The user edits the task list in Quarto's visual editor, which saves markdown in its own form: `[!NOTE]` became `\[!NOTE\]`, so GitHub alerts never rendered, and HTML divs became Quarto fenced divs. A test of 24 formats (2026-10-01) found the bordered boxes clearest.

**Decision.** Claude's reply is a fenced div with a blue border, the user's with an orange one (the exact lines are in `.claude/CLAUDE.md`), each headed in bold. Markdown inside, not HTML: the editor shows raw `<b>` tags. The file stays `tasklist.md`; the same boxes work in a `.qmd`.

**Rejected.** Filled boxes (also rendered, but busier); coloured text, highlights, tables, collapsible blocks, `diff` code blocks and the rest of the test.

### D27. Nothing outside the plan documents restates them

**Amends D1.**

**Context.** Notes written before the plan documents (`reference/cosmos_parquet_ref.yaml`, `Questions.md`) repeated facts that are now in design, decisions and roadmap, so two copies could drift.

**Decision.** Once a note's content is in the plan documents, the note is deleted. Other files point to the plan documents rather than restating them. `cosmos_parquet_ref.yaml` and `Questions.md` were deleted on 2026-10-02. Questions for the user's attending are kept in `reference/plan/Attending Questions.md`, which asks rather than decides.

------------------------------------------------------------------------

## Study Design

### D4. Cases: D89.44 on two or more dates; index at the first

**Decision.** A case has D89.44 (hereditary alpha tryptasemia) on at least 2 distinct dates. The index date is the date of the first D89.44.

**Rejected.** The first date of any HaT-related code (D89.40–D89.49). Those are mast-cell activation codes, broader than HaT, and would pull the index earlier for patients who were never HaT.

**Consequences.** D89.44 entered ICD-10-CM around October 2021, so no index is earlier; a patient coded D89.40 or D89.49 before then has an index later than their real diagnosis. How many is measured, not assumed (roadmap).

**Superseded by D24** for the case rule (1+ dates); the index (first D89.44) stands.

### D5. Controls never had D89.44; one-code patients are neither

**Decision.** Controls are patients with no D89.44 at any date, "no known HaT" rather than proven non-HaT. Patients with exactly one D89.44 are neither cases nor controls, so the control exclusion list is everyone with any D89.44.

**Cost.** Untested controls may include undiagnosed HaT: exposure misclassification, stated in the write-up.

**Amended by D24:** with a 1-date case rule there is no one-code group; everyone with any D89.44 is a case.

### D6. Control pseudo-index dates come from an encounter in a case quarter

**Decision.** For each calendar quarter, sample about 50 controls per case in that quarter from patients with a completed outpatient face-to-face encounter then, one random encounter per patient, each patient once overall. That encounter's date is the control's index date and its `AgeKey` gives their age, the same way the case's is found.

**Rejected.** Choosing controls with a new diagnosis in the same window, or with nearby (GI, immune) diagnoses. That selects on outcomes; controls should match on the chance to be observed, not on phenotype.

**Amended by D30:** how the pool is drawn in a Telescope pull.

### D7. Match 4:1 in MatchIt

**Decision.** Exact on sex and index quarter; nearest neighbour on a logistic propensity score from age at index, years before and after index, log(clinic visits before index), race and ethnicity; caliper 0.2 SD, no replacement, 4 controls per case. Balance is checked (standardized mean difference under 0.1) and unmatched cases are reviewed.

**Consequences.** The PheWAS tests against the \~4× matched controls; the rest of the \~50× pool is discarded (D16).

**Amended by D32:** 10 controls per case.

### D8. Utilization is clinic visits

**Decision.** A clinic visit is a distinct `DateKey` with an EncounterFact row where `IsOutpatientFaceToFaceVisit = 1` and the encounter is completed. Eligibility (cases and controls): at least 2 clinic-visit days in the 365 days before index. Matching: the count of clinic-visit days in those 365 days. ED visits (`IsEdVisit`) and admissions (`IsHospitalAdmission`) are counted separately if used, not lumped in.

**Amended by D26:** a clinic visit is an Office Visit only.

### D9. No matching or adjusting on diagnosis or problem-list counts

**Context.** The first tutorial matched on the number of diagnoses before index, and the extraction plan collected a problem-list count.

**Decision.** Neither is collected or used. In a pre-index PheWAS those diagnoses are the outcomes: HaT patients have more of them because of HaT, so matching on their count cancels out part of the difference being measured. Clinic visits are the utilization measure (D8).

### D10. Demographics: group unknown race, keep ethnicity, use ReliableSex

**Decision.** Blank, unknown, refused and "other" race values are grouped into one level, not dropped, since dropping can remove cases and controls unevenly. `Ethnicity` is kept (race does not capture Hispanic ethnicity). `ReliableSex`, "cleaned for analytic use", is preferred to `Sex`; `MultiRacial` is pulled alongside `FirstRace`.

**Amended by D25:** `ReliableSex`, falling back to `Sex` when Ambiguous.

### D11. Exposure-defining codes are removed from the PheWAS events

**Context.** D89.44 maps to phecode GE_969.4 "Hereditary alpha tryptasemia". Left in the events, every case has it and no control does: on the synthetic data it came back at OR ≈ 100,000, p ≈ 10⁻¹⁷⁴, with its parent GE_969.

**Decision.** `tutorial/prepare_phewas_inputs.py` drops D89.44 from the events before pheauxWAS sees them. pheauxWAS has no option to drop a phecode.

### D12. Pre-index with a 3-year lookback is primary; post-index is sensitivity

**Decision.** The primary PheWAS uses diagnoses in the 3 years before index: phenotypes present before HaT was diagnosed, with the same window for every patient. The post-index PheWAS is a sensitivity analysis: hits only after index may be diagnostic workup. The index day is in neither.

**Rejected.** All history since the start of the pull (2018). It gives more events, but the window length varies with index date (about 3.75 to 7 years).

**Consequences.** 3 years is the longest window every patient fully has: the earliest index is about October 2021, and 3 years back is still after 2018 (D14).

### D13. The matched cohort is analysed with ordinary adjusted logistic regression

**Decision.** pheauxWAS ignores MatchIt's matched sets (`subclass`) and fits covariate-adjusted logistic regression on the matched cohort. Stated in the methods.

**Rejected, for now.** Conditional logistic regression within matched sets: the stricter choice, which pheauxWAS does not do.

### D24. Cases: D89.44 on at least one date

**Supersedes D4's 2-date rule; provisional.**

**Context.** Profile queries (2026-10-01): 5,967 patients have D89.44 at least once, 3,693 on 2 or more distinct dates. The 2-date rule is a PheWAS habit for common conditions, where one-off and rule-out codes are frequent. HaT is diagnosed by genetic testing, so a single D89.44 is likely reliable, and the user's earlier work and papers use the ~6,000.

**Decision.** A case has D89.44 on at least one date (5,967). The index stays the first D89.44 (D4). 2+ dates is the sensitivity analysis. Both counts are reported.

**Consequences.** The pull is unchanged: it holds everyone with any D89.44 and every D89.44 date, so the rule can be switched in Python if the user's attending advises it (`Attending Questions.md`).

### D25. Sex: ReliableSex, falling back to Sex

**Amends D10.**

**Context.** Among HaT patients, `ReliableSex` is Female 4,452, Male 1,379 and Ambiguous 136; for the Ambiguous, `Sex` says Female 105, Male 30, Unknown 1.

**Decision.** Use `ReliableSex`; where it is Ambiguous, use `Sex`; drop the one patient whose `Sex` is Unknown, since exact matching and sex-specific phecodes need Male or Female.

### D26. A clinic visit is an Office Visit

**Amends D8.**

**Context.** `IsOutpatientFaceToFaceVisit = 1` covers both Office Visit and Hospital Outpatient Visit (profile query 5), and the second can be labs, imaging or infusions, which would count testing as clinic contact.

**Decision.** A clinic visit is an EncounterFact row with `DerivedEncounterStatus = 'Complete'` and `DerivedEncounterType_X = 'Office Visit'`, counted as distinct `DateKey`s. Query 10 lists every flagged type, in case another belongs.

**Amended by D31:** Follow-Up counts too.

### D31. A clinic visit is an Office Visit or a Follow-Up

**Amends D26.**

**Context.** Profile query 10 showed the face-to-face flag also covers Follow-Up, Procedure visit, Telemedicine, Routine Prenatal, Infusion, Home Care Visit, Surgery and Anticoagulation Visit.

**Decision.** A clinic visit is a completed (`DerivedEncounterStatus = 'Complete'`) encounter whose `DerivedEncounterType_X` is `Office Visit` or `Follow-Up`. Control pseudo-index visits are drawn from the same types.

### D32. 10 controls per case

**Amends D7.**

**Decision.** MatchIt keeps 10 controls per case (about 60,000 for 5,967 cases); everything else in D7 stands.

### D33. One runner, two commands: match, then run

**Context.** After the group files, the steps were separate commands typed with long paths: MatchIt, `prepare_phewas_inputs.py`, then pheauxWAS. The user asked (2026-10-06) for the PheWAS commands in one script, each tool writing to its own folder under `runs/`.

**Decision.** `tutorial/run_phewas.py` has two commands. `match` runs `matchit_example.R` on the two group files and writes `runs/matching/`. `run` starts from that matched cohort, applies one window with `prepare_phewas_inputs.py`, runs every tool, and writes `runs/<name>/`, one folder per tool, with a log of every command. Matching stays a separate command so its balance is read before anything runs on it. The runner adds no analysis of its own, and it refuses to overwrite an existing run folder.

**Rejected.** One command that matches and runs the PheWAS: nothing would stop a run on a poorly balanced cohort.

### D34. pyPheWAS is a cross-check, bridged by pheauxWAS on Phecode 1.2

**Context.** pyPheWAS (2a8fff1) is a different analysis: Phecode 1.2 with its ICD-10 beta map (no D89.44), a case on one code, no exclusions, L1-penalized logistic regression (alpha 0.1), 5 cases minimum. Its results cannot be compared phecode by phecode with the study's phecodeX run.

**Decision.** The runner makes three runs on the same windowed events: `pheauxwas/` (the study's result), `pyphewas/`, and `pheauxwas_phecode12/`, which is pheauxWAS on pyPheWAS's own map with pyPheWAS's rules. The last two should agree phecode for phecode, and `pheauxWAS.py --compare` lines them up in `comparison/`. pyPheWAS is skipped, with a message, when its packages are missing.

### D35. The runner's defaults are the VM's layout

**Context.** On the VM the repo root holds `hat_phewas_parquets/` and `control_phewas_parquets/`, the builder's outputs for each group.

**Decision.** The runner's default paths are those folders' files, relative to the repo root (`--root`, the current folder by default), so on the VM `python run_phewas.py match` and `python run_phewas.py run --window pre --lookback-years 3` need no paths. The tutorial passes its synthetic paths explicitly.

**Amended by D36:** the root defaults to the runner's own folder when `pheauxWAS/` is there.

### D36. On the VM, every command is one or two words

**Context.** Everything on the VM is typed by hand; long commands, paths and PACK_IDs were hard to type and easy to get wrong (2026-10-06).

**Decision.** `phewas.bat`, beside `run_phewas.py`, runs it: `.\phewas check`, `match`, `pre`, `post`, `update`. `pre` and `post` are the study's two windows (D12); `check` lists what is present and missing (Python packages, Rscript and the R packages, the files); `update` unpacks the newest `*bundle*.py` in the folder over the scripts. `vscode` points VSCodium's terminal and R extension at the newest R in its user settings, for every folder, since Rscript was not on its PATH. Anything new the VM must run becomes such a command, with its paths as defaults. The runner finds `Rscript` itself (the PATH, then `Program Files\R`), keeps mapped-drive paths as typed, and renames an unfinished run folder out of the way rather than refusing to start.


### D37. The short commands run through Python, not a .bat

**Amends D36.**

**Context.** On the VM, `.\phewas` failed: the `Z:` project share does not allow `.bat` files to run ("Access is denied", 2026-10-06). Python scripts run there.

**Decision.** The launcher is `phewas`, a Python file with no extension beside `run_phewas.py`, so a command is `python phewas check` (or `python phewas --check`); everything else in D36 stands. `phewas.bat` is gone.

### D38. Every step ends in a one-sheet

**Context.** The matching log was long and hard to read off the VM (2026-10-07). The user asked that every step give, in at most a page, what is needed to judge it and move on, to copy into the chat.

**Decision.** `python phewas sheet` writes `runs/sheet.txt`: the groups (size, eligible, why not), the match (largest standardized mean difference and any over 0.1, unmatched cases and their quarters, controls per case), each PheWAS run (inputs, phecodes tested and significant, the top eight with OR, interval, q and cases, and whether pyPheWAS and the Phecode 1.2 bridge agree), and the next command. `match`, `pre` and `post` print it when they finish. `python phewas balance` gives the match alone with every variable's standardized mean difference, computed as MatchIt's `summary()` does.

### D39. A presentation narrative, kept beside the plan documents

**Amends D27.**

**Context.** The user presents the study to others and needs it told in one place: each phase's code, why each choice was made, and how to read the results (2026-10-07).

**Decision.** `reference/phewasHistoryAndDecisions.md` restates the study for that purpose, pointing to D numbers. It is updated after each phase's results are discussed. The plan documents stay the source of truth; where the two differ, the narrative is corrected.

### D40. The post-index PheWAS adjusts for follow-up after index

**Context.** After matching (2026-10-07), every standardized mean difference was under 0.1 except `YearsAfterIndex`, at 0.102: HaT patients have slightly more follow-up after index. Diagnoses before index cannot depend on it; diagnoses after index can, since more follow-up is more chance to be coded.

**Decision.** Windows that count diagnoses after index (`post`, `all`) add `YearsAfterIndex` to the covariates, in pheauxWAS, the Phecode 1.2 bridge and pyPheWAS alike. The primary pre-index model is unchanged. The match is kept as is.

**Rejected.** Rematching with a tighter caliper: it would cost cases to fix one variable that only the sensitivity analysis needs.

### D41. The repository is organized by role

**Context.** The study's own pipeline lived in `tutorial/` beside the synthetic-data walkthrough, the plan documents and reports sat in `reference/` with source material, and bundles, sync scripts and the vendored pyPheWAS were spread across the root (2026-10-07). `tools/setup_env.py`, then in `syncing/`, looked for `requirements.txt` beside itself and so could not work.

**Decision.** Folders by role: `study/` (what runs on the VM, with `study/pulls/`), `tutorial/` (synthetic data only), `docs/` (`plan/`, the narrative, `reports/`), `reference/` (source material), `vendor/pyPheWAS-2a8fff1/`, `tools/`, `bundles/`; `pheauxWAS/`, `phecode/` and `Ilarias Work/` stay at the root. Script names are unchanged, and the VM's folder layout is unchanged (D35): the bundle still unpacks the scripts at the root of the pheauxWAS folder, and the runner finds pyPheWAS in `vendor/` or at the root, and its root as its own folder or its parent. Older entries keep their old paths; they map as follows:

| Was | Now |
|---|---|
| `tutorial/run_phewas.py`, `tutorial/phewas`, `tutorial/prepare_phewas_inputs.py`, `tutorial/matchit_example.R` | `study/` (same names) |
| `tutorial/adapting-cosmos/build_group_parquet.py`, its `README.md` | `study/build_group_parquet.py`, `study/README.md` |
| `tutorial/adapting-cosmos/ctrl_PheWAS*_intake.yaml`, `tutorial/pulling-cohorts/*` | `study/pulls/` |
| `reference/plan/`, `reference/phewasHistoryAndDecisions.md`, `reference/reports/` | `docs/plan/`, `docs/phewasHistoryAndDecisions.md`, `docs/reports/` |
| `pyPheWAS-2a8fff1/` | `vendor/pyPheWAS-2a8fff1/` |
| `bundling/make_bundle.py`, `syncing/*.py` | `tools/` |
| `bundling/phewas_vm_runner_bundle.py` | `bundles/` (rebuilt by `tools/build_vm_bundle.py`) |
| `readme.md` | `README.md` |

Removed: `bundling/phewas_vm_bundle.py` (the 2026-10-05 bundle, superseded and rebuildable from history) and `reference/plan/format_test_files/` (rendering leftovers from D22's format test).

**Consequences.** Nothing a study run computes changed: the synthetic pipeline from group building to both PheWAS windows gives the same outputs before and after the move. Paths in commands and documents changed; on the VM nothing does.

### D42. One D89.44 is a case: settled

**Settles D24** (no longer provisional; review question 10.1 answered by the user, 2026-10-08).

**Context.** D24 kept the single-code rule pending the attending. A D89.44 diagnosis requires a genetic test (*TPSAB1* copy number), so a single code stands for a tested patient.

**Decision.** D89.44 on at least one date defines a case in the primary analysis. Miscoding is possible but treated as negligible, and is stated as a limitation, not analysed around.

**Consequences.** The review report drops the question and says this in its case definition and limitations. Whether the 2+ date run is still wanted as a robustness check is open (roadmap).

### D43. The reviewers' checks are one command, `python phewas review`

**Context.** The 2026-10-08 review asked for checks that need the results and group files on the VM: whether the cases have high tryptase, utilization the match did not use, how far the whole phenome is shifted, the share of HaT patients with mast-cell neoplasm codes, prevalence in each group beside the ORs, and which ICD codes make up phecodes whose names mislead (hypermobility includes hEDS; "allergy to insects" includes unspecified allergy).

**Decision.** `python phewas review` prints them on one page (D38). pheauxWAS 1.2 writes, for a 0/1 predictor, each phecode's cases and totals in each group; the command reruns pheauxWAS on each finished run's own inputs into `runs/review/` to get them, and checks the rerun gives the same betas. Counts of 1–10 are shown as `<11`. The ten negative-control phecodes (cataract, cerumen, myopia, presbyopia, appendicitis, seborrheic and actinic keratosis, lipoma, kidney stones, dental caries) are a proposal for discussion, chosen as having no known link to HaT, mast cells or hypermobility.

**Rejected, for now.** Specialist (allergy/immunology) visits as a covariate: the encounter files' specialty column is in the pull folders, not the pheauxWAS folder; ED visits and admissions, already in the group files, show unmatched utilization first.

### D44. The HaT cluster is chosen by a stated rule, `python phewas cluster`

**Context.** The report's leading associations (§6.3) came from each window's top 20 by p, which favours common diagnoses and leaves out strong but rarer ones; the user asked for the full set (2026-10-08).

**Decision.** A phecode is in the cluster when it has FDR < 0.05 in both the pre and post windows and an OR of at least twice that window's median OR over all tested phecodes (the background shift), and is not in an exposure-adjacent family (GE_969, BI_180, SS_823, CA_120, CA_125). Children are listed under their nearest parent in the cluster, by pheauxWAS's rollup; families are ordered by their strongest member's smaller OR. `python phewas cluster` prints the first 40 lines and the phecodes lower in HaT in both windows on one page, and writes the full list to `runs/cluster/cluster.csv`. It reports §6.3.1 of the review report.

**Rejected.** Ranking by p (as §6.3 does): it measures certainty, not strength. A fixed OR cut-off: the background shift differs by window, so the cut-off is set relative to it.

### D45. phecodeX's sex file is part of every run; one command runs the study

**Context.** The 2026-10-08 run log showed the study's PheWAS ran without sex restriction: the runner passed only `phecodeX_info.csv`, which has no sex columns, and phecodeX keeps sex-specificity in a separate file (`phecodeX_R_sex.csv`, 320 male- or female-only phecodes) that its own R workflow passes as `sex.restriction`. pheauxWAS read nothing and said nothing. The same log's "no exclusion criteria" warning is expected: phecodeX defines no exclusion ranges, and its workflow uses none.

**Decision.** The runner passes the sex file as a second `--definitions` everywhere it runs phecodeX, and stops if it is missing. After each run it checks the outcome: every sex-specific phecode in the results must carry its restriction (`sex restriction: applied …` in the run log), or the run is marked failed. `python phewas selftest` checks the wiring on a made-up cohort (a female-only phecode coded in both sexes must be analysed in women only, and the check must catch it without the sex file). The bundle carries the sex file to `phecode/` on the VM. `python phewas all` runs the self-test, moves the last run's outputs (not the matching) to `runs/archive/run_<when it started>/`, runs pre, post, review and cluster, and writes every page to `runs/all_results.txt` as well as each step's own files.

**Consequences.** The 2026-10-07 results, with sex-specific phecodes analysed in both sexes, are kept in `runs/archive/` on the VM; the report is updated from the rerun. The tutorial's synthetic data has no sex-specific codes, so its results are unchanged; its command now passes the sex file too.

### D46. Reports: one folder per study run, Quarto sources, one Word template

**Context.** The 2026-10-07 report was revised in place after the rerun (D45), and the user rewrote it as Quarto (`.qmd`) to send as PDF and Word, with a concise version (2026-10-08). The PDF needed a font with "≥" and "↳" (the default drops them silently) and compact title spacing; Word needed compact table-of-contents and table styles.

**Decision.** `docs/reports/` holds one folder per study run, `run<N>_<date>/`, with that run's reports and their rendered PDF and Word files: `run1_2026-10-07/` (the first run's report, restored from git, superseded) and `run2_2026-10-08/` (the full and concise reports sent to the reviewers). Reports are `.qmd`; the PDF block uses Arial with "≥" and "↳" taken from Arial Unicode MS, 1-inch margins and a compact title; Word uses `docs/reports/report-reference.docx` (compact TOC 1–3, smaller title, 9-pt table text). Wide tables set their widths with `tbl-colwidths`, which visual editors keep (they rewrite dash widths). This amends CLAUDE.md's "a newer report gets a new file": a new run's reports get a new folder.

**Amended (2026-10-09):** the PDF settings moved to `docs/reports/pdf-header.tex`, the same file as the research template's: Arial where installed, else Latin Modern Sans; symbols from Latin Modern Math, which ships with TeX, so the reports render on macOS, Windows and Linux; and `\tracinglostchars=3`, so a character no font has stops the render instead of vanishing. Arial Unicode MS (macOS only) is no longer used.

### D47. p-values for every cited phecode, from the results already computed

**Context.** The reviewers asked for p-values for everything (2026-10-09). pheauxWAS computes p and q for every tested phecode and writes them to each run's results file, but the reports printed only ORs and CIs (and q for each window's top 20).

**Decision.** `python phewas pvalues` prints, from the existing results, p and q in both windows for every phecode the reports cite, with Bonferroni marked, and writes every tested phecode's OR, CI, p and q to `runs/pvalues/all_phecodes_p_q.csv`. No model is refitted. The reports' tables gain p (and q) columns from its pages.

**Rejected.** Rerunning the PheWAS to report p: the values exist; a rerun would only reproduce them.

**Amended (2026-10-09):** one command, one file: `python phewas pvalues` writes every row to `runs/pvalues/pvalues.txt`.

------------------------------------------------------------------------

## The Cosmos Pull



### D14. One window for everyone: 2018-01-01 to 2026-06-01

**Decision.** `min_date_key = 20180101`, `max_date_key = 20260601` (the latest Cosmos has; moved when Cosmos is refreshed). Cases and controls share the floor: a longer lookback for either would give it more chances to collect diagnoses.

**Consequences.** Nobody's first encounter can be earlier than 2018, so `YearsBeforeIndex` is capped: equal for cases and controls, but not anyone's true record length.

**Superseded by D23** for the pull: profile queries found D89.44 from 2018.

### D15. ICD-10-CM only

**Decision.** `dt.Type = 'ICD-10-CM'`, the spelling Cosmos uses (profile query 6, 2026-10-01; ICD-9 is `'ICD-9-CM'`).

**Rejected.** ICD-9-CM: the window starts after the 2015 switch to ICD-10. ICD-10-AM, -CA and -GM: the phecodeX map in this repo covers ICD-10-CM and ICD-9-CM only, so those codes would not map to phecodes, and D89.44 is a CM code.

### D16. Patient-level fields for the pool; diagnosis history for the matched only

**Decision.** The \~50× candidate pool needs one row per patient (demographics, index, first and last encounter, clinic-visit counts) for MatchIt. The full diagnosis history is pulled only for the \~30k matched patients.

**Consequences.** About 276k candidates never have their diagnoses pulled.

**Superseded by D30:** the control pull is one stage.

### D17. Diagnoses are pulled one row per diagnosis event

**Context.** The first intake kept one row per patient, code and date. When several rows share a day, only one survived, and its `Type` and `Status` with it, so a later filter (dropping ruled-out diagnoses) could lose a date that also had a billed diagnosis.

**Decision.** `hat_Diagnoses` dedups on `[DiagnosisEventKey, DiagnosisCode]`: one row per event and code. Python filters, then collapses to patient + code + date.

**Cost.** A bigger table, manageable at \~30k patients (D16).

### D23. Pull all history; set the analysis window in Python

**Supersedes D14 for the pull.**

**Context.** Profile queries (2026-10-01) found D89.44 from April 2018, not late 2021 as assumed, and query 1 had only searched from 2018. With a 2018 floor, a patient whose first D89.44 is earlier gets the wrong index, and cases indexed in 2018–2020 have no 3 years of history for the lookback (D12).

**Decision.** `min_date_key = 19900101`, `max_date_key = 20260601`. The pull finds each patient's true first D89.44 and keeps all their history; the 3-year lookback (D12) is applied in Python, the same for cases and controls.

**Consequences.** `YearsBeforeIndex` is now true record length, not capped. The pull is bigger, which is cheap at ~6,000 HaT patients; for controls, history is pulled for the matched only (D16).

**Amended by D28:** the pull as run starts at 2015-01-01.

### D18. The pull is a Telescope intake built from dictionary tables

**Decision.** `reference/HaT_PheWAS_intake.yaml`, project "HaT PheWAS", builds its tables from Cosmos dictionary tables directly, not from Telescope recipes (D3). HaT tables are named `hat_`, control tables will be `ctrl_`, with the same columns.

### D28. The hat_ pull as run: every column, tryptase labs, from 2015

**Amends D18 and D23.**

**Context.** The user widened the intake in Telescope before running it on the VM (2026-10-02); the blueprint as run is `reference/hat_cosmos_blueprint.yaml`, with notes in `reference/plan/Future discussions/HaT Considerations.md`.

**Decision.** Every table takes every column its Cosmos tables offer, culled in Python. `hat_Labs` adds every tryptase result (eight LabComponentKeys, every LabComponentResultFact and LabComponentDim column), to validate cases and later screen controls. `hat_Encounters` LEFT JOINs DepartmentDim for specialty. The window starts at 2015-01-01, not 1990: three years before the earliest index seen in 2018, and the ICD-10 era.

**Consequences.** A patient whose first D89.44 is before 2015 gets a later index from this pull; profile query 7 counts them (some first dates are in 2017 and earlier). The `ctrl_` pull takes the same columns.

### D29. Each group is two parquets: patients and diagnoses

**Decision.** `tutorial/adapting-cosmos/build_group_parquet.py` turns a pull's parquets into `<group>_group.parquet` (one row per patient: everything matching needs) and `<group>_group_diagnoses.parquet` (one row per patient, ICD-10-CM code and date). The groups are `hat` and `control`.

**Rejected.** One file with each patient's diagnoses as a list inside their row: one file, but harder to read and to reason about.

### D30. The control pull is one stage, a random pool of 300,000

**Supersedes D16; amends D6.**

**Context.** Telescope can cap a PK inside Cosmos only with `smallset`, `stop_at_for_pk_table` and `random_pk_sample` (a reproducible sample ordered by a hash of the key, Telescope's D60). Its control sampling (`row_mult`, Telescope's D59) balances per batch but samples after the whole population lands in Projects, which cannot work for Cosmos's hundreds of millions of patients. Cases begin in earnest in 2021 Q4 (244 that quarter, against 19 the quarter before) and reach 486 in a quarter.

**Decision.** One pull, shaped like the `hat_` pull: `ctrl_Patients` is the PK and `ctrl_Encounters`, `ctrl_Diagnoses` and `ctrl_Labs` are fact tables with the same columns. The PK is one random clinic visit (D31) per patient, from 2021-10-01 to 2026-06-01, for patients not in `hat_Patients` (uploaded keys, `NOT IN`). A hash of the patient key first thins Cosmos to about 1% of patients, so the dedup and the hash-ordered `TOP` run on millions of rows, not billions; `stop_at_for_pk_table` then caps the pool at 300,000 (about 50 per case). MatchIt's exact quarter does the balancing (D7).

**Consequences.** Every table is pulled for 300,000 patients, most of whom MatchIt discards: a long pull, chunked like the `hat_` one. Quarters are not balanced in SQL, so the busiest (486 cases) relies on the pool's size. Patients whose only D89.44 is before 2015 are not in the uploaded keys; the builder drops any control with a D89.44.

------------------------------------------------------------------------

## The Tutorial

### D19. Synthetic data uses the real HaT code and events on both sides of index

**Decision.** The generator gives cases the real D89.44 (not a made-up code), so the exposure-code problem (D11) shows up in the tutorial as it would in real data, and it writes events before and after index, with a larger post-index enrichment, so the windows (D12) visibly differ.

**Amended (2026-10-03):** the generator is now `make_synthetic_cosmos_parquets.py`, writing pulls shaped like the real ones (D29); the patterns stand.

### D20. The greedy example match is labelled as such

**Decision.** `example_4to1_*` files come from a simple greedy match in the generator, kept to show a matched-pairs file's shape. The tutorial's match is MatchIt's, `matchit_4to1_matched.parquet`.

**Superseded (2026-10-03):** the greedy example went with the old generator; the tutorial's only match is MatchIt's.
