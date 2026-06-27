# RPG Char Gen

Small browser-based D&D character generator with:

- 5d6 per stat, keeping the best 3
- stats shown in classic `SIWDCCh` order
- editable sheet fields
- room for armor, weapons, magic items, and notes
- a rerollable, in-browser portrait generator
- optional OpenAI Images API portrait generation using `gpt-image-2` with `OPENAI_API_KEY` loaded server-side from `.env`
- light and dark modes with saved preference
- portrait export as PNG

## Run it

Serve the folder locally so AI portraits can use `OPENAI_API_KEY` from `/srv/containers/edq/.env` or a project-local `.env`:

```bash
cd /home/edq/projects/dnd-generator
PORT=4173 python3 server.py
```

Opening [index.html](./index.html) directly still works for local SVG portraits, but AI portrait generation needs the server.

## Dashboard

This project is also registered with the Dragonsuite dashboard:

```bash
cd /srv/containers/edq
bash scripts/start_dnd_generator.sh
```
