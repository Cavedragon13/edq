# Overnight conformance runbook (unattended)

You are running unattended on udragon at night via `scripts/overnight_agent.sh`. Ed is
asleep; nobody will answer questions. Work carefully, verify everything, leave every
service at least as good as you found it, and write the morning report.

## First, read

1. `/srv/containers/edq/CLAUDE.md` and `/srv/containers/edq/tasks/lessons.md` (apply every rule).
2. `~/knowledge-base/Dragonsuite/Conformance.md` — tonight's to-do list (rewritten at 00:15).
3. The two reference launchers that show the standard: `scripts/start_fish_speech.sh`
   (converted 2026-09-24) and `scripts/start_ace_step.sh`, plus `scripts/vram_guard.sh`.

## Queue — do at most 3 units of work tonight, in this priority order

1. **[vram] launchers still on `gpu_preflight`.** Convert one service = one unit, exactly like
   `start_fish_speech.sh`: add `TOOL_NAME` / `REQ_VRAM_MIB` / `REQ_RAM_MIB` + `source scripts/vram_guard.sh`,
   replace `gpu_preflight "$PORT"` with `vram_preflight || exit 1` + `clear_port "$PORT"`,
   `register_tool` the PID that actually holds the GPU (the server itself, not a wrapper —
   see how start_ace_step.sh registers the port owner), give `wait_for_port` enough time.
   Then MEASURE: launch it, run a real generation at the UI's default settings, log peak VRAM
   (`nvidia-smi --query-gpu=memory.used ... -lms 500`) and peak RSS; set REQ_VRAM_MIB to the
   measured peak above the ~1GB desktop baseline + ~5% headroom, REQ_RAM_MIB likewise, and
   update that service's `vram_gb` in `config/dragonsuite.json` (preserve file formatting:
   json.dumps indent=4, ensure_ascii=True; diff must touch only that line).
2. **[download] missing download scripts** for GPU services: write
   `scripts/download_<service>_models.sh` from what the code actually loads (read it; HF repo ids
   verified against the model card), run it, confirm it's a no-op when weights exist.
3. **[output] wiring**: only when the fix is unambiguous (the app has a documented output
   setting). Otherwise report it for Ed.

## Never (report instead)

- The MiniMax Music 3 dedupe test is deferred to a supervised session with Ed.
  Do not launch it or finalize its backups during unattended runs.
- GPU room is handled for you (Ed, 2026-10-23: anything idle between midnight and 04:00
  may be stopped as long as it comes back). Before you start, the supervisor checks the
  GPU is idle, stops every running GPU service (Krea2 included), unloads Ollama models,
  and lists what it stopped as `evicted` in the journal; it restarts them when you finish.
  Do not stop services to make room yourself, and do not restart evicted ones.
  If nothing was evicted because the GPU was busy, someone is working: defer GPU tests
  and do non-GPU units only.
- Never delete `logs/overnight_agent/*.services.json` (the supervisor's journal).
- All test launches MUST use `python3 scripts/overnight_services.py start
  "$OVERNIGHT_SERVICE_JOURNAL" <service-id>` (on one command line). This records
  ownership before the dashboard launch so the external supervisor can clean up.
  Do not launch via raw dashboard start requests or direct launcher commands.
- The supervisor enforces 90 minutes for the run and 20 minutes per test service.
  Never finish a one-shot session saying you are waiting for a background task:
  complete the test or stop it, record the deferral, and write the report.
- Krea 2 (`krea2*`) — do not touch its launcher, files or LoRAs.
- `[update]` items (Ed's own code, uncommitted edits, git-ignored projects), ComfyUI
  migrations, retiring/deleting services, deleting model data, anything requiring sudo,
  systemd, crontab, fstab, network or firewall changes, `git push`, installing new services.
- Test launches go through the journal helper above; the dashboard detaches launchers.
- Only one GPU service at a time; stop it via `curl -s -X POST http://127.0.0.1:8100/api/stop/<id>`
  and confirm VRAM returns to baseline before starting the next.
- If Ed starts new GPU work during a test, stop only your own test services and
  write the report. Never stop a running service that was not evicted.

## Verify every unit

- `bash -n` / `python3 -m py_compile` every file you changed.
- Launch-verify through the journal helper (which uses the dashboard path) and
  print its JSON reply (a "vram_warning" reply means the launcher did not run).
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
