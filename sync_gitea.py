#!/usr/bin/env python3
"""Push the current GitHub collaboration branch to the private Gitea remote."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def git(args: list[str], *, capture: bool = False) -> str:
    cmd = ["git", *args]
    if capture:
        return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)
    return ""


def remote_exists(name: str) -> bool:
    return name in git(["remote"], capture=True).splitlines()


def current_branch() -> str:
    branch = git(["branch", "--show-current"], capture=True)
    if not branch:
        raise SystemExit("Could not find a current branch. Are you in detached HEAD?")
    return branch


def require_clean_tree() -> None:
    status = git(["status", "--porcelain"], capture=True)
    if status:
        raise SystemExit(
            "There are uncommitted changes. Commit them first, then run this again.\n"
            "Use 'git status' to see what still needs to be committed."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Push committed work from the collab repo back to private Gitea."
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Gitea remote name (default: origin)",
    )
    parser.add_argument(
        "--target-branch",
        help="branch name to push to on Gitea (default: current branch)",
    )
    parser.add_argument(
        "--include-tags",
        action="store_true",
        help="also push git tags to Gitea",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="push even when the working tree has uncommitted changes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be pushed without updating Gitea",
    )
    args = parser.parse_args()

    if not remote_exists(args.remote):
        raise SystemExit(f"Remote '{args.remote}' does not exist.")

    branch = current_branch()
    target_branch = args.target_branch or branch

    if not args.allow_dirty:
        require_clean_tree()

    push_args = ["push"]
    if args.dry_run:
        push_args.append("--dry-run")
    push_args.extend([args.remote, f"{branch}:{target_branch}"])
    git(push_args)

    if args.include_tags:
        tag_args = ["push"]
        if args.dry_run:
            tag_args.append("--dry-run")
        tag_args.extend([args.remote, "--tags"])
        git(tag_args)

    print(f"\nSynced {branch} -> {args.remote}/{target_branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
