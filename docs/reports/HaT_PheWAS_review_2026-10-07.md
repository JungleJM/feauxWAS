# Phenome-Wide Association Study of Hereditary Alpha-Tryptasemia in Epic Cosmos

**Status report for clinical and statistical review — 2026-10-07, revised 2026-10-08**

*Primary (pre-index) and sensitivity (post-index) PheWAS complete; further sensitivity analyses planned. Counts of 1–10 patients are masked (Cosmos small-cell rule). Section 8 sets out every criticism we can identify, Section 10 the specific questions for reviewers. Revised 2026-10-08: corrections to §6.2 and §6.5, the case definition settled (§3.1), the mastocytosis subgroup added (§6.2, §8.1.12, §10), and the full cluster (§6.3.1).*

------------------------------------------------------------------------

## Summary

- **Design.** Matched cohort PheWAS in Epic Cosmos. Cases: patients with ICD-10-CM D89.44 (HaT); index = first D89.44. Controls: a random pool of 300,000 patients without D89.44, each indexed at one random completed clinic visit. Up to 10 controls per case by propensity-score nearest-neighbour matching, exact on sex and calendar quarter of index.
- **Cohort.** 5,969 HaT patients[^1] → 4,144 eligible → **3,911 matched** to **28,670 controls** (mean 7.3 per case). All matching covariates balanced (standardized mean difference \< 0.1) except years of follow-up after index (0.102), which is adjusted for in the post-index analysis.
- **Analysis.** For each phecode (phecodeX, ≥ 20 cases, case = code on ≥ 2 dates), covariate-adjusted logistic regression (Firth under separation), Bonferroni and Benjamini–Hochberg FDR. Primary window: the 3 years before index; sensitivity: after index.
- **Results.** Pre-index: 1,818 phecodes tested, **482 Bonferroni-significant** (468 higher in HaT), 863 at FDR \< 0.05. Post-index: 1,611 tested, 512 Bonferroni-significant (511 higher). Leading associations in both windows: urticaria (OR 47.5 pre), anaphylaxis (61.2), insect and food allergy, POTS (30.4), joint hypermobility (32.8), flushing, rhinitis/asthma — alongside exposure-adjacent mast-cell and tryptase codes (MCAS, R74.8, mastocytosis).
- **Verification.** An independent implementation (pyPheWAS) on identical inputs reproduces the estimates (r = 0.999 on non-separated phecodes, all in the same direction).
- **A mastocytosis subgroup.** 30% of matched cases carry a mastocytosis code (D47.0x, C96.2x) at some point, mostly D47.09 ("other mast cell neoplasms"); 9% carry systemic mastocytosis (D47.02). HaT is enriched in systemic mastocytosis, whose patients are routinely tested for it. The subgroup does not explain the phenotype: cases without these codes still show it (anaphylaxis 15.1% vs 0.6% of controls, POTS 10.2% vs 0.5%) (§8.1.12).
- **Main interpretive caveat.** Because HaT is diagnosed by testing driven by symptoms, pre-index associations largely describe the phenotype that leads to testing (indication), not consequences of HaT. Persistence after index supports these being the HaT phenotype rather than transient workup.
- **Tryptase is on record for only 18% of cases** (704 of 3,911). Of those measured, 92% have a baseline serum tryptase ≥ 8 ng/mL (median 15.3), consistent with HaT; but for most cases the test that typically starts the workup is not in the data, probably because it was run at an outside or reference laboratory or recorded under a lab component or unit not captured here. Case status rests on the D89.44 code (§3.1).

[^1]: Three counts of patients with any D89.44 appear in this study, from different date ranges: 5,974 in all years (profile query 2), 5,967 with D89.44 dated 2018-01-01 to 2026-06-01 (profile queries, 2026-10-01), and 5,969 in the study's pull, 2015-01-01 to 2026-06-01 (2026-10-02). The analysis uses the pull's 5,969.

------------------------------------------------------------------------

## 1. Objective

To identify, across the phenome, diagnoses that are more or less common in patients with HaT than in comparable patients without a HaT diagnosis, as a hypothesis-generating description of the HaT phenotype in a large US EHR population.

## 2. Data Source

| Item | Detail |
|------------------------------------|------------------------------------|
| Source | Epic Cosmos (de-identified, multi-system EHR), queried on a secured VM via Telescope pull definitions |
| Data window | 2015-01-01 to 2026-06-01 (both pulls) |
| Vocabulary | ICD-10-CM only |
| HaT pull | 2026-10-02: every patient with D89.44; their encounters, diagnosis events (one row per event and code) and tryptase results |
| Control pull | 2026-10-06: 300,000 patients; 29.8 M encounters, 92.1 M diagnosis rows, 948 tryptase results |
| Software | Python 3.13 (pandas, numpy), R 4.6.1 (MatchIt, cobalt), pheauxWAS 1.1.1, pyPheWAS (commit 2a8fff1) |

Patient-level data never leave the VM; all code is developed and tested on synthetic data of identical structure.

## 3. Cohort Construction

### 3.1 Cases

- **Definition:** D89.44 on **at least one** date. A D89.44 diagnosis requires a genetic test (*TPSAB1* copy number), so a single code stands for a tested patient. Miscoding is possible; it is treated as negligible and stated as a limitation (§8.1.6). Of 5,967 patients with D89.44 in profiling, 3,693 (62%) had it on ≥ 2 dates.
- **Index date:** first D89.44 not recorded as ruled-out or erroneous (diagnosis status containing "rule", "error", "delete" or "cancel" is dropped). Other mast-cell codes (D89.40–D89.49) do not define cases or the index: they are broader than HaT.
- **Cases indexed before 2021-10-01** (n = 119) are not matched: D89.44 entered ICD-10-CM in October 2021, so earlier codes were likely applied retrospectively, and the control pool starts at that date.

### 3.2 Controls

- **Pool:** a reproducible random sample of Cosmos patients without D89.44 (hash of patient key, \~1% of Cosmos, first 300,000 in hash order). HaT patients are excluded by key; any control with a D89.44 anywhere is also dropped.
- **Pseudo-index:** one randomly chosen completed clinic visit (Office Visit or Follow-Up) between 2021-10-01 and 2026-06-01. Controls are thus anchored on an opportunity to be observed, not on any diagnosis. (Selecting controls by diagnoses was rejected as conditioning on outcomes.)
- Controls are "no known HaT", not genotyped: see §7.

### 3.3 Variables (identical code for both groups)

| Variable | Definition |
|------------------------------------|------------------------------------|
| AgeAtIndex | Age at index (cases: at the first D89.44, shifted if the status filter moved the index) |
| Sex | Cosmos `ReliableSex`; `Sex` where ReliableSex is Ambiguous |
| Race, Ethnicity | Unknown, blank and refused grouped as one "Unknown" level |
| ClinicVisits365Before | Distinct days with a completed Office Visit or Follow-Up in \[index − 365, index) |
| YearsBeforeIndex / YearsAfterIndex | First completed encounter to index / index to last completed encounter (capped at death and data end) |

Diagnosis or problem-list counts are deliberately **not** used for matching or adjustment: in a pre-index PheWAS those diagnoses are the outcomes.

### 3.4 Eligibility

At least 2 clinic-visit days in the year before index (ensures both groups were similarly observable before index), a usable sex, and (cases) an index from 2021-10-01.

### 3.5 Flow

|   | HaT | Controls |
|----|----|----|
| In pull | 5,969 | 300,000 |
| \< 2 clinic-visit days in prior year | 1,753 | 172,748 |
| Index before 2021-10-01 | 119 | — |
| No usable sex | \<11 | 110 |
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
- Caliper 0.2 SD of the propensity score, on the probability scale. Austin (2011)[^2] recommends 0.2 SD of the *logit* of the propensity score; see §8.2.3. Variable ratio results: cases get up to 10 controls, fewer where close controls are exhausted.
- `log1p` of visits to limit the influence of very heavy users.

[^2]: Austin PC. Optimal caliper widths for propensity-score matching when estimating differences in means and differences in proportions in observational studies. *Pharmaceutical Statistics* 2011;10(2):150–161. From simulations, it recommends a caliper of 0.2 standard deviations of the logit of the propensity score. MatchIt applies `caliper = 0.2, std.caliper = TRUE` to the distance as estimated (the probability, with `distance = "glm"`) unless `link = "linear.logit"` is given.

### 4.2 Diagnostics

| Check | Result | Assessment |
|------------------------|------------------------|------------------------|
| Balance (SMD, MatchIt `summary()` definition) | All \< 0.1 except **YearsAfterIndex 0.102**; sex and quarter exact | Acceptable; YearsAfterIndex adjusted in post-index models |
| Unmatched cases | 233 / 4,144 (5.6%); concentrated in the busiest quarters (2025Q2: 50, 2024Q2: 43, 2023Q4: 25) | Acceptable; reflects crowding without replacement, not an unmatchable subgroup |
| Controls per case | 10: 2,210 · 9: 62 · 8: 128 · 7: 108 · 6: 110 · 5: 183 · 4: 266 · 3: 247 · 2: 255 · 1: 342; mean 7.3 | As expected for 10:1 without replacement with a caliper |
| Effective sample size of controls (MatchIt weights) | 16,402 of 28,670 | Reflects uneven set sizes |

