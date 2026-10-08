# HaT PheWAS: History, Decisions and Results

*As of 2026-10-07: cohorts built, matched, and the pre- and post-index PheWAS run. Sensitivity analyses not yet run.*

This document explains the HaT PheWAS from start to finish so it can be presented: what was done at each phase, which code did it, why each choice was made, and how to read the results so far. "D" numbers (D24, D30, …) point to the full entries in `docs/plan/decisions.md`; the plan documents remain the source of truth, and this document is updated after each phase.

------------------------------------------------------------------------

## 1. The Question

Which diagnoses, across the whole phenome, are more or less common in patients with **hereditary alpha tryptasemia (HaT)** than in similar patients without known HaT?

A PheWAS (phenome-wide association study) tests every diagnosis group (a *phecode*) one at a time, so it is a discovery tool: it finds associations among comparable patients, not causes. Everything below is designed to make "comparable" true, so that a difference in a diagnosis reflects HaT and not, for example, one group simply seeing doctors more often.

## 2. The Pipeline at a Glance

| Phase | What happens | Code | Output |
|------------------|------------------|------------------|------------------|
| 1\. HaT cohort | Pull every patient with a HaT diagnosis from Epic Cosmos | Telescope intake (`HaT_PheWAS_intake.yaml`), run on the VM | `hat_Patients`, `hat_Encounters`, `hat_Diagnoses`, `hat_Labs` |
| 2\. Control pool | Pull a random pool of 300,000 patients without HaT | Telescope intake (`ctrl_PheWAS_intake.yaml`) | `ctrl_` tables, same shape |
| 3\. Group files | Turn each pull into one row per patient, plus a clean diagnosis list | `build_group_parquet.py` | `hat_group.parquet`, `control_group.parquet` (+ `_diagnoses`) |
| 4\. Matching | Choose up to 10 similar controls per HaT patient | `python phewas match` → `matchit_example.R` (R package MatchIt) | `runs/matching/matched_cohort.parquet` |
| 5\. PheWAS | Test every phecode: HaT vs matched controls | `python phewas pre` / `post` → `prepare_phewas_inputs.py`, `pheauxWAS.py`, pyPheWAS | `runs/pre_3y/`, `runs/post/` |

Patient data never leaves the VM; all code is developed and tested on synthetic data shaped exactly like the real pulls. In the repository the pulls are in `study/pulls/` and every script above is in `study/` (`pheauxWAS.py` in `pheauxWAS/`); on the VM they sit in the pheauxWAS folder.

------------------------------------------------------------------------

## 3. Phase 1: The HaT Cohort

### Who is a case, and when their "clock" starts

| Rule | Choice | Why |
|------------------------|------------------------|------------------------|
| Case definition | D89.44 (the ICD-10-CM code for HaT) on **at least one date** (D24) | HaT is diagnosed by genetic testing, so one code is likely reliable. The common PheWAS "2+ dates" rule guards against rule-out codes in common conditions. 2+ dates is kept as a sensitivity analysis. |
| Index date | The **first** D89.44 that is not a ruled-out or error entry (D4) | The point at which HaT is known. Diagnoses are then split into "before" and "after" this date. |
| Codes used | ICD-10-CM only (D15) | The phecode map covers ICD-10-CM, and D89.44 is a CM code. |
| History window | 2015-01-01 to 2026-06-01 (D28) | ICD-10 era, and 3 years before the earliest index seen (2018). |

D89.40–D89.49 (other mast-cell codes) do **not** define a case or the index: they are broader than HaT and would pull the index earlier for patients who were never HaT (D4).

### The variables, and why each one

| Variable | Definition | Why it is needed |
|------------------------|------------------------|------------------------|
| `AgeAtIndex` | Age at the index date | Age drives nearly every diagnosis. |
| `Sex` | Cosmos `ReliableSex`; its `Sex` when that is Ambiguous (D25) | Sex-specific diagnoses; exact matching needs Male or Female. |
| `Race`, `Ethnicity` | Unknown, blank and refused values grouped as `Unknown`, not dropped (D10) | Dropping unknowns can remove cases and controls unevenly. |
| `ClinicVisits365Before` | Days with a completed Office Visit or Follow-Up in the 365 days before index (D8, D26, D31) | **Utilization.** Patients who see doctors more collect more diagnoses; HaT patients are often heavily worked up. Without this, almost everything would look "associated with HaT". |
| `YearsBeforeIndex`, `YearsAfterIndex` | Years from the first completed encounter to index, and from index to the last (capped at death and data end) | How much record each patient has on each side of index. |
| Diagnoses | Every ICD-10-CM diagnosis event, ruled-out and error statuses removed, one row per patient, code and date (D17) | The outcomes the PheWAS tests. |
| Tryptase labs | Baseline serum tryptase results | To describe and validate the cases (not used in matching). |

