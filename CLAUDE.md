# CLAUDE.md

Guidance for Claude Code working in this personal AI development environment on udragon (Ubuntu 24.04, RTX 5070 Ti Blackwell).

## Canonical Host

**udragon is the source of truth.** Dragonsuite apps, service launchers, API keys, docs, project repos, model caches, and generated outputs live under `/srv/containers/edq` on udragon (`192.168.7.226`). Mac hosts such as cdragon are clients for browsing, editing, SSH, SMB/Obsidian access, and light local work; do not infer that a project should live on cdragon because a local shell or SSH alias resolves there. When in doubt, SSH to udragon and work from `/srv/containers/edq`.

## Directory Structure

```
/srv/containers/edq/
├── .env                # API keys — single source of truth, NEVER duplicate
├── .mcp.json           # MCP server config — NEVER duplicate
├── config/             # dragonsuite.json (service registry)
├── scripts/            # Shell launchers (start_*.sh) and Python scripts
├── docs/               # Architecture patterns, service docs, venvs.md
├── projects/           # Cloned AI project repos (self-contained)
├── models/             # Downloaded AI model weights
├── media/              # HTML apps, media files
├── mcp-servers/        # Custom MCP server implementations
├── venv_*/             # Virtual environments (see docs/venvs.md)
└── cache_huggingface/  # HF hub cache (symlinked from ~/.cache/huggingface)
```

## Service Registry

`config/dragonsuite.json` is the single source of truth for every Dragonsuite service (port, category, description, launch/stop commands, output_dir) — do not keep a parallel list here. Query it directly:

```bash
jq -r '.services[] | "\(.port)\t\(.name)\t\(.category)"' config/dragonsuite.json | sort -n
```

