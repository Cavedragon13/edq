# Battle Cars on udragon

3D post-apocalyptic car combat racer, playable at `http://192.168.7.226:8069/`. Standalone Dragonsuite service in the Games category: no GPU, no models, no venv (the server is Python standard library only; Three.js is vendored).

## Lifecycle

- Source: `/srv/containers/edq/projects/battle-cars` (plain ES modules, no build step).
- Start: `bash /srv/containers/edq/scripts/start_battle_cars.sh` (port 8069, vram_guard footprint 0 MiB VRAM).
- Stop: `bash /srv/containers/edq/scripts/stop_battle_cars.sh` (stops by listening port).
- Log: `/srv/containers/edq/logs/battle-cars/server.log`.
- Save game (both campaign profiles + settings): `/home/edq/ai_generated/battle-cars/save.json`, written by the server's `/api/save`; the browser also keeps a `localStorage` copy and the newer one wins.
- Three.js r186 lives in `projects/battle-cars/vendor/` (module build + core + license). Update by replacing those two files from the `three` npm package.

## Game

- Campaign: nine levels, each with a cross-country (point-to-point, hostile raiders) and a circuit (3 laps, a boss racer). Two profiles let two players take turns; each keeps its own locked car, upgrades and progress.
- Cash comes from destroying raiders on cross-country tracks and buys vehicle upgrades (engine, top speed, tires, armor, each to level 8). Credits come from finishing cross-country tracks quickly and buy weapon levels (missile, disk, grenade, each to level 5).
- A level unlocks when both its tracks are cleared: finish the cross-country track in time, and finish the circuit ahead of the boss.
- Versus: two-player split screen on any of the 18 tracks, optional AI racers, a tuning handicap (stock / mid / maxed), and the first three bosses (Grinder, Viper, Crusher) as selectable cars with alternate colors.
- Controls are in the game's Controls screen (P1 WASD + Space, P2 arrows + Enter, gamepads supported).

## Code map

| File | Role |
| --- | --- |
| `js/tracks.js` | Procedural track generation (pure data; `node validate_tracks.mjs` checks all 18) |
| `js/world.js` | Builds the scene: road, barriers, scenery, sky, pickups |
| `js/car.js`, `js/ai.js` | Arcade physics, wall handling, AI driving and firing |
| `js/race.js` | Race engine: weapons, damage, pickups, cameras, split screen, HUD |
| `js/data.js` | Cars, bosses, weapons, upgrade costs, level themes (balance knobs live here) |
| `js/ui.js` | Menus, garage, versus setup, results, campaign progression |

## Testing hooks

`window.BC.quick(level, 'circuit'|'xc', {auto:true, tune:0..8, laps})` starts a race with an autopilot human; `BC.race.simulate(seconds)` fast-forwards without rendering; `BC.snap()` dumps state. URL form: `/?quick=3,circuit&auto=1&speed=4`. Headless Chrome needs `--use-angle=swiftshader`.
