#!/usr/bin/env python3
"""
publish_gallery.py — Upload a Dragonart gallery ZIP to Hostinger via SFTP

Usage:
    python scripts/publish_gallery.py <zipfile>           # upload
    python scripts/publish_gallery.py <zipfile> --delete  # remove from hosting
    python scripts/publish_gallery.py --list              # list published galleries

Credentials read from /srv/containers/edq/.env:
    HOSTINGER_SFTP_HOST      e.g. 31.220.X.X  (from hPanel → Hosting → Details)
    HOSTINGER_SFTP_USER      e.g. u123456789  (FTP username)
    HOSTINGER_SFTP_PASS      your FTP password
    HOSTINGER_SFTP_PORT      optional, default 22
    HOSTINGER_PUBLIC_HTML    e.g. /home/u123456789/domains/seed13.com/public_html
    HOSTINGER_GALLERY_URL    e.g. https://seed13.com/gallery
"""

import os
import re
import sys
import zipfile
import tempfile
from pathlib import Path

ENV_FILE = "/srv/containers/edq/.env"

# ── Load credentials ─────────────────────────────────────────────────────────

def load_env():
    env = {}
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    env.update(os.environ)  # env vars override .env file
    return env

def get_sftp_config(env):
    missing = []
    for key in ('HOSTINGER_SFTP_HOST', 'HOSTINGER_SFTP_USER', 'HOSTINGER_SFTP_PASS',
                'HOSTINGER_PUBLIC_HTML', 'HOSTINGER_GALLERY_URL'):
        if not env.get(key):
            missing.append(key)
    if missing:
        print("Missing credentials in .env:")
        for k in missing:
            print(f"  {k}=")
        print(f"\nAdd them to {ENV_FILE} and retry.")
        sys.exit(1)
    return {
        'host':        env['HOSTINGER_SFTP_HOST'],
        'username':    env['HOSTINGER_SFTP_USER'],
        'password':    env['HOSTINGER_SFTP_PASS'],
        'port':        int(env.get('HOSTINGER_SFTP_PORT', '22')),
        'public_html': env['HOSTINGER_PUBLIC_HTML'].rstrip('/'),
        'gallery_url': env['HOSTINGER_GALLERY_URL'].rstrip('/'),
    }

# ── Helpers ───────────────────────────────────────────────────────────────────

def zip_to_slug(zip_path: str) -> str:
    name = Path(zip_path).stem
    name = re.sub(r'_gallery$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[\s_]+', '-', name).strip('-').lower()
    return name

def ensure_paramiko():
    try:
        import paramiko
        return paramiko
    except ImportError:
        print("Installing paramiko for SFTP support…")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'paramiko'])
        import paramiko
        return paramiko

def sftp_mkdir_p(sftp, remote_path):
    parts = remote_path.split('/')
    current = ''
    for part in parts:
        if not part:
            current = '/'
            continue
        current = f"{current}/{part}".replace('//', '/')
        try:
            sftp.mkdir(current)
        except OSError:
            pass  # already exists

def sftp_upload_dir(sftp, local_dir: Path, remote_dir: str, verbose=True):
    sftp_mkdir_p(sftp, remote_dir)
    for item in sorted(local_dir.rglob('*')):
        if item.is_dir():
            rel = item.relative_to(local_dir)
            sftp_mkdir_p(sftp, f"{remote_dir}/{rel}")
        elif item.is_file():
            rel = item.relative_to(local_dir)
            remote_path = f"{remote_dir}/{rel}"
            if verbose:
                print(f"  ↑ {rel}")
            sftp.put(str(item), remote_path)

def connect(cfg, paramiko):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=cfg['host'],
        port=cfg['port'],
        username=cfg['username'],
        password=cfg['password'],
        timeout=30,
    )
    return client

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_upload(zip_path, cfg, paramiko):
    zip_path = Path(zip_path)
    if not zip_path.exists():
        print(f"File not found: {zip_path}")
        sys.exit(1)
    if not zipfile.is_zipfile(zip_path):
        print(f"Not a valid ZIP file: {zip_path}")
        sys.exit(1)

    slug = zip_to_slug(str(zip_path))
    remote_dir = f"{cfg['public_html']}/gallery/{slug}"
    public_url = f"{cfg['gallery_url']}/{slug}/"

    print(f"Gallery: {slug}")
    print(f"Remote:  {remote_dir}")
    print(f"URL:     {public_url}")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print("Extracting…")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)

        print("Connecting to Hostinger…")
        client = connect(cfg, paramiko)
        with client.open_sftp() as sftp:
            print("Uploading…")
            sftp_upload_dir(sftp, tmp_path, remote_dir)
        client.close()

    print()
    print(f"✓ Live at: {public_url}")

def cmd_delete(zip_path, cfg, paramiko):
    slug = zip_to_slug(zip_path)
    remote_dir = f"{cfg['public_html']}/gallery/{slug}"
    print(f"Removing: {remote_dir}")

    client = connect(cfg, paramiko)
    with client.open_sftp() as sftp:
        def rm_rf(sftp, path):
            try:
                attrs = sftp.lstat(path)
                import stat
                if stat.S_ISDIR(attrs.st_mode):
                    for entry in sftp.listdir(path):
                        rm_rf(sftp, f"{path}/{entry}")
                    sftp.rmdir(path)
                else:
                    sftp.remove(path)
            except FileNotFoundError:
                pass
        rm_rf(sftp, remote_dir)
    client.close()
    print(f"✓ Removed: {slug}")

def cmd_list(cfg, paramiko):
    gallery_root = f"{cfg['public_html']}/gallery"
    client = connect(cfg, paramiko)
    with client.open_sftp() as sftp:
        try:
            entries = sftp.listdir(gallery_root)
        except FileNotFoundError:
            entries = []
    client.close()

    if not entries:
        print("No galleries published yet.")
        return
    print(f"Published galleries ({len(entries)}):")
    for name in sorted(entries):
        print(f"  {cfg['gallery_url']}/{name}/")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    env = load_env()
    cfg = get_sftp_config(env)
    paramiko = ensure_paramiko()

    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print(__doc__)
        sys.exit(0)

    if args == ['--list']:
        cmd_list(cfg, paramiko)
    elif len(args) == 2 and args[1] == '--delete':
        cmd_delete(args[0], cfg, paramiko)
    elif len(args) == 1:
        cmd_upload(args[0], cfg, paramiko)
    else:
        print("Usage: publish_gallery.py <zipfile> [--delete] | --list")
        sys.exit(1)

if __name__ == '__main__':
    main()