*Std. pair distances* within matched sets are large for some variables (e.g. AgeAtIndex 1.25): the propensity score balances group means, not individual pairs; the outcome models adjust for these covariates.

## 5. Outcome Definition and Analysis

| Element | Specification |
|------------------------------------|------------------------------------|
| Exposure codes | D89.44 removed from outcome events (it maps to its own phecode, GE_969.4; 16,969 rows removed) |
| Windows | **Pre (primary):** diagnoses in \[index − 3 years, index). **Post (sensitivity):** (index, end of observation\]. The index day is excluded from both |
| Phecodes | phecodeX (ICD-10-CM map), child phecodes rolled up to parents |
| Phecode case | Code on ≥ 2 distinct dates in the window |
| Excluded from a phecode | 1 date only. No related-phecode exclusions: phecodeX defines no exclusion ranges, and its own workflow uses none. Sex restriction: **not applied in this run** (the phecodeX sex file was not passed to the tool), so the 320 sex-specific phecodes were analysed in both sexes, adjusted for sex; being corrected |
| Phecode control | All other matched patients |
| Minimum | 20 cases per phecode |
| Model | `phecode ~ HaT_Flag + AgeAtIndex + Sex + Race + Ethnicity + YearsBeforeIndex + ClinicVisits365Before` (+ `YearsAfterIndex` in post); unconditional logistic regression on the matched cohort, unweighted, ignoring matched sets |
| Separation | Firth penalized regression when separation is detected (including a 0/1 exposure with an empty cell against the outcome); Wald CI, penalized likelihood-ratio p |
| Multiplicity | Bonferroni (α = 0.05 / phecodes tested in that window) and Benjamini–Hochberg q-values |
| Verification | pyPheWAS (Phecode 1.2, ≥ 1 code, no exclusions, L1-penalized logistic, α = 0.1) run on identical events, compared phecode-for-phecode with pheauxWAS run under pyPheWAS's map and rules |

### 5.1 Which ICD codes were tested, and how specific codes can be examined

**No codes were chosen in advance.** A PheWAS is hypothesis-free: every ICD-10-CM diagnosis recorded for the matched patients in the window entered the analysis (4.6 million patient-code-date rows before index, 3.0 million after).

**What is tested is the phecode, not the individual ICD code.** Each ICD-10-CM code is mapped to a phecode (phecodeX), a group of related codes that stands for one clinical condition. For example, every urticaria code (L50.x) becomes DE_666 "Urticaria". A phecode is tested when at least 20 patients are phecode cases:

|                              | Before index | After index |
|------------------------------|--------------|-------------|
| Phecodes observed            | 3,395        | 3,263       |
| Phecodes tested (≥ 20 cases) | 1,818        | 1,611       |

Codes with no phecode are dropped. **81.3%** of diagnosis rows mapped to a phecode before index (3,774,357 of 4,640,043) and **82.0%** after (2,448,724 of 2,985,445); 99.5% and 91.1% of patients had at least one mapped code. The unmapped rows are almost all Z-codes for encounters, status and screening, not diseases. The ten most frequent before index: Z79.899 (other long-term drug therapy), Z23 (immunization), Z00.00 (general adult examination), Z12.31 (screening mammogram), Z79.4 (insulin use), Z79.01 (anticoagulant use), Z98.890 (other post-procedural states), Z20.822 (COVID-19 exposure), Z01.818 (pre-procedural examination), Z12.11 (screening colonoscopy); after index the list is nearly the same. The accurate description is therefore: *all ICD-10-CM diagnoses recorded in the window were mapped to phecodeX, and every phecode with at least 20 cases was tested.* It is not "every ICD-10 code was tested".

**Why it matters for reading the results.** A phecode's name can be narrower than what it contains:

- *Hypermobility syndrome* (MS_712.51) includes the Ehlers–Danlos codes, among them hypermobile EDS (Q79.62).
- *Allergy to insects* (SS_840.2) also includes "Allergy, unspecified" (T78.40) and "non-medicinal substance allergy" (Z91.04x).
- *Anaphylactic reaction* (SS_840.9) includes "personal history of anaphylaxis" (Z87.892).
- CA_125 is mainly the mastocytosis codes (§6.2).

**Examining specific ICD codes.** Two ways, from the same data:

1.  **Which codes make up a phecode.** For any phecode, count the patients with each of its ICD codes, in HaT and in controls. This is being done now for hypermobility, insect allergy, anaphylaxis, CA_125 and GE_978 (results pending). It can be run for any phecode or any list of codes a reviewer names, such as Q79.62 alone or Z91.030 (bee allergy) alone.
2.  **A PheWAS on individual ICD codes**, each code treated as its own outcome, with the same model. It separates codes the phecodes merge, such as hEDS from other hypermobility. The cost: many more tests (a stricter threshold), sparser codes (fewer reach 20 cases), one condition split across several codes (L50.0, L50.9), and no exclusion rules for related conditions. It is best used as a follow-up on the phecodes found significant, not as the main analysis.

Reviewers are welcome to name codes or phenotypes they want examined this way.

## 6. Results

### 6.1 Overview

|   | Pre-index (primary) | Post-index (sensitivity) |
|------------------------|------------------------|------------------------|
| Matched patients (HaT / controls) | 32,581 (3,911 / 28,670) | same |
| Patient-code-date diagnoses in window | 4,640,043 | 2,985,445 |
| Phecodes tested / not tested (\< 20 cases) | 1,818 / 1,577 | 1,611 / 1,652 |
| Bonferroni-significant (higher / lower in HaT) | 482 (468 / 14) | 512 (511 / 1) |
| FDR \< 0.05 (higher / lower) | 863 (787 / 76) | 863 (843 / 20) |
| Firth fits (of which FDR \< 0.05) | 473 (122) | 472 (137) |
| FDR hits by category (largest) | GI 95, Neurological 87, Musculoskeletal 86, Endocrine/Metabolic 69, Symptoms 69, Respiratory 55, Cardiovascular 51, Dermatological 51 | Musculoskeletal 97, GI 87, Neurological 82, Endocrine/Metabolic 78, Symptoms 70, Cardiovascular 59, Respiratory 56 |

### 6.2 Exposure-adjacent phecodes (reported separately)

These capture the diagnostic workup or the diagnosis itself rather than independent phenotypes. Each enters the results for a clinical reason:

- **R74.8** (abnormal serum enzymes) is how a raised tryptase is usually coded: the test that leads to genetic testing. It is highest before index and falls after.
- **D89.40–D89.49** (mast cell activation) are often the label used before the specific HaT code (1,523 cases had one before their first D89.44).
- **D47.0x and C96.2x** (mastocytosis; ICD-10-CM classifies mastocytosis among the neoplasms of hematopoietic tissue, following the WHO, though most systemic mastocytosis is indolent) point to a **subgroup**: HaT is more common in systemic mastocytosis than in the general population, and patients with mastocytosis are tested for HaT, so some cases are mastocytosis patients who also carry HaT. In CA_125, 682 patients are phecode cases before index with an OR of 234; an OR this large means nearly all of them are HaT patients, so the subgroup may be of the order of one in six cases. Their own phenotype (anaphylaxis, venom reactions, flushing, bone disease) overlaps the HaT signal (§8.1.12).

| Phecode | Content (ICD-10-CM) | OR pre | OR post |
|------------------|------------------|------------------|------------------|
| BI_180 / BI_180.6 | Mast cell activation syndrome and related (D89.40–D89.43, D89.49) | 40.9 / 650 | 61.1 / — |
| SS_823 / SS_823.2 | Abnormal serum enzymes; R74.8 (usual code for raised tryptase) | 19.1 / 27.2 | 11.2 / 16.3 |
| CA_120.1, CA_120.15 | Myeloid; mast-cell neoplasms (C96.2x, D47.0x incl. systemic mastocytosis D47.02) | 29.3, 897 | 23.2, — |
| CA_125, CA_125.1 | CA_125: mainly systemic mastocytosis (D47.02), other mast-cell neoplasms (D47.09, D47.0) and C96.2x, with D47.9 and D47.Z; CA_125.1: cutaneous mastocytosis (D47.01) | 234, 185 | — |

(— : not in the post-index top results shown on the summary sheet; available in the full results file.)

### 6.3 Leading non-adjacent associations, both windows

