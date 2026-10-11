# Rogue Gauntlet on udragon

Top-down roguelike dungeon crawler, playable at `http://192.168.7.226:8072/`. Standalone Dragonsuite service in the Games category: no GPU, no models, no venv (Python stdlib server, plain ES modules, Canvas 2D, zero dependencies). All art is painted procedurally in code, so there are no image assets.

## Lifecycle

- Source: `/srv/containers/edq/projects/rogue-gauntlet` (own git repo).
- Start: `bash scripts/start_rogue_gauntlet.sh` (port 8072, 0 MiB VRAM). Stop: `bash scripts/stop_rogue_gauntlet.sh` (by port).
- Log: `logs/rogue-gauntlet/server.log`.
- Save: `/home/edq/ai_generated/rogue-gauntlet/save.json` via `/api/save`; a `localStorage` copy is kept too and the newer one wins. Delete the file to reset soul shards and ranks.

## Game

- Four classes, each with a male and a female hero: Warrior (melee arc, Whirlwind), Ranger (arrows, Volley), Wizard (explosive bolts, Nova), Paladin (mace, Radiance heal + stun).
- Five floors of procedurally generated rooms. Combat rooms lock until cleared; bone-pile spawners keep producing enemies until destroyed. Special rooms: shop, healing fountain, treasure (one guaranteed relic upgrade), boss. Bosses: Ogre King, The Lich, Dragon Lord.
- Leveling: every level-up offers 3 upgrade cards. Four upgrade tracks, 5 tiers each: Weapon, Armor, Healing, Magic. Gear tier recolors the hero's weapon/armor sprite. The shop sells tiers, potions and a full restore.
- Roguelike: permadeath. Every run pays soul shards (win or lose), spent in the Soul Forge on permanent ranks (Vitality, Might, Fortune, Provisions).
- Difficulty: Casual / Normal / Brutal (enemy HP and damage, shard payout).
- Controls: WASD move; Space/J/click attack (arrow keys or mouse aim); K/Shift/right-click spell; Q potion; E interact; Esc pause; M mute. Gamepad supported (sticks, A/X/B/Y), not hardware-tested.

## Code map

| File | Role |
| --- | --- |
| `js/data.js` | All balance knobs: classes, enemies, tracks, floors, difficulty, meta, shop prices |
| `js/game.js` | State, combat, enemy and boss AI, pickups, leveling, rendering, test bot |
| `js/dungeon.js` | Floor graph and room tile layouts |
| `js/sprites.js` | Procedural pixel art (heroes, enemies, bosses, tiles) |
| `js/ui.js`, `js/main.js`, `js/input.js`, `js/audio.js`, `js/save.js` | Overlays, wiring, input, WebAudio sfx, save |
| `dev/sprite-sheet.html` | Shows every sprite; `#3` previews gear tier 3 |

## Testing

Headless Chromium with `playwright-core@1.49` (system node is 18) and `--use-angle=swiftshader`. Hooks: `RG.quick(cls, gender, {floor, lvl, up, auto, sloppy, seed, difficulty})`, `RG.simulate(sec)`, `RG.snapshot()`. `auto:true` runs a built-in bot; `sloppy:true` makes it dodge and kite like a mediocre player. Bot results at the shipped balance: competent bot clears every run; sloppy bot clears about half, with the Ranger the most fragile. Screenshots go in `ai_generated/test-artifacts/screenshots/rogue-gauntlet/`.

## Lessons from building it

- Ground enemies need obstacle steering, and the room must never hold an unreachable or embedded enemy (rooms lock until clear). Both are handled (`steer`, `unstick`).
- Flying enemies must use flying collision everywhere, or they get trapped in pillars.
- Keys the UI handles (Esc, E) must be swallowed so the frame loop doesn't re-trigger them.
