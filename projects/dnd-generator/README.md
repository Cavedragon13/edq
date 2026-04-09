# Dungeon Generator

Small browser-based D&D character generator with:

- 5d6 per stat, keeping the best 3
- stats shown in classic `SIWDCCh` order
- editable sheet fields
- room for armor, weapons, magic items, and notes
- a rerollable, in-browser portrait generator
- light and dark modes with saved preference
- portrait export as PNG

## Run it

Open [index.html](./index.html) in a browser, or serve the folder locally:

```bash
cd /home/edq/projects/dnd-generator
python3 -m http.server 4173
```

## Dashboard

This project is also registered with the Dragonsuite dashboard:

```bash
cd /srv/containers/edq
bash scripts/start_dnd_generator.sh
```