For live running/stopped state (a static list can't show this), use the `dragonsuite` MCP tools: `dragonsuite_status`, `dragonsuite_check_port`, `dragonsuite_vram`.

**Not tracked in dragonsuite.json** (genuinely external, not derivable from the registry):

- `ballpark-fingerprint` (port 8056) — personal FastAPI project on a Mac (192.168.7.131), started manually, not part of Dragonsuite
- **minidragon** (`192.168.7.114`, always-on, separate machine): Immich 2283, Navidrome 4533, Jellyfin 8096, Home Assistant 8123, Portainer 9000, Komga 25600 — Docker services, see `minidragon.md` memory
- **udragon always-on infra**: Ollama API 11434 (systemd), RustDesk Server 21115-21119 (Docker)

## Quick Start

```bash
cd /srv/containers/edq
bash scripts/start_dragonsuite.sh            # dashboard → http://192.168.7.226:8100
bash scripts/start_<service>.sh              # any individual service
python3 scripts/health_check.py --all        # structural check, all services
```

## API Keys

Central `.env` at `/srv/containers/edq/.env` — load with `from dotenv import load_dotenv` (Python) or `source /srv/containers/edq/.env` (bash). Keys: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`. Google keys are from the **'vscode'** Cloud project — enable new APIs there.

**Browser SPAs must never expose keys.** Proxy via the Python server: Browser → `/api/proxy` → Python → external API.

## Hardware

- **GPU**: RTX 5070 Ti, 16GB VRAM, Blackwell (sm_120 / CUDA 12.0)
- **PyTorch**: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128`
- **OOM fix**: `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` in launcher
- Only one GPU-heavy service at a time. See `docs/venvs.md` for venv registry.

## Core Rules

1. **RTFM before writing.** Before any external API/SDK/CLI call: read docs, verify exact method names. Wrong names fail completely. Run `/rtfm` skill after writing any API code.
2. **Do the work yourself.** Never ask the user to run commands or paste output — use Bash, filesystem, Playwright, MCP tools directly.
3. **Syntax-check before done.** Python: `python3 -m py_compile`. HTML JS: extract script blocks and validate with node. See CLAUDE.md history for the full command template.
4. **Generative output sanity before done.** Run a representative prompt at default/typical settings (not the cheapest input that merely exercises the code), inspect the actual file, confirm it follows the prompt. Outputs must land in `~/ai_generated/<service>/` with timestamps.
5. **Dark mode always required.** Every web UI defaults to dark on first load with localStorage persistence. See `knowledge-base/claude-sync/web_ui_patterns.md` for the full standard.

## Test Artifacts & Cleanup

- Real user-facing generated media belongs in `/home/edq/ai_generated/<service>/` with timestamped filenames.
- Smoke tests, one-step sanity checks, audit runs, screenshots, API response samples, and other throwaway outputs belong in `/home/edq/ai_generated/test-artifacts/<type>/`, usually `images/`, `videos/`, `api-responses/`, or `screenshots/`.
- Do not put throwaway test output in `/home/edq/Downloads`, Mac Downloads, the root of iCloud `1Projects`, or a service's user-facing gallery/output folder.
- `scripts/cleanup_test_artifacts.sh` prunes test artifacts older than 30 days. Keep logs and internal traces in service log folders unless they are part of a deliberate audit artifact.

## Transcript Mining

- Claude/Codex JSONL transcripts are valid historical research material for old ideas, lessons, preferences, and house patterns.
- Read `/home/edq/knowledge-base/claude-sync/transcript_mining.md` before mining transcripts. Treat them as leads, verify live facts, and promote durable nuggets into shared docs such as `feedback_log.md`, `global-CLAUDE.md`, `directory_map.md`, or focused topic notes.

## SOPs

**Model downloads:** NEVER let first launch download models. Create `scripts/download_<service>_models.sh` using `snapshot_download()`, run to completion before declaring done. See `docs/sop-model-downloads.md`.

**Weekly update flags:** at session start, check whether `logs/weekly_update_attention.md` exists — if so, Sunday's auto-update hit something needing a human decision (failed launch-verify, merge conflict, etc.). Mention it proactively without being asked. The file clears itself automatically once the underlying issue resolves.

**New service checklist** (use `dragonsuite-add` skill):

- Standalone-first by default. If the model sort-of fits into WanGP or another existing multi-model app, that's an option to *propose*, not a silent default — reuse is agent-convenient, not automatically user-convenient. Ask.
- venv at `venv_<service>` + entry in `docs/venvs.md`
- start script in `scripts/`, stop_command in `config/dragonsuite.json`
- `output_dir` set in `config/dragonsuite.json` for all generative services
- `~/ai_generated/<service>/` directory exists on disk
- Verify VRAM drops to baseline after stop (`nvidia-smi`)

## Shorthand Commands

**`llkb`** — update memory files + today's Obsidian daily note + CLAUDE.md (service registry pointer and facts ONLY — never add sections, lessons, or patterns here; those go in memory files). "No summary" is not acceptable.

**`tasks/lessons.md`** — append after any correction immediately:
`- YYYY-MM-DD: [what failed] → [rule going forward]`
Read at session start and apply all rules.

## MCP Server Policy

Default active: `dragonsuite` (project), `gbrain` + `sqlite` (user). Everything else is in `_pool` — move to `mcpServers` in `.mcp.json` and restart VSCodium to enable.

| Server             | Enable for                                        |
| ------------------ | ------------------------------------------------- |
| `github`           | GitHub repos, PRs, code search                    |
| `playwright`       | UI/browser testing                                |
| `supabase`         | GBrain DB, Supabase queries                       |
| `topaz-labs`       | Image/video enhancement (cloud)                   |
| `stitch`           | `/stitch-design` UI generation                    |
| `mongodb`          | MongoDB cluster work                              |
| `blender`          | 3D modeling (Blender + MCP addon must be running) |
| `vocab-translator` | Translation QA pipeline                           |

Remote claude.ai servers (Gmail, Calendar, Canva, etc.) — manage via Settings → Integrations on claude.ai.

## Skill Routing

Invoke via the Skill tool **first** when the request matches.

| Request type                                    | Skill                 |
| ----------------------------------------------- | --------------------- |
| Product ideas, brainstorming, "worth building?" | `office-hours`        |
| Bugs, errors, 500s, "why broken?"               | `investigate`         |
| Ship / deploy / create PR                       | `ship`                |
| QA, find bugs, test the site                    | `qa`                  |
| Code review                                     | `review`              |
| Update docs after shipping                      | `document-release`    |
| Design system, brand                            | `design-consultation` |
| Visual audit, design polish                     | `design-review`       |
| Architecture review                             | `plan-eng-review`     |
| New Dragonsuite service                         | `dragonsuite-add`     |

## GBrain

- Engine: postgres (Supabase — project zvkwushxufacojfbmppq, us-east-1)
- Config: `~/.gbrain/config.json` (mode 0600), MCP registered user scope (`gbrain serve`)
- Cross-machine restore: copy `~/.gstack-brain-remote.txt` to new machine, run `gstack-brain-restore`