**Deliberately not used:** the number of diagnoses or problem-list entries before index (D9). In a pre-index PheWAS those diagnoses *are* the outcomes; matching on their count would cancel part of the difference being measured.

### What the code does (`build_group_parquet.py`)

1.  `read()` / `read_diagnoses()`: read only the needed columns; diagnoses are read in chunks of a few million rows (the control file has 92 million).
2.  Drop diagnoses whose status contains "rule", "error", "delete" or "cancel"; collapse to one row per patient, code and date.
3.  Index: the first surviving D89.44 (cases). Age is shifted by the years the index moved, if the status filter moved it.
4.  Demographics as in the table above.
5.  Observation time from completed encounters; `count_days()` counts clinic-visit days in \[index − 365, index), so **the index day itself is not counted**.
6.  Earlier mast-cell codes and tryptase are recorded for describing the cases.
7.  **Eligible for matching** if: ≥ 2 clinic-visit days in the year before index (D8), a usable sex, and (cases) an index on or after 2021-10-01, when the control pool begins (D30).

### Result

|   | HaT |
|----|----|
| Patients with any D89.44 | **5,969** |
| Eligible for matching | **4,144** (69%) |
| Not eligible: under 2 clinic visits in the prior year | 1,753 |
| Not eligible: index before 2021-10-01 | 119 |
| Not eligible: no usable sex | \<11 (masked: Cosmos small-cell rule) |

(Reasons overlap, so they sum to more than the 1,825 not eligible.)

**How to read it.** The large loss is the utilization rule: 29% of HaT patients had fewer than 2 clinic visits in the year before their HaT diagnosis. This rule is applied identically to controls; it ensures both groups were similarly "observable" before index, at the cost of excluding low-utilization patients. That should be stated when presenting, because it shapes who the results describe: HaT patients who were engaged in care before diagnosis. The 119 indexed before October 2021 cannot be matched by calendar quarter, because the control pool starts then. Their first D89.44 predates the code's introduction in October 2021, so it was likely mapped onto older records after the fact (task list, "Three choices", item 1, awaiting confirmation).

------------------------------------------------------------------------

## 4. Phase 2: The Control Pool

### The logic

A control is a patient with **no D89.44 on any date** (D5): "no known HaT", not proven non-HaT, since HaT is under-tested.

Controls have no diagnosis to anchor an index on, so each gets a **pseudo-index**: one randomly chosen completed clinic visit (Office Visit or Follow-Up) between 2021-10-01 and 2026-06-01 (D6, D30, D31). Their age, prior visits and "before/after" windows are all measured from that date, exactly as for cases.

| Choice | Why |
|------------------------------------|------------------------------------|
| Anchor on a random clinic visit | Controls should resemble cases in their *chance to be observed*, not in their diagnoses. |
| *Rejected:* controls chosen for a new diagnosis, or for nearby (GI, immune) diagnoses (D6) | That selects on outcomes and biases every comparison. |
| Pool of 300,000 (\~50 per case) | Enough to find 10 close matches per case even in the busiest quarters (up to 486 cases in one quarter). |
| Random, reproducible sample | A hash of the patient key keeps \~1% of Cosmos, then the first 300,000 in hash order (D30). |
| HaT patients excluded | Their keys were uploaded and excluded in SQL; the builder also drops any control found to have a D89.44. |
| Same tables and columns as the HaT pull | Both groups go through identical code. |

### Result

Pull (2026-10-06, about 4 hours): 300,000 patients, 29,822,443 encounters, 92,143,391 diagnosis rows, 948 tryptase results.

|                                                       | Controls          |
|-----------------------------------------------------|-------------------|
| Patients                                              | **300,000**       |
| Eligible for matching                                 | **127,223** (42%) |
| Not eligible: under 2 clinic visits in the prior year | 172,748           |
| Not eligible: no usable sex                           | 110               |

