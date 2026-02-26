# CLAUDE-MAC.md

This file provides guidance to Claude Code (claude.ai/code) when working on **macOS** with the Dragonsuite infrastructure.

**Companion to:** [CLAUDE.md](../CLAUDE.md) (Ubuntu/GPU server)

## Platform Overview

This is the **macOS client setup** for the Dragonsuite AI development environment. Heavy GPU workloads run on the Ubuntu server (`udragon` at 192.168.7.226), while the Mac is used for:

- Development and scripting
- Remote service access
- Documentation and organization
- Light local testing

## Core Principles (Same on All Platforms)

1. **RTFM First** - Read official docs before building
2. **Single Source of Truth** - No duplicates, use symlinks
3. **Parallel Execution** - Run independent operations simultaneously
4. **Centralized Organization** - One place for configs, scripts, docs

See [organization-principles.md](organization-principles.md) for full details.

## macOS Directory Structure

```
~/Projects/dragonsuite/         # Local project workspace (Mac)
├── docs/                        # Symlink to SMB share
├── scripts/                     # Mac-compatible helper scripts
├── local-projects/              # Mac-native development
└── .env                         # Local copy of API keys (or symlink to SMB)

/Volumes/knowledge-base/         # SMB mount from Ubuntu
└── AI Projects/                 # Obsidian vault (synced)
    ├── CLAUDE.md -> (Ubuntu)    # Ubuntu-specific docs
    ├── CLAUDE-MAC.md -> (this)  # Mac-specific docs
    ├── Docs/ -> (Ubuntu)        # Shared documentation
    └── Memory/ -> (Ubuntu)      # Shared memory/lessons
```

## Network Access

**Ubuntu Server (udragon):**

- **IP:** 192.168.7.226
- **SMB Share:** `smb://192.168.7.226/knowledge-base`
- **Services:** All run on Ubuntu, accessed remotely

**Mount SMB Share on Mac:**

```bash
# Mount via Finder: Cmd+K → smb://192.168.7.226/knowledge-base
# Or via command line:
mkdir -p /Volumes/knowledge-base
mount_smbfs //guest@192.168.7.226/knowledge-base /Volumes/knowledge-base

# Auto-mount on login: System Settings → General → Login Items → Add network volume
```

## Remote Service Access (Ubuntu GPU Services)

All GPU-intensive services run on Ubuntu. Access them from Mac via browser or API:

| Port  | Service               | Access URL                 | Notes                          |
| ----- | --------------------- | -------------------------- | ------------------------------ |
| 8100  | Dragonsuite Dashboard | http://192.168.7.226:8100  | Central launcher               |
| 8080  | Dragonsight 4         | http://192.168.7.226:8080  | Vision AI                      |
| 8001  | DragonFlux Klein      | http://192.168.7.226:8001  | Image generation               |
| 8002  | Wan2GP                | http://192.168.7.226:8002  | Video generation               |
| 8011  | Z-Image Base          | http://192.168.7.226:8011  | Text-to-image                  |
| 8020  | MCP Inspector         | http://192.168.7.226:8020  | MCP security audit             |
| 11434 | Ollama API            | http://192.168.7.226:11434 | LLM backend                    |
| 1234  | LM Studio API         | http://192.168.7.226:1234  | Alternative LLM (manual start) |

**Quick Access:**

- **Dashboard:** Bookmark `http://192.168.7.226:8100` - shows all services
- **QR Codes:** Dashboard generates QR codes for mobile access

See [Ubuntu CLAUDE.md](../CLAUDE.md) for full service documentation.

## macOS-Specific Tools

### Package Management

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Essential tools for Dragonsuite development
brew install python@3.11 node git gh ffmpeg
brew install --cask visual-studio-code obsidian
```

### Python Environment

```bash
# Mac uses system Python or Homebrew Python
python3 --version  # Should be 3.11+

# Create venvs for Mac-native projects (NOT for Ubuntu GPU projects)
python3 -m venv ~/Projects/dragonsuite/venv_<project>
source ~/Projects/dragonsuite/venv_<project>/bin/activate
```

**Important:** Don't try to replicate Ubuntu GPU venvs on Mac. Those require CUDA and won't work. Use Ubuntu venvs via SSH or remote development instead.

### SSH Access to Ubuntu

```bash
# SSH into Ubuntu for terminal access
ssh edq@192.168.7.226

# Run commands on Ubuntu from Mac
ssh edq@192.168.7.226 "cd /srv/containers/edq && bash scripts/start_dragonsuite.sh"

# Mount remote filesystem via SSHFS (alternative to SMB)
brew install macfuse sshfs
sshfs edq@192.168.7.226:/srv/containers/edq ~/mounts/dragonsuite
```

## Development Workflow

### When to Use Mac vs Ubuntu

**Use Mac for:**

- ✅ Writing Python scripts (no GPU needed)
- ✅ Web development (HTML/CSS/JS)
- ✅ Documentation editing
- ✅ Git operations (push/pull/commit)
- ✅ API testing with curl/Postman
- ✅ Light Node.js projects

**Use Ubuntu for:**

- 🎮 **GPU-intensive tasks** (image gen, video gen, LLM inference)
- 🎮 Running Gradio services
- 🎮 Training/fine-tuning models
- 🎮 CUDA operations
- 🎮 Docker containers with GPU access

### Hybrid Workflow Example

**Scenario:** Develop a new Gradio UI for an existing Ubuntu service

1. **On Mac:** Write HTML/CSS/JS or Python code in VS Code
2. **On Mac:** Test logic locally (mock API responses)
3. **On Mac:** Commit to Git, push to Ubuntu
4. **On Ubuntu:** Pull changes, test with actual GPU service
5. **On Mac:** Access via browser at `http://192.168.7.226:8xxx`

