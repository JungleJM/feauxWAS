# Task list

File for discussing ideas and open questions. Your notes, then Claude's reply in a blue box and yours in an orange box (D22). Write anywhere inside your box, between its `:::` lines. New notes go above **Settled**; what is agreed moves there, then into the plan documents (`design.md`, `decisions.md`, `roadmap.md`) and is deleted from here (D1). Pasted images land in `images/` beside this file.

**Starting a new chat.** Paste this, with the section's heading filled in:

``` text
Work on the task list section "<heading>" in docs/plan/tasklist.md.
```

A new chat reads `.claude/CLAUDE.md` by itself, which sends it to the plan documents and tells it to answer here. The one rule that keeps it true: **anything that matters and was only said in a chat goes into this file before that chat ends**, under the section it belongs to.

## Three choices made while building

::: {style="border:2px solid #4a90e2; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Claude: in the code now, for you to confirm**

1.  **Cases indexed before 2021-10-01 aren't matched.** 134 of the 5,974 have their first D89.44 before the code existed (query 2): 15 before 2015, 119 from 2015 to 2021 Q3. The control pool starts at 2021-10-01 (D30), so exact-quarter matching has no controls for them, and their D89.44 was likely mapped after the fact. The script marks them (`IndexBeforeD8944Existed`) and makes them ineligible. **Recommend:** keep it so, and report them; widening the pool back to 2015 would roughly double the pool for 2% of cases.
2.  **Earlier mast-cell codes will show up as a PheWAS result.** Only D89.44 is dropped from the events, so the 1,523 cases with an earlier D89.40–D89.49 put phecode `BI_180.6` (Mast cell activation syndrome) into the pre-index window: partly the HaT workup itself (Attending Questions, question 1). **Recommend:** primary analysis drops D89.44 only, and reads `BI_180.6` as exposure-adjacent; a sensitivity analysis drops all of D89.40–D89.49 (`--exclude-codes D89.40 D89.41 D89.42 D89.43 D89.44 D89.49`).
3.  **Controls with a high tryptase are kept.** A control with a baseline tryptase above about 8 ng/mL may be undiagnosed HaT. The script records `TryptaseMax` for controls but doesn't drop anyone. **Recommend:** drop controls with `TryptaseMax` above 8 before matching; there should be very few, and it reduces misclassification of controls.

**For you to decide:** each of 1–3.
:::

::: {style="border:2px solid #e2904a; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Your response\
See if you can update based on our information.**

1.  

2.  

3.  
:::

## From the results discussion, 2026-10-08

What we found discussing the first results is in the review reports (`docs/reports/run2_2026-10-08/` (full and concise reports)) and D42–D45. One thing is still open:

::: {style="border:2px solid #4a90e2; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Claude: what is still open from the results discussion**

1.  **A tested comparator.** Persistence after diagnosis shows the phenotype is real and lasting, not that HaT causes it: patients are tested *because* of POTS, hypermobility or anaphylaxis, and they keep those codes after diagnosis whatever the cause. A comparison that removes this is HaT patients against patients who had a serum tryptase drawn (someone suspected mast-cell disease) and have no D89.44: both came through the same door. It needs a new pull (the control pool has 948 tryptase results among 300,000) and a decision that it differs from what D6 rejected (it selects on the test, not on outcome diagnoses). **Recommend:** raise it with the reviewers as the main way to address indication bias; build it if they agree.

**For you to decide:** 1 (raise it, build it, or neither). The report carries the rerun's numbers and the cluster reading guide (§6.3.1).
:::

::: {style="border:2px solid #e2904a; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Your response**
:::

## Suggested order

1.  **Three choices**: items 2 and 3 are now sensitivity analyses in the roadmap; item 1 is in the code and the report (§3.1). Confirm or change.
2.  **Tested comparator**: for the reviewers; decide after their answers.

# Settled

Nothing waiting.