# Task list

File for discussing ideas and open questions. Your notes, then Claude's reply in a blue box and yours in an orange box (D22). Write anywhere inside your box, between its `:::` lines. New notes go above **Settled**; what is agreed moves there, then into the plan documents (`design.md`, `decisions.md`, `roadmap.md`) and is deleted from here (D1). Pasted images land in `images/` beside this file.

**Starting a new chat.** Paste this, with the section's heading filled in:

``` text
Work on the task list section "<heading>" in reference/plan/tasklist.md.
```

A new chat reads `.claude/CLAUDE.md` by itself, which sends it to the plan documents and tells it to answer here. The one rule that keeps it true: **anything that matters and was only said in a chat goes into this file before that chat ends**, under the section it belongs to.

## Profile query results 7–11

You're rerunning 1–10 for whole results (and 11, the case count by number of D89.44 dates). What 1–6 settled is now in D23–D26 and `Attending Questions.md`.

::: {style="border:2px solid #4a90e2; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Claude: what's still waiting on them**

Paste each result as text (in SSMS: Ctrl+A on the grid, right-click → **Copy with Headers**).

- **7**: patients whose first D89.44 is before 2018. With the pull now from 1990 (D23), this mainly tells us how far back the cohort goes.
- **8**: how long before the first D89.44 the other D89.4x codes came. Goes into `Attending Questions.md`, question 1.
- **9**: every race and ethnicity value, to check the Unknown grouping (D10).
- **10**: every encounter type flagged face-to-face, in case one besides Office Visit belongs (D26).
- **11**: the single-date patients: recent, or only on a problem list. Goes into `Attending Questions.md`, question 2.
:::

::: {style="border:2px solid #e2904a; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Your response**

7.

8.

9.

10.

11.
:::

## Other files that restate the plan docs

Your rule (D27): anything already in design, decisions or roadmap gets deleted elsewhere, so nothing can drift. `cosmos_parquet_ref.yaml` and `Questions.md` are deleted. Other files still restate the study.

::: {style="border:2px solid #4a90e2; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Claude: what else restates it**

- **`tutorial/`**: `control-matching-tutorial.md`, `why-and-how-for-phewas.md` and `hat-control-recipe.yaml` describe the matching, windows and case rule, partly as the real study's choices. They've already drifted: the tutorial's case rule is still 2 dates (D24 made it 1).
- **`HaT_PheWAS_intake.yaml`**: its header comment explains the three tables, which `design.md` (The Cosmos Pull) also does.
- **`profile_queries.sql`**: its "Look for" comments are fine, since they're instructions, not facts.

**Recommend:** keep the tutorial as teaching material on synthetic data, but strip it of the real study's decisions: it explains the *method*, and points to `design.md` for what the HaT study actually does. Cut the intake's header comment to one line pointing to `design.md`, since Telescope only needs the YAML itself.

**For you to decide:** that, or delete the tutorial's HaT-specific files outright.
:::

::: {style="border:2px solid #e2904a; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Your response**
:::

## Precision

(Your note, 2026-10-01: "once done we'll talk through more of precision".)

::: {style="border:2px solid #4a90e2; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Claude: what to cover**

Not started. Say what you want to cover and I'll answer here: for example how many cases each phecode needs (pheauxWAS's `--min-cases 20`), the power at 4:1 with 5,967 cases, or how tight the matching needs to be.
:::

::: {style="border:2px solid #e2904a; border-radius:6px; padding:8px 12px; margin:8px 0;"}
**Your response**
:::

## Suggested order

1.  **Profile query results 7–11**: they fill in the attending questions and confirm the race and visit definitions before the Python builder is written.
2.  **Other files that restate the plan docs**: quick, and the tutorial has already drifted.
3.  **Precision**: whenever you're ready; it doesn't block the pull.

# Settled

Nothing waiting.