## macOS MCP Server Setup

**MCP Config Location:** `~/.claude/mcp.json` or project-specific

**Mac-Compatible MCP Servers:**

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
      }
    },
    "obsidian": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-obsidian", "/Volumes/knowledge-base/AI Projects"],
      "description": "Access Obsidian vault via SMB mount"
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/YOUR_USERNAME/Projects/dragonsuite",
        "/Volumes/knowledge-base"
      ],
      "description": "Local Mac filesystem + Ubuntu SMB share"
    },
    "ubuntu-services": {
      "comment": "Custom MCP to trigger Ubuntu GPU services via SSH/API",
      "status": "TODO: Implement wrapper MCP for remote service control"
    }
  }
}
```

**Note:** GPU-specific MCPs (dragonsuite, topaz-labs) won't work on Mac. Access those services via web UI or API instead.

## API Keys & Environment Variables

**Shared .env:** Access via SMB mount at `/Volumes/knowledge-base/` or create local copy

```bash
# Option 1: Symlink to SMB share (requires mount)
ln -s /Volumes/knowledge-base/.env ~/.dragonsuite.env
source ~/.dragonsuite.env

# Option 2: Local copy (less preferred - violates single source of truth)
# Only use if SMB frequently disconnects
cp /Volumes/knowledge-base/.env ~/.dragonsuite.env
echo "source ~/.dragonsuite.env" >> ~/.zshrc  # or ~/.bash_profile
```

**Keys you'll need on Mac:**

- `OPENAI_API_KEY` - For API testing
- `ANTHROPIC_API_KEY` - For Claude API
- `GITHUB_PERSONAL_ACCESS_TOKEN` - For gh CLI and MCP
- `TOPAZ_API_KEY` - If calling Topaz Labs API directly

## Code Style (Same as Ubuntu)

See [CLAUDE.md Code Style](../CLAUDE.md#code-style) section - same principles apply.

**Mac-specific notes:**

- Use `zsh` (default macOS shell) instead of `bash` where applicable
- Paths use `/Users/` instead of `/home/`
- Use `open` command instead of `xdg-open`
- Use `pbcopy`/`pbpaste` for clipboard (instead of `xclip`)

## Obsidian Integration

**Vault Location:** `/Volumes/knowledge-base/AI Projects/`

**Setup:**

1. Mount SMB share (see Network Access above)
2. Open Obsidian → Open folder as vault → Select `/Volumes/knowledge-base/AI Projects/`
3. Install plugins: Local REST API (optional, for MCP integration)

**Vault Contents:**

- `CLAUDE.md` - Ubuntu documentation (symlink)
- `CLAUDE-MAC.md` - This file (symlink)
- `Docs/` - Shared documentation (symlink to Ubuntu)
- `Memory/` - Shared lessons learned (symlink to Ubuntu)

All symlinks point to Ubuntu filesystem via SMB.

## Troubleshooting

### SMB Mount Disconnects

```bash
# Check if mounted
ls /Volumes/knowledge-base

# Remount if needed
mount_smbfs //guest@192.168.7.226/knowledge-base /Volumes/knowledge-base

# Auto-reconnect: Use Automator or add to Login Items
```

### Can't Access Ubuntu Services

```bash
# Verify network connectivity
ping 192.168.7.226

# Check if service is running on Ubuntu
ssh edq@192.168.7.226 "curl -s http://localhost:8100 > /dev/null && echo 'Running' || echo 'Not running'"

# Check firewall (Ubuntu side)
ssh edq@192.168.7.226 "sudo ufw status"
```

### Python Version Conflicts

```bash
# Mac may have multiple Python versions
which python3
python3 --version

# Use Homebrew Python explicitly
/opt/homebrew/bin/python3 --version

# Create venv with specific version
/opt/homebrew/bin/python3 -m venv venv_project
```

## Best Practices

### Do's ✅

1. **Use SMB mount for docs** - Single source of truth
2. **Develop locally, test remotely** - Edit on Mac, run GPU on Ubuntu
3. **Bookmark the Dashboard** - `http://192.168.7.226:8100`
4. **Use git for sync** - Commit on Mac, pull on Ubuntu (or vice versa)
5. **Follow same organizational principles** - RTFM, no duplicates, parallel execution

### Don'ts ❌

1. **Don't replicate GPU venvs** - CUDA doesn't work on Mac
2. **Don't hardcode 192.168.7.226** - Use env var `UBUNTU_SERVER_IP` if scripting
3. **Don't create local copies of .env** - Use symlink to SMB share
4. **Don't run GPU services locally** - They need CUDA, won't work
5. **Don't scatter configs** - Keep everything in central location (SMB share or `~/Projects/dragonsuite/`)

## Multi-Platform Workflow

See [multi-platform-workflow.md](multi-platform-workflow.md) for detailed guide on:

- When to work on which platform
- How to sync code and configs
- Managing platform-specific dependencies
- Remote development patterns

## Resources

**Ubuntu Documentation:**

- [CLAUDE.md](../CLAUDE.md) - Full Ubuntu/GPU setup
- [organization-principles.md](organization-principles.md) - Shared principles
- [venvs.md](venvs.md) - Ubuntu virtual environments (reference only)

**macOS Specific:**

- [Homebrew Docs](https://docs.brew.sh/) - Package management
- [macOS Terminal Guide](https://support.apple.com/guide/terminal/welcome/mac) - Shell basics

**Network:**

- Ubuntu server: `192.168.7.226`
- SMB share: `smb://192.168.7.226/knowledge-base`
- Services: `http://192.168.7.226:8xxx`

---

**Last Updated:** 2026-02-14
**Platform:** macOS (client) + Ubuntu 24.04 (server)
**Architecture:** Mac (development) → Ubuntu (GPU compute)