**How to read it.** Most random clinic visits belong to people who rarely visit, so 58% of the pool fails the same utilization rule applied to cases. That is expected and harmless: 127,223 eligible controls is still about 31 per eligible case.

------------------------------------------------------------------------

## 5. How MatchIt Works (in brief)

MatchIt (an R package) picks, for each case, controls who look like it on chosen characteristics.

1.  **Propensity score.** A logistic regression predicts "is this patient a case?" from the matching variables. Each patient's predicted probability is their propensity score: one number summarizing how case-like they are.
2.  **Nearest neighbour.** Each case is paired with the controls whose scores are closest.
3.  **Exact variables.** Some variables must match exactly (a control must share the case's value).
4.  **Caliper.** A control further than a set distance from the case's score is never used, even if that leaves the case with fewer controls.
5.  **Ratio and replacement.** Up to *k* controls per case; without replacement, each control is used once.
6.  **Output.** The matched patients, a `subclass` (which matched set each belongs to) and a `weight` (controls in sets with fewer controls weigh more, so each set counts equally).

The test of success is **balance**: after matching, the two groups' averages should be close on every variable. It is measured by the **standardized mean difference (SMD)**: the difference in means divided by the cases' standard deviation. An SMD under 0.1 is the conventional threshold for negligible imbalance.

------------------------------------------------------------------------

## 6. The Matching We Used, and Why

``` r
matchit(HaT_Flag ~ AgeAtIndex + YearsBeforeIndex + YearsAfterIndex +
          log1p(ClinicVisits365Before) + Race + Ethnicity,
        data = eligible patients of both groups,
        method = "nearest", distance = "glm",
        exact = ~ Sex + IndexQuarter,
        ratio = 10, replace = FALSE, caliper = 0.2, std.caliper = TRUE)
```

| Element | Choice | Reason |
|------------------------|------------------------|------------------------|
| Who is matched | Only patients with `EligibleForMatching = 1` | Same entry rules for both groups (Phase 1, step 7). |
| Propensity variables | Age; years of record before and after index; clinic visits; race; ethnicity | The main drivers of how many diagnoses a patient accumulates, other than HaT itself. |
| `log1p(ClinicVisits365Before)` | log(1 + visits) | Visit counts are highly skewed; the log stops a few very heavy users from dominating the score. |
| Exact on `Sex` | Same sex | Many phecodes are sex-specific; sex is too important to leave to the score. |
| Exact on `IndexQuarter` | Same calendar quarter (e.g. 2024Q2) | Coding practice, Cosmos coverage and the COVID period change over time; a control's index must come from the same period as the case's. |
| `ratio = 10` (D32) | Up to 10 controls per case | More controls give more power for rare phecodes. Gains shrink after the first few controls, but the pool is large enough that 10 costs nothing in quality: the caliper still rejects poor matches. |
| `replace = FALSE` | Each control used once | Keeps patients independent in the later regression. |
| `caliper = 0.2, std.caliper = TRUE` | No control further than 0.2 standard deviations of the propensity score from its case | Prevents poor matches; the price is that some cases get fewer than 10 controls, or none. |
| Not matched on | Diagnosis counts (D9) | They are the outcomes (see Phase 1). |

**What runs.** `python phewas match` (in `run_phewas.py`) finds Rscript and runs `matchit_example.R` with the two group files. The R script binds the groups (`bind_rows`), keeps the eligible (`filter(EligibleForMatching == 1)`), turns Sex, Race, Ethnicity and IndexQuarter into factors, calls `matchit()`, prints `summary(match)` to `matching_log.txt`, writes `match.data(match)` to `matched_cohort.parquet`, and draws the balance plot with `cobalt::love.plot()`. `python phewas balance` and `sheet` recompute the SMDs exactly as MatchIt's `summary()` does (checked against it), and summarize unmatched cases and controls per case.

**How the match is judged** (the rules behind "good", "borderline" or "bad"):

| Check | Good | Why this threshold |
|------------------------|------------------------|------------------------|
| SMD of every variable | under 0.1 | The conventional threshold for negligible imbalance in matched studies. |
| Unmatched cases | under about 10%, and not concentrated in one kind of patient | A working rule for this study, not a published standard: more loss starts to change who the cases represent. |
| Controls per case | reported; no fixed threshold | Fewer controls means less power, not bias. |

------------------------------------------------------------------------

## 7. Matching Results

|                             | Controls   | Cases (HaT) |
|-----------------------------|------------|-------------|
| Eligible (entered matching) | 127,223    | 4,144       |
| Matched                     | **28,670** | **3,911**   |
| Unmatched                   | 98,553     | 233         |
| Effective sample size (ESS) | 16,401.65  | 3,911       |

### Balance: good, with one borderline variable

Every variable's SMD is under 0.1 except **YearsAfterIndex, at 0.102**. Sex and index quarter are matched exactly (SMD 0).

**What 0.102 means.** HaT patients have slightly longer follow-up after index than their controls, by about a tenth of a standard deviation. It is just over the threshold, and its effect depends on the window:

- **Pre-index PheWAS (primary, 3 years before index):** no effect. Those diagnoses all come before index, so follow-up after index cannot add to them.
- **Post-index PheWAS (sensitivity):** relevant. More follow-up means more chances to record diagnoses after index, which would push odds ratios up for HaT. **Decided (D40):** the post-index regression adds `YearsAfterIndex` as a covariate; the match is kept, since rematching would cost cases to fix a variable only the sensitivity analysis needs.

### Unmatched cases: acceptable

233 of 4,144 eligible cases (5.6%) found no control inside the caliper with the same sex and quarter. They cluster in the busiest quarters (2025Q2: 50, 2024Q2: 43, 2023Q4: 25), where many cases compete for the same nearby controls and each control can be used only once. The loss is small and comes from crowding, not from one type of patient being unmatchable.

### Controls per case: as expected

| Controls | 10    | 9   | 8   | 7   | 6   | 5   | 4   | 3   | 2   | 1   |
|----------|-------|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| Cases    | 2,210 | 62  | 128 | 108 | 110 | 183 | 266 | 247 | 255 | 342 |

Mean 7.3 controls per matched case; 57% of cases got all 10. Cases with fewer controls are those whose nearby controls ran out (same reason as above).

**Effective sample size (16,402 of 28,670 controls).** MatchIt's weights give controls in small sets more weight, so each case's set counts equally. ESS is the number of equally weighted controls that would carry the same information; it is lower than the raw count because the weights are uneven. **Note for the analysis:** the PheWAS regression is ordinary covariate-adjusted logistic regression on the matched cohort and does not use these weights or the matched sets (D13). Sets with 10 controls therefore contribute more control information than sets with 1, and the covariates in the regression handle residual differences. Conditional logistic regression within matched sets is the stricter alternative, noted as a limitation.

### "Std. Pair Dist." in the MatchIt log

The log also reports, per variable, the average difference *within* matched sets (e.g. AgeAtIndex 1.25). Propensity matching balances the groups' averages, not each individual pair, so individual cases and their controls can still differ in age. Group balance (the SMD) is what matters for comparing groups, and the regression adjusts for age, sex, race, ethnicity, record length and visits on top.

### Verdict

The match is **good enough to proceed**: the primary pre-index PheWAS as specified, the post-index one with `YearsAfterIndex` added (D40).

### Patient flow so far

``` text
HaT:      5,969 with D89.44 ──► 4,144 eligible ──► 3,911 matched   (233 unmatched)
Controls: 300,000 pool     ──► 127,223 eligible ──► 28,670 matched
```

------------------------------------------------------------------------

## 8. Phase 5: The PheWAS

### What runs

`python phewas pre`, then `python phewas post` (each prints its one-page sheet; `python phewas results pre|post` reprints it):

1.  `prepare_phewas_inputs.py`: keeps the matched patients' diagnoses; **removes D89.44** (otherwise every case "has HaT" and it tops the list: on synthetic data, OR ≈ 100,000, D11); keeps one window: **pre** = the 3 years before index (primary, D12), **post** = after index to the end of observation (sensitivity). The index day is in neither, because codes entered on the diagnosis day are usually part of the HaT workup.
2.  `pheauxWAS.py` (the study's PheWAS, v1.1.1), for each phecode:
    - maps ICD-10-CM codes to phecodeX, rolling child phecodes up to their parents;
    - a patient is a **phecode case** with the code on **2+ distinct dates**; patients with it on 1 date are excluded from that phecode (phecodeX defines no related-phecode exclusions); sex-specific phecodes use one sex only, from phecodeX's sex file (D45);
    - phecodes with fewer than **20 cases** are skipped;
    - fits `phecode ~ HaT_Flag + AgeAtIndex + Sex + Race + Ethnicity + YearsBeforeIndex + ClinicVisits365Before`, plus `YearsAfterIndex` in the post window (D40), by logistic regression, switching to **Firth** regression when *separation* is detected: a variable that predicts the phecode perfectly, where ordinary estimates break down. Since v1.1.1 this includes a phecode whose cases are all HaT patients, as expected for the mast-cell phecode (BI_180.6);
    - corrects for testing many phecodes with **Bonferroni** (0.05 ÷ phecodes tested) and **Benjamini–Hochberg FDR** (q-values). Results are read by q-value, not raw p.
3.  **Cross-check** (D34): pyPheWAS, a published tool, runs on the same events with its own rules and older phecode system; pheauxWAS is also run with pyPheWAS's rules and map, and the two are compared phecode by phecode. Agreement there checks the code. The study's result is the pheauxWAS phecodeX run.

### Results at a glance

From the rerun of 2026-10-08. The first run (2026-10-07) had analysed phecodeX's 320 sex-specific phecodes in both sexes, because the sex file was never passed to pheauxWAS (D45). Fixing it changed little: about 85 fewer phecodes in each window needed Firth regression (the missing male cases of a female-only phecode had looked like separation), a few significance counts moved by single figures, and the leading odds ratios are unchanged.

|   | Pre (3 years before index; primary) | Post (after index; sensitivity) |
|------------------------|------------------------|------------------------|
| People | 32,581 (3,911 HaT, 28,670 controls) | same |
| Diagnoses in window (patient-code-date) | 4,640,043 | 2,985,445 |
| D89.44 rows removed (both windows' source) | 16,969 | 16,969 |
| Phecodes tested (≥ 20 cases) | 1,817 | 1,611 |
| Bonferroni-significant (higher / lower in HaT) | 482 (470 / 12) | 514 (513 / 1) |
| FDR \< 0.05 (higher / lower) | 858 (786 / 72) | 865 (845 / 20) |
| Fitted with Firth (of which FDR \< 0.05) | 387 (96) | 390 (117) |
| Cross-check: phecodes compared, same direction | 978, 978 | 933, 933 |
| Cross-check: correlation of betas, excluding separated phecodes (n) | 0.999 (26 excluded) | 0.999 (32 excluded) |

"Cases" in the tables below are phecode cases in the matched cohort (HaT and controls together). ORs are adjusted; q \< 1e-300 means the value underflowed, not that it is zero.

### Pre-index (primary): top 20 by p

| Phecode | Description | OR \[95% CI\] | q | Cases |
|---------------|---------------|---------------|---------------|---------------|
| BI_180 | Other disorders involving the immune mechanism | 40.9 \[35.0–47.9\] | \<1e-300 | 1,068 |
| CA_120 | Hemo onc, by cell of origin | 14.7 \[12.9–16.6\] | \<1e-300 | 1,244 |
| CA_120.1 | Myeloid | 29.3 \[25.1–34.2\] | \<1e-300 | 929 |
| DE_666 | Urticaria | 47.5 \[40.5–55.6\] | \<1e-300 | 1,103 |
| DE_679 | Skin symptoms | 6.86 \[6.25–7.52\] | \<1e-300 | 2,654 |
| SS_823 | Abnormal serum enzyme levels | 19.1 \[17.4–21.0\] | \<1e-300 | 2,496 |
| SS_823.2 | Abnormal levels of other serum enzymes (R74.8) | 27.2 \[24.5–30.2\] | \<1e-300 | 2,099 |
| SS_840 | Allergy | 7.95 \[7.33–8.63\] | \<1e-300 | 6,803 |
| SS_840.2 | Allergy to insects | 13.1 \[11.4–15.2\] | 7.8e-269 | 849 |
| NS_343 | Disorders of autonomic nervous system | 22.2 \[18.6–26.5\] | 8.5e-256 | 667 |
| SS_840.1 | Food allergy | 13.0 \[11.2–15.1\] | 4.1e-249 | 798 |
| MS_712 | Joint derangements and related disorders | 8.50 \[7.43–9.73\] | 2.9e-209 | 950 |
| SS_840.8 | Allergies related to other diseases/symptoms | 3.98 \[3.64–4.35\] | 1.3e-201 | 3,291 |
| RE_463 | Rhinitis and nasal congestion | 3.59 \[3.31–3.90\] | 5.9e-201 | 4,541 |
| MS_712.5 | Disorder of ligament | 29.0 \[23.3–36.1\] | 8.7e-197 | 493 |
| MS_712.51 | Hypermobility syndrome | 32.8 \[26.1–41.4\] | 1.6e-190 | 473 |
| SS_840.9 | Anaphylactic reaction | 61.2 \[46.5–80.5\] | 1.7e-188 | 478 |
| NS_343.7 | Postural orthostatic tachycardia syndrome | 30.4 \[24.2–38.1\] | 2.7e-187 | 466 |
| CA_125 | Other malignant neoplasms of lymphoid, hematopoietic and related tissue | 234 \[159–345\] | 1.1e-165 | 682 |
| DE_679.3 | Flushing | 13.2 \[11.0–15.9\] | 4.3e-162 | 504 |

Lower in HaT (FDR \< 0.05), top 5: current tobacco use 0.584 \[0.505–0.677\]; fractures 0.663 \[0.578–0.761\]; secondary malignant neoplasm 0.29 \[0.185–0.457\]; nicotine dependence 0.776 \[0.703–0.857\]; hypertension 0.799 \[0.730–0.874\].

### Post-index (sensitivity): top 20 by p

| Phecode | Description | OR \[95% CI\] | q | Cases |
|---------------|---------------|---------------|---------------|---------------|
| BI_180 | Other disorders involving the immune mechanism | 61.1 \[50.9–73.5\] | \<1e-300 | 1,007 |
| DE_666 | Urticaria | 55.1 \[45.6–66.7\] | \<1e-300 | 884 |
| SS_823 | Abnormal serum enzyme levels | 11.2 \[10.0–12.6\] | \<1e-300 | 1,483 |
| SS_823.2 | Abnormal levels of other serum enzymes (R74.8) | 16.3 \[14.3–18.5\] | \<1e-300 | 1,186 |
| SS_840 | Allergy | 6.43 \[5.90–7.02\] | \<1e-300 | 4,215 |
| CA_120.1 | Myeloid | 23.2 \[19.6–27.4\] | 6.6e-297 | 759 |
| CA_120 | Hemo onc, by cell of origin | 11.8 \[10.3–13.5\] | 4.6e-282 | 1,032 |
| NS_343 | Disorders of autonomic nervous system | 24.3 \[20.1–29.2\] | 1.7e-245 | 644 |
| MS_712 | Joint derangements and related disorders | 13.3 \[11.4–15.5\] | 5.4e-236 | 783 |
| MS_712.5 | Disorder of ligament | 38.7 \[30.4–49.4\] | 5e-188 | 484 |
| NS_343.7 | Postural orthostatic tachycardia syndrome | 36.4 \[28.6–46.4\] | 1.2e-184 | 471 |
| MS_712.51 | Hypermobility syndrome | 39.9 \[31.2–51.2\] | 8.2e-184 | 474 |
| DE_679 | Skin symptoms | 5.11 \[4.55–5.75\] | 8.9e-161 | 1,503 |
| RE_463 | Rhinitis and nasal congestion | 3.85 \[3.49–4.25\] | 1.3e-156 | 2,692 |
| RE_475 | Asthma | 3.59 \[3.26–3.94\] | 4.2e-154 | 2,802 |
| SS_840.9 | Anaphylactic reaction | 44.6 \[33.5–59.3\] | 7.8e-148 | 384 |
| GE_978 | Genetic disorders relating to growth and musculoskeletal system | 38.4 \[29.1–50.8\] | 5.7e-143 | 379 |
| SS_840.1 | Food allergy | 11.8 \[9.74–14.3\] | 9.7e-141 | 483 |
| SS_840.8 | Allergies related to other diseases/symptoms | 4.01 \[3.60–4.47\] | 5.2e-139 | 1,948 |
| GI_527 | Abdominal pain | 3.10 \[2.84–3.39\] | 2.4e-138 | 4,233 |

Lower in HaT (FDR \< 0.05), top 5: current tobacco use 0.575 \[0.478–0.691\]; secondary malignant neoplasm 0.409 \[0.268–0.626\]; psychoactive substance abuse 0.461 \[0.301–0.706\]; diabetes mellitus 0.821 \[0.733–0.919\]; alcohol abuse and dependence 0.472 \[0.302–0.737\].

### How to read the results

1.  **The calculations are verified.** Where pheauxWAS (run with pyPheWAS's map and rules) and pyPheWAS can be compared without separation, their estimates correlate at 0.999 in both windows, and every shared phecode agrees in direction. The overall correlations (0.744 pre, 0.783 post) are lower only because of 26–32 *separated* phecodes, where unpenalized logistic regression gives near-infinite estimates and pyPheWAS's L1 penalty shrinks them, by design.
2.  **Some top hits are the diagnosis itself, not findings (exposure-adjacent).** BI_180 and its child BI_180.6 (mast cell activation syndrome, D89.40–D89.49); SS_823 and SS_823.2 (R74.8, "abnormal levels of other serum enzymes", the usual code for a raised tryptase); CA_120.1, CA_120.15 and CA_125(.1) (mast-cell neoplasms and mastocytosis, C96.2x and D47.0x). These are the codes of the workup that leads to, or follows, a HaT diagnosis. They are reported separately and are the reason for the planned sensitivity analysis that drops all D89.4x codes.
3.  **The phenotype is consistent with the HaT literature.** Urticaria and flushing, anaphylaxis, insect and food allergy, dysautonomia and POTS, joint hypermobility and ligament disorders, rhinitis, asthma and abdominal pain: the multisystem picture reported for HaT, which gives the results face validity.
4.  **Pre-index means "what precedes diagnosis", not "what HaT causes".** HaT is diagnosed by testing, and patients are tested because of these symptoms. The large odds ratios (often 20–60) in the pre-index window largely reflect *why patients are tested* (indication), so they describe the phenotype that brings a patient to diagnosis.
5.  **The same phenotypes persist after diagnosis.** Most top phenotypes appear in both windows with similar or larger odds ratios after index (urticaria 47.5 → 55.1, POTS 30.4 → 36.4, hypermobility 32.8 → 39.9), so they are not only workup around the diagnosis. The shifts fit how diagnosis works: abnormal-tryptase codes fall after diagnosis (SS_823.2: 27.2 → 16.3, since testing precedes it) and mast-cell codes rise (BI_180: 40.9 → 61.1, as ongoing care codes them). New in the post-index top 20: GE_978, the parent of the Ehlers–Danlos codes (Q79.6x, GE_978.22), Marfan syndrome and skeletal dysplasias; with hypermobility this strong it is most plausibly Ehlers–Danlos, coded after genetic evaluation (to confirm from GE_978.22's own row).
6.  **Most hits are "higher in HaT".** 786 of 858 FDR hits pre-index (845 of 865 post) are more common in HaT. HaT patients carry more coded conditions overall even after matching on clinic visits: partly real phenotype, partly specialist workup that a one-year count of office visits does not capture.
7.  **"Lower in HaT" likely reflects population differences.** Tobacco, alcohol and substance use, diabetes and hypertension being less common in HaT patients probably reflects who they are (about three quarters female; likely a different socioeconomic profile) rather than protection. They should be reported with that caveat.
8.  **Many hits are not independent.** Phecodes roll up into their parents (e.g. SS_840 Allergy and its children), so parent and child hits count the same patients; the 482 and 858 overstate the number of distinct findings.

### The review checks and the full cluster (2026-10-08)

Discussed with the review report (`docs/reports/HaT_PheWAS_review_2026-10-07.md`, which has the tables); from `python phewas review` and `python phewas cluster` on the rerun.

- **How far everything is shifted.** The median odds ratio across all tested phecodes is 1.46 before index and 1.75 after; ten negative-control phecodes with no known link to HaT (cataract, cerumen, myopia and others) give 1.42 and 1.89. So HaT patients carry roughly 1.5 to 1.9 times the odds of almost any code, mostly from more contact with care: ED visits in the year before index (unmatched) 37% vs 30%, and clinic visits after index 6.45 vs 4.23 days a year. An odds ratio of 3 is therefore only about twice the background; urticaria (47), anaphylaxis (61), POTS (30) and Ehlers–Danlos (41) are twenty to forty times it.
- **Cases.** Only 18% have a serum tryptase on record (probably outside laboratories); of those, 92% are at or above 8 ng/mL (median 15.3), as expected for HaT. 64% have D89.44 on two or more dates.
- **The mastocytosis subgroup.** 30% of cases carry a mastocytosis code at some point, mostly D47.09 ("other mast cell neoplasms"); 9% carry systemic mastocytosis (D47.02). It does not explain the phenotype: cases without these codes still show it (anaphylaxis 15.1% vs 0.6% of controls, POTS 10.2% vs 0.5%), and the coded cases are higher on every phenotype, POTS and hypermobility included, so they look more thoroughly evaluated rather than different. Whether D47.09 means confirmed clonal disease is a question for the clinical reviewer.
- **What the phecode names hide.** "Hypermobility syndrome" includes the Ehlers–Danlos codes; "allergy to insects" is mostly "allergy, unspecified" (T78.40); "anaphylactic reaction" includes "history of anaphylaxis".
- **The cluster.** 156 phecodes in 90 families are significant in both windows at more than twice the background. They form the mast-cell mediator and allergic core (idiopathic urticaria 91, angioedema 72, anaphylaxis 61), the hEDS–POTS pattern with conditions reported alongside it (Chiari-type malformations, CSF leak, celiac artery compression), eosinophilic and functional GI disease, immunoglobulin deficiencies, other genetic diagnoses that testing tends to find (alpha-1-antitrypsin deficiency, hemochromatosis), and a few unexpected rows for the reviewers (liver malignancy and transplant, adrenal disorders, post-COVID condition). It describes who is diagnosed with HaT and their care; it cannot by itself say what HaT causes.

## 9. Open Decisions

| Decision | Status | Effect |
|------------------------|------------------------|------------------------|
| YearsAfterIndex (SMD 0.102): add as a covariate in the post-index PheWAS | **Decided and run** (D40, 2026-10-07): post adds it; pre unchanged; no rematch | Post-index results only |
| Cases indexed before 2021-10-01 (119) are not matched | Implemented, awaiting confirmation (task list) | Already excluded above |
| Earlier mast-cell codes (D89.40–D89.49): primary drops D89.44 only and reads BI_180.6 (mast cell activation) as exposure-adjacent; sensitivity drops all D89.4x | Proposed (task list); sensitivity run not built | Confirmed: BI_180 is the top hit in both windows |
| Sensitivity: cases with D89.44 on 2+ dates (D24) | Planned, not built | Tests whether single-code cases dilute or drive the results |
| Controls with high baseline tryptase (\> 8 ng/mL), possibly undiagnosed HaT | Proposed: drop before matching (task list) | Very few expected; would need rematching |
| Case rule: 1+ vs 2+ D89.44 dates; index date | Provisional, questions for the attending (D24) | Sensitivity analysis planned |

------------------------------------------------------------------------

## 10. Engineering Notes That Bear on Accuracy

- **Memory.** The control pull's 92 million diagnosis rows did not fit in memory. `build_group_parquet.py` now reads them in chunks and stores each diagnosis compactly; its output was checked identical to the original method on synthetic data and on copies of up to 30 million rows. `prepare_phewas_inputs.py` reads only matched patients' rows.
- **pheauxWAS 1.1.1.** A phecode whose cases were all HaT patients was not recognized as needing Firth regression and crashed the results file. Fixed and covered by the tool's self-test; earlier results are unchanged.
- **Reproducibility.** Each run writes `run_log.txt` (every command, its duration and outcome); pheauxWAS logs the SHA-256 of itself and every input file.
- **Verification.** The pipeline's code is tested end to end on synthetic data before each use on the VM.

------------------------------------------------------------------------

## Glossary

| Term | Meaning |
|------------------------------------|------------------------------------|
| Phecode | A group of ICD codes representing one clinical phenotype (phecodeX here). |
| Index date | The date that separates "before" from "after": first D89.44 for cases, a random clinic visit for controls. |
| Propensity score | A patient's predicted probability of being a case, from the matching variables. |
| Caliper | The maximum allowed distance in propensity score between a case and its control. |
| SMD | Standardized mean difference: group difference in means, in units of the cases' standard deviation. Under 0.1 means negligible. |
| ESS | Effective sample size: how many equally weighted patients the weighted controls are worth. |
| Firth regression | A penalized logistic regression that gives finite, usable estimates when a phecode's cases are all or none in one group. |
| Bonferroni / FDR | Corrections for testing many phecodes. Bonferroni controls the chance of any false positive; FDR (q-value) controls the expected share of false positives among the hits. |