# pheauxWAS and pyPheWAS

pheauxWAS is a single-script PheWAS tool in Python. This repo holds it, the HaT PheWAS study that runs on it (Epic Cosmos, on the VM), a tutorial on synthetic data, and the published pyPheWAS for cross-checking.

## Layout

| Folder | What it holds |
|---|---|
| `pheauxWAS/` | `pheauxWAS.py`, the PheWAS tool (Python and numpy only; `--selftest`, `--help`) |
| `study/` | The HaT study's pipeline, everything that runs on the VM: group building, matching, the runner (`python phewas ...`); `study/pulls/` has the Telescope intakes |
| `tutorial/` | The method end to end on synthetic data, using the scripts in `study/` |
| `phecode/` | phecodeX maps and definitions |
| `docs/` | `plan/` (design, decisions, roadmap, task list), the study narrative, `reports/` for reviewers, `gitissues.md` (git problems on the VM and their fixes) |
| `reference/` | Source material: the Cosmos data dictionary copy and the `hat_` pull as run |
| `vendor/pyPheWAS-2a8fff1/` | The published pyPheWAS, unedited |
| `tools/` | Bundling, environment setup, remote syncing |
| `bundles/` | The current bundle for the VM |
| `Ilarias Work/` | A colleague's save folder |

Working rules for Claude are in `.claude/CLAUDE.md`; where things stand is in `docs/plan/roadmap.md`.

## To get python to read numpy and the pheauxWAS.py

you need to use the function (crtl-cmd-p) "python: select interpreter" and do the venv. That has numpy. Soon i'll figure out how to do global but that's later

## Friend setup / dependencies

Do not share the `.venv` folder itself. It is tied to your computer's paths and operating system, so it usually breaks on someone else's machine.

Instead, share the project with `requirements.txt` and `tools/setup_env.py`. After downloading the project, your friend can run:

```bash
python3 tools/setup_env.py
```

On Windows, use:

```bat
py tools\setup_env.py
```

That creates a fresh `.venv`, installs the Python packages in `requirements.txt`, and installs the bundled `vendor/pyPheWAS-2a8fff1` package. Then in VS Code, use "Python: Select Interpreter" and choose the `.venv` for this project.

## Collaboration and private Gitea sync

Normal collaboration happens on the private GitHub repo.

For a collaborator who cloned from GitHub, the normal workflow is:

```bash
git add .
git commit -m "Describe the change"
git push
```

For a fresh GitHub clone, `origin` is GitHub, so plain `git push` goes back to the shared repo.

On JM's machine, `master` tracks the GitHub remote named `github`, so plain `git push` also goes to the shared repo at `git@github.com:JungleJM/pheauxwas-collab.git`.

JM's private Gitea repo stays configured as `origin`. When JM wants to manually catch it up to the GitHub collaboration branch, run:

```bash
python3 tools/sync_gitea.py
```

The script pushes the current branch to `origin` only if `origin` looks like the private Gitea URL. This prevents a collaborator's GitHub clone from accidentally treating GitHub as the private Gitea remote. It also stops if there are uncommitted changes, because only commits can be synced.

If you ever need to manually push to GitHub without the default branch tracking, use:

```bash
git push github master
```

## bundling

**The VM bundle** (what `python phewas update` unpacks on the VM):

```bash
python3 tools/build_vm_bundle.py
```

It writes `bundles/phewas_vm_runner_bundle.py` and prints its PACK_ID.

**Any other bundle**: use `tools/make_bundle.py` directly. For the whole repo:

```
python3 tools/make_bundle.py --out pheauxwas_bundle.py \
  --dir .=pheauxwas_build \
  --exclude-dir bundles --exclude-dir runs --exclude-dir .venv \
  --exclude-file README.md \
  --exclude-ext png,jpg,jpeg,gif,bmp,ico,svg,webp,tif,tiff,gz \
  --check-deps numpy,pandas,scipy,statsmodels,matplotlib,tqdm \
  --pythonpath pheauxwas_build/vendor/pyPheWAS-2a8fff1 \
  --note "pheauxWAS 1.1.1 + pyPheWAS commit 2a8fff1"
```

For file exclusion, how the path works: it's relative to the folder you run the command from. So --exclude-file README.md drops only the README in pheauxwas_build itself. I tested this: the top-level README was left out and pyPheWAS/README.md was kept.

pyPheWAS's README too: add --exclude-file vendor/pyPheWAS-2a8fff1/README.md. Other files: repeat --exclude-file once per file. Every .md file everywhere: add md to the --exclude-ext list instead.

## WHat's inside

pheauxWAS is my thing, and phyPheWAS last had a push 3 years go, so that commit is likely the last for a while.
