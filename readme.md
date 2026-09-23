


# PheauxWAS and pyPheWASA

PheaxWAS is a single-script pheWAS python script that runs a phewas study

## To get python to read numpy and the pheauxWAS.py

you need to use the function (crtl-cmd-p) "python: select interpreter" and do the venv. That has numpy. Soon i'll figure out how to do global but that's later

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

pyPheWAS's README too: add --exclude-file pyPheWAS/README.md.
Other files: repeat --exclude-file once per file.
Every .md file everywhere: add md to the --exclude-ext list instead.


## WHat's inside

pheauxWAS is my thing, and phyPheWAS last had a push 3 years go, so that commit is likely the last for a while.