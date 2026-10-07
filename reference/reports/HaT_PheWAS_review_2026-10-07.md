# Phenome-Wide Association Study of Hereditary Alpha-Tryptasemia in Epic Cosmos

**Status report for clinical and statistical review — 2026-10-07**

*Primary (pre-index) and sensitivity (post-index) PheWAS complete; further sensitivity analyses planned. Counts of 1–10 patients are masked (Cosmos small-cell rule). Section 8 sets out every criticism we can identify, Section 10 the specific questions for reviewers.*

------------------------------------------------------------------------

## Summary

- **Design.** Matched cohort PheWAS in Epic Cosmos. Cases: patients with ICD-10-CM D89.44 (HaT); index = first D89.44. Controls: a random pool of 300,000 patients without D89.44, each indexed at one random completed clinic visit. Up to 10 controls per case by propensity-score nearest-neighbour matching, exact on sex and calendar quarter of index.
- **Cohort.** 5,969 HaT patients → 4,144 eligible → **3,911 matched** to **28,670 controls** (mean 7.3 per case). All matching covariates balanced (standardized mean difference < 0.1) except years of follow-up after index (0.102), which is adjusted for in the post-index analysis.
- **Analysis.** For each phecode (phecodeX, ≥ 20 cases, case = code on ≥ 2 dates), covariate-adjusted logistic regression (Firth under separation), Bonferroni and Benjamini–Hochberg FDR. Primary window: the 3 years before index; sensitivity: after index.
- **Results.** Pre-index: 1,818 phecodes tested, **482 Bonferroni-significant** (468 higher in HaT), 863 at FDR < 0.05. Post-index: 1,611 tested, 512 Bonferroni-significant (511 higher). Leading associations in both windows: urticaria (OR 47.5 pre), anaphylaxis (61.2), insect and food allergy, POTS (30.4), joint hypermobility (32.8), flushing, rhinitis/asthma — alongside exposure-adjacent mast-cell and tryptase codes (MCAS, R74.8, mastocytosis).
- **Verification.** An independent implementation (pyPheWAS) on identical inputs reproduces the estimates (r = 0.999 on non-separated phecodes, all in the same direction).
- **Main interpretive caveat.** Because HaT is diagnosed by testing driven by symptoms, pre-index associations largely describe the phenotype that leads to testing (indication), not consequences of HaT. Persistence after index supports these being the HaT phenotype rather than transient workup.

------------------------------------------------------------------------

## 1. Objective

To identify, across the phenome, diagnoses that are more or less common in patients with HaT than in comparable patients without a HaT diagnosis, as a hypothesis-generating description of the HaT phenotype in a large US EHR population.

## 2. Data Source

| Item | Detail |
|---|---|
| Source | Epic Cosmos (de-identified, multi-system EHR), queried on a secured VM via Telescope pull definitions |
| Data window | 2015-01-01 to 2026-06-01 (both pulls) |
| Vocabulary | ICD-10-CM only |
| HaT pull | 2026-10-02: every patient with D89.44; their encounters, diagnosis events (one row per event and code) and tryptase results |
| Control pull | 2026-10-06: 300,000 patients; 29.8 M encounters, 92.1 M diagnosis rows, 948 tryptase results |
| Software | Python 3.13 (pandas, numpy), R 4.6.1 (MatchIt, cobalt), pheauxWAS 1.1.1, pyPheWAS (commit 2a8fff1) |

Patient-level data never leave the VM; all code is developed and tested on synthetic data of identical structure.

## 3. Cohort Construction

### 3.1 Cases

- **Definition:** D89.44 on **at least one** date. Single-code cases are retained because HaT is diagnosed by genetic testing (*TPSAB1* copy number), so one code is expected to be reliable; a ≥ 2-date definition is a planned sensitivity analysis (§8). Of 5,967 patients with D89.44 in profiling, 3,693 (62%) had it on ≥ 2 dates.
- **Index date:** first D89.44 not recorded as ruled-out or erroneous (diagnosis status containing "rule", "error", "delete" or "cancel" is dropped). Other mast-cell codes (D89.40–D89.49) do not define cases or the index: they are broader than HaT.
- **Cases indexed before 2021-10-01** (n = 119) are not matched: D89.44 entered ICD-10-CM in October 2021, so earlier codes were likely applied retrospectively, and the control pool starts at that date.

