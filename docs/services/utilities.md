# Utility Services & Tools

## Hunyuan3D-2 (Image to 3D)

**Port:** 8007
**Purpose:** Tencent's image-to-3D model generation

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_hunyuan3d.sh
```

**Access at:** `http://192.168.7.226:8007`

### Configuration

- **Location**: `projects/hunyuan3d/`
- **Launcher**: `scripts/start_hunyuan3d.sh`
- **Venv**: `venv_hunyuan3d`
- **Requirements**: ~6GB VRAM (shape), ~16GB (with texture)

### Features

- Image to 3D mesh
- Texture synthesis
- GLB/OBJ export

### Key Considerations

- Upload image → generates 3D mesh
- First launch downloads ~10GB of models
- ~6GB VRAM for shape only, ~16GB for shape + texture
- Exports GLB/OBJ formats

---

## MCP Inspector

**Port:** 8020
**Purpose:** Security auditing tool for Model Context Protocol servers

### Launch

```bash
cd /srv/containers/edq
bash scripts/start_mcp_inspector.sh
```

**Access at:** `http://192.168.7.226:8020`

### Overview

Security auditing tool for Model Context Protocol servers. Follows the "write your own when you can" principle for security-critical tools.

### Features

**Installed Servers Tab:**

- Trust scoring (⭐⭐⭐ official, ⭐⭐ moderate, ⭐ unknown)
- Security pattern detection (eval, exec, subprocess)
- Source code viewing for local Python servers
- NPM package statistics (stars, downloads)

**Browse Catalog Tab:**

- Search official MCP registry
- One-click installation to .mcp.json
- Trust scoring for external servers
- Verification badges for official servers

### Architecture

- Pure HTML/JS frontend (no framework dependencies for auditability)
- Backend: Python HTTP server with SO_REUSEADDR
- Cursor-based pagination for browse catalog
- Trust scoring based on verification status and package popularity
- Atomic writes to prevent config corruption

### Key Considerations

- **Official registry is incomplete** - Many MCP servers exist on NPM, PyPI, or GitHub but aren't listed in the registry yet
- Registry uses cursor-based pagination ("Load More" to see additional servers)
- Installed servers (like blender-mcp, obsidian-mcp-server) may not appear in browse results if not submitted to registry
- MCP servers run with full system permissions - always review before installing
- Installation requires Claude Code restart to activate new servers
- Local inspection remains critical even with registry browsing

---

## Pinokio Launcher System

**Location:** `pinokio/`
**Purpose:** Cross-platform launcher framework for AI apps

### Important Files

- `.cursorrules`: Contains strict development guidelines (always reference when working with Pinokio)
- `PINOKIO.md`: Full API documentation
- `prototype/system/examples/`: Reference examples for all launcher patterns

### Critical Workflow

1. Always reference `.cursorrules` before any Pinokio script changes
2. Check `/home/edq/pinokio/prototype/system/examples` for reference patterns
3. Review `PINOKIO.md` for API syntax
4. Check logs in `logs/` or `pinokio/logs/` for debugging
5. Use relative paths (never absolute) in `shell.run` commands

### Key Patterns

- Always use `venv` attribute for Python apps
- Capture server URLs with regex patterns like `/(http:\/\/[0-9.:]+)/`
- Set local variables with `local.set` using `{{input.event[1]}}`
- Use `daemon: true` for server launchers
- Prefer `uv` over `pip` for Python package installation

### Project Structure

```
launcher-root/
├── install.js    # Installation script
├── start.js      # Launch script (daemon: true for servers)
├── reset.js      # Reset dependencies
├── update.js     # Update app and scripts
├── pinokio.js    # UI generator (dynamic menu)
└── pinokio.json  # Metadata
```

---

## Llama.cpp Integration

**Location:** `projects/llama.cpp/`
**Purpose:** GGUF model inference for quantized models

---

## Dragonart Studio (Image Transformation)

**Port:** 8015 (production)
**Location:** `projects/dragonart-studio/`
**Tech Stack:** React + TypeScript + Vite

### Overview

Professional AI-powered image transformation tool with 70+ edit modes

### Production Deployment

Dragonart Studio runs as a production service on port 8015, managed by the Dragonsuite Dashboard:

- **Production URL:** `http://192.168.7.226:8015`
- **Server:** `scripts/dragonart_server.py` (Python HTTP server)
- **Launch:** `bash scripts/start_dragonart.sh` (auto-builds if needed)
- **Dashboard:** Integrated into Dragonsuite on port 8100

