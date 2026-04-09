# Dragonsuite Custom Thumbnails

This directory contains custom thumbnail images for Dragonsuite services.

## Specifications

### Image Requirements
- **Format**: PNG (with transparency) or SVG
- **Dimensions**: 128x128 pixels (displays at 44x44, higher res for quality)
- **Aspect Ratio**: 1:1 (square)
- **Background**: Transparent recommended
- **Color Space**: RGB
- **File Size**: Keep under 50KB for fast loading

### Design Guidelines
- **Simple & bold**: Must be recognizable at 44px display size
- **High contrast**: Should work on both light and dark backgrounds
- **Avoid fine details**: Small text or intricate patterns won't be visible
- **Test both modes**: Preview on light and dark dashboard themes

### File Naming
Name files to match the service ID from `dragonsuite.json`:
- `mule-game.png` → for service with `"id": "mule-game"`
- `dragonflux-klein.png` → for service with `"id": "dragonflux-klein"`
- etc.

## Usage

### Add a Custom Thumbnail

1. **Create your image** (128x128 PNG with transparency)
2. **Save it here**: `/srv/containers/edq/media/thumbnails/[service-id].png`
3. **Update config**: Edit `/srv/containers/edq/config/dragonsuite.json`

```json
{
  "id": "mule-game",
  "name": "M.U.L.E.",
  "icon": "&#127918;",  // Emoji fallback (required!)
  "thumbnail": "/media/thumbnails/mule-game.png",  // Add this line
  ...
}
```

4. **Reload dashboard**: The thumbnail will appear automatically

### Fallback Behavior
- If `thumbnail` is specified but image fails to load → shows `icon` emoji
- If `thumbnail` is not specified → shows `icon` emoji
- If neither specified → shows default 💻 icon

## Example Thumbnails

### M.U.L.E. Game Ideas
- Pixel art robot in retro style
- Bunten Berry (blueberry with circuits)
- Planet Irata hex grid scene
- Vintage game cartridge design

### General Style Tips
- **Pixel art**: 8-bit or 16-bit aesthetic works well
- **Flat design**: Simple shapes with solid colors
- **Isometric**: 3D-looking icons are eye-catching
- **Retro**: Vintage computing/gaming style fits the theme

## Tools for Creating Thumbnails

### AI Generation (via Dragonsuite!)
```bash
# Use Z-Image for pixel art style
# Prompt: "pixel art icon, [your service], 128x128, game sprite, transparent background"

# Or use DragonFlux Klein
# Prompt: "minimalist icon design, [your service], square, clean, modern"
```

### Manual Editing
- **GIMP**: Free, powerful (like Photoshop)
- **Krita**: Great for digital art
- **Inkscape**: Perfect for SVG icons
- **Aseprite**: Excellent for pixel art

## Testing

After adding a thumbnail:
1. Open dashboard: http://192.168.7.226:8100
2. Hard refresh: Ctrl+Shift+R (bypass cache)
3. Check both light and dark modes
4. Verify fallback works (temporarily rename file)

## Current Thumbnails

| Service | File | Status |
|---------|------|--------|
| `mule-game` | `mule-game.png` | Active |
| `dnd-generator` | `dnd-generator.png` | Active |

*Add entries here as you create thumbnails*

---

**Note**: Emoji icons are perfectly fine! Only create custom thumbnails if you want a unique visual identity for a service.
