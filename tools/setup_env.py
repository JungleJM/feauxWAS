#!/usr/bin/env python3
"""Create a local virtual environment and install project dependencies."""

from __future__ import annotations

import argparse
import os
import subprocess
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent   # the repo root (this file is in tools/)
DEFAULT_VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def ensure_pip(python: str) -> None:
    try:
        subprocess.check_call(
            [python, "-m", "pip", "--version"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        print("pip is missing from this virtual environment; bootstrapping it.")
        run([python, "-m", "ensurepip", "--upgrade"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create .venv and install the Python packages for pheauxWAS."
    )
    parser.add_argument(
        "--venv",
        default=str(DEFAULT_VENV),
        help="virtual environment directory (default: .venv)",
    )
    parser.add_argument(
        "--skip-pip-upgrade",
        action="store_true",
        help="do not upgrade pip before installing requirements",
    )
    args = parser.parse_args()

    venv_dir = Path(args.venv).expanduser()
    if not venv_dir.is_absolute():
        venv_dir = ROOT / venv_dir

    if not REQUIREMENTS.exists():
        raise SystemExit(f"Missing dependency file: {REQUIREMENTS}")

    if not venv_python(venv_dir).exists():
        print(f"Creating virtual environment: {venv_dir}")
        venv.EnvBuilder(with_pip=True).create(venv_dir)
    else:
        print(f"Using existing virtual environment: {venv_dir}")

    python = str(venv_python(venv_dir))
    ensure_pip(python)
    if not args.skip_pip_upgrade:
        run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-r", str(REQUIREMENTS)])

    print("\nDone.")
    if os.name == "nt":
        print(r"Activate it with: .venv\Scripts\activate")
    else:
        print("Activate it with: source .venv/bin/activate")
    print("VS Code: run 'Python: Select Interpreter' and choose this .venv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
