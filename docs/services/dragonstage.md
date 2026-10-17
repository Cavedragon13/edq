# DragonStage (2026-10-16)

Native Godot 4.7.2 scene composer, primary development on odragon at `/Users/edq/Documents/DragonStage`. Canonical Linux checkout and Git mirror: `/srv/containers/edq/projects/dragonstage`. Source, builds and acceptance ledger are in that repository. No venv, model, CUDA or external API dependency.

The existing Dashboard Start action runs `scripts/start_dragonstage.sh` over SSH and opens `/Applications/DragonStage.app` on **odragon**. The running application supplies a read-only status page on odragon `odragon.local:8073`. The launcher resolves the Mac’s current non-loopback IPv4 address, so DHCP changes do not require a registry edit. This status listener is disabled for normal standalone launches. Stop requests normal macOS Quit; unsaved work prompts must be resolved at the native window, never force-killed. No dashboard server/UI modifications were needed.

Native Mac saves default to `~/Documents/DragonStage Scenes`; dashboard-launched saves/exports copy to `/home/edq/ai_generated/dragonstage/dragonstage_<timestamp>_<id>.<extension>`. Copy failures retain local files and report the failure. Standalone Linux exports default directly to that output directory. Test outputs are under `/home/edq/ai_generated/test-artifacts/images/dragonstage-linux`, not the production gallery.

Milestones are **not all complete**. See repository `docs/PROGRESS.md` for evidence and remaining image references, recovery, true HDR output, depth/masks and interface refinement. Builds are ad-hoc signed for local Mac use, not notarized for public distribution. No Apple licenses were accepted.

2026-10-17: 0.4.0 adds verified GLB/glTF, OBJ and STL export, including affine geometry and portable baked materials. Multi-file exports are packaged as ZIP files before mirroring. Mac and Linux application suites passed 111 checks each; Blender passed 40 downstream checks. A DHCP address change from .133 to .134 exposed the old fixed-IP assumption; the launcher and registry now use local-name resolution. Existing registry entries were verified unchanged. Real-output mirroring still awaits its final end-to-end check.
