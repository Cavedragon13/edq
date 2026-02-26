# Dragonsuite Git Usage Guide

Version control is now set up to prevent file corruption and track changes.

## Quick Reference

### Daily Usage

```bash
# Check what changed
git status

# View changes in detail
git diff

# Save your work (manual snapshot)
bash scripts/git_snapshot.sh

# View history
git log --oneline -10

# See what changed in a specific commit
git show <commit-hash>

# Restore a file from history
git checkout <commit-hash> -- path/to/file
```

### Automatic Snapshots

**Pre-Reboot Protection** (optional setup):

```bash
# Install systemd service for automatic snapshots before shutdown
sudo cp scripts/dragonsuite-snapshot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dragonsuite-snapshot.service
```

This will automatically save a git snapshot before every reboot/shutdown.

### Manual Commits (for major milestones)

```bash
cd /srv/containers/edq

# Stage specific files
git add scripts/new_feature.py media/dragonsight4.js

# Or stage everything
git add -A

# Commit with a message
git commit -m "Added new feature X"

# View commit
git log -1 --stat
```

### Recovering from Corruption

If a file gets corrupted (like dragonsight4.js did):

```bash
# 1. See what changed
git diff media/dragonsight4.js

# 2. Restore from last commit
git checkout HEAD -- media/dragonsight4.js

# 3. Or restore from specific commit
git log --oneline -- media/dragonsight4.js  # find the commit
git checkout <commit-hash> -- media/dragonsight4.js
```

### Branching (for experiments)

```bash
# Create experimental branch
git checkout -b experiment-new-ui

# Make changes...
# Test...

# If good, merge back
git checkout master
git merge experiment-new-ui

# If bad, just delete
git checkout master
git branch -D experiment-new-ui
```

## What's Tracked

✅ **Tracked** (committed to git):

- Scripts (start\__.sh, _\_gradio.py)
- Configuration (config/dragonsuite.json, .env.example)
- HTML/JS/CSS (media/_.html, media/_.js)
- Documentation (docs/\*.md, CLAUDE.md)
- MCP servers (source code only)

❌ **Not Tracked** (in .gitignore):

- Virtual environments (venv\_\*)
- AI models (models/)
- Generated output (ai_generated/)
- Application binaries (apps/)
- Cloned projects (projects/\*/)
- Sensitive files (.env, \*.key)
- Logs (\*.log)

## Repository Info

- **Location**: `/srv/containers/edq/.git`
- **Initial Commit**: `487315f` (2026-02-06)
- **What**: Complete Dragonsuite v1.0 infrastructure
- **Size**: ~14MB (compressed)

## Tips

1. **Before major changes**: `bash scripts/git_snapshot.sh`
2. **After reboot**: `git status` to check if anything corrupted
3. **Weekly**: `git log --since="1 week ago" --oneline` to review changes
4. **Before uninstalling**: `git add -A && git commit -m "Backup before cleanup"`

## Aliases (optional)

Add to `~/.bashrc`:

```bash
alias ds-status='cd /srv/containers/edq && git status'
alias ds-snap='cd /srv/containers/edq && bash scripts/git_snapshot.sh'
alias ds-log='cd /srv/containers/edq && git log --oneline -20'
alias ds-diff='cd /srv/containers/edq && git diff'
```

Then: `source ~/.bashrc`

Now you can use:

- `ds-status` - Check for changes
- `ds-snap` - Quick snapshot
- `ds-log` - View recent commits
- `ds-diff` - See what changed
