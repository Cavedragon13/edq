"""Discover exact LoRA sources and install verified updates without losing favorites."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import errno
import threading
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler


class ScopedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        if urlparse(url).scheme != 'https':
            raise ValueError('Model download redirected to a non-HTTPS address')
        redirected = super().redirect_request(request, response, code, message, headers, url)
        if urlparse(request.full_url).hostname != urlparse(url).hostname:
            redirected.remove_header('Authorization')
        return redirected


urlopen = build_opener(ScopedRedirect()).open


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tensor_header(path):
    with path.open('rb') as stream:
        size = int.from_bytes(stream.read(8), 'little')
        if not 2 <= size <= 32 * 1024 * 1024:
            raise ValueError('Not a valid safetensors file')
        header = json.loads(stream.read(size))
    tensors = {k:v for k,v in header.items() if k != '__metadata__'}
    if not tensors or any(not isinstance(v, dict) or 'data_offsets' not in v for v in tensors.values()):
        raise ValueError('No valid tensors in downloaded file')
    end = max(v['data_offsets'][1] for v in tensors.values())
    if end + size + 8 != path.stat().st_size:
        raise ValueError('Safetensors length is inconsistent')
    return tensors


class Library:
    def __init__(self, root, log_dir, manifest, generation_lock):
        self.root, self.log_dir, self.manifest = Path(root), Path(log_dir), Path(manifest)
        self.generation_lock = generation_lock
        self.lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.cache_path = self.log_dir / 'lora-library.json'
        try:
            self.rows = json.loads(self.cache_path.read_text())
        except (OSError, ValueError):
            self.rows = {}
        self.job = {'running': False, 'message': 'Check updates to identify sources and versions.'}

    def snapshot(self):
        with self.state_lock:
            return json.loads(json.dumps({'job':self.job, 'files':self.rows}))

    def store(self, filename, row):
        with self.state_lock:
            self.rows[filename] = row
            self.log_dir.mkdir(parents=True, exist_ok=True)
            temp = self.cache_path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.rows, indent=2))
            temp.replace(self.cache_path)

    def request(self, url):
        host = urlparse(url).hostname
        if host not in ('huggingface.co', 'civitai.com'):
            raise ValueError('Unrecognized model source')
        headers = {'User-Agent':'Dragonsuite-Krea2/1.0'}
        key = os.environ.get('CIVITAI_API_KEY') if host == 'civitai.com' else os.environ.get('HF_TOKEN')
        if key:
            headers['Authorization'] = 'Bearer ' + key
        return Request(url, headers=headers)

    def remote_json(self, url):
        with urlopen(self.request(url), timeout=25) as response:
            return json.load(response)

    def official(self, path):
        try:
            items = json.loads(self.manifest.read_text()).get('official', [])
        except (OSError, ValueError):
            return None
        stem = re.sub(r'^z_sfw_', '', path.stem)
        return next((item for item in items if Path(item['filename']).stem == stem), None)

    def resolve(self, path, previous):
        stat = path.stat()
        fingerprint = [stat.st_size, stat.st_mtime_ns]
        sha = previous.get('sha256') if previous.get('fingerprint') == fingerprint else file_hash(path)
        row = {**previous, 'sha256':sha, 'fingerprint':fingerprint}
        official = self.official(path)
        if official:
            repo, filename = official['repo_id'], official['filename']
            data = self.remote_json(f'https://huggingface.co/api/models/{repo}?blobs=true')
            file = next(f for f in data['siblings'] if f['rfilename'] == filename)
            expected = file.get('lfs', {}).get('sha256')
            if not expected:
                raise ValueError('Source did not provide a SHA256 checksum')
            row.update(name=official['name'], source='Hugging Face', source_url=f'https://huggingface.co/{repo}',
                       latest=data['sha'][:10], expected=expected.lower(),
                       download=f'https://huggingface.co/{repo}/resolve/{data["sha"]}/{quote(filename)}')
            with urlopen(self.request(f'https://huggingface.co/{repo}/raw/main/README.md'), timeout=25) as response:
                card = response.read().decode()
            trigger = re.search(r'Trigger word:\**\s*`([^`]+)`', card)
            row['trigger'] = trigger.group(1) if trigger else ''
        else:
            current = self.remote_json(f'https://civitai.com/api/v1/model-versions/by-hash/{sha}')
            model = self.remote_json(f'https://civitai.com/api/v1/models/{int(current["modelId"])}')
            row.update(name=model.get('name',path.stem), source='Civitai',
                       source_url=f'https://civitai.com/models/{int(current["modelId"])}',
                       installed=current.get('name',str(current['id'])))
            # Keep the source link even if the weight variant needs manual selection.
            self.store(path.relative_to(self.root).as_posix(),row)
            base = current.get('baseModel', '')
            if 'krea' not in base.lower():
                raise ValueError(f'Base model is {base or "unknown"}; no automatic replacement')
            versions = [v for v in model.get('modelVersions', []) if v.get('baseModel') == base
                        and v.get('availability', 'Public') == 'Public']
            if not versions:
                raise ValueError('No public version with the same base model')
            latest = max(versions, key=lambda v: v.get('publishedAt') or v.get('createdAt') or '')
            current_date = current.get('publishedAt') or current.get('createdAt') or ''
            latest_date = latest.get('publishedAt') or latest.get('createdAt') or ''
            if current_date and latest_date < current_date:
                row.update(name=model.get('name', path.stem), source='Civitai',
                           source_url=f'https://civitai.com/models/{int(model["id"])}',
                           installed=current.get('name',''), latest=current.get('name',''),
                           trigger=', '.join(current.get('trainedWords', [])), status='No newer compatible public version')
                return row
            files = [f for f in latest.get('files', []) if f.get('type') == 'Model'
                     and f.get('name', '').endswith('.safetensors') and f.get('hashes', {}).get('SHA256')]
            if len(files) != 1:
                raise ValueError('Multiple or missing weight variants; choose a version on the source page')
            file = files[0]
            row.update(name=model.get('name', path.stem), source='Civitai',
                       source_url=f'https://civitai.com/models/{int(model["id"])}',
                       installed=current.get('name', str(current['id'])), latest=latest.get('name', str(latest['id'])),
                       expected=file['hashes']['SHA256'].lower(), download=file['downloadUrl'],
                       trigger=', '.join(latest.get('trainedWords', [])))
        row['status'] = 'Up to date' if sha == row['expected'] else 'Update available'
        row['checked'] = time.strftime('%Y-%m-%d %H:%M')
        return row

    def install(self, path, row):
        temp = path.with_suffix('.download')
        try:
            with urlopen(self.request(row['download']), timeout=60) as source, temp.open('wb') as target:
                while chunk := source.read(4 * 1024 * 1024):
                    target.write(chunk)
            if file_hash(temp) != row['expected']:
                raise ValueError('Downloaded checksum did not match; original retained')
            tensor_header(temp)
            # Do not swap an unrelated adapter family into a working favorite.
            old_keys, new_keys = set(tensor_header(path)), set(tensor_header(temp))
            if not old_keys.intersection(new_keys):
                raise ValueError('Adapter tensor names differ; original retained for manual review')
            if not self.generation_lock.acquire(blocking=False):
                raise ValueError('Generation is active; update deferred, original retained')
            try:
                if file_hash(path) != row['sha256']:
                    raise ValueError('Local weights changed since check; original retained')
                backup_dir = self.log_dir / 'lora-backups'
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup = backup_dir / (hashlib.sha256(str(path).encode()).hexdigest()[:12] + '-' + row['sha256'] + '.bak')
                if not backup.exists():
                    try:
                        os.link(path, backup)
                    except OSError as exc:
                        if exc.errno != errno.EXDEV:
                            raise
                        shutil.copy2(path, backup)
                temp.replace(path)
                row.update(sha256=row['expected'], fingerprint=[path.stat().st_size,path.stat().st_mtime_ns],
                           previous_version=row.get('installed','Previous version'),
                           installed=row['latest'], status='Updated; previous weights retained', backup=str(backup))
            finally:
                self.generation_lock.release()
        finally:
            temp.unlink(missing_ok=True)

    def restore(self, filename):
        path = (self.root / filename).resolve()
        if self.root.resolve() not in path.parents or path.suffix != '.safetensors':
            raise ValueError('Invalid LoRA filename')
        with self.state_lock:
            row = dict(self.rows.get(filename, {}))
        backup = Path(row.get('backup', '')).resolve()
        if backup.parent != (self.log_dir / 'lora-backups').resolve() or not backup.is_file():
            raise ValueError('No previous weights are available')
        if not self.generation_lock.acquire(blocking=False):
            raise ValueError('Wait until the generation finishes before restoring weights')
        temp = path.with_suffix('.restore')
        try:
            tensor_header(backup)
            shutil.copy2(backup, temp)
            # Preserve the version being replaced as well, so restore can be toggled.
            current_hash = file_hash(path)
            current_backup = backup.parent / (hashlib.sha256(str(path).encode()).hexdigest()[:12] + '-' + current_hash + '.bak')
            if not current_backup.exists():
                shutil.copy2(path, current_backup)
            temp.replace(path)
            row.update(sha256=file_hash(path), fingerprint=[path.stat().st_size,path.stat().st_mtime_ns],
                       backup=str(current_backup), installed=row.get('previous_version','Previous version'),
                       previous_version=row.get('installed',''), status='Restored previous weights')
            self.store(filename,row)
        finally:
            temp.unlink(missing_ok=True)
            self.generation_lock.release()

    def start(self, apply=False):
        if not self.lock.acquire(blocking=False):
            return self.snapshot()
        with self.state_lock:
            self.job = {'running':True, 'message':'Starting…', 'apply':apply}
        threading.Thread(target=self.run, args=(apply,), daemon=True).start()
        return self.snapshot()

    def run(self, apply):
        try:
            files = sorted(p for p in self.root.rglob('*.safetensors') if p.is_file())
            for index,path in enumerate(files):
                name = path.relative_to(self.root).as_posix()
                with self.state_lock:
                    self.job['message'] = f'{index+1}/{len(files)} · {path.stem}'
                    previous = dict(self.rows.get(name, {}))
                try:
                    stat = path.stat()
                    fingerprint = [stat.st_size, stat.st_mtime_ns]
                    if previous.get('fingerprint') != fingerprint:
                        previous.update(sha256=file_hash(path), fingerprint=fingerprint)
                        self.store(name, previous)
                    row = self.resolve(path, previous)
                    self.store(name, row)
                    if apply and row['status'] == 'Update available':
                        self.install(path, row)
                    self.store(name, row)
                except Exception as exc:
                    if isinstance(exc, HTTPError):
                        message = {401:'Source requires authentication',403:'Source denied access; may need an API key',
                                   404:'Source not found by exact hash',429:'Source rate limited; retry later'}.get(exc.code, f'Source HTTP {exc.code}')
                    else:
                        message = str(exc)
                    self.store(name, {**self.snapshot()['files'].get(name, previous), 'status':message})
            with self.state_lock:
                self.job.update(running=False, message='Update pass finished.' if apply else 'Source and update check finished.')
        except Exception as exc:
            with self.state_lock:
                self.job.update(running=False, message='Update pass failed: ' + str(exc))
        finally:
            self.lock.release()
