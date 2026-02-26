# Multi-Platform Workflow Guide

**Last Updated:** 2026-02-14

This guide explains how to work seamlessly across macOS and Ubuntu while maintaining the same organizational philosophy and avoiding duplicate configs.

## Platform Roles

### Ubuntu Server (udragon - 192.168.7.226)

**Role:** GPU Compute & Heavy Workloads

**Strengths:**

- RTX 5070 Ti GPU (16GB VRAM)
- CUDA support for PyTorch/TensorFlow
- Runs all GPU-intensive services (image gen, video gen, LLMs)
- Always-on (server role)
- Fast local disk I/O

**Use for:**

- Running Gradio services
- Model inference (Ollama, LM Studio, custom models)
- Video/image processing
- Training/fine-tuning (if needed)
- Docker containers with GPU access

### macOS (Client - Multiple Macs)

**Role:** Development & Remote Access

**Strengths:**

- Portable (laptops)
- Native macOS tools (Xcode, Safari debugging)
- Better battery life than remoting into Ubuntu desktop
- Clean development environment

**Use for:**

- Code editing (Python, JavaScript, HTML/CSS)
- Git operations
- Documentation writing
- API testing
- Web browsing/research
- Remote service access via browser

## The "Single Source of Truth" Across Platforms

### What's Shared (Via SMB)

**Location:** `smb://192.168.7.226/knowledge-base`

**Shared via Obsidian Vault:**

1. **Documentation** (`CLAUDE.md`, `CLAUDE-MAC.md`, `docs/`)
2. **Memory** (lessons learned, troubleshooting guides)
3. **Organization principles** (RTFM, no duplicates, etc.)

**Access:**

- **Ubuntu:** Native filesystem at `/home/edq/knowledge-base/`
- **Mac:** SMB mount at `/Volumes/knowledge-base/`

### What's Platform-Specific

**Ubuntu-Only:**

- `/srv/containers/edq/` - Main project directory
- `venv_*` - GPU-dependent virtual environments
- `models/` - Downloaded model weights (large files)
- `.mcp.json` - GPU service MCPs

**Mac-Only:**

- `~/Projects/dragonsuite/` - Mac development workspace
- Mac-specific venvs (non-GPU projects)
- `.mcp.json` - Mac-compatible MCPs (GitHub, Obsidian, filesystem)

