# Deployment Folder

Purpose: keep deploy-specific helpers and quick references out of repo root.

## Contents

- `verify_deploy_hash.py`
  - Compares zip-member SHA-256 to deployed file SHA-256 on the droplet.
  - Run after extract, before restart.
- `cleanup_post_run.ps1`
  - Removes local test/deploy artifacts.
  - Optional `-CleanRemote` removes known deploy leftovers from droplet `/tmp`.

## Canonical Deploy Workflow

- `docs/directives/dev_environment_and_workflow.md`
  - Source of truth for preflight, one-shot deploy order, verification, and cleanup policy.
