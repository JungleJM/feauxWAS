# PheauxWAS and pyPheWASA

PheaxWAS is a single-script pheWAS python script that runs a phewas study

## To get python to read numpy and the pheauxWAS.py

you need to use the function (crtl-cmd-p) "python: select interpreter" and do the venv. That has numpy. Soon i'll figure out how to do global but that's later

## Friend setup / dependencies

Do not share the `.venv` folder itself. It is tied to your computer's paths and operating system, so it usually breaks on someone else's machine.

Instead, share the project with `requirements.txt` and `setup_env.py`. After downloading the project, your friend can run:

```bash
python3 setup_env.py
```

On Windows, use:

```bat
py setup_env.py
```

That creates a fresh `.venv`, installs the Python packages in `requirements.txt`, and installs the bundled `pyPheWAS-2a8fff1` package. Then in VS Code, use "Python: Select Interpreter" and choose the `.venv` for this project.

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
python3 sync_gitea.py
```

The script pushes the current branch to `origin` only if `origin` looks like the private Gitea URL. This prevents a collaborator's GitHub clone from accidentally treating GitHub as the private Gitea remote. It also stops if there are uncommitted changes, because only commits can be synced.

If you ever need to manually push to GitHub without the default branch tracking, use:

```bash
git push github master
```

## bundling

Use make_bundle.py, use this command:

```         
python3 bundling/make_bundle.py --out bundling/pheauxwas_bundle.py \
  --dir .=pheauxwas_build \
  --exclude-dir bundling \
  --exclude-file README.md \
  --exclude-ext png,jpg,jpeg,gif,bmp,ico,svg,webp,tif,tiff,gz \
  --check-deps numpy,pandas,scipy,statsmodels,matplotlib,tqdm \
  --pythonpath pheauxwas_build/pyPheWAS \
  --note "pheauxWAS 1.1.0 + pyPheWAS commit 2a8fff1"
```

For file exclusion, how the path works: it's relative to the folder you run the command from. So --exclude-file README.md drops only the README in pheauxwas_build itself. I tested this: the top-level README was left out and pyPheWAS/README.md was kept.

pyPheWAS's README too: add --exclude-file pyPheWAS/README.md. Other files: repeat --exclude-file once per file. Every .md file everywhere: add md to the --exclude-ext list instead.

## WHat's inside

pheauxWAS is my thing, and phyPheWAS last had a push 3 years go, so that commit is likely the last for a while.
