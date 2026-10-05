# Open Dots on udragon

Open Dots is a single-owner AI workspace at `http://192.168.7.226:8007/app`. The Dragonsuite card starts and stops it. The Next.js web process listens on port 8007 and proxies `/api/v1/*` to a FastAPI process bound only to `127.0.0.1:8048`.

## Local model

- The saved provider is Ollama's stateless Responses API at `http://127.0.0.1:11434/v1`.
- Default and primary assistant: `gemma4:12b`. `qwen3:8b` is also listed as an optional model.
- Both models were already installed in Ollama. Open Dots does not own the model download or Ollama's process, so its stop action leaves Ollama running.
- The workspace's conversation and approval state is in `/home/edq/.open-dots/open-dots.sqlite3`. This is application state, not generated media.

## Access and lifecycle

- Sign in with the owner token stored at `/home/edq/.open-dots/.auth-token` (mode 0600). Keep it private. The browser stores a revocable session cookie; restarting the API requires signing in again.
- Source: `/srv/containers/edq/projects/open-dots`.
- Python environment: `/srv/containers/edq/venv_open_dots`; web dependencies and build are inside the source checkout.
- Computer image: `open-dots-computer:1.62.1`, built from the project's `runtime/Dockerfile`. Rebuild it after runtime updates.
- Start: `bash /srv/containers/edq/scripts/start_open_dots.sh`.
- Stop: `bash /srv/containers/edq/scripts/stop_open_dots.sh`.
- Logs and PID files: `/srv/containers/edq/logs/open-dots/`.
- The file workspace is confined to `/home/edq/.open-dots/workspace`; computer workspaces live under `/home/edq/.open-dots/computers`.

## Current scope

Chat, saved conversations, named assistants, and the approval gateway are enabled. The optional Docker computer provider gives each assistant a separate browser and workspace, with a 2 CPU and 2 GB memory limit. It does not control the host desktop. Composio connectors need separate credentials. The project is an early prototype and is configured for one owner on the local network.

The Next.js 15 dependency tree currently has an upstream PostCSS security advisory; `npm audit --omit=dev` reports one high and one moderate finding. We did not force a major Next.js upgrade into this upstream prototype. Recheck on update before broader exposure.
