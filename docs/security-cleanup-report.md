# Security Cleanup Report

**Project:** AgentPay  
**Repository:** `D:\Paypal`  
**Branch inspected:** `main`  
**Status:** cleanup proposed; history has not been rewritten and nothing has been pushed.

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

## Proposed cleanup (pending approval)

1. Replace every value in both `.env.example` templates with a descriptive safe
   placeholder while retaining variable names, comments, and configuration
   structure.
2. Keep `.gitignore` rules that ignore `.env` and `.env.*` while explicitly
   allowing only the two example templates.
3. Use `git filter-repo` (installed only after approval) with a replacement map
   containing the two exposed values. Rewrite all reachable commits and refs;
   do not delete project directories or legitimate files.
4. Verify that neither exposed value is present in reachable history, run the
   frontend build and backend test suite, and inspect repository size.
5. Do not push automatically. Coordinate a force push only if the remote branch
   contains the prior history; otherwise a normal first push can be used.

## Rotation required

The exposed GCP credential and Supabase secret must be revoked/rotated in their
respective provider consoles. No external account access was attempted, and the
exposed values must not be reused.

## Current remote finding

A read-only query returned no advertised `origin/main` ref at the time of
inspection. This must be checked again immediately before any push.