### Making Changes

```bash
# Option 1: Development (faster iteration)
cd /srv/containers/edq/projects/dragonart-studio
npm run dev  # Vite dev server on random port (3000+)

# Option 2: Production deployment (for dashboard)
npm run build  # Build to dist/
bash /srv/containers/edq/scripts/start_dragonart.sh  # Restart on port 8015
```

**CRITICAL:** Type changes (types.ts) and constant changes (constants.ts) require `npm run build` to take effect in production. The dev server hot-reloads, but production serves static built files from `dist/`.

### Features

- Image-to-image transformation with prompt control
- 70+ edit modes: Trading cards, movie posters, magazine covers, comic art, etc.
- Multi-model support: Gemini 3 Pro, Gemini 3 Flash, GPT-Image-1
- Video generation: Veo 3.1, Veo 3.1 Fast, Sora-2
- Session management with undo/redo history
- Reference image support for style transfer
- Automatic aspect ratio cropping per mode
- Export sessions as HTML galleries

### Key Modes

- **Trading Cards**: MTG, Sports (7 types), Non-Sports (10 vintage styles)
- **Posters**: Horror, Fantasy, Sci-Fi, Wanted
- **Magazines**: Harper's, Syrens, Joxtrap, Freestyle (20 genres)
- **Comic Art**: Pages, Splash panels, Covers
- **Transformations**: Diorama, Action Figure, Puppet, Pin-up
- **Art Styles**: Anime, Watercolor, Gothic, Illustration

### Models Available

- Gemini 3 Pro → Veo 3.1 (best quality, all 70+ modes)
- Gemini 3 Flash → Veo 3.1 Fast (faster, good quality)
- GPT-Image-1 → Sora-2 (OpenAI models)

### Technical Notes

- Uses React with TypeScript strict mode
- State management via useState + useCallback hooks
- All edit mode dropdowns have conditional sub-selectors (sports, genres, styles)
- Prompts designed for fair use (no trademarked names in templates)

### Key Considerations

- React + TypeScript app with strict mode enabled
- Uses Gemini 3 Pro / Flash API (requires Google Cloud API key in `/srv/containers/edq/.env`)
- All state managed via React hooks (useState, useCallback, useEffect)
- Image processing happens client-side before API calls
- Sessions auto-save to localStorage with compression
- **Always rebuild after TypeScript/React changes before deploying to production**

### Common Workflows

**1. Adding a new edit mode:**

- Add mode to `EditMode` type in `types.ts`
- Create prompt template in `constants.ts`
- Add to `MODE_CONFIGS` in `components/ControlPanel.tsx`
- Add case in `getPromptForMode()` switch statement
- If needs aspect ratio: add to `ASPECT_RATIO_MAP` in `App.tsx`

**2. Adding a dropdown selector (like Non-Sports Card styles):**

- Create new type in `types.ts` (e.g., `NonSportsCardStyle`)
- Add state in `App.tsx`: `const [style, setStyle] = useState<Type>('default')`
- Pass to ControlPanel props and add to function parameters
- Add conditional dropdown in ControlPanel using `{editMode === 'mode' && (...)}`
- Add to `getPromptForMode` parameters and use in prompt building
- **CRITICAL:** Add new state variable to `handleGenerateClick` dependency array!

**3. Debugging state sync issues:**

- Check useCallback dependency arrays include ALL state variables used
- Missing dependencies cause stale closure bugs (dropdown changes don't apply)
- Add console.log in handleGenerateClick to verify current state values
- React StrictMode causes double-renders (normal in dev, not production)

**4. Fair use / content filtering:**

- Avoid trademarked names in prompts ("Star Wars" → "classic sci-fi movie")
- Use generic style descriptors ("Marvel" → "superhero comic style")
- Keep prompt_snippets focused on visual aesthetics, not brand names

### Troubleshooting

- **Changes not appearing:** Rebuild with `npm run build` and restart via dashboard or launch script
- **API errors:** Check Google Cloud API key has billing enabled in `/srv/containers/edq/.env`
- **Content filtering:** Review prompts for trademarked names (use generic descriptors)
- **State not updating:** Check useCallback/useEffect dependency arrays for missing dependencies
- **Aspect ratio issues:** Verify mode is in ASPECT_RATIO_MAP in `App.tsx`
- **Session not saving:** Check localStorage isn't full (browser quota ~5-10MB)
- **Server conflicts:** Don't run dev server when production server is running on port 8015
