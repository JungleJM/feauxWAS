# Attending Questions

Questions for my attending about the HaT PheWAS: patterns in the Epic Cosmos data where a clinical judgement would change how the study is defined. Each says what we saw, what the study does for now, and what I'd like to know.

**The study.** A phenome-wide association study (PheWAS) of hereditary alpha tryptasemia (HaT, ICD-10-CM D89.44) in Epic Cosmos. HaT patients are matched 4:1 to patients with no HaT code, then every diagnosis in the 3 years before the HaT diagnosis is compared between the two groups.

Counts are from Cosmos, run 2026-10-01, for diagnoses dated 2018-01-01 to 2026-06-01.

------------------------------------------------------------------------

## 1. Should the HaT diagnosis date be an earlier mast-cell code?

**What we saw.** Of 5,967 patients with a D89.44 code, many had another mast-cell activation code *before* their first D89.44:

| Code | Description | Patients with it before their first D89.44 |
|----|----|----|
| D89.40 | Mast cell activation, unspecified | 1,433 (about 24%) |
| D89.49 | Other mast cell activation disorder | 150 |
| D89.42 | Idiopathic mast cell activation syndrome | 126 |
| D89.41 | Monoclonal mast cell activation syndrome | 33 |
| D89.43 | Secondary mast cell activation | 14 |

A patient can appear in more than one row. How long before the first D89.44 these codes came (weeks, or years) is still being measured.

**What the study does for now.** The diagnosis date is the first D89.44. The analysis looks at diagnoses in the 3 years before that date.

**Why it matters.** If these earlier codes are usually the same workup, recorded before the specific HaT code was used, the true diagnosis date is earlier. Then some of the "3 years before" window is really time after the patient was recognized, and diagnoses from that workup would look like part of the HaT phenotype.

**Question.** In practice, is D89.40 (or another D89.4x code) usually an early label for patients later confirmed as HaT? Should the diagnosis date be the first mast-cell code when it comes shortly before D89.44, and if so, how shortly?

------------------------------------------------------------------------

## 2. Is one D89.44 code enough to count as HaT?

**What we saw.** 5,967 patients have D89.44 at least once; 3,693 have it on 2 or more different dates. So 2,274 (38%) have it on a single date only.

**What the study does for now.** One D89.44 is enough: all 5,967 are cases. Requiring 2 dates (3,693) is run as a sensitivity analysis, and both numbers are reported.

**Why it matters.** PheWAS studies usually require a code on 2 dates, because for common conditions a single code is often a rule-out or a one-off. HaT is diagnosed by genetic testing (tryptase genotyping), so I expect a single D89.44 to be reliable, but a single code could also be a suspected diagnosis entered before testing.

**Question.** How likely is a single D89.44 to be a patient who doesn't have HaT (for example, coded while testing was pending)? Is one code enough for the primary analysis?