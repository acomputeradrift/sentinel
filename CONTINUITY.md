# Continuity

Living handoff for **local agents** and **cloud/Grokbot agents**. Read this once at session start. Update **in place** at session end. Do not append a diary.

## Protocol

- **Start:** read this file. Open another doc only if a row in **Pointers** says to.
- **End (required):** if any fact in **Now** / **Facts** / **Do not** changed, rewrite that line. Bump `Updated`. Delete stale lines. Do not add narrative.
- **Size:** keep this file under ~80 lines. If a section grows, replace old bullets; do not accumulate.
- **Never write:** secrets, private keys, passwords, env values, transcripts, test logs.

## Now

- **Updated:** 2026-08-30
- **Branch:** `cursor/select-group-chrome-ff08`
- **Repo HEAD:** `02e79fe` (Mac = GitHub, 0 ahead / 0 behind)
- **Droplet HEAD:** `02e79fe` at `/opt/sentinel/app` — service `active`
- **Live:** `http://24.199.106.213/commissioning/` · health `http://24.199.106.213/health`
- **Open:** none beyond this handoff. Technician Select/group chrome is on this branch (PR 6).
- **Next:** use this file; do not rediscover SSH/droplets.

## Facts

- Two droplets, two keys. **Not** interchangeable.
  - Landing: Host `my-do-server` → `161.35.236.81` as `root`, key `~/.ssh/id_ed25519`
  - Sentinel: Host `sentinelServer` → `24.199.106.213` as `root`, key `~/.ssh/id_ed25519_sentinel`
- Cloud/Grokbot VMs **cannot** see Jamie’s Mac `~/.ssh`. Local agents on the Mac can `ssh sentinelServer`.
- `/opt/sentinel/app` is now a git checkout of `cursor/select-group-chrome-ff08`. Working tree may look dirty (old extract leftovers). **Running code is `src/`**. Keep `uploads/`.
- **Documented deploy:** `docs/directives/dev_environment_and_workflow.md` + `deployment/deploy_from_head.ps1` (`git archive HEAD src`). Last ship (2026-08-30) was an **explicit exception**: clone/pull that branch on the droplet, restart `sentinel.service`. Do not invent a third path.
- Do not commit `.tmp_apex_env/`, `generated/`, `uploads/`. Windows venv was untracked in `02e79fe`.
- Tests: agent runs them (`devtools/run_regression_with_venv.py` or `python -m unittest`). Jamie does not.

## Pointers

| When | Read |
|---|---|
| Standing process / approval | `AGENTS.md` / `agents.md` |
| Product/arch briefing | `bootstrap.md` |
| Official deploy | `docs/directives/dev_environment_and_workflow.md` |
| Deploy “Jamie said deploy” | `.cursor/rules/deploy-commit-scope.mdc` |
| Live-update / no-strand (not a deploy script) | `docs/architecture/live_update_no_strand_strategy.md` |

## Do not

- Treat `161.35.236.81` / `my-do-server` as Sentinel.
- Reuse one SSH key for both droplets.
- Ask Jamie to run tests to “verify.”
- Commit the ~70k-file Windows venv or local `generated/` / `uploads/`.
- Use `git archive` when Jamie said pull on the server; do not use ad-hoc pull when Jamie said `deploy`.
