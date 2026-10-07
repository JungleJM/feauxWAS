#!/usr/bin/env python3
"""Build bundles/phewas_vm_runner_bundle.py: the files the VM runs, in one file.

    python tools/build_vm_bundle.py

Packs study/phewas, study/run_phewas.py, study/prepare_phewas_inputs.py and
study/matchit_example.R at the bundle's top level, and pheauxWAS/pheauxWAS.py
under pheauxWAS/, which is the layout of the pheauxWAS folder on the VM (D35, D41).
On the VM, copy the bundle into that folder and run: python phewas update
(the first time: python phewas_vm_runner_bundle.py unpack . --force).
Prints the PACK_ID; give its first 8 characters with the bundle.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = "bundles/phewas_vm_runner_bundle.py"
FILES = ["study/phewas", "study/run_phewas.py", "study/prepare_phewas_inputs.py", "study/matchit_example.R"]

if __name__ == "__main__":
    (ROOT / OUT).unlink(missing_ok=True)            # make_bundle refuses to overwrite
    cmd = [sys.executable, "tools/make_bundle.py", "--out", OUT]
    for f in FILES:
        cmd += ["--file", f]
    cmd += ["--dir", "pheauxWAS=pheauxWAS",
            "--check-deps", "numpy,pandas,pyarrow,scipy,statsmodels,matplotlib,tqdm",
            "--note", "python phewas check|match|balance|sheet|results|pre|post|update|vscode"]
    sys.exit(subprocess.run(cmd, cwd=ROOT).returncode)