### 3.2 Controls

- **Pool:** a reproducible random sample of Cosmos patients without D89.44 (hash of patient key, ~1% of Cosmos, first 300,000 in hash order). HaT patients are excluded by key; any control with a D89.44 anywhere is also dropped.
- **Pseudo-index:** one randomly chosen completed clinic visit (Office Visit or Follow-Up) between 2021-10-01 and 2026-06-01. Controls are thus anchored on an opportunity to be observed, not on any diagnosis. (Selecting controls by diagnoses was rejected as conditioning on outcomes.)
- Controls are "no known HaT", not genotyped: see §7.

### 3.3 Variables (identical code for both groups)

| Variable | Definition |
|---|---|
| AgeAtIndex | Age at index (cases: at the first D89.44, shifted if the status filter moved the index) |
| Sex | Cosmos `ReliableSex`; `Sex` where ReliableSex is Ambiguous |
| Race, Ethnicity | Unknown, blank and refused grouped as one "Unknown" level |
| ClinicVisits365Before | Distinct days with a completed Office Visit or Follow-Up in [index − 365, index) |
| YearsBeforeIndex / YearsAfterIndex | First completed encounter to index / index to last completed encounter (capped at death and data end) |

Diagnosis or problem-list counts are deliberately **not** used for matching or adjustment: in a pre-index PheWAS those diagnoses are the outcomes.

### 3.4 Eligibility

At least 2 clinic-visit days in the year before index (ensures both groups were similarly observable before index), a usable sex, and (cases) an index from 2021-10-01.

### 3.5 Flow

| | HaT | Controls |
|---|---|---|
| In pull | 5,969 | 300,000 |
| < 2 clinic-visit days in prior year | 1,753 | 172,748 |
| Index before 2021-10-01 | 119 | — |
| No usable sex | <11 | 110 |
| **Eligible** (reasons overlap) | **4,144** (69%) | **127,223** (42%) |
| **Matched** | **3,911** (94% of eligible) | **28,670** |

The utilization rule removes 29% of HaT patients; results therefore describe HaT patients engaged in care before diagnosis.

## 4. Matching

### 4.1 Specification

``` r
matchit(HaT_Flag ~ AgeAtIndex + YearsBeforeIndex + YearsAfterIndex +
          log1p(ClinicVisits365Before) + Race + Ethnicity,
        method = "nearest", distance = "glm",
        exact = ~ Sex + IndexQuarter,
        ratio = 10, replace = FALSE, caliper = 0.2, std.caliper = TRUE)
```

- Propensity score from logistic regression; nearest-neighbour matching without replacement.
- Exact on sex (sex-specific phecodes) and calendar quarter of index (secular change in coding, Cosmos coverage and the COVID period).
- Caliper 0.2 SD of the propensity score (probability scale, not the logit). Variable ratio results: cases get up to 10 controls, fewer where close controls are exhausted.
- `log1p` of visits to limit the influence of very heavy users.

### 4.2 Diagnostics

| Check | Result | Assessment |
|---|---|---|
| Balance (SMD, MatchIt `summary()` definition) | All < 0.1 except **YearsAfterIndex 0.102**; sex and quarter exact | Acceptable; YearsAfterIndex adjusted in post-index models |
| Unmatched cases | 233 / 4,144 (5.6%); concentrated in the busiest quarters (2025Q2: 50, 2024Q2: 43, 2023Q4: 25) | Acceptable; reflects crowding without replacement, not an unmatchable subgroup |
| Controls per case | 10: 2,210 · 9: 62 · 8: 128 · 7: 108 · 6: 110 · 5: 183 · 4: 266 · 3: 247 · 2: 255 · 1: 342; mean 7.3 | As expected for 10:1 without replacement with a caliper |
| Effective sample size of controls (MatchIt weights) | 16,402 of 28,670 | Reflects uneven set sizes |

*Std. pair distances* within matched sets are large for some variables (e.g. AgeAtIndex 1.25): the propensity score balances group means, not individual pairs; the outcome models adjust for these covariates.

## 5. Outcome Definition and Analysis

| Element | Specification |
|---|---|
| Exposure codes | D89.44 removed from outcome events (it maps to its own phecode, GE_969.4; 16,969 rows removed) |
| Windows | **Pre (primary):** diagnoses in [index − 3 years, index). **Post (sensitivity):** (index, end of observation]. The index day is excluded from both |
| Phecodes | phecodeX (ICD-10-CM map), child phecodes rolled up to parents |
| Phecode case | Code on ≥ 2 distinct dates in the window |
| Excluded from a phecode | 1 date only; a related phecode in its exclusion range; wrong sex for a sex-specific phecode |
| Phecode control | All other matched patients |
| Minimum | 20 cases per phecode |
| Model | `phecode ~ HaT_Flag + AgeAtIndex + Sex + Race + Ethnicity + YearsBeforeIndex + ClinicVisits365Before` (+ `YearsAfterIndex` in post); unconditional logistic regression on the matched cohort, unweighted, ignoring matched sets |
| Separation | Firth penalized regression when separation is detected (including a 0/1 exposure with an empty cell against the outcome); Wald CI, penalized likelihood-ratio p |
| Multiplicity | Bonferroni (α = 0.05 / phecodes tested in that window) and Benjamini–Hochberg q-values |
| Verification | pyPheWAS (Phecode 1.2, ≥ 1 code, no exclusions, L1-penalized logistic, α = 0.1) run on identical events, compared phecode-for-phecode with pheauxWAS run under pyPheWAS's map and rules |

## 6. Results

### 6.1 Overview

| | Pre-index (primary) | Post-index (sensitivity) |
|---|---|---|
| Matched patients (HaT / controls) | 32,581 (3,911 / 28,670) | same |
| Patient-code-date diagnoses in window | 4,640,043 | 2,985,445 |
| Phecodes tested / not tested (< 20 cases) | 1,818 / 1,577 | 1,611 / 1,652 |
| Bonferroni-significant (higher / lower in HaT) | 482 (468 / 14) | 512 (511 / 1) |
| FDR < 0.05 (higher / lower) | 863 (787 / 76) | 863 (843 / 20) |
| Firth fits (of which FDR < 0.05) | 473 (122) | 472 (137) |
| FDR hits by category (largest) | GI 95, Neurological 87, Musculoskeletal 86, Endocrine/Metabolic 69, Symptoms 69, Respiratory 55, Cardiovascular 51, Dermatological 51 | Musculoskeletal 97, GI 87, Neurological 82, Endocrine/Metabolic 78, Symptoms 70, Cardiovascular 59, Respiratory 56 |

### 6.2 Exposure-adjacent phecodes (reported separately)

These capture the diagnostic workup or the diagnosis itself rather than independent phenotypes:

| Phecode | Content (ICD-10-CM) | OR pre | OR post |
|---|---|---|---|
| BI_180 / BI_180.6 | Mast cell activation syndrome and related (D89.40–D89.43, D89.49) | 40.9 / 650 | 61.1 / — |
| SS_823 / SS_823.2 | Abnormal serum enzymes; R74.8 (usual code for raised tryptase) | 19.1 / 27.2 | 11.2 / 16.3 |
| CA_120.1, CA_120.15 | Myeloid; mast-cell neoplasms (C96.2x, D47.0x incl. systemic mastocytosis D47.02) | 29.3, 897 | 23.2, — |
| CA_125, CA_125.1 | Other lymphoid/hematopoietic neoplasms; cutaneous mastocytosis (D47.01) | 234, 185 | — |

(— : not in the post-index top results shown on the summary sheet; available in the full results file.)

### 6.3 Leading non-adjacent associations, both windows