| Phecode | Description | OR pre \[95% CI\] | OR post \[95% CI\] |
|------------------|------------------|------------------|------------------|
| DE_666 | Urticaria | 47.5 \[40.5–55.6\] | 55.1 \[45.6–66.7\] |
| SS_840.9 | Anaphylactic reaction | 61.2 \[46.5–80.5\] | 44.6 \[33.5–59.3\] |
| NS_343.7 | Postural orthostatic tachycardia syndrome | 30.4 \[24.2–38.1\] | 36.4 \[28.6–46.4\] |
| NS_343 | Disorders of autonomic nervous system | 22.2 \[18.6–26.5\] | 24.3 \[20.1–29.2\] |
| MS_712.51 | Hypermobility syndrome | 32.8 \[26.1–41.4\] | 39.9 \[31.2–51.2\] |
| MS_712.5 | Disorder of ligament | 29.0 \[23.3–36.1\] | 38.7 \[30.4–49.4\] |
| MS_712 | Joint derangements and related disorders | 8.50 \[7.43–9.73\] | 13.3 \[11.4–15.5\] |
| DE_679.3 | Flushing | 13.2 \[11.0–15.9\] | — |
| SS_840.2 | Allergy to insects | 13.1 \[11.4–15.2\] | — |
| SS_840.1 | Food allergy | 13.0 \[11.2–15.1\] | 11.8 \[9.74–14.3\] |
| SS_840 | Allergy | 7.95 \[7.33–8.63\] | 6.43 \[5.90–7.02\] |
| RE_463 | Rhinitis and nasal congestion | 3.59 \[3.31–3.90\] | 3.85 \[3.49–4.25\] |
| RE_475 | Asthma | — | 3.59 \[3.26–3.94\] |
| GI_527 | Abdominal pain | — | 3.10 \[2.84–3.39\] |
| GE_978 | Genetic disorders of growth and musculoskeletal system (mainly Ehlers–Danlos, unspecified, Q79.60) | 27.1 \[21.1–34.8\] | 38.4 \[29.1–50.8\] |

All q \< 1e-130. "—" = not among the top 20 on that window's summary sheet (values are in the full results files). Many hits are hierarchically related (parent and child phecodes share patients).

This table is drawn from each window's top 20 by p-value, which favours common diagnoses: it shows the most *certain* associations, not every strong one. §6.3.1 gives the full set by a stated rule.

#### 6.3.1 Full cluster

*Run 2026-10-08: all 156 phecodes, in 90 families.*

**This run's thresholds:** OR ≥ 2.92 before index (2 × median 1.46) and ≥ 3.51 after (2 × median 1.75). 12 exposure-adjacent phecodes left out: BI_180, BI_180.3, BI_180.31, BI_180.6, CA_120, CA_120.1, CA_120.15, CA_125, CA_125.1, GE_969, SS_823, SS_823.2.

**The rule.** A phecode is in the cluster when all of these hold:

- it is significant (FDR \< 0.05) in **both** windows, before and after index;
- its OR is **at least twice the median OR** of all tested phecodes, in each window. The median measures the background shift seen across the whole phenome (§7.4), so a phecode in the cluster stands well above it;
- it is not in an exposure-adjacent family: the HaT code's own (GE_969), mast cell activation (BI_180), raised tryptase (SS_823), or the haematological families that hold the mastocytosis codes (CA_120, CA_125). These are reported in §6.2.

Children are listed under their parent phecode, so a family (e.g. Allergy → Food allergy) reads as one finding, not several. Families are ordered by their strongest member, judged by the smaller of its two ORs. Each row gives the OR with its 95% CI and the percentage of HaT patients and of controls who are phecode cases, in each window.

