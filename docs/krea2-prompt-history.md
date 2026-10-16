# Krea2 prompt history

Open **History** in the Krea2 header. Prompts and settings save automatically while
you edit; you do not need to generate an image or switch pages to save them.
Wait for the History button's tooltip to say the draft is saved before switching
machines. Save failures appear beside the prompt.

Use **Session name** above the prompt to name an idea or project. Search history by session
name or prompt text, then choose **Restore prompt & settings** to continue it on
another machine. This restores dimensions, steps, seed setting, guidance, sampler,
LoRAs and their weights, and source image when retained. Successful generations
include image links; failures retain the prompt and error. **New session** starts
another idea. Each browser tab starts independently; reloading restores its draft.

Both machines must open the same udragon Krea2 service on port 8062. This history
does not synchronize a separate Mac-hosted runner. Session names group the history;
existing image files stay where they are. New images use that name plus a sequential
number, for example `Moonlit-Harbor-0001.png`. Numbering continues after reloads,
between browsers, and across server restarts. Names are made safe for filenames;
sessions with the same sanitized name share a sequence. Unnamed sessions use
`session-YYYYMMDD-0001.png`. Existing images are never renamed or overwritten.
Restoring a seed of -1 requests another
random seed, rather than reproducing the original image.

History lives in `krea2/logs/prompt-history.sqlite3`; retained source images live in
`krea2/logs/inputs/`. These are local runtime data, outside Git. No models, LoRAs,
or generation defaults are changed. Old prompts can be recovered idempotently with
`python3 krea2/import_prompt_history.py krea2/logs /home/edq/ai_generated/krea2`.
Imported prompts are grouped by date; images are linked when still present.

The dashboard's Running tab means the web server is reachable. An individual
sd-cli generation can still fail, for example from GPU memory pressure. Its error
now identifies memory exhaustion and points to its generation log. Invalid-input
errors release the generation lock so a new request can proceed without restarting.

## LoRA library

**LoRA Library** opens a side panel with search, source links, installed/latest
versions, trigger phrases, and buttons to add a LoRA or its trigger to the prompt.
The service status and folder path are under **Service details**, out of the prompt
area. **Open folder** opens udragon's file manager. On a Mac, **Open in Finder**
uses the existing `edq` Samba share; **Browse files** works in the browser anywhere.

**Check updates** only reads source metadata. **Update all** checks the installed
files and replaces those with an unambiguous newer compatible release. Official
renamed LoRAs map to their Hugging Face repositories; other files are identified by
exact SHA256 through Civitai. Downloads require a matching published checksum and
a valid safetensors header with a matching tensor family. Variants on a different
base model, ambiguous files, unknown sources, blocked downloads, and updates during
an active generation are left unchanged and reported in the panel.

Updates preserve local filenames and selected weights. Previous files are retained
under `krea2/logs/lora-backups/` (the panel's source page lists upstream versions).
This verifies file integrity and compatibility metadata, not artistic quality; old
weights remain available with a **Restore previous** button if a new version is less
useful. Source metadata and cached
hashes live in `krea2/logs/lora-library.json`. Civitai authentication, when needed,
uses `CIVITAI_API_KEY` from the central `/srv/containers/edq/.env`; credentials never
go to the browser. No automatic schedule is installed.

## Source-image limits

The current runner accepts one PNG, JPEG or WebP source image, at most 20 MB. The
two-output cap is a local memory precaution. This is the existing image-to-image
path, not multi-reference editing. Krea2 reference editing is a separate conditioning
workflow using compatible edit/reference LoRAs; it is not enabled by adding more
files to this input. No source-image behavior or model defaults change here.