| Phecode | Description | OR pre [95% CI] | OR post [95% CI] |
|---|---|---|---|
| DE_666 | Urticaria | 47.5 [40.5–55.6] | 55.1 [45.6–66.7] |
| SS_840.9 | Anaphylactic reaction | 61.2 [46.5–80.5] | 44.6 [33.5–59.3] |
| NS_343.7 | Postural orthostatic tachycardia syndrome | 30.4 [24.2–38.1] | 36.4 [28.6–46.4] |
| NS_343 | Disorders of autonomic nervous system | 22.2 [18.6–26.5] | 24.3 [20.1–29.2] |
| MS_712.51 | Hypermobility syndrome | 32.8 [26.1–41.4] | 39.9 [31.2–51.2] |
| MS_712.5 | Disorder of ligament | 29.0 [23.3–36.1] | 38.7 [30.4–49.4] |
| MS_712 | Joint derangements and related disorders | 8.50 [7.43–9.73] | 13.3 [11.4–15.5] |
| DE_679.3 | Flushing | 13.2 [11.0–15.9] | — |
| SS_840.2 | Allergy to insects | 13.1 [11.4–15.2] | — |
| SS_840.1 | Food allergy | 13.0 [11.2–15.1] | 11.8 [9.74–14.3] |
| SS_840 | Allergy | 7.95 [7.33–8.63] | 6.43 [5.90–7.02] |
| RE_463 | Rhinitis and nasal congestion | 3.59 [3.31–3.90] | 3.85 [3.49–4.25] |
| RE_475 | Asthma | — | 3.59 [3.26–3.94] |
| GI_527 | Abdominal pain | — | 3.10 [2.84–3.39] |
| GE_978 | Genetic disorders of growth and musculoskeletal system (incl. Ehlers–Danlos Q79.6x) | — | 38.4 [29.1–50.8] |

All q < 1e-130. "—" = not among the top 20 on that window's summary sheet (values are in the full results files). Many hits are hierarchically related (parent and child phecodes share patients).

### 6.4 Lower in HaT (FDR < 0.05, top 5)

| Pre-index | OR [95% CI] | Post-index | OR [95% CI] |
|---|---|---|---|
| Current tobacco use | 0.584 [0.505–0.677] | Current tobacco use | 0.575 [0.478–0.691] |
| Fractures | 0.663 [0.578–0.761] | Secondary malignant neoplasm | 0.409 [0.268–0.626] |
| Secondary malignant neoplasm | 0.29 [0.185–0.457] | Psychoactive substance abuse | 0.461 [0.301–0.706] |
| Nicotine dependence | 0.776 [0.703–0.857] | Diabetes mellitus | 0.821 [0.733–0.919] |
| Hypertension | 0.799 [0.730–0.874] | Alcohol abuse and dependence | 0.472 [0.302–0.737] |

### 6.5 Verification against pyPheWAS

| | Pre | Post |
|---|---|---|
| Phecodes in both / same direction | 978 / 978 | 933 / 933 |
| Median absolute beta difference | 0.0067 | 0.0082 |
| Correlation of betas, all | 0.744 | 0.783 |
| Separated phecodes (|β| > 10 in either) | 26 | 32 |
| Correlation excluding separated; max abs difference | **0.999**; 0.201 | **0.999**; 0.412 |

The lower overall correlation arises solely from separated phecodes, where unpenalized ML estimates diverge and pyPheWAS's L1 penalty shrinks them toward zero. The largest non-separated differences (0.20 pre, 0.41 post, in log-odds) are at large effects, where the L1 penalty shrinks most.

**What this does and does not show.** It verifies the computation: phecode mapping, case counting, covariate handling and model fitting give the same answers in two independent implementations. It does **not** validate the study's own results directly, because the comparison is run under pyPheWAS's rules (Phecode 1.2 map, 1 code makes a case, no exclusions, no Firth). The study's phecodeX analysis, with its stricter case definition and exclusions, is a different analysis by design; its correctness rests on the same code paths verified here plus the tool's self-tests.

## 7. Interpretation

1. **Face validity.** The leading phenotypes (urticaria and flushing, anaphylaxis, insect and food allergy, dysautonomia/POTS, joint hypermobility, rhinitis/asthma, abdominal pain) match the multisystem phenotype described for HaT.
2. **Indication, not causation, in the pre-index window.** HaT is diagnosed by testing, prompted by these symptoms; the very large pre-index odds ratios (20–60) largely reflect selection into testing. The pre-index results describe the phenotype preceding diagnosis.
3. **Persistence after diagnosis.** Most leading phenotypes recur after index with similar or larger effects, arguing against purely transient workup. Shifts are as expected: tryptase-abnormal codes fall after diagnosis (testing precedes it), MCAS codes rise (coded in follow-up care), and Ehlers–Danlos codes appear post-index (plausibly after genetic evaluation).
4. **Breadth and direction.** 47% (pre) and 54% (post) of tested phecodes are FDR-significant, and > 90% of those are higher in HaT. Beyond true phenotype, this indicates residual differences in healthcare intensity not captured by one year of office visits (specialist evaluation, testing cascades).

## 8. Criticisms and Limitations