| Phecode | Description | OR pre \[95% CI\] | HaT / controls pre | OR post \[95% CI\] | HaT / controls post |
|---|---|---|---|---|---|
| DE_666 | **Urticaria** | 47.5 \[40.5–55.6\] | 25.6% / 0.7% | 55.1 \[45.6–66.7\] | 20.8% / 0.5% |
| DE_666.2 | &emsp;↳ Idiopathic urticaria | 90.6 \[59.5–138\] | 7.2% / 0.1% | 123 \[80.7–189\] | 9.6% / 0.1% |
| DE_666.4 | &emsp;↳ Dermatographic urticaria | 19 \[10.8–33.4\] | 1.1% / 0.1% | 56.4 \[20.9–153\] | 0.7% / \<11 |
| DE_666.1 | &emsp;↳ Allergic urticaria | 16.9 \[7.58–37.5\] | 0.5% / \<11 | 12.2 \[5.54–26.9\] | 0.3% / \<11 |
| SS_812.2 | **Angioneurotic edema** | 71.5 \[48.2–106\] | 6.4% / 0.1% | 60.5 \[35.3–104\] | 3.1% / 0.1% |
| SS_840 | **Allergy** | 7.95 \[7.33–8.63\] | 63.9% / 19.0% | 6.43 \[5.9–7.02\] | 42.8% / 10.8% |
| SS_840.9 | &emsp;↳ Anaphylactic reaction | 61.2 \[46.5–80.5\] | 11.5% / 0.2% | 44.6 \[33.5–59.3\] | 8.8% / 0.2% |
| SS_840.1 | &emsp;↳ Food allergy | 13 \[11.2–15.1\] | 13.0% / 1.2% | 11.8 \[9.74–14.3\] | 7.8% / 0.7% |
| SS_840.18 | &emsp;&emsp;↳ Egg allergy | 10.9 \[6.55–18.3\] | 0.8% / 0.1% | 13.7 \[7.59–24.8\] | 0.7% / 0.1% |
| SS_840.11 | &emsp;&emsp;↳ Peanut allergy | 8.07 \[5.4–12.1\] | 1.3% / 0.2% | 8.08 \[4.94–13.2\] | 0.9% / 0.1% |
| SS_840.17 | &emsp;&emsp;↳ Milk allergy | 7.08 \[4.63–10.8\] | 1.1% / 0.2% | 8 \[4.44–14.4\] | 0.6% / 0.1% |
| SS_840.12 | &emsp;&emsp;↳ Seafood allergy | 6.3 \[4.33–9.17\] | 1.4% / 0.2% | 7.4 \[4.72–11.6\] | 1.1% / 0.1% |
| SS_840.2 | &emsp;↳ Allergy to insects | 13.1 \[11.4–15.2\] | 14.5% / 1.3% | 9.97 \[8.28–12\] | 7.5% / 0.8% |
| SS_840.6 | &emsp;↳ Drug and medical agent allergy | 3.37 \[3.04–3.75\] | 18.5% / 6.7% | 3.73 \[3.3–4.21\] | 13.2% / 3.9% |
| SS_840.62 | &emsp;&emsp;↳ Allergy to anesthetic agent | 5.74 \[2.67–12.3\] | 0.3% / 0.1% | 10.6 \[4.94–22.8\] | 0.4% / \<11 |
| SS_840.64 | &emsp;&emsp;↳ Allergy to analgesic agent | 3.88 \[3.03–4.98\] | 2.6% / 0.7% | 4.63 \[3.52–6.09\] | 2.4% / 0.5% |
| SS_840.65 | &emsp;&emsp;↳ Allergy to serum and vaccine | 3.45 \[1.93–6.16\] | 0.4% / 0.1% | 5.74 \[3.06–10.7\] | 0.4% / 0.1% |
| SS_840.5 | &emsp;↳ Allergy to radiographic dye | 5.55 \[3.95–7.78\] | 1.5% / 0.3% | 6.78 \[4.83–9.53\] | 1.7% / 0.3% |
| SS_840.4 | &emsp;↳ Latex allergy | 4.3 \[3.25–5.7\] | 2.1% / 0.5% | 5.32 \[3.81–7.42\] | 1.7% / 0.3% |
| SS_840.8 | &emsp;↳ Allergies related to other diseases/symptoms | 3.98 \[3.64–4.35\] | 28.4% / 9.0% | 4.01 \[3.6–4.47\] | 18.1% / 4.9% |
| GE_972 | **Genetic neuromuscular disease** | 8.05 \[6.67–9.71\] | 6.2% / 0.8% | 11.4 \[9.29–13.9\] | 6.7% / 0.6% |
| GE_972.5 | &emsp;↳ Familial dysautonomia [Riley-Day] (G90.1) | 43.6 \[30.3–62.8\] | 5.2% / 0.1% | 46.9 \[32.3–68\] | 5.6% / 0.1% |
| GE_978 | **Genetic disorders of growth and musculoskeletal system** | 27.1 \[21.1–34.8\] | 7.6% / 0.3% | 38.4 \[29.1–50.8\] | 8.3% / 0.2% |
| GE_978.2 | &emsp;↳ Hereditary connective tissue diseases | 37.5 \[28.2–49.8\] | 7.4% / 0.2% | 56.6 \[40.8–78.6\] | 8.2% / 0.1% |
| GE_978.22 | &emsp;&emsp;↳ Ehlers–Danlos syndrome | 40.8 \[30.4–54.8\] | 7.4% / 0.2% | 57.3 \[41.1–79.9\] | 8.1% / 0.1% |
| MS_712 | **Joint derangements and related disorders** | 8.5 \[7.43–9.73\] | 13.0% / 1.7% | 13.3 \[11.4–15.5\] | 13.0% / 1.0% |
| MS_712.5 | &emsp;↳ Disorder of ligament | 29 \[23.3–36.1\] | 10.0% / 0.4% | 38.7 \[30.4–49.4\] | 10.5% / 0.3% |
| MS_712.51 | &emsp;&emsp;↳ Hypermobility syndrome | 32.8 \[26.1–41.4\] | 9.9% / 0.3% | 39.9 \[31.2–51.2\] | 10.3% / 0.3% |
| MS_712.63 | &emsp;↳ Spinal instabilities | 6.69 \[3.85–11.6\] | 0.6% / 0.1% | 10.2 \[5.64–18.3\] | 0.7% / 0.1% |
| MS_712.3 | &emsp;↳ Articular cartilage disorder | 4.33 \[2.35–7.97\] | 0.4% / 0.1% | 4.23 \[2.22–8.03\] | 0.3% / 0.1% |
| NS_343 | **Disorders of autonomic nervous system** | 22.2 \[18.6–26.5\] | 12.8% / 0.6% | 24.3 \[20.1–29.2\] | 12.9% / 0.6% |
| NS_343.7 | &emsp;↳ Postural orthostatic tachycardia syndrome | 30.4 \[24.2–38.1\] | 9.5% / 0.4% | 36.4 \[28.6–46.4\] | 10.1% / 0.3% |
| NS_343.3 | &emsp;↳ Complex regional pain syndrome | 5.42 \[3.43–8.56\] | 0.8% / 0.1% | 5.1 \[3.16–8.23\] | 0.8% / 0.1% |
| SS_841 | **Adverse effect of food (not allergy)** | 27.1 \[19.9–36.8\] | 4.9% / 0.2% | 37.7 \[25–56.9\] | 3.6% / 0.1% |
| BI_179 | **Immunodeficiencies** | 5.09 \[4.34–5.98\] | 7.1% / 1.5% | 6.29 \[5.36–7.38\] | 8.0% / 1.3% |
| BI_179.7 | &emsp;↳ Common variable immunodeficiency | 18.4 \[10–33.5\] | 1.0% / 0.1% | 19 \[10.7–33.7\] | 1.2% / 0.1% |
| BI_179.6 | &emsp;↳ Selective deficiency of IgG subclasses | 12.7 \[6.56–24.7\] | 0.6% / 0.0% | 12.6 \[6.63–23.9\] | 0.6% / 0.0% |
| BI_179.1 | &emsp;↳ Hypogammaglobulinemia NOS | 10.3 \[7.15–14.7\] | 1.9% / 0.2% | 10.3 \[7.2–14.8\] | 2.0% / 0.2% |
| BI_179.4 | &emsp;↳ Selective IgA deficiency | 8.75 \[5–15.3\] | 0.6% / 0.1% | 13.2 \[6.1–28.5\] | 0.4% / \<11 |
| BI_179.9 | &emsp;↳ Immunodeficiency NOS | 4.23 \[3.38–5.28\] | 3.4% / 0.8% | 5.29 \[4.24–6.61\] | 3.8% / 0.7% |
| GE_981 | **Other genetic diseases (arbitrary group 1)** | 9.03 \[4.99–16.3\] | 0.5% / 0.1% | 16.7 \[9.07–30.6\] | 0.9% / 0.1% |
| GE_981.1 | &emsp;↳ Alpha-1-antitrypsin deficiency | 15.9 \[8.05–31.6\] | 0.5% / \<11 | 22.3 \[11.7–42.7\] | 0.8% / \<11 |
| GI_522.5 | **Allergic and dietetic gastroenteritis and colitis** | 14.9 \[7.42–29.8\] | 0.5% / 0.0% | 22.4 \[9.4–53.6\] | 0.4% / \<11 |
| GI_532 | **Other disorders of the intestines** | 3.27 \[2.65–4.02\] | 3.6% / 1.1% | 3.95 \[3.11–5.01\] | 2.9% / 0.7% |
| GI_532.5 | &emsp;↳ Small intestinal bacterial overgrowth | 12.2 \[8.03–18.5\] | 1.6% / 0.1% | 13 \[8.07–20.9\] | 1.4% / 0.1% |
| BI_171.7 | **Eosinophilia** | 17.1 \[12–24.5\] | 2.5% / 0.2% | 11.3 \[7.14–17.9\] | 1.2% / 0.1% |
| MS_700 | **Diffuse diseases of connective tissue** | 4.2 \[3.59–4.92\] | 6.9% / 1.7% | 4.77 \[4.02–5.67\] | 6.3% / 1.2% |
| MS_700.6 | &emsp;↳ Autoinflammatory syndromes | 11.2 \[5.99–21.1\] | 0.6% / 0.0% | 30.3 \[13.1–70\] | 0.6% / \<11 |
| MS_700.2 | &emsp;↳ Sicca syndrome [Sjogren syndrome] | 4.79 \[3.68–6.23\] | 2.5% / 0.5% | 6.06 \[4.6–7.97\] | 2.7% / 0.4% |
| CM_750 | **Congenital malformations of nervous system** | 11.2 \[9.05–13.8\] | 5.8% / 0.6% | 18.1 \[14.2–23.1\] | 6.2% / 0.3% |
| GI_522.6 | **Eosinophilic gastroenteritis and colitis** | 11 \[8.01–15.1\] | 2.5% / 0.2% | 15.1 \[10.9–20.9\] | 3.0% / 0.2% |
| GI_522.61 | &emsp;↳ Eosinophilic esophagitis | 10.5 \[7.6–14.6\] | 2.3% / 0.2% | 13.9 \[9.96–19.5\] | 2.7% / 0.2% |
| DE_679 | **Skin symptoms** | 6.86 \[6.25–7.52\] | 31.4% / 6.3% | 5.11 \[4.55–5.75\] | 16.3% / 3.5% |
| DE_679.3 | &emsp;↳ Flushing | 13.2 \[11–15.9\] | 8.5% / 0.7% | 9.26 \[7.3–11.7\] | 4.5% / 0.4% |
| DE_679.4 | &emsp;↳ Pruritus | 7.11 \[6.03–8.39\] | 7.9% / 1.2% | 6.11 \[4.96–7.53\] | 4.7% / 0.8% |
| DE_679.1 | &emsp;↳ Rash and other nonspecific skin eruption | 5.25 \[4.65–5.91\] | 14.7% / 3.1% | 3.52 \[2.98–4.16\] | 6.3% / 1.7% |
| DE_668.6 | **Prurigo** | 7.64 \[4.51–13\] | 0.7% / 0.1% | 8.99 \[4.99–16.2\] | 0.6% / 0.1% |
| CV_443.2 | **Celiac artery compression syndrome** | 7.45 \[4.05–13.7\] | 0.5% / 0.1% | 12.5 \[6.17–25.4\] | 0.5% / \<11 |
| SS_847.3 | **Liver transplant** | 7.45 \[4.31–12.9\] | 0.6% / 0.1% | 7.76 \[4.57–13.2\] | 0.7% / 0.1% |
| EM_211 | **Disorders of adrenal glands** | 3.66 \[2.94–4.56\] | 3.3% / 0.9% | 4.15 \[3.26–5.29\] | 2.9% / 0.6% |
| EM_211.1 | &emsp;↳ Adrenal hyperfunction | 5.35 \[3.45–8.3\] | 0.9% / 0.2% | 5.96 \[3.49–10.2\] | 0.7% / 0.1% |
| EM_211.13 | &emsp;&emsp;↳ Cushing's syndrome | 7.44 \[3.96–14\] | 0.5% / 0.1% | 7.76 \[3.74–16.1\] | 0.4% / \<11 |
| EM_211.11 | &emsp;&emsp;↳ Hyperaldosteronism | 5.61 \[2.92–10.8\] | 0.3% / 0.1% | 4.35 \[2.11–8.98\] | \<11 / 0.1% |
| EM_211.2 | &emsp;↳ Adrenocortical insufficiency [Addison's disease] | 5.82 \[4.23–8.01\] | 1.8% / 0.3% | 6.22 \[4.54–8.52\] | 2.0% / 0.3% |
| RE_463 | **Rhinitis and nasal congestion** | 3.59 \[3.31–3.9\] | 36.1% / 13.4% | 3.85 \[3.49–4.25\] | 23.8% / 7.2% |
| RE_463.1 | &emsp;↳ Chronic rhinitis | 7.07 \[5.91–8.45\] | 6.6% / 1.0% | 9.86 \[7.87–12.4\] | 5.1% / 0.5% |
| RE_463.2 | &emsp;↳ Allergic rhinitis | 3.53 \[3.21–3.87\] | 23.7% / 8.0% | 3.54 \[3.16–3.97\] | 14.9% / 4.4% |
| RE_463.23 | &emsp;&emsp;↳ Allergic rhinitis, due to animal hair and dander | 6.59 \[4.67–9.31\] | 1.6% / 0.2% | 9.38 \[6.25–14.1\] | 1.5% / 0.1% |
| RE_463.3 | &emsp;↳ Vasomotor rhinitis | 4.89 \[2.71–8.84\] | 0.5% / 0.1% | 6.43 \[3.77–11\] | 0.6% / 0.1% |
| NS_344 | **Disorders of the circulation of the cerebrospinal fluid** | 3.18 \[2.31–4.39\] | 1.4% / 0.4% | 3.58 \[2.58–4.97\] | 1.5% / 0.4% |
| NS_344.3 | &emsp;↳ Cerebrospinal fluid leak | 7.04 \[3.82–13\] | 0.5% / 0.1% | 15.8 \[7.37–33.8\] | 0.5% / \<11 |
| NS_344.2 | &emsp;↳ Benign intracranial hypertension | 3.7 \[2.33–5.89\] | 0.7% / 0.2% | 4.31 \[2.77–6.71\] | 0.9% / 0.2% |
| GE_962 | **Disorders of amino-acid transport and metabolism** | 3.15 \[1.91–5.22\] | 0.6% / 0.2% | 4.07 \[2.42–6.83\] | 0.6% / 0.1% |
| GE_962.4 | &emsp;↳ Disturbances of sulphur-bearing amino-acid metabolism | 6.65 \[3.27–13.5\] | 0.4% / 0.1% | 8.16 \[4.25–15.7\] | 0.5% / 0.0% |
| SS_807.3 | **Post COVID-19 condition** | 6.4 \[4.82–8.49\] | 2.4% / 0.4% | 12.2 \[8.52–17.6\] | 2.2% / 0.2% |
| ID_020 | **Borrelia** | 6.13 \[3.75–10\] | 0.8% / 0.1% | 6.41 \[3.62–11.4\] | 0.5% / 0.1% |
| ID_020.1 | &emsp;↳ Lyme disease | 4.55 \[2.63–7.87\] | 0.5% / 0.1% | 4.88 \[2.5–9.54\] | 0.3% / 0.1% |
| GU_625.3 | **Vulvodynia** | 6.01 \[3.24–11.1\] | 0.4% / 0.1% | 7.73 \[3.73–16\] | 0.4% / \<11 |
| CA_101.6 | **Malignant neoplasm of the liver and intrahepatic bile ducts** | 5.08 \[2.86–9.03\] | 0.5% / 0.1% | 4.35 \[2.45–7.75\] | 0.5% / 0.1% |
| CA_101.61 | &emsp;↳ Malignant neoplasm of the liver | 6.74 \[3.61–12.6\] | 0.5% / 0.1% | 5.93 \[3.17–11.1\] | 0.4% / 0.1% |
| DE_672.1 | **Acute skin changes due to ultraviolet radiation** | 6.26 \[3.56–11\] | 0.6% / 0.1% | 5.9 \[2.74–12.7\] | 0.3% / 0.0% |
| GI_525 | **Intestinal malabsorption** | 5.83 \[4.9–6.93\] | 6.5% / 1.1% | 6.93 \[5.65–8.49\] | 5.2% / 0.7% |
| GI_525.1 | &emsp;↳ Celiac disease | 5.35 \[4–7.15\] | 2.1% / 0.4% | 6.24 \[4.46–8.73\] | 1.8% / 0.3% |
| DE_668.4 | **Dermatitis due to substances taken internally** | 5.69 \[3.69–8.77\] | 1.0% / 0.2% | 5.71 \[3.16–10.3\] | 0.5% / 0.1% |
| NS_333.7 | **Narcolepsy** | 5.52 \[3.57–8.53\] | 0.9% / 0.1% | 6.88 \[4.17–11.3\] | 0.8% / 0.1% |
| SS_807.1 | **Chronic fatigue syndrome** | 5.46 \[4.71–6.32\] | 9.0% / 1.7% | 6.53 \[5.45–7.83\] | 6.5% / 0.9% |
| RE_472 | **Diseases of vocal cords and larynx, not elsewhere classified** | 5.32 \[4.15–6.81\] | 2.9% / 0.5% | 5.65 \[4.2–7.59\] | 2.2% / 0.4% |
| RE_472.4 | &emsp;↳ Laryngeal spasm | 7.06 \[3.53–14.1\] | 0.3% / 0.0% | 4.97 \[2.33–10.6\] | \<11 / 0.0% |
| GI_516 | **Other diseases of stomach and duodenum** | 3.95 \[3.31–4.72\] | 5.5% / 1.5% | 5.56 \[4.61–6.72\] | 5.6% / 0.9% |
| GI_516.4 | &emsp;↳ Gastroparesis | 5.3 \[4.17–6.75\] | 3.2% / 0.6% | 7.25 \[5.67–9.28\] | 3.7% / 0.4% |
| GI_510.5 | **Dyskinesia of esophagus** | 5.07 \[3.36–7.63\] | 1.0% / 0.2% | 6.63 \[4.27–10.3\] | 1.1% / 0.2% |
| SO_367.12 | **Allergic conjunctivitis** | 4.88 \[3.74–6.37\] | 2.4% / 0.5% | 7.97 \[5.68–11.2\] | 2.0% / 0.2% |
| GI_552.1 | **Cholangitis** | 5.31 \[2.76–10.2\] | 0.4% / 0.1% | 4.74 \[2.44–9.21\] | 0.4% / 0.1% |
| CV_446.2 | **Orthostatic hypotension** | 5.12 \[4.15–6.31\] | 4.1% / 0.8% | 4.7 \[3.69–5.97\] | 3.1% / 0.7% |
| SS_826 | **Other abnormal immunological findings in serum** | 4.27 \[3.68–4.95\] | 8.0% / 1.9% | 5.03 \[4.18–6.05\] | 5.5% / 1.0% |
| SS_826.4 | &emsp;↳ Other and unspecified nonspecific immunological findings | 4.66 \[3.99–5.45\] | 7.4% / 1.6% | 5.14 \[4.21–6.27\] | 4.7% / 0.9% |
| NS_335 | **Nerve root and plexus disorders** | 3.19 \[2.13–4.77\] | 0.9% / 0.3% | 4.63 \[3.05–7.02\] | 1.0% / 0.2% |
| NS_335.1 | &emsp;↳ Nerve plexus lesions | 4.64 \[2.9–7.43\] | 0.7% / 0.2% | 6.08 \[3.65–10.1\] | 0.8% / 0.1% |
| NS_324.33 | **Fasciculation** | 9.22 \[5.4–15.7\] | 0.8% / 0.1% | 4.48 \[2.27–8.84\] | 0.4% / 0.1% |
| GI_529.2 | **Flatulence, eructation, and gas pain** | 4.36 \[3.78–5.02\] | 8.8% / 2.1% | 4.37 \[3.63–5.25\] | 5.3% / 1.1% |
| CV_448.1 | **Raynaud's syndrome** | 4.33 \[3.37–5.57\] | 2.7% / 0.6% | 4.92 \[3.71–6.52\] | 2.3% / 0.4% |
| NS_334.1 | **Trigeminal nerve disorders [CN5]** | 4.3 \[3.04–6.09\] | 1.3% / 0.3% | 4.43 \[2.94–6.66\] | 1.0% / 0.2% |
| NS_334.11 | &emsp;↳ Trigeminal neuralgia | 4.18 \[2.75–6.35\] | 0.9% / 0.2% | 3.77 \[2.37–6.01\] | 0.7% / 0.2% |
| DE_685 | **Disorders of sweat glands** | 4.01 \[3.2–5.02\] | 3.3% / 0.8% | 4.08 \[3.07–5.41\] | 2.1% / 0.5% |
| DE_685.8 | &emsp;↳ Hyperhidrosis | 4.27 \[3.33–5.48\] | 2.7% / 0.6% | 4.09 \[2.99–5.61\] | 1.7% / 0.4% |
| DE_685.82 | &emsp;&emsp;↳ Generalized hyperhidrosis | 4.53 \[3.52–5.85\] | 2.7% / 0.6% | 4.24 \[3.08–5.84\] | 1.7% / 0.4% |
| EM_230.5 | **Early satiety** | 4.19 \[2.99–5.86\] | 1.4% / 0.3% | 4.64 \[3.07–7\] | 1.1% / 0.2% |
| RE_481.1 | **Pulmonary eosinophilia** | 4.44 \[2.17–9.1\] | \<11 / 0.1% | 4.17 \[1.93–9\] | \<11 / 0.0% |
| GI_524 | **Functional intestinal disorder** | 4.16 \[3.66–4.73\] | 11.1% / 2.8% | 4.68 \[4.02–5.45\] | 8.4% / 1.7% |
| GI_524.1 | &emsp;↳ Irritable bowel syndrome | 3.91 \[3.42–4.47\] | 9.9% / 2.6% | 4.45 \[3.8–5.22\] | 7.6% / 1.6% |
| SS_835 | **Cytology and pathology findings** | 4.16 \[3.17–5.45\] | 2.3% / 0.5% | 4.95 \[3.55–6.92\] | 1.6% / 0.3% |
| RE_471.5 | **Nasal polyps** | 4.06 \[2.6–6.35\] | 0.8% / 0.2% | 7.04 \[4.36–11.4\] | 0.9% / 0.1% |
| MS_717.3 | **Occipital neuralgia** | 3.96 \[2.85–5.5\] | 1.5% / 0.4% | 5.33 \[3.74–7.59\] | 1.5% / 0.2% |
| GI_527.3 | **Functional dyspepsia** | 3.92 \[2.75–5.59\] | 1.3% / 0.3% | 6.46 \[4.21–9.92\] | 1.1% / 0.2% |
| GI_506.5 | **Disturbances of salivary secretion** | 3.82 \[2.73–5.34\] | 1.4% / 0.4% | 4.27 \[2.91–6.27\] | 1.1% / 0.2% |
| GI_506.51 | &emsp;↳ Dry mouth | 3.92 \[2.6–5.9\] | 0.9% / 0.2% | 5.4 \[3.43–8.53\] | 0.8% / 0.1% |
| NS_337.2 | **Inflammatory polyneuropathy** | 3.53 \[1.98–6.29\] | 0.4% / 0.1% | 3.9 \[2.07–7.35\] | 0.4% / 0.1% |
| NS_337.22 | &emsp;↳ Chronic inflammatory demyelinating polyneuritis | 3.83 \[1.72–8.55\] | \<11 / 0.1% | 5.98 \[2.49–14.4\] | \<11 / 0.0% |
| GI_522.8 | **Duodenitis** | 3.83 \[2.25–6.5\] | 0.5% / 0.2% | 4.98 \[2.74–9.06\] | 0.4% / 0.1% |
| NS_321 | **Encephalitis, myelitis and encephalomyelitis** | 3.82 \[2.04–7.15\] | 0.3% / 0.1% | 4.79 \[2.49–9.2\] | 0.3% / 0.1% |
| GI_507.11 | **Recurrent oral aphthae [Recurrent aphthous stomatitis]** | 7.29 \[3.97–13.4\] | 0.5% / 0.1% | 3.79 \[1.84–7.81\] | \<11 / 0.1% |
| MS_724.1 | **Myalgia** | 3.77 \[3.39–4.2\] | 17.3% / 5.3% | 4.21 \[3.73–4.75\] | 13.9% / 3.4% |
| GU_592.12 | **Chronic cystitis** | 3.73 \[2.71–5.14\] | 1.5% / 0.4% | 4.74 \[3.22–6.98\] | 1.2% / 0.2% |
| ID_052.4 | **Infectious mononucleosis** | 3.65 \[2.15–6.22\] | 0.5% / 0.1% | 6.82 \[3.17–14.7\] | 0.4% / 0.0% |
| NS_350.3 | **Abnormal reflex** | 3.63 \[2.18–6.05\] | 0.6% / 0.2% | 4.2 \[2.17–8.12\] | 0.4% / 0.1% |
| RE_494 | **Voice disturbance** | 3.34 \[2.63–4.23\] | 2.7% / 0.9% | 4.29 \[3.29–5.6\] | 2.4% / 0.5% |
| RE_494.1 | &emsp;↳ Dysphonia | 3.6 \[2.79–4.64\] | 2.4% / 0.7% | 4.72 \[3.58–6.22\] | 2.3% / 0.5% |
| MB_291 | **Dissociative and somatoform disorders** | 3.17 \[2.34–4.31\] | 1.6% / 0.5% | 3.86 \[2.79–5.33\] | 1.6% / 0.4% |
| MB_291.1 | &emsp;↳ Conversion disorder | 3.53 \[2.2–5.66\] | 0.7% / 0.2% | 4.62 \[2.98–7.16\] | 0.9% / 0.2% |
| NS_331.63 | **Menstrual migraine** | 4.08 \[2.3–7.23\] | 0.4% / 0.1% | 3.51 \[1.84–6.7\] | 0.3% / 0.1% |
| DE_668.3 | **Contact dermatitis** | 3.48 \[2.78–4.35\] | 3.1% / 0.9% | 4.89 \[3.74–6.4\] | 2.6% / 0.5% |
| NS_331.61 | **Migraine with aura** | 3.48 \[2.95–4.1\] | 6.0% / 1.7% | 3.89 \[3.24–4.67\] | 5.3% / 1.2% |
| GI_522.14 | **Microscopic colitis** | 3.47 \[2.22–5.43\] | 0.7% / 0.2% | 4.52 \[2.77–7.36\] | 0.6% / 0.1% |
| NS_331.64 | **Chronic migraine without aura** | 3.45 \[2.91–4.09\] | 5.6% / 1.5% | 3.68 \[3.07–4.41\] | 5.3% / 1.3% |
| EM_247.71 | **Hemochromatosis** | 3.44 \[2.1–5.64\] | 0.6% / 0.2% | 3.99 \[2.38–6.68\] | 0.6% / 0.2% |
| EM_252.51 | **Disorders of intestinal carbohydrate absorption** | 3.41 \[2.2–5.29\] | 0.8% / 0.2% | 4.38 \[2.53–7.57\] | 0.6% / 0.1% |
| MS_741.4 | **Sprains and strains of hip and thigh** | 3.41 \[2.29–5.09\] | 1.0% / 0.3% | 4.87 \[2.9–8.17\] | 0.7% / 0.1% |
| BI_168.3 | **Spontaneous ecchymoses** | 3.38 \[2.29–4.98\] | 1.0% / 0.3% | 3.76 \[2.28–6.2\] | 0.6% / 0.1% |
| ID_052.5 | **Cytomegalovirus [CMV]** | 3.34 \[1.73–6.44\] | 0.3% / 0.1% | 8.58 \[4.12–17.9\] | 0.3% / 0.0% |
| NS_331.3 | **Headache syndromes, non migraine** | 3.32 \[2.66–4.16\] | 3.1% / 0.9% | 3.92 \[3.02–5.09\] | 2.5% / 0.5% |
| GI_554.3 | **Exocrine pancreatic insufficiency** | 3.32 \[1.67–6.58\] | 0.3% / 0.1% | 6.78 \[3.56–12.9\] | 0.4% / 0.1% |
| GE_967 | **Genetic disorders of vitamin and mineral metabolism** | 3.07 \[1.74–5.41\] | 0.4% / 0.2% | 5.14 \[2.98–8.87\] | 0.6% / 0.1% |
| GE_967.4 | &emsp;↳ Hereditary hemochromatosis | 3.3 \[1.8–6.07\] | 0.4% / 0.1% | 4.01 \[2.26–7.1\] | 0.4% / 0.1% |
| NS_331.4 | **Cluster headaches** | 3.27 \[1.86–5.72\] | 0.5% / 0.1% | 5.62 \[2.68–11.8\] | 0.3% / 0.1% |
| SS_829.2 | **Abnormal level of blood mineral** | 3.26 \[2.34–4.53\] | 1.4% / 0.4% | 3.66 \[2.57–5.22\] | 1.3% / 0.3% |
| GE_982 | **Genetic susceptibility of disease, NOS** | 3.23 \[2.46–4.23\] | 2.1% / 0.6% | 4.33 \[3.26–5.74\] | 2.2% / 0.4% |
| RE_477 | **Inhalation lung injury** | 3.2 \[1.62–6.29\] | \<11 / 0.1% | 3.79 \[1.78–8.08\] | \<11 / 0.1% |
| GU_615 | **Endometriosis** | 3.16 \[2.43–4.11\] | 2.2% / 0.7% | 3.76 \[2.76–5.12\] | 1.7% / 0.4% |
| CM_768 | **Congenital deformities of chest and bony thorax** | 3.16 \[1.61–6.2\] | \<11 / 0.1% | 4.3 \[1.97–9.4\] | \<11 / 0.0% |
| CV_417.1 | **Palpitations** | 3.13 \[2.82–3.48\] | 15.9% / 5.6% | 3.58 \[3.14–4.08\] | 10.4% / 2.9% |
| SO_395 | **Other diseases of inner ear** | 3.07 \[1.54–6.08\] | \<11 / 0.1% | 3.92 \[1.89–8.14\] | \<11 / 0.1% |
| RE_475 | **Asthma** | 3.06 \[2.82–3.33\] | 27.8% / 10.9% | 3.59 \[3.26–3.94\] | 22.9% / 7.2% |
| DE_668.1 | **Atopic dermatitis** | 3.05 \[2.49–3.74\] | 3.7% / 1.4% | 4.55 \[3.59–5.77\] | 3.1% / 0.7% |
| DE_668.5 | **Lichen simplex chronicus** | 3.02 \[1.57–5.82\] | 0.3% / 0.1% | 3.59 \[1.59–8.07\] | \<11 / 0.0% |
| NS_333.4 | **Circadian rhythm sleep disorder** | 2.98 \[1.86–4.78\] | 0.6% / 0.2% | 4.28 \[2.39–7.67\] | 0.4% / 0.1% |
| BI_174.2 | **Splenomegaly** | 2.96 \[2.12–4.14\] | 1.3% / 0.4% | 5.77 \[3.77–8.84\] | 1.0% / 0.2% |

Percentages are phecode cases (code on ≥ 2 dates) over the patients analysed for that phecode; \<11 = 1–10 patients, masked. GE_972.5 is a single code, G90.1 (familial dysautonomia, Riley–Day syndrome), a rare inherited disease: in 5.2% of HaT patients it is almost certainly G90.1 used for dysautonomia in general (G90.A for POTS exists only from October 2022), and it is read with NS_343.

**Lower in HaT in both windows** (19 phecodes; strongest 5, OR pre / post): stimulant use disorders 0.20 / 0.16; stimulant abuse or dependence 0.18 / 0.21; permanent atrial fibrillation 0.33 / 0.33; secondary malignant neoplasm 0.29 / 0.41; persistent atrial fibrillation 0.46 / 0.47.

### 6.4 Lower in HaT (FDR \< 0.05, top 5)

| Pre-index | OR \[95% CI\] | Post-index | OR \[95% CI\] |
|------------------|------------------|------------------|------------------|
| Current tobacco use | 0.584 \[0.505–0.677\] | Current tobacco use | 0.575 \[0.478–0.691\] |
| Fractures | 0.663 \[0.578–0.761\] | Secondary malignant neoplasm | 0.409 \[0.268–0.626\] |
| Secondary malignant neoplasm | 0.29 \[0.185–0.457\] | Psychoactive substance abuse | 0.461 \[0.301–0.706\] |
| Nicotine dependence | 0.776 \[0.703–0.857\] | Diabetes mellitus | 0.821 \[0.733–0.919\] |
| Hypertension | 0.799 \[0.730–0.874\] | Alcohol abuse and dependence | 0.472 \[0.302–0.737\] |

### 6.5 Verification against pyPheWAS

|   | Pre | Post |
|------------------------|------------------------|------------------------|
| Phecodes in both / same direction | 978 / 978 | 933 / 933 |
| Median absolute beta difference | 0.0067 | 0.0082 |
| Correlation of betas, all | 0.744 | 0.783 |
| Separated phecodes (absolute beta \> 10 in either) | 26 | 32 |
| Correlation excluding separated; max abs difference | **0.999**; 0.201 | **0.999**; 0.412 |

The lower overall correlation arises solely from separated phecodes, where unpenalized ML estimates diverge and pyPheWAS's L1 penalty shrinks them toward zero. The largest non-separated differences (0.20 pre, 0.41 post, in log-odds) are at large effects, where the L1 penalty shrinks most.

**What this does and does not show.** It verifies the computation: phecode mapping, case counting, covariate handling and model fitting give the same answers in two independent implementations. It does **not** validate the study's own results directly, because the comparison is run under pyPheWAS's rules (Phecode 1.2 map, 1 code makes a case, no exclusions, no Firth). The study's phecodeX analysis, with its stricter case definition and exclusions, is a different analysis by design; its correctness rests on the same code paths verified here plus the tool's self-tests.

## 7. Interpretation

1.  **Face validity.** The leading phenotypes (urticaria and flushing, anaphylaxis, insect and food allergy, dysautonomia/POTS, joint hypermobility, rhinitis/asthma, abdominal pain) match the multisystem phenotype described for HaT.
2.  **Indication, not causation, in the pre-index window.** HaT is diagnosed by testing, prompted by these symptoms; the very large pre-index odds ratios (20–60) largely reflect selection into testing. The pre-index results describe the phenotype preceding diagnosis.
3.  **Persistence after diagnosis.** Most leading phenotypes recur after index with similar or larger effects, arguing against purely transient workup. Shifts are as expected: tryptase-abnormal codes fall after diagnosis (testing precedes it), MCAS codes rise (coded in follow-up care), and Ehlers–Danlos codes are already common before index (GE_978.22: 7.4% of HaT vs 0.2% of controls, OR 40.8) and somewhat stronger after (OR 57.3).
4.  **Breadth and direction.** 47% (pre) and 54% (post) of tested phecodes are FDR-significant, and \> 90% of those are higher in HaT. Beyond true phenotype, this indicates residual differences in healthcare intensity not captured by one year of office visits (specialist evaluation, testing cascades).

## 8. Criticisms and Limitations

Every weakness we can identify, so reviewers can weigh the results against them. Each item gives the problem, the likely direction of bias, what the study does now, and what would address it. Items marked **(major)** could change the main conclusions.

### 8.1 Design and bias

1.  **Indication (protopathic) bias in the pre-index window (major).** HaT is diagnosed because symptomatic patients are tested; the 3 years before index are, for cases, the period of symptoms and workup that led to testing. *Bias:* away from the null, very large. *Now:* framed as "phenotype preceding diagnosis", not effects of HaT; post-index window as a check. *Remedy:* cannot be removed in this design; a population with systematic testing (e.g. genotyped biobank) would be needed for causal claims.
2.  **Asymmetric index events (major).** A case's index is a diagnostic event, often at a specialist after a workup; a control's is a random office visit. The windows on either side of these anchors are not exchangeable: cases' pre-index windows are dense with evaluation, controls' are ordinary care. *Bias:* away from the null, broadly. *Now:* index day excluded; utilization matched on prior-year office visits. *Remedy:* anchor controls on a comparable evaluative encounter (e.g. an allergy/immunology visit), or lag the pre-index window (e.g. exclude the 6–12 months before index).
3.  **Health-system and referral confounding (major).** HaT is diagnosed mainly at centres with mast-cell expertise; cases are therefore concentrated in particular health systems with their own coding practices and specialist density, while controls are drawn at random across Cosmos. Health system, region and payer are **not** matched or adjusted. *Bias:* unpredictable, potentially large for coding-sensitive phecodes. *Remedy:* match or stratify on health system (or at least region), or restrict controls to the systems that diagnose HaT.
4.  **Residual healthcare-intensity confounding (major).** Matching on office/follow-up visit days in the year before index does not capture specialist visits, ED use, testing intensity, or the 3-year window. *Evidence:* 91–98% of significant phecodes are higher in HaT, including many with no known link to HaT. *Bias:* away from the null, broad. *Remedy:* adjust or match on specialist and ED visits, or on diagnosis counts from outside the analysis window; use negative-control outcomes to calibrate the background excess.
5.  **Control misclassification.** Controls are not genotyped; HaT affects an estimated 4–6% of the population and is under-diagnosed, so some controls have HaT. *Bias:* toward the null, modest and non-differential. *Remedy:* exclude controls with elevated baseline tryptase (few have one measured); accept as a stated limitation.
6.  **Case misclassification.** A D89.44 diagnosis requires a genetic test, so one code is taken as a case; a code entered in error or as a rule-out remains possible, and genetic results are not in the data. Treated as negligible. *Bias:* toward the null, if any. *Now:* status filter for ruled-out/error codes. *Check:* the share of cases with a baseline tryptase ≥ 8 ng/mL (pending).
7.  **The diagnosis-status filter is unverified on the real data.** Statuses containing "rule", "error", "delete" or "cancel" are dropped, but the actual status values in Cosmos (listed in the build reports) have not yet been reviewed. *Effect:* if real spellings differ, rule-out codes may remain as diagnoses (or valid ones may be dropped). *Remedy:* review `hat_group_report.txt` and `control_group_report.txt` before final analysis.
8.  **Selection by eligibility.** 29% of HaT patients fail the prior-utilization rule and 119 indexed before October 2021 are excluded; results describe HaT patients engaged in care before diagnosis, diagnosed after the code existed. *Remedy:* report characteristics of excluded cases; a sensitivity analysis with a relaxed utilization rule.
9.  **Calendar and code-introduction effects.** D89.44 exists only from October 2021; earlier HaT diagnoses carry other codes (D89.40/D89.49), so some "controls" and some cases' histories may contain HaT under other codes. *Effect:* exposure-adjacent contamination of outcomes (see 8.3.2) and possible earlier true index. *Remedy:* report earlier D89.4x codes among cases (recorded by the builder); treat D89.4x as exposure-adjacent.
10. **Population differences not modelled.** \~75% of cases are female; socioeconomic status, insurance and region are unmeasured. Lower tobacco, substance use, diabetes and hypertension in HaT are more plausibly residual confounding than protection.
11. **Control pool representativeness.** Controls are a hash-based \~1% sample of Cosmos patients with a clinic visit from October 2021, capped at 300,000. The sample is reproducible and not obviously biased, but its representativeness of Cosmos has not been checked against Cosmos-wide distributions.
12. **A mastocytosis subgroup among the cases.** HaT is enriched in systemic mastocytosis, and mastocytosis patients are tested for HaT, so the cases may include patients whose primary disease is clonal mast-cell disease (§6.2). Mastocytosis independently causes anaphylaxis, severe venom reactions, flushing and osteoporosis. *Counts* (matched cases, 3 years before index to end of observation): 1,180 (30.2%) with D47.0x or C96.2x, against 21 controls; by code, D47.09 1,028, D47.02 359, D47.01 201, C96.2x 47 (patients can have several); D89.41 (monoclonal MCAS) 47. That most are D47.09 suggests it is often used for mast-cell disorders generally rather than confirmed clonal disease (§10, clinical 1). *Does it drive the phenotype?* Codes on ≥ 1 date in the 3 years before index, cases with a mastocytosis code / cases without / controls: urticaria 41.3% / 29.9% / 2.2%; anaphylaxis 22.6% / 15.1% / 0.6%; flushing 18.6% / 11.1% / 1.7%; POTS 15.8% / 10.2% / 0.5%; hypermobility/EDS 16.2% / 10.5% / 0.5%; fractures 9.9% / 9.1% / 12.0%. The coded cases are higher on every phenotype, including POTS and hypermobility, which are not features of mastocytosis, so they look more intensively evaluated rather than distinct; cases without the codes keep the whole phenotype, and fractures show no excess. *Bias:* modest, away from the null for the mediator phenotypes. *Remedy:* a sensitivity analysis excluding cases with D47.0x or C96.2x (and possibly D89.41, monoclonal MCAS); reporting HaT without mastocytosis as the main phenotype.

### 8.2 Matching

1.  **The outcome model ignores the matched design (major for inference).** Unconditional, unweighted logistic regression on the matched cohort (D13): sets with 1 to 10 controls contribute unequally, MatchIt's weights are not used, and within-set correlation is not modelled. *Effect:* estimates are for a population weighted toward cases with many controls; standard errors may be mis-stated. *Remedy:* conditional logistic regression on matched sets, or weighted regression with cluster-robust SEs by set; at minimum, compare.
2.  **Variable ratio.** 342 cases have 1 control, 2,210 have 10. Cases who matched poorly (crowded quarters) are represented by few controls. *Remedy:* as 8.2.1; report results restricted to full 10:1 sets.
3.  **Caliper scale.** 0.2 SD of the propensity score on the probability scale, not the logit of the propensity score as Austin (2011)[^3] recommends. With small propensities, the probability-scale caliper is tighter in some regions and looser in others. *Remedy:* refit with `link = "linear.logit"`; compare balance and unmatched counts.
4.  **Propensity model specification.** Main effects only, linear in age and record length; no interactions. Balance was checked on means (SMD) only, not on variances or distributions beyond MatchIt's summary. *Remedy:* report variance ratios and eCDF statistics (available in the MatchIt log); add splines if imbalance appears.
5.  **Imperfect balance on follow-up.** YearsAfterIndex SMD 0.102; adjusted in the post-index model only (D40).
6.  **Pair-level differences.** Std. pair distances are large (e.g. age 1.25 SD): group means balance, individual pairs do not. Acceptable for group comparison with regression adjustment, but relevant if conditional analysis is adopted.

[^3]: Austin PC. Optimal caliper widths for propensity-score matching when estimating differences in means and differences in proportions in observational studies. *Pharmaceutical Statistics* 2011;10(2):150–161. From simulations, it recommends a caliper of 0.2 standard deviations of the logit of the propensity score. MatchIt applies `caliper = 0.2, std.caliper = TRUE` to the distance as estimated (the probability, with `distance = "glm"`) unless `link = "linear.logit"` is given.

### 8.3 Outcomes

1.  **Unequal observation time.** The pre-index window is nominally 3 years, but patients with less than 3 years of prior record get a truncated window (adjusted only through `YearsBeforeIndex`). The post-index window varies with follow-up (adjusted through `YearsAfterIndex`). Logistic regression on "ever coded" does not model time at risk. *Remedy:* require ≥ 3 years of prior observation; for post, model rates (Poisson/negative binomial with an offset) or fix the window length.
2.  **Exposure-adjacent outcomes (major for presentation).** MCAS (D89.40–D89.49), raised tryptase (R74.8) and mastocytosis (D47.0x, C96.2x) codes lead the results; they are part of the diagnostic pathway, not independent phenotypes. *Remedy:* planned sensitivity analysis removing them; report separately.
3.  **Phecode hierarchy.** Child phecodes roll up into parents, so parent and child hits share patients; 482 or 863 significant phecodes are far fewer distinct findings. *Remedy:* report leaf-level or collapsed results; cluster related phecodes.
4.  **Two-date case rule and exclusions.** A phecode case needs codes on 2+ dates; 1-date patients are excluded from that phecode's analysis. phecodeX has no related-phecode exclusions, so a phecode's controls can include patients with a closely related phecode (e.g. other autonomic disorders among the controls for POTS), which biases toward the null. Sex-specific phecodes were not restricted to one sex in this run (§5). Because of the 1-date exclusion, each phecode's denominator differs, and the excluded share can differ between groups.
5.  **Coding, not disease.** Outcomes are billing codes; differences in coding thoroughness between specialist and primary care settings translate directly into "associations".

### 8.4 Statistics

1.  **Odds ratios exaggerate risk ratios for common outcomes.** Several phecodes are common (allergy: 6,803 cases, \~21% of the cohort); ORs overstate relative risks there. *Remedy:* report absolute prevalences in each group, or risk ratios for common phecodes.
2.  **Firth fits for 26–29% of tested phecodes.** These report Wald intervals with penalized likelihood-ratio p-values, which can disagree; profile-likelihood intervals would be consistent. Some separation arises from sparse covariate levels (small race/ethnicity groups) rather than the exposure.
3.  **Multiplicity under dependence.** Bonferroni is very conservative with correlated phecodes; BH assumes positive dependence (likely acceptable). Hierarchical FDR would match the structure better.
4.  **Extreme p-values.** Many underflow (q \< 1e-300); they carry no ranking information. Effect sizes and intervals should be the basis of interpretation.
5.  **Winner's curse.** Effect sizes for the top hits are selected for being extreme and will tend to shrink on replication.
6.  **No replication.** A single discovery analysis; no independent cohort, held-out sample, or negative-control outcomes yet.

### 8.5 Data and implementation

1.  **Cosmos data quality.** Multi-organization EHR data with varying coding practices, missing race/ethnicity grouped as "Unknown", and site participation changing over time (sites' Cosmos-usable dates are pulled but not yet used to restrict observation).
2.  **Pull window.** History starts 2015-01-01; a patient whose first D89.44 predates 2015 gets a later index (rare, since the code dates from 2021, but relevant to earlier D89.4x codes).
3.  **Custom software.** The study's PheWAS runs on pheauxWAS, a purpose-written tool. It is verified against pyPheWAS (Section 6.5, r = 0.999 on comparable phecodes) and by self-tests, but it is not a published package. A fix during this work (v1.1.1) added detection of separation when all of a phecode's cases are exposed; earlier synthetic results were unchanged.
4.  **Small cells.** Cosmos restricts publication of counts of 1–10 patients; phecodes near the 20-case minimum may have exposure-group cells under 11 and need masking before publication.

## 9. Planned Sensitivity Analyses

| Analysis | Question | Change |
|------------------------|------------------------|------------------------|
| Drop all D89.40–D89.49 (and consider R74.8, D47.0x, C96.2x) from outcomes | Do the non-adjacent phenotypes stand without mast-cell coding? | Exposure-code exclusion list |
| Exclude cases with mastocytosis codes (D47.0x, C96.2x; possibly D89.41) | Does the phenotype stand without them? (Counts in §8.1.12 suggest it does.) | Case definition; rematch |
| Cases with D89.44 on ≥ 2 dates (optional robustness check; the case rule is settled, §3.1) | Are single-code cases diluting or driving results? | Case definition; rematch |
| Conditional logistic regression (or weighted, cluster-robust) | Is inference robust to respecting the matched design? | Model |
| Controls with baseline tryptase \> 8 ng/mL removed | Effect of possible undiagnosed HaT among controls | Control eligibility; rematch |
| Broader utilization adjustment (specialist/ED visits, test counts) | How much of the breadth is healthcare intensity? | Covariates |
| Health system / region matching or stratification | Is the breadth driven by where HaT is diagnosed? | Matching; needs organization or region from Cosmos |
| Lagged pre-index window (e.g. exclude the 6–12 months before index) | Are pre-index hits workup immediately before diagnosis? | Window |
| Require ≥ 3 years of prior observation | Effect of truncated pre-index windows | Eligibility |
| Logit-scale caliper; restrict to full 10:1 sets | Sensitivity to matching choices | Matching |
| Negative-control outcomes | Calibrate the background excess from healthcare intensity | Interpretation |

## 10. Questions for Reviewers

**Clinical (attending).**

*Settled:* a single D89.44 defines a case, because the diagnosis requires a genetic test (§3.1).

1.  **Mastocytosis.** How many HaT patients in a practice like yours carry a mastocytosis diagnosis, and how reliable are D47.0x codes (is D47.09 used loosely for suspected or non-clonal disease)? Should the main HaT phenotype be reported without them?
2.  Index date: We had built this assuming the first D89.44 is the right Index anchor. That said, what do you think of setting it to a prior workup (tryptase, MCAS codes) that precedes it?
3.  Which codes should be treated as exposure-adjacent and excluded in sensitivity analysis: D89.40–D89.49 only, or also R74.8 and mastocytosis (D47.0x, C96.2x)?
4.  Should controls with elevated baseline tryptase be excluded?
5.  Do the post-index Ehlers–Danlos associations fit clinical experience (hEDS diagnosed after HaT testing)?

**Statistical.**

1.  Is unconditional adjusted logistic regression acceptable as primary given variable-ratio matching, or should conditional logistic regression (or weights with cluster-robust SEs) be primary?
2.  Caliper on the propensity-score probability scale (0.2 SD) rather than the logit: change for consistency with Austin (2011)[^4]?
3.  Multiplicity across a hierarchy of dependent phecodes: report at leaf level, collapse to parents, or use a hierarchical FDR?
4.  Utilization adjustment: which additional measures of healthcare intensity are appropriate without conditioning on outcomes?
5.  Reporting extreme associations: preferred presentation when p underflows and Firth is used for \~26% of fitted phecodes.
6.  Health-system confounding (8.1.3): match, stratify, or restrict controls to diagnosing systems?
7.  Time at risk (8.3.1): require full windows, or model rates?

[^4]: Austin PC. Optimal caliper widths for propensity-score matching when estimating differences in means and differences in proportions in observational studies. *Pharmaceutical Statistics* 2011;10(2):150–161. From simulations, it recommends a caliper of 0.2 standard deviations of the logit of the propensity score. MatchIt applies `caliper = 0.2, std.caliper = TRUE` to the distance as estimated (the probability, with `distance = "glm"`) unless `link = "linear.logit"` is given.

------------------------------------------------------------------------

## Appendix: Reproducibility

- **Pipeline (VM):** `python phewas match` → `python phewas balance` → `python phewas pre` → `python phewas post`; `python phewas sheet` summarizes. Each run writes `run_log.txt` (commands, durations, outcomes); pheauxWAS logs SHA-256 hashes of itself and every input.
- **Outputs:** `runs/matching/` (matched cohort, MatchIt summary, love plot, balance), `runs/pre_3y/` and `runs/post/` (inputs, pheauxWAS results CSV and Manhattan plot, pyPheWAS regressions, comparison).
- **Design rationale:** decision log in `docs/plan/decisions.md` (D-numbers); full narrative in `docs/phewasHistoryAndDecisions.md`.