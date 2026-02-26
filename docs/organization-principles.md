# Organization Principles for `/srv/containers/edq`

**Last Updated:** 2026-02-14

## Philosophy

**Single Source of Truth** - No duplicates. Use symlinks when a file must exist in multiple locations.

## Directory Structure

```
/srv/containers/edq/               # Root - centralized configs and venvs
├── .env                           # API keys (NEVER duplicate)
├── .mcp.json                      # MCP server config (NEVER duplicate)
├── CLAUDE.md                      # Project documentation
├── config/                        # Service configurations
│   └── dragonsuite.json          # Dashboard service definitions
├── docs/                          # Documentation
│   ├── venvs.md                  # Virtual environment registry
│   ├── services/                 # Per-service documentation
│   └── organization-principles.md # This file
├── scripts/                       # Launch scripts (start_*.sh, *_gradio.py)
├── media/                         # HTML apps, generated media
├── mcp-servers/                   # Custom MCP server implementations
├── venv_*/                        # Virtual environments (top-level, named by project)
├── projects/                      # Cloned repositories (self-contained)
│   ├── wan2gp/                   # Each project has its own structure
│   ├── dragonart-studio/         # Don't modify unless working on that project
│   └── ...
├── models/                        # Downloaded AI model weights
├── cache_huggingface/             # HF hub cache (symlinked from ~/.cache/huggingface)
└── lmstudio/                      # LM Studio data (symlinked from ~/.lmstudio)
```

## Rules

### ✅ DO

1. **Centralize configs** at `/srv/containers/edq/` top level
2. **Use symlinks** when a file must exist elsewhere:
   ```bash
   ln -s /srv/containers/edq/.env /some/other/location/.env
   ```
3. **Update registries** immediately:
   - Add venv → update `docs/venvs.md`
   - Add service → update `config/dragonsuite.json`
   - Add script → follow naming pattern `start_<service>.sh`

4. **Keep projects self-contained** - Each cloned repo in `projects/` should work independently
5. **Use absolute paths** in scripts: `/srv/containers/edq/...` not `~/containers/...`

### ❌ DON'T

1. **Never duplicate `.env`** - Use symlinks or `source /srv/containers/edq/.env`
2. **Never duplicate `.mcp.json`** - VS Code reads from parent directory automatically
3. **Don't scatter configs** - If you create a new config, put it in `config/` or document why it's elsewhere
4. **Don't hardcode API keys** - Always use `.env` variables
5. **Don't create venvs inside projects/** - Create them at top level as `venv_<project_name>`
6. **Never put source code in `ai_generated/`** - That directory is for output files only (images, audio, video). Source code belongs in `projects/`. If you find `package.json` or `.py` files in `ai_generated/`, delete them.

## Development Best Practices

### Parallel Execution

**Whenever you need to perform multiple independent operations, invoke all relevant tools simultaneously rather than sequentially.**

**Examples:**

```bash
# ✅ GOOD - Parallel execution
# Run multiple independent checks at once
git status & git diff & git log --oneline -5

# ❌ BAD - Sequential execution
git status
# wait...
git diff
# wait...
git log --oneline -5
```

**When working with Claude Code:**

- Reading multiple unrelated files → call Read tool multiple times in one message
- Searching different patterns → call Grep multiple times in parallel
- Running independent bash commands → use multiple Bash tool calls

**Benefits:**

- Faster execution (no waiting between operations)
- More efficient use of resources
- Better overall workflow speed

**When NOT to parallelize:**

- Operations with dependencies (e.g., must `cd` before running command in that directory)
- Commands that modify state sequentially (e.g., `git add && git commit`)
- Operations where output order matters

## Symlink Examples

### When Blender needs the addon in its config dir:

```bash
# Addon MUST be at: /home/edq/.config/blender/5.0/scripts/addons/
# (Blender hardcoded path - can't change)
# Keep it there, reference it in .mcp.json
```

### When a script needs the .env file:

```bash
# WRONG: Copy .env to project directory
# RIGHT: Source it from central location
source /srv/containers/edq/.env

# Or in Python:
from dotenv import load_dotenv
load_dotenv('/srv/containers/edq/.env')
```

### Large caches moved to 4TB SSD (2026-02-18):

```bash
# HuggingFace cache (~181GB) - models, datasets
~/.cache/huggingface -> /srv/containers/edq/cache_huggingface

# LM Studio (~14GB) - models, extensions
~/.lmstudio -> /srv/containers/edq/lmstudio
```

### When Obsidian needs access to docs:

```bash
# Create symlinks IN the Obsidian vault pointing TO central docs
cd /home/edq/knowledge-base/AI\ Projects/
ln -s /srv/containers/edq/CLAUDE.md "Dragonsuite CLAUDE.md"
ln -s /srv/containers/edq/docs/venvs.md "Virtual Environments.md"
```

## Dashboard (Dragonsuite) Integration

The dashboard at `http://192.168.7.226:8100` serves as the **visual registry** of all services.

**When adding a new service:**

1. Create launch script in `scripts/start_<service>.sh`
2. Add entry to `config/dragonsuite.json`:
   ```json
   {
     "name": "Service Name",
     "port": 8XXX,
     "description": "What it does",
     "category": "vision|image|video|audio|utilities",
     "url": "http://192.168.7.226:8XXX",
     "launcher": "/srv/containers/edq/scripts/start_service.sh"
   }
   ```
3. Document in appropriate `docs/services/<category>.md` file
4. Update `CLAUDE.md` port table

## Benefits of This Organization

1. **Memory** - Dashboard shows everything you have
2. **No confusion** - One config file, one source of truth
3. **Easy backup** - `/srv/containers/edq` contains everything important
4. **LAN access** - SMB shares point to centralized locations
5. **Scalability** - Add services without creating chaos

## Verification Commands

```bash
# Check for duplicate .env files (should only find one)
find /srv/containers/edq -name ".env" | wc -l  # Should be: 1

# Check for duplicate .mcp.json files (should only find one)
find /srv/containers/edq -name ".mcp.json" | wc -l  # Should be: 1

# List all venvs
ls -d /srv/containers/edq/venv_*/

# Verify all services in dashboard config
cat /srv/containers/edq/config/dragonsuite.json | jq '.services[].name'
```

## Recovery from Chaos

If you find yourself with duplicate configs:

1. Identify the **canonical location** (usually `/srv/containers/edq/`)
2. Backup duplicates: `mv duplicate.json duplicate.json.backup`
3. Create symlink if needed: `ln -s /srv/containers/edq/config.json /other/location/`
4. Test that everything still works
5. Delete backups after confirming

---

**Remember:** Organization now = less chaos later. Take 2 minutes to put things in the right place instead of spending 30 minutes searching later.
