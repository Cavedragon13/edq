# DragonStage (2026-10-16)

Native Godot 4.7.2 scene composer, primary development on odragon at `/Users/edq/Documents/DragonStage`. Canonical Linux checkout and Git mirror: `/srv/containers/edq/projects/dragonstage`. Source, builds and acceptance ledger are in that repository. No venv, model, CUDA or external API dependency.

The existing Dashboard Start action runs `scripts/start_dragonstage.sh` over SSH and opens `/Applications/DragonStage.app` on **odragon**. The running application supplies a read-only status page on odragon `192.168.7.133:8073`. This status listener is disabled for normal standalone launches. Stop requests normal macOS Quit; unsaved work prompts must be resolved at the native window, never force-killed. No dashboard server/UI modifications were needed.

Native Mac saves default to `~/Documents/DragonStage Scenes`; dashboard-launched saves/exports copy to `/home/edq/ai_generated/dragonstage/dragonstage_<timestamp>_<id>.<extension>`. Copy failures retain local files and report the failure. Standalone Linux exports default directly to that output directory. Test outputs are under `/home/edq/ai_generated/test-artifacts/images/dragonstage-linux`, not the production gallery.

Milestones are **not all complete**. See repository `docs/PROGRESS.md` for evidence and remaining image references, mapping/material enhancements, presets, depth/masks and secondary export work. Builds are ad-hoc signed for local Mac use, not notarized for public distribution. No Apple licenses were accepted.
