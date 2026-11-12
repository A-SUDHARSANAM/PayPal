# Security Cleanup Report

**Project:** AgentPay  
**Repository:** `D:\Paypal`  
**Branch inspected:** `main`  
**Status:** local cleanup completed and validated; history has been rewritten
locally and nothing has been pushed.

## Incident scope

GitHub Push Protection identified two credentials in commit
`56ab8857d25b6c46393497418d67b8ee5938a379`:

1. A GCP API key in `backend/.env.example` (line 1).
2. A Supabase secret key in `.env.example` (line 6 reported by GitHub).

The values are deliberately not recorded in this report.

Both values are also reachable through local branch
`backup-pre-generated-files-cleanup-20261112`, so every reachable ref must be
included in the rewrite.

## Backup record

Before any cleanup, the following non-overwriting backups were created outside
the repository:

- Git mirror: `D:\AgentPay-backups\AgentPay-20261112-131946.git`
- Verified Git bundle: `D:\AgentPay-backups\AgentPay-20261112-131946.bundle`
- Working-tree patch: `D:\AgentPay-backups\AgentPay-20261112-132035-working-tree.patch`
- Untracked-file inventory:
  `D:\AgentPay-backups\AgentPay-20261112-132035-untracked-files.txt`

An earlier filesystem-copy attempt could not read a local Python cache directory;
that incomplete copy is not considered a backup. The Git mirror and bundle are
the valid repository backups.

## Completed cleanup

1. Every value in `.env.example` and `backend/.env.example` was replaced with a
   descriptive safe placeholder while retaining the variable names and template
   structure.
2. `.gitignore` was verified to ignore `.env` and `.env.*`, while explicitly
   allowing only the example templates.
3. `git-filter-repo` rewrote all project branch history, including
   `backup-pre-generated-files-cleanup-20261112`, using a replacement map that
   was deleted immediately after use.
4. Four credential-bearing Codex-internal snapshot tree refs, which cannot be
   rewritten as commits, were removed. Git reflogs were expired and unreachable
   objects garbage-collected. No project branch, source directory, backup, or
   user working-tree change was removed.
5. The pre-existing `next-env.d.ts` change and `.vscode/` directory were
   restored after the rewrite.

## Validation results

- Both exposed values have **zero matches** in all reachable refs and reachable
  commit history.
- Both environment example templates have **zero non-placeholder values**.
- `package.json`, `package-lock.json`, the backend, documentation, and database
  migration content remain present.
- `git fsck --full --no-dangling` completed cleanly. Packed repository size is
  approximately 272 MiB.
- `npm run build` completed successfully.
- Backend tests: 8 passed and 1 failed because the test attempts an outbound
  Supabase HTTP request that is blocked by the execution sandbox. A networked
  retry was not performed because it could transmit authenticated data.

## Rotation required

The exposed GCP credential and Supabase secret must be revoked/rotated in their
respective provider consoles. No external account access was attempted, and the
exposed values must not be reused.

## Push preparation

A final read-only query found no advertised `origin/main` ref. The next push is
a normal first push, not a force push. Recheck immediately before pushing, then
run:

```powershell
git status
git ls-remote --heads origin main
git push -u origin main
```

If `origin/main` is created by someone else before the push and contains the
pre-cleanup history, stop and coordinate with every collaborator before using a
lease-protected force push:

```powershell
git fetch origin main
git log --oneline --left-right origin/main...main
git push --force-with-lease=refs/heads/main:<remote-main-commit-id> origin main:main
```

Never use `--force` alone and never bypass GitHub Push Protection. Before any
push, rotate/revoke the exposed GCP and Supabase credentials in their provider
consoles.