**Why?** GPU venvs require CUDA, model weights are huge (don't duplicate), MCP servers have platform-specific commands.

## Workflow Patterns

### Pattern 1: Develop on Mac, Execute on Ubuntu

**Use Case:** Creating a new Gradio service

**Steps:**

1. **Mac:** Write Python code in VS Code

   ```bash
   cd ~/Projects/dragonsuite/
   code new_service_gradio.py
   ```

2. **Mac:** Test logic locally (mock data, no GPU)

   ```bash
   python3 new_service_gradio.py --mock
   ```

3. **Mac:** Commit to Git

   ```bash
   git add new_service_gradio.py
   git commit -m "Add new service UI"
   git push origin main
   ```

4. **Ubuntu:** Pull and deploy

   ```bash
   ssh edq@192.168.7.226
   cd /srv/containers/edq/projects/YOUR_PROJECT
   git pull
   bash /srv/containers/edq/scripts/start_new_service.sh
   ```

5. **Mac:** Access via browser
   ```
   http://192.168.7.226:8xxx
   ```

### Pattern 2: Quick Edits on Ubuntu, View on Mac

**Use Case:** Tweaking a live service

**Steps:**

1. **Mac:** SSH into Ubuntu

   ```bash
   ssh edq@192.168.7.226
   ```

2. **Ubuntu:** Edit file with nano/vim

   ```bash
   cd /srv/containers/edq/scripts/
   nano start_service.sh
   ```

3. **Ubuntu:** Restart service

   ```bash
   bash start_service.sh
   ```

4. **Mac:** Refresh browser to see changes
   ```
   http://192.168.7.226:8xxx
   ```

### Pattern 3: Documentation Editing (Either Platform)

**Use Case:** Update CLAUDE.md or add to memory

**Option A - Mac:**

1. Open Obsidian on Mac
2. Edit file (auto-synced via SMB)
3. Changes immediately visible on Ubuntu

**Option B - Ubuntu:**

1. Edit file directly: `nano /srv/containers/edq/CLAUDE.md`
2. Changes immediately visible on Mac via SMB

**Why it works:** Same file via different access methods (SMB vs native filesystem)

### Pattern 4: Remote Service Control from Mac

**Use Case:** Start/stop Ubuntu services from Mac

**Method 1: SSH Commands**

```bash
# Start Dragonsuite Dashboard
ssh edq@192.168.7.226 "cd /srv/containers/edq && bash scripts/start_dragonsuite.sh"

# Check service status
ssh edq@192.168.7.226 "curl -s http://localhost:8100/api/status"

# Stop service (if supported)
ssh edq@192.168.7.226 "pkill -f 'python.*dragonsuite'"
```

**Method 2: Dashboard Web UI**

```
# Open Dashboard in browser
http://192.168.7.226:8100

# Click "Start" next to service name
```

**Method 3: Custom MCP Server (Future)**

```
# TODO: Create ubuntu-services MCP that wraps SSH commands
# Would allow Claude Code on Mac to start/stop Ubuntu services
```

## Code Synchronization

### Recommended: Git for Projects

**Setup:**

```bash
# Ubuntu: Initialize repo
cd /srv/containers/edq/projects/YOUR_PROJECT
git init
git remote add origin git@github.com:USERNAME/project.git

# Mac: Clone repo
cd ~/Projects/dragonsuite/
git clone git@github.com:USERNAME/project.git
```

**Workflow:**

```bash
# Mac: Make changes, commit, push
git add .
git commit -m "Update feature"
git push

# Ubuntu: Pull changes
ssh edq@192.168.7.226
cd /srv/containers/edq/projects/YOUR_PROJECT
git pull
```

### Alternative: Direct SMB Access (Docs Only)

**For documentation and configs, NOT code:**

```bash
# Mac: Edit directly on SMB mount
code /Volumes/knowledge-base/AI\ Projects/CLAUDE.md

# Ubuntu: See changes immediately
cat /home/edq/knowledge-base/AI\ Projects/CLAUDE.md
```

**Why NOT for code?** SMB can be slow for large file operations, git handles conflicts better.

## Managing Secrets & API Keys

### Shared .env File

**Location:** `/srv/containers/edq/.env` (Ubuntu native)

**Mac Access Options:**

**Option 1: Symlink via SMB (Preferred)**

```bash
# Assumes SMB is mounted and .env is shared
ln -s /Volumes/knowledge-base/.env ~/.dragonsuite.env
source ~/.dragonsuite.env
```

**Option 2: SSH to Read (Secure)**

```bash
# Fetch .env from Ubuntu when needed
scp edq@192.168.7.226:/srv/containers/edq/.env ~/.dragonsuite.env
source ~/.dragonsuite.env

# Add to .gitignore
echo ".dragonsuite.env" >> ~/.gitignore
```

**Option 3: Local Copy with Sync Script**

```bash
#!/bin/bash
# sync_env.sh - Run before starting work
scp edq@192.168.7.226:/srv/containers/edq/.env ~/.dragonsuite.env
echo "✓ Environment synced from Ubuntu"
```

**Security Note:** Don't commit `.env` to Git on either platform!

## Common Pitfalls & Solutions

### Pitfall 1: Duplicate Configs

**Problem:** Creating `.env` on both Mac and Ubuntu with different values

**Solution:** Use symlink or sync script, **never manually edit both copies**

### Pitfall 2: Path Hardcoding

**Problem:** Script with `/srv/containers/edq/` won't work on Mac

**Solution:** Use platform detection:

```python
import platform
import os

if platform.system() == "Darwin":  # macOS
    BASE_DIR = os.path.expanduser("~/Projects/dragonsuite")
elif platform.system() == "Linux":
    BASE_DIR = "/srv/containers/edq"
```

### Pitfall 3: Installing CUDA on Mac

**Problem:** Trying to run GPU venv on Mac, failing with CUDA errors

**Solution:** **Don't install CUDA on Mac.** Use Ubuntu for GPU tasks, Mac for development.

### Pitfall 4: SMB Mount Disconnects

**Problem:** SMB share unmounts, breaking symlinks

**Solution:** Auto-reconnect script:

```bash
#!/bin/bash
# check_smb.sh - Add to cron or LaunchAgent
if [ ! -d "/Volumes/knowledge-base" ]; then
    mount_smbfs //guest@192.168.7.226/knowledge-base /Volumes/knowledge-base
fi
```

### Pitfall 5: Conflicting Git Changes

**Problem:** Edited same file on both platforms, merge conflict

**Solution:**

1. **Always pull before editing:** `git pull`
2. **Use branches:** Mac = `feature/mac-dev`, Ubuntu = `main`
3. **Communicate:** If working simultaneously, use different files

## Platform-Specific Cheat Sheet

### Mac → Ubuntu Quick Reference

| Mac Command        | Ubuntu Equivalent        | Notes                  |
| ------------------ | ------------------------ | ---------------------- |
| `open .`           | `xdg-open .`             | Open directory in GUI  |
| `pbcopy < file`    | `xclip -sel clip < file` | Copy file to clipboard |
| `brew install pkg` | `sudo apt install pkg`   | Package manager        |
| `/Users/user/`     | `/home/user/`            | Home directory         |
| `~/Library/`       | `~/.config/`             | App config dir         |
| `launchctl`        | `systemctl`              | Service management     |

### Common Paths Translation

| Purpose        | Mac                                    | Ubuntu                                  |
| -------------- | -------------------------------------- | --------------------------------------- |
| Home           | `/Users/edq/`                          | `/home/edq/`                            |
| Projects       | `~/Projects/dragonsuite/`              | `/srv/containers/edq/`                  |
| Obsidian Vault | `/Volumes/knowledge-base/AI Projects/` | `/home/edq/knowledge-base/AI Projects/` |
| Temp Files     | `/tmp/` or `~/Downloads/`              | `/tmp/` or `~/Downloads/`               |

## When Things Go Wrong

### Can't Access Ubuntu Services from Mac

**Check:**

1. Ubuntu server is running: `ping 192.168.7.226`
2. Service is running on Ubuntu: SSH in and check `netstat -tulpn | grep 8100`
3. Firewall allows access: `sudo ufw status` on Ubuntu
4. Browser isn't caching: Hard refresh (Cmd+Shift+R)

### SMB Share Not Mounting

**Check:**

1. Network connectivity: `ping 192.168.7.226`
2. Samba is running: `ssh edq@192.168.7.226 'sudo systemctl status smbd'`
3. Share is exported: `ssh edq@192.168.7.226 'cat /etc/samba/smb.conf | grep knowledge-base'`
4. Try manual mount: `mount_smbfs //guest@192.168.7.226/knowledge-base /Volumes/knowledge-base`

### Git Sync Issues

**Check:**

1. SSH keys configured: `ssh -T git@github.com`
2. Correct remote: `git remote -v`
3. No uncommitted changes: `git status`
4. Branches in sync: `git fetch && git status`

## Best Practices Summary

### Do's ✅

1. **Use Git for code sync** - Don't rely on SMB for active development
2. **Edit docs on either platform** - They sync via SMB automatically
3. **Keep secrets centralized** - One `.env`, symlink or sync to Mac
4. **Use Ubuntu for GPU tasks** - Don't try to replicate on Mac
5. **Bookmark the Dashboard** - Quick access to all services
6. **Follow same org principles** - RTFM, no duplicates, parallel execution

### Don'ts ❌

1. **Don't create duplicate configs** - Use symlinks or sync scripts
2. **Don't hardcode IP addresses** - Use env vars or platform detection
3. **Don't run GPU services on Mac** - CUDA won't work
4. **Don't manually sync files** - Use Git or SMB, not copy/paste
5. **Don't scatter projects** - Keep Mac projects in `~/Projects/dragonsuite/`, Ubuntu in `/srv/containers/edq/`

## Future Enhancements

**Planned:**

1. **Custom MCP Server** - Control Ubuntu services from Mac Claude Code
2. **Auto-sync script** - Cron job to keep Mac .env in sync
3. **Platform-aware launcher** - Detect platform and adjust paths automatically
4. **Remote Jupyter** - Access Ubuntu Jupyter from Mac browser (port 8888)

---

**Questions?** See platform-specific docs:

- [CLAUDE.md](../CLAUDE.md) - Ubuntu setup
- [CLAUDE-MAC.md](CLAUDE-MAC.md) - macOS setup
- [organization-principles.md](organization-principles.md) - Shared principles
