#!/bin/bash
# Pre-download Supra2-IMG and its inference dependencies.
set -e
cd /srv/containers/edq
source venv_supra2_img/bin/activate
export HF_HUB_DISABLE_XET=1
python3 - <<'PY'
from pathlib import Path
from huggingface_hub import snapshot_download

root = Path('/srv/containers/edq/models/supra2-img')
root.mkdir(parents=True, exist_ok=True)
jobs = [
    ('SupraLabs/Supra2-IMG', root, ['model_final_ema.pt']),
    ('google/flan-t5-base', root / 'flan-t5-base', [
        'config.json', 'generation_config.json', 'model.safetensors',
        'special_tokens_map.json', 'spiece.model', 'tokenizer.json',
        'tokenizer_config.json',
    ]),
    ('stabilityai/sd-vae-ft-mse', root / 'sd-vae-ft-mse', [
        'config.json', 'diffusion_pytorch_model.safetensors',
    ]),
]
for repo_id, local_dir, allow_patterns in jobs:
    local_dir.mkdir(parents=True, exist_ok=True)
    print(f'Downloading {repo_id} -> {local_dir}', flush=True)
    kwargs = {'repo_id': repo_id, 'local_dir': str(local_dir)}
    if allow_patterns:
        kwargs['allow_patterns'] = allow_patterns
    snapshot_download(**kwargs)
print('Supra2-IMG models are ready.')
PY
