# CoverSynth OpenAI

Updated 2026-09-13. Canonical source: `/srv/containers/edq/projects/coversynth-openai`; launcher: `scripts/start_coversynth_openai.sh`; port 8053. Uses existing `venv_dragonsuite`, shared model discovery, and the single `/srv/containers/edq/.env`. No GPU or model download is needed.

The image default is `gpt-image-2.5-flare`, selected from the live account model list. Playlist analysis uses the existing selectable text model. Covers are generated as 1024x1024 PNGs, medium quality by default. Higher quality options include xhigh and max. The existing refinement workflow augments the prompt and regenerates; it does not supply the previous cover as an image-edit reference.

Each successful generation now saves an actual timestamped PNG to `/home/edq/ai_generated/coversynth-openai/` before returning it to the browser. Response `file` identifies the saved path. Logs now go to `/srv/containers/edq/logs/coversynth-openai/`, not the image gallery; older historical logs remain untouched. For tests use `COVERSYNTH_OUTPUT_DIR=/home/edq/ai_generated/test-artifacts/images/<run>` and restart normally afterward. Browser download remains available. Theme defaults to dark with a persistent toggle.

This standalone app remains a playlist-analysis/cover-generation workflow. DragonArt Studio is a separate image-editing/session workflow; neither is removed or merged by this update.

Official model reference: https://developers.openai.com/api/docs/guides/image-generation .

## Verification — 2026-09-13

OpenAI generation passed through the API and Chrome UI; PNGs decoded and were visually inspected. Studio Auto size/quality passed. CoverSynth playlist analysis and persisted PNG generation passed. Theme persistence and Studio session restoration passed. TypeScript, build, 16 unit tests and image-category structural health checks passed; npm audit reports zero vulnerabilities after compatible dependency fixes. Dashboard stop/start verified separately. Test images and JSON evidence are under `/home/edq/ai_generated/test-artifacts/{images,api-responses}/dragonart-refresh-20260913/`.

Google stable image models and naming/metadata helpers were attempted before and after promotional-credit redemption. They remain blocked by depleted prepaid credits; account authentication/model listing succeeds. Veo proxy was checked against SDK documentation but no video output was generated due to the same billing block. Google generation is not marked verified.

Billing identity check: the running DragonArt GOOGLE_API_KEY matches AI_Studio in the Gemini API project, Tier 2 Prepay, not the free-tier Translation Game key. The previous VSCode attribution in CLAUDE.md was corrected.
