#!/usr/bin/env python3
"""Push this repository to a private GitHub mirror."""

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
    remotes = git(["remote"], capture=True).splitlines()
    return name in remotes


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


def configure_remote(name: str, repo_url: str | None, set_url: bool) -> None:
    if remote_exists(name):
        if repo_url and set_url:
            git(["remote", "set-url", name, repo_url])
        return

    if not repo_url:
        raise SystemExit(
            f"Remote '{name}' does not exist yet.\n"
            f"Run once with: python3 sync_github.py --repo GITHUB_REPO_URL"
        )
    git(["remote", "add", name, repo_url])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Push commits from this repo to a GitHub mirror remote."
    )
    parser.add_argument(
        "--repo",
        help="GitHub repo URL, for example git@github.com:USER/pheauxWAS.git",
    )
    parser.add_argument(
        "--remote",
        default="github",
        help="remote name to use for the GitHub mirror (default: github)",
    )
    parser.add_argument(
        "--target-branch",
        help="branch name to push to on GitHub (default: current branch)",
    )
    parser.add_argument(
        "--set-url",
        action="store_true",
        help="update the remote URL if the remote already exists",
    )
    parser.add_argument(
        "--include-tags",
        action="store_true",
        help="also push git tags to GitHub",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="push even when the working tree has uncommitted changes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be pushed without updating GitHub",
    )
    args = parser.parse_args()

    branch = current_branch()
    target_branch = args.target_branch or branch

    if not args.allow_dirty:
        require_clean_tree()

    configure_remote(args.remote, args.repo, args.set_url)

    push_args = ["push"]
    if args.dry_run:
        push_args.append("--dry-run")
    push_args.extend(["-u", args.remote, f"{branch}:{target_branch}"])
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