Every weakness we can identify, so reviewers can weigh the results against them. Each item gives the problem, the likely direction of bias, what the study does now, and what would address it. Items marked **(major)** could change the main conclusions.

### 8.1 Design and bias

1. **Indication (protopathic) bias in the pre-index window (major).** HaT is diagnosed because symptomatic patients are tested; the 3 years before index are, for cases, the period of symptoms and workup that led to testing. *Bias:* away from the null, very large. *Now:* framed as "phenotype preceding diagnosis", not effects of HaT; post-index window as a check. *Remedy:* cannot be removed in this design; a population with systematic testing (e.g. genotyped biobank) would be needed for causal claims.
2. **Asymmetric index events (major).** A case's index is a diagnostic event, often at a specialist after a workup; a control's is a random office visit. The windows on either side of these anchors are not exchangeable: cases' pre-index windows are dense with evaluation, controls' are ordinary care. *Bias:* away from the null, broadly. *Now:* index day excluded; utilization matched on prior-year office visits. *Remedy:* anchor controls on a comparable evaluative encounter (e.g. an allergy/immunology visit), or lag the pre-index window (e.g. exclude the 6–12 months before index).
3. **Health-system and referral confounding (major).** HaT is diagnosed mainly at centres with mast-cell expertise; cases are therefore concentrated in particular health systems with their own coding practices and specialist density, while controls are drawn at random across Cosmos. Health system, region and payer are **not** matched or adjusted. *Bias:* unpredictable, potentially large for coding-sensitive phecodes. *Remedy:* match or stratify on health system (or at least region), or restrict controls to the systems that diagnose HaT.
4. **Residual healthcare-intensity confounding (major).** Matching on office/follow-up visit days in the year before index does not capture specialist visits, ED use, testing intensity, or the 3-year window. *Evidence:* 91–98% of significant phecodes are higher in HaT, including many with no known link to HaT. *Bias:* away from the null, broad. *Remedy:* adjust or match on specialist and ED visits, or on diagnosis counts from outside the analysis window; use negative-control outcomes to calibrate the background excess.
5. **Control misclassification.** Controls are not genotyped; HaT affects an estimated 4–6% of the population and is under-diagnosed, so some controls have HaT. *Bias:* toward the null, modest and non-differential. *Remedy:* exclude controls with elevated baseline tryptase (few have one measured); accept as a stated limitation.
6. **Case misclassification.** A single D89.44 may be a rule-out, an error, or carried forward without confirmation; no genetic results are available. *Bias:* toward the null if non-cases are included. *Now:* status filter for ruled-out/error codes. *Remedy:* ≥ 2-date sensitivity analysis; tryptase ≥ 8 ng/mL as supporting evidence.
7. **The diagnosis-status filter is unverified on the real data.** Statuses containing "rule", "error", "delete" or "cancel" are dropped, but the actual status values in Cosmos (listed in the build reports) have not yet been reviewed. *Effect:* if real spellings differ, rule-out codes may remain as diagnoses (or valid ones may be dropped). *Remedy:* review `hat_group_report.txt` and `control_group_report.txt` before final analysis.
8. **Selection by eligibility.** 29% of HaT patients fail the prior-utilization rule and 119 indexed before October 2021 are excluded; results describe HaT patients engaged in care before diagnosis, diagnosed after the code existed. *Remedy:* report characteristics of excluded cases; a sensitivity analysis with a relaxed utilization rule.
9. **Calendar and code-introduction effects.** D89.44 exists only from October 2021; earlier HaT diagnoses carry other codes (D89.40/D89.49), so some "controls" and some cases' histories may contain HaT under other codes. *Effect:* exposure-adjacent contamination of outcomes (see 8.3.2) and possible earlier true index. *Remedy:* report earlier D89.4x codes among cases (recorded by the builder); treat D89.4x as exposure-adjacent.
10. **Population differences not modelled.** ~75% of cases are female; socioeconomic status, insurance and region are unmeasured. Lower tobacco, substance use, diabetes and hypertension in HaT are more plausibly residual confounding than protection.
11. **Control pool representativeness.** Controls are a hash-based ~1% sample of Cosmos patients with a clinic visit from October 2021, capped at 300,000. The sample is reproducible and not obviously biased, but its representativeness of Cosmos has not been checked against Cosmos-wide distributions.

