# Krea2 prompt history

Open **History** in the Krea2 header. Prompts and settings save automatically while
you edit; you do not need to generate an image or switch pages to save them.
Wait for the History button's tooltip to say the draft is saved before switching
machines. Save failures appear beside the prompt.

Use **Current session name** to name an idea or project. Search history by session
name or prompt text, then choose **Restore prompt & settings** to continue it on
another machine. This restores dimensions, steps, seed setting, guidance, sampler,
LoRAs and their weights, and source image when retained. Successful generations
include image links; failures retain the prompt and error. **New session** starts
another idea. Each browser tab starts independently; reloading restores its draft.

Both machines must open the same udragon Krea2 service on port 8062. This history
does not synchronize a separate Mac-hosted runner. Session names group the history;
existing image files stay where they are. Restoring a seed of -1 requests another
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
