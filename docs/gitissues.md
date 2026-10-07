# Git issues on the VM

## Push fails with "unpacker error" / "Broken pipe"

```
fatal: sha1 file '<stdout>' write error: Broken pipe
error: remote unpack failed: unpack-objects abnormal exit
! [remote rejected] main -> main (unpacker error)
```

**Cause (2026-10-07):** a commit included `runs\` (patient-level CSVs, e.g.
`diagnosis_events_pre.csv`, 4.6M lines; PNG plots) and `__pycache__\*.pyc`.
Too large for GitLab, and patient data must not go there anyway. If a push
fails like this, don't retry it: find what's in the commit first.

On the VM there is one remote, `origin`, pointing at the GitLab server. (The
`gitlab:` in the error message is the server name, not a remote.)

## Find what's in the unpushed commits

```
git log --oneline origin/main..main
git --no-pager diff --stat origin/main main
```

The first lists the unpushed commits; the second lists every file they would
send. Large files show as `Bin 0 -> <bytes>` or long `+++++` bars. Without
`--no-pager` the list opens in a pager; press `q` to leave it.

## Remove files from the commit, keeping them on disk

Works only while the commits are unpushed.

```
git reset --soft origin/main
git rm -r --cached --ignore-unmatch runs "*.pyc"
git status
```

- `reset --soft` undoes the unpushed commits; changes stay staged, files stay on disk.
- `rm --cached` stops tracking the files and leaves them on disk. Plain
  `git rm` (without `--cached`) would delete them.
- Check `git status` lists nothing under `runs\` and no `.pyc`, then commit and push.

If a bad file is in a commit that's **already on GitLab**, this isn't enough:
history has to be rewritten. Ask before doing anything.

## Keep it from happening again

```
Set-Content .git\info\exclude "runs/","__pycache__/","*.pyc","*.parquet" -Encoding ascii
```

`.git\info\exclude` works like `.gitignore` but lives only on the VM and is
never committed. Use `Set-Content ... -Encoding ascii`, not `echo ... >>`:
Windows PowerShell's `>>` writes UTF-16, which git can't read, so the rule
silently does nothing.