### 8.2 Matching

1. **The outcome model ignores the matched design (major for inference).** Unconditional, unweighted logistic regression on the matched cohort (D13): sets with 1 to 10 controls contribute unequally, MatchIt's weights are not used, and within-set correlation is not modelled. *Effect:* estimates are for a population weighted toward cases with many controls; standard errors may be mis-stated. *Remedy:* conditional logistic regression on matched sets, or weighted regression with cluster-robust SEs by set; at minimum, compare.
2. **Variable ratio.** 342 cases have 1 control, 2,210 have 10. Cases who matched poorly (crowded quarters) are represented by few controls. *Remedy:* as 8.2.1; report results restricted to full 10:1 sets.
3. **Caliper scale.** 0.2 SD of the propensity score on the probability scale, not the logit (Austin's recommendation). With small propensities, the probability-scale caliper is tighter in some regions and looser in others. *Remedy:* refit with `link = "linear.logit"`; compare balance and unmatched counts.
4. **Propensity model specification.** Main effects only, linear in age and record length; no interactions. Balance was checked on means (SMD) only, not on variances or distributions beyond MatchIt's summary. *Remedy:* report variance ratios and eCDF statistics (available in the MatchIt log); add splines if imbalance appears.
5. **Imperfect balance on follow-up.** YearsAfterIndex SMD 0.102; adjusted in the post-index model only (D40).
6. **Pair-level differences.** Std. pair distances are large (e.g. age 1.25 SD): group means balance, individual pairs do not. Acceptable for group comparison with regression adjustment, but relevant if conditional analysis is adopted.

### 8.3 Outcomes

1. **Unequal observation time.** The pre-index window is nominally 3 years, but patients with less than 3 years of prior record get a truncated window (adjusted only through `YearsBeforeIndex`). The post-index window varies with follow-up (adjusted through `YearsAfterIndex`). Logistic regression on "ever coded" does not model time at risk. *Remedy:* require ≥ 3 years of prior observation; for post, model rates (Poisson/negative binomial with an offset) or fix the window length.
2. **Exposure-adjacent outcomes (major for presentation).** MCAS (D89.40–D89.49), raised tryptase (R74.8) and mastocytosis (D47.0x, C96.2x) codes lead the results; they are part of the diagnostic pathway, not independent phenotypes. *Remedy:* planned sensitivity analysis removing them; report separately.
3. **Phecode hierarchy.** Child phecodes roll up into parents, so parent and child hits share patients; 482 or 863 significant phecodes are far fewer distinct findings. *Remedy:* report leaf-level or collapsed results; cluster related phecodes.
4. **Two-date case rule and exclusions.** A phecode case needs codes on 2+ dates; 1-date patients and those with related phecodes are excluded from that phecode's analysis, so the comparison group differs by phecode. Standard PheWAS practice, but it means denominators vary and exclusions can themselves differ by group.
5. **Coding, not disease.** Outcomes are billing codes; differences in coding thoroughness between specialist and primary care settings translate directly into "associations".

### 8.4 Statistics

1. **Odds ratios exaggerate risk ratios for common outcomes.** Several phecodes are common (allergy: 6,803 cases, ~21% of the cohort); ORs overstate relative risks there. *Remedy:* report absolute prevalences in each group, or risk ratios for common phecodes.
2. **Firth fits for 26–29% of tested phecodes.** These report Wald intervals with penalized likelihood-ratio p-values, which can disagree; profile-likelihood intervals would be consistent. Some separation arises from sparse covariate levels (small race/ethnicity groups) rather than the exposure.
3. **Multiplicity under dependence.** Bonferroni is very conservative with correlated phecodes; BH assumes positive dependence (likely acceptable). Hierarchical FDR would match the structure better.
4. **Extreme p-values.** Many underflow (q < 1e-300); they carry no ranking information. Effect sizes and intervals should be the basis of interpretation.
5. **Winner's curse.** Effect sizes for the top hits are selected for being extreme and will tend to shrink on replication.
6. **No replication.** A single discovery analysis; no independent cohort, held-out sample, or negative-control outcomes yet.

### 8.5 Data and implementation

1. **Cosmos data quality.** Multi-organization EHR data with varying coding practices, missing race/ethnicity grouped as "Unknown", and site participation changing over time (sites' Cosmos-usable dates are pulled but not yet used to restrict observation).
2. **Pull window.** History starts 2015-01-01; a patient whose first D89.44 predates 2015 gets a later index (rare, since the code dates from 2021, but relevant to earlier D89.4x codes).
3. **Custom software.** The study's PheWAS runs on pheauxWAS, a purpose-written tool. It is verified against pyPheWAS (Section 6.5, r = 0.999 on comparable phecodes) and by self-tests, but it is not a published package. A fix during this work (v1.1.1) added detection of separation when all of a phecode's cases are exposed; earlier synthetic results were unchanged.
4. **Small cells.** Cosmos restricts publication of counts of 1–10 patients; phecodes near the 20-case minimum may have exposure-group cells under 11 and need masking before publication.

## 9. Planned Sensitivity Analyses

| Analysis | Question | Change |
|---|---|---|
| Drop all D89.40–D89.49 (and consider R74.8, D47.0x, C96.2x) from outcomes | Do the non-adjacent phenotypes stand without mast-cell coding? | Exposure-code exclusion list |
| Cases with D89.44 on ≥ 2 dates | Are single-code cases diluting or driving results? | Case definition; rematch |
| Conditional logistic regression (or weighted, cluster-robust) | Is inference robust to respecting the matched design? | Model |
| Controls with baseline tryptase > 8 ng/mL removed | Effect of possible undiagnosed HaT among controls | Control eligibility; rematch |
| Broader utilization adjustment (specialist/ED visits, test counts) | How much of the breadth is healthcare intensity? | Covariates |
| Health system / region matching or stratification | Is the breadth driven by where HaT is diagnosed? | Matching; needs organization or region from Cosmos |
| Lagged pre-index window (e.g. exclude the 6–12 months before index) | Are pre-index hits workup immediately before diagnosis? | Window |
| Require ≥ 3 years of prior observation | Effect of truncated pre-index windows | Eligibility |
| Logit-scale caliper; restrict to full 10:1 sets | Sensitivity to matching choices | Matching |
| Negative-control outcomes | Calibrate the background excess from healthcare intensity | Interpretation |

## 10. Questions for Reviewers

**Clinical (attending).**

1. Case definition: is a single D89.44 sufficient for the primary analysis, with ≥ 2 dates as sensitivity, or the reverse?
2. Index date: is the first D89.44 the right anchor, given that workup (tryptase, MCAS codes) precedes it?
3. Which codes should be treated as exposure-adjacent and excluded in sensitivity analysis: D89.40–D89.49 only, or also R74.8 and mastocytosis (D47.0x, C96.2x)?
4. Should controls with elevated baseline tryptase be excluded?
5. Do the post-index Ehlers–Danlos associations fit clinical experience (hEDS diagnosed after HaT testing)?

**Statistical.**

1. Is unconditional adjusted logistic regression acceptable as primary given variable-ratio matching, or should conditional logistic regression (or weights with cluster-robust SEs) be primary?
2. Caliper on the propensity-score probability scale (0.2 SD) rather than the logit: change for consistency with Austin's recommendation?
3. Multiplicity across a hierarchy of dependent phecodes: report at leaf level, collapse to parents, or use a hierarchical FDR?
4. Utilization adjustment: which additional measures of healthcare intensity are appropriate without conditioning on outcomes?
5. Reporting extreme associations: preferred presentation when p underflows and Firth is used for ~26% of fitted phecodes.
6. Health-system confounding (8.1.3): match, stratify, or restrict controls to diagnosing systems?
7. Time at risk (8.3.1): require full windows, or model rates?

------------------------------------------------------------------------

## Appendix: Reproducibility

- **Pipeline (VM):** `python phewas match` → `python phewas balance` → `python phewas pre` → `python phewas post`; `python phewas sheet` summarizes. Each run writes `run_log.txt` (commands, durations, outcomes); pheauxWAS logs SHA-256 hashes of itself and every input.
- **Outputs:** `runs/matching/` (matched cohort, MatchIt summary, love plot, balance), `runs/pre_3y/` and `runs/post/` (inputs, pheauxWAS results CSV and Manhattan plot, pyPheWAS regressions, comparison).
- **Design rationale:** decision log in `reference/plan/decisions.md` (D-numbers); full narrative in `reference/phewasHistoryAndDecisions.md`.
