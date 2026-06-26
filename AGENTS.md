# AGENTS.md

Codex guidance for `/srv/containers/edq` on udragon.

## First Reads

- Read `/home/edq/.codex/AGENTS.md` for global Codex rules.
- Read `/srv/containers/edq/CLAUDE.md` for the live Dragonsuite environment, port table, API key policy, hardware constraints, and SOP references.
- Read `/srv/containers/edq/tasks/lessons.md` before changing behavior; append it after corrections using its existing format.

## Canonical Defaults

- udragon is the home base for Dashboard, Dragonsuite, GPU/model, and Linux-hosted AI service work.
- Home project folder: `/srv/containers/edq/projects`
- Dashboard: `http://192.168.7.226:8100/`
- Downloads Gallery: `http://192.168.7.226:8060/`
- Generated outputs: `/home/edq/ai_generated`

Use Mac/iCloud `1Projects` only when the task is Mac-native, synced between Macs, explicitly placed there by the user, or starts on Mac because of MLX/Apple Silicon requirements.

## Output Policy

- Real user-facing generated media belongs in `/home/edq/ai_generated/<service>/`.
- Smoke tests, audits, one-step sanity checks, screenshots, API samples, and other throwaway outputs belong in `/home/edq/ai_generated/test-artifacts/<type>/`.
- Do not put throwaway test output in Downloads, the root of `1Projects`, or service gallery/output folders.
- Keep `ai_generated/<service>/` output-only. Source, package files, venvs, model caches, and logs belong elsewhere.

## Dragonsuite Work

- For new services, read `/home/edq/.claude/skills/dragonsuite-add/SKILL.md` before implementation.
- Every generative service needs an `output_dir` in `/srv/containers/edq/config/dragonsuite.json`.
- Model downloads should be explicit scripts and completed before first launch.
- Run the relevant health check before calling Dashboard work done.
