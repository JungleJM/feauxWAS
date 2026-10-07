# pheauxWAS

A single-file PheWAS tool (`pheauxWAS/pheauxWAS.py`), the published pyPheWAS beside it, a tutorial on synthetic data, and the HaT PheWAS: hereditary alpha tryptasemia (HaT) patients against matched controls, pulled from Epic Cosmos.

Read before working:

- `reference/plan/design.md`: what exists, as built: the tools, the study design, the Cosmos pull, the tutorial.
- `reference/plan/roadmap.md`: status, what is next, open problems. Check it first.
- `reference/plan/decisions.md`: why things are the way they are (D1 onward). Read the relevant entry before reversing anything; append a new entry rather than editing an old one's reasoning.

## Keeping The Docs True

- A fact lives in one of those three documents only. Status lives only in the roadmap.
- When code or the study design changes, update `design.md` in the same commit. When an item is built, delete it from the roadmap. When something is decided, add a numbered decision.
- Nothing outside the three documents restates them: once a note's content is in them, the note is deleted, and other files point to them (D27).
- `reference/plan/Future discussions/Attending Questions.md` holds questions for the user's attending: what the data showed, what the study does for now, and the question. Add to it when the user asks; it asks, it doesn't decide.
- Do not add new design documents. `reference/plan/tasklist.md` is not one: it holds only what is still under discussion (D1).
- **"Update docs"** means: bring `design.md`, `decisions.md` and `roadmap.md` up to date with the code and the task list by the rules above, move every settled task-list item into them and delete it from the task list, and delete any pasted image in `reference/plan/images/` that no document mentions.

## Planning And Doing Work

The user works in this cycle; follow it for any change bigger than a small fix.

0.  **A new chat** is usually started with a task-list section's heading: read that section, the plan documents above, and the code behind it, then answer under it. Before a chat ends, write anything it settled or learned that lives only in the chat into the task list (or, if agreed, the plan documents).
1.  **Respond topic by topic, in `reference/plan/tasklist.md`.** When the user brings research, notes or ideas, read the code and data behind each topic first. Under each, in a blue box headed `**Claude: <topic>**`, say what exists today, give a recommendation, and end with "For you to decide" where the choice is theirs; follow it with an orange box headed `**Your response**`, empty. The boxes are Quarto fenced divs, written exactly so, with markdown (not HTML) inside (D22):

    ``` markdown
    ::: {style="border:2px solid #4a90e2; border-radius:6px; padding:8px 12px; margin:8px 0;"}
    **Claude: <topic>**

    ...
    :::

    ::: {style="border:2px solid #e2904a; border-radius:6px; padding:8px 12px; margin:8px 0;"}
    **Your response**
    :::
    ```

    Close with a numbered **Suggested order**: one line per item, most urgent first, saying why it sits where it does. Agreed items move to the `# Settled` section at the bottom; new notes go above it.
2.  **Document before code.** Once the user agrees, write the numbered decisions, put the order in `roadmap.md` under "Next", and move each settled item out of the task list into the three documents, then delete it there: Settled should not become a graveyard.
3.  **Build in that order.** One commit per item (small ones may share), each with its tests.
4.  **Report, discuss, then document.** Report what was built, what was chosen along the way, and what the user needs to do or decide. Do not edit the plan documents with the results until the user has discussed them.

## Layout

- `pheauxWAS/pheauxWAS.py`: the PheWAS tool, Python and numpy only. `--selftest` runs its checks; `--help` documents every flag.
- `pyPheWAS-2a8fff1/`: the published pyPheWAS at commit 2a8fff1, for cross-checking. Not ours to edit.
- `phecode/`: the phecodeX ICD-CM map and phecode definitions (Latin-1 encoded).
- `tutorial/`: the method on synthetic data, end to end (design.md, The Tutorial); `tutorial/pulling-cohorts/` holds the HaT intake and the profile queries.
- `reference/`: the Cosmos data dictionary (a copy; Telescope's is the source of truth, D2), the pull as run on the VM (`hat_cosmos_blueprint.yaml`), and `plan/`.
- `bundling/make_bundle.py`: packs the repo into one file for the VM.

## Constraints

- Patient data never enters this repo. Cosmos is reached only on the VM; everything here is tested on synthetic data, and the user runs pulls and queries and reports back, often with screenshots.
- Study-design decisions come from this repo and the user. The Telescope project (`/Users/jmath/Documents/code/telescope`) is used for its pull-YAML format, its validator and its data dictionary, nothing else (D3). Do not write into it without asking.
- `pheauxWAS.py` stays a single file needing only Python 3.7+ and numpy.

## Commands For The VM

Everything run on the VM is typed by hand. Every instruction for it, in chat and in the plan documents, is one or two words: `.\phewas <command>` from the pheauxWAS folder (D36). A step that needs more is added as a command to `tutorial/run_phewas.py` (with `phewas.bat` beside it), with its paths as defaults; never hand over a long command, a long path or a full PACK_ID to type. New or changed scripts reach the VM in a bundle that `.\phewas update` unpacks; to compare a PACK_ID, give its first 8 characters.

## Working Conventions

- On the Mac, scripts that need pandas or pyarrow run as `uv run --with pandas --with pyarrow python ...`; R scripts as `Rscript` (MatchIt, arrow, cobalt, dplyr). Validate the pull with Telescope: `python3.13 scripts/makeYaml.py --template <intake> --validate`, run from the Telescope folder; it writes nothing.
- A bug fix gets a test of the **outcome** (what ends up in the results), confirmed to fail with the bug reintroduced.
- Prefer a loud error that suggests a fix over inferring what the user meant. The user wants to make the choice.
- Work on `master`. The user asks for commits and pushes; end commit messages with the `Co-Authored-By` line.
- Never run destructive git commands on uncommitted work.
