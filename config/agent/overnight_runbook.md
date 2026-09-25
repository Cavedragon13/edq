# Overnight conformance runbook (unattended)

You are running unattended on udragon at night via `scripts/overnight_agent.sh`. Ed is
asleep; nobody will answer questions. Work carefully, verify everything, leave every
service at least as good as you found it, and write the morning report.

## First, read

1. `/srv/containers/edq/CLAUDE.md` and `/srv/containers/edq/tasks/lessons.md` (apply every rule).
2. `~/knowledge-base/Dragonsuite/Conformance.md` — tonight's to-do list (rewritten at 04:30).
3. The two reference launchers that show the standard: `scripts/start_fish_speech.sh`
   (converted 2026-09-24) and `scripts/start_ace_step.sh`, plus `scripts/vram_guard.sh`.

## Queue — do at most 3 units of work tonight, in this priority order

1. **Pending link tests.** If `find /srv/containers/edq/models /srv/containers/edq/projects -name '*.dedupe-bak'`
   finds backups, launch the owning service (AuK → `models/auk/`, MiniMax Music 3 →
   `models/minimax-music3/`), run one real generation at default settings, check the output
   is real (ffprobe duration, volumedetect not silent). Release backups with
   `python3 scripts/dedupe_models.py finalize backups/dedupe_plan_20260924.json [KEEP ...]` —
   the extra arguments name backups to KEEP (services that have NOT passed yet):
   both passed → no extra arguments; only AuK passed → `minimax-music3/`; only MiniMax
   passed → `models/auk/`; neither → don't run finalize.
   If the launcher is refused for lack of RAM, record it and move on — do not force.
2. **[vram] launchers still on `gpu_preflight`.** Convert one service = one unit, exactly like
   `start_fish_speech.sh`: add `TOOL_NAME` / `REQ_VRAM_MIB` / `REQ_RAM_MIB` + `source scripts/vram_guard.sh`,
   replace `gpu_preflight "$PORT"` with `vram_preflight || exit 1` + `clear_port "$PORT"`,
   `register_tool` the PID that actually holds the GPU (the server itself, not a wrapper —
   see how start_ace_step.sh registers the port owner), give `wait_for_port` enough time.
   Then MEASURE: launch it, run a real generation at the UI's default settings, log peak VRAM
   (`nvidia-smi --query-gpu=memory.used ... -lms 500`) and peak RSS; set REQ_VRAM_MIB to the
   measured peak above the ~1GB desktop baseline + ~5% headroom, REQ_RAM_MIB likewise, and
   update that service's `vram_gb` in `config/dragonsuite.json` (preserve file formatting:
   json.dumps indent=4, ensure_ascii=True; diff must touch only that line).
3. **[download] missing download scripts** for GPU services: write
   `scripts/download_<service>_models.sh` from what the code actually loads (read it; HF repo ids
   verified against the model card), run it, confirm it's a no-op when weights exist.
4. **[output] wiring**: only when the fix is unambiguous (the app has a documented output
   setting). Otherwise report it for Ed.

## Never (report instead)

- Krea 2 (`krea2*`) — do not touch its launcher, files or LoRAs.
- `[update]` items (Ed's own code, uncommitted edits, git-ignored projects), ComfyUI
  migrations, retiring/deleting services, deleting model data, anything requiring sudo,
  systemd, crontab, fstab, network or firewall changes, `git push`, installing new services.
- Never run a model launcher as a child of your shell (a memory spike OOM-kills your session):
  always `setsid nohup bash scripts/start_X.sh > <log> 2>&1 < /dev/null &` and poll the port.
- Only one GPU service at a time; stop it via `curl -s -X POST http://127.0.0.1:8100/api/stop/<id>`
  and confirm VRAM returns to baseline before starting the next.
- If Ed's own work appears (a GPU process you didn't start, besides idle ComfyUI), stop your
  run, leave everything stopped/clean, and write the report.

## Verify every unit

- `bash -n` / `python3 -m py_compile` every file you changed.
- Launch-verify from the dashboard path too: `curl -s -X POST http://127.0.0.1:8100/api/start/<id>`
  and print the JSON reply (a "vram_warning" reply means the dashboard didn't run the launcher).
- Real generation at defaults, inspect the output file (image: look at it; audio/video: ffprobe +
  a frame/volume check). Test outputs go to `~/ai_generated/test-artifacts/<type>/`, never the
  service's gallery — move them out if the app wrote them there.
- Stop → VRAM back to baseline.
- `python3 scripts/health_check.py --all` — the unit's conformance entry must be gone.

## If a unit fails

Revert that service's files (`git -C /srv/containers/edq checkout -- <files>` for tracked files,
or restore your own copy), stop anything you started, and record exactly what failed with the
log lines. Never leave a service broken or half-converted.

## Commit

For each successful unit: `git -C /srv/containers/edq add <exact files>` then
`git commit -m "overnight: <service> — <what changed>"` (no push). Nothing else.

## Morning report (always write it, even if you did nothing)

Write `~/knowledge-base/Dragonsuite/Overnight/<YYYY-MM-DD>.md` with:

- **Done** — each unit: what changed, measured VRAM/RAM, test evidence (file + what it showed).
- **Failed / reverted** — what, why, log excerpt.
- **Needs Ed** — decisions you were not allowed to make, with your recommendation.
- **Tomorrow** — the next 3 queue items.
Keep it short and plain; Ed reads it with coffee.
