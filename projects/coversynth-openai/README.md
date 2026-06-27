# CoverSynth OpenAI

Dragonsuite browser app for playlist analysis and square cover generation with OpenAI.

- Analysis uses the Responses API with a selectable lightweight model.
- Cover generation uses `gpt-image-2` at `1024x1024`.
- The OpenAI key stays server-side via `/srv/containers/edq/.env`.
- Results are logged to `/home/edq/ai_generated/coversynth-openai/coversynth-openai.jsonl`.

Run through Dragonsuite or directly:

```bash
cd /srv/containers/edq
bash scripts/start_coversynth_openai.sh
```
