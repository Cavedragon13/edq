# DragonArt Studio

Updated 2026-09-13. Canonical source: `/srv/containers/edq/projects/dragonart-studio`; Python server: `scripts/dragonart_server.py`; launcher: `scripts/start_dragonart.sh`; port 8015. Uses the existing `venv_dragonsuite` (openai, google-genai, python-dotenv) and Node 20 for the React production build. No local GPU model or download is required.

Image modes use stable `gemini-3.1-flash-image` (Nano Banana 2), `gemini-3-pro-image` (Nano Banana Pro), `gpt-image-2.5-sunburst`, and default `gpt-image-2.5-flare`. The existing internal `gpt-image-2` UI ID is retained for compatibility; the visible label and outgoing request identify Sunburst. Shared live model discovery recognizes stable Gemini image IDs and both GPT Image 2.5 variants. Other services retain their existing default ranking.

All provider calls, including naming, metadata and existing Veo video generation, run through the Python proxy. Keys are loaded only from `/srv/containers/edq/.env`; do not put credentials in `.env.local` or Vite define. `/api/config` returns configured booleans and model IDs, never keys. The launcher always rebuilds so service-module edits cannot leave a stale bundle. Development Vite proxies `/api` to 8015.

Sunburst supports auto size and quality, the documented dimension limits, and extra-high/maximum quality. Fixed per-image cost estimates were removed because they used obsolete pricing and did not reflect output dimensions or actual usage. Theme defaults to dark and persists via localStorage.

Normal image/video/session outputs go to `/home/edq/ai_generated/dragonart-studio/`. For tests launch with `DRAGONART_OUTPUT_DIR=/home/edq/ai_generated/test-artifacts/images/<run>`; restart without this variable after testing. Runtime logs: `/srv/containers/edq/logs/dragonart-studio/`. Launch/stop uses the shared zero-VRAM gate and recorded PID. Dashboard stop matches the absolute server script path.

Existing session ZIP exports also copy into the Publish queue. Do not use export as a smoke test unless publication is intended.

Official references: https://ai.google.dev/gemini-api/docs/image-generation and https://developers.openai.com/api/docs/guides/image-generation .

## Verification — 2026-09-13

OpenAI generation passed through the API and Chrome UI; PNGs decoded and were visually inspected. Studio Auto size/quality passed. CoverSynth playlist analysis and persisted PNG generation passed. Theme persistence and Studio session restoration passed. TypeScript, build, 16 unit tests and image-category structural health checks passed; npm audit reports zero vulnerabilities after compatible dependency fixes. Dashboard stop/start verified separately. Test images and JSON evidence are under `/home/edq/ai_generated/test-artifacts/{images,api-responses}/dragonart-refresh-20260913/`.

After the $5 prepaid balance was added, both stable Google image models generated valid 1024×1024 PNGs through the production proxy: Nano Banana 2 in 59.2 seconds and Nano Banana Pro in 23.5 seconds. Both outputs decoded successfully and were visually inspected. Naming and metadata helpers also passed after their response validation was tightened. Veo proxy was checked against SDK documentation; video output was not part of this image-model verification.

Billing identity check: the running DragonArt GOOGLE_API_KEY matches AI_Studio in the Gemini API project, Tier 2 Prepay, not the free-tier Translation Game key. The previous VSCode attribution in CLAUDE.md was corrected.

## Sprite sheets and drawing presets — 2026-09-13

GPT Image 2.5 Flare is the Studio default (`gpt-flare` -> `gpt-image-2.5-flare`); Sunburst remains selectable. Char Sheet has concept turnaround and game sprite modes, with rendering, camera and action-pack dropdowns. Sprite output is one 1536x2304 transparent PNG, 4 columns x 6 rows of 384px cells. It bypasses the old source crop, requests real alpha, and uses Flare when Gemini is selected. A four-frame row covers each action; these are generated animation assets and may need alignment/timing cleanup in a game editor.

Edge includes blueprint, Da Vinci scientific parchment, architectural drawing, Da Vinci architectural parchment, and conceptual PCB diagram. Canny is now a real local OpenCV filter (Gaussian blur + thresholds 80/160), with no image API charge. Depth and thermal modes are explicitly inferred/stylized, not measured maps. Drawing presets are prompt-based raster illustrations, not CAD/netlists.

Session persistence now uses IndexedDB and original image bytes. It migrates legacy localStorage after a successful commit, retains full resolution and alpha, and saves sprite/drawing settings. A still-open old tab's later localStorage write is preferred on the next restore. Existing tabs are never force-reloaded. No session export was used for tests (it would enqueue publication).

Backend dependencies are in `projects/dragonart-studio/requirements-server.txt`. OpenCV and NumPy were added to the existing CPU/API venv. Separate staging uses `DRAGONART_DIST_DIR` and `DRAGONART_OUTPUT_DIR`; the normal service output remains unchanged.

Tests: Flare generated a verified 24-frame RGBA sheet and all nine Edge choices produced outputs, including a binary same-size Canny result. Test images are in `/home/edq/ai_generated/test-artifacts/images/dragonart-next-20260913/`. TypeScript, production build and 21 unit tests passed, including large-image storage, legacy migration, pending-save/clear ordering and old-tab writes.

## External layers and Krea connection status

Canva Magic Layers succeeded through Ed's connected Codex Canva account: design DAHVGwsJQ1Q, https://www.canva.com/d/ZYjOj6oZySZDX8j . This is a working assistant handoff, not a native Studio button. Canva requires allowlisting a custom app's redirect URI before native MCP access: https://www.canva.dev/docs/mcp/ . Do not imply an account password or Vaultwarden unlock bypasses that registration.

Krea OAuth uses the selected workspace's compute units; API keys use its separate API balance. No Krea API key was present. OAuth setup is prepared in `work/dragonart-next-20260913/krea_connect.py`. Krea rejects plain HTTP LAN callbacks, so the setup uses temporary SSH loopback forwarding to port 18116; tokens and client registration are stored only in `/home/edq/.config/dragonart/` with mode 0600. Account consent and authenticated model/schema discovery are still pending. Do not claim Krea generation is wired until an authenticated output test passes. No Canva password or Vaultwarden master password was accessed.

Deployment verification: production port 8015 reports `gpt-image-2.5-flare` as its default, and the live hidden-browser menu shows all nine Edge choices. Real UI sprite generation persisted a 1536x2304 PNG (6,037,250-character data URI), with identical checksum after reload and retained dropdown selections. UI Canny generated step 2 successfully. Production Canny returned a binary 1536x2304 image from a transparent source. Image-category health: 16 PASS, 0 WARN, 0 FAIL. The isolated 18115 server and only our hidden test tabs were closed; user Chrome tabs were untouched.
