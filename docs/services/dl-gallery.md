# Downloads Gallery

URL: http://192.168.7.226:8060/ — service ID `dl-gallery`.
Source: `scripts/dl_gallery.py`; environment: `venv_dl_gallery`.
The always-on systemd unit is `dl-gallery.service`; restart it after source changes.
The Dashboard launcher is `scripts/start_dl_gallery.sh`.

## Folder navigation

The location dropdown is populated on each page load from Downloads plus every
immediate directory in `/home/edq/ai_generated/`, including service symlinks.
There is no separate manually maintained folder list. Favorites is an aggregate view.
New folders appear after Refresh. Subfolders are clickable folder cards, with
breadcrumbs and an Up link; navigation works to arbitrary depth inside each root.
URLs use `?root=downloads&dir=CGDream_Zips%2F2025-02`, so folders can be bookmarked.
Only the current directory's images and videos are displayed; entering a folder
does not recursively flatten its contents. Hidden folders are omitted. Subfolder
symlinks escaping the chosen root are not browsable. Existing top-level service
symlinks remain supported.

Click an image to open the lightbox, or focus its card and press Enter. Use the
star to select Favorites across folders; choose Favorites in the dropdown to
review those selections together. Slideshow starts from the open image, or from
the first image when launched in the grid. Empty folders disable slideshow.
The theme defaults to dark and the header toggle persists the chosen theme.

Favorites are stored in `/home/edq/.dl_gallery_favorites.json` as pairs of root
key and path relative to that root. Existing favorites remain compatible.
Thumbnail, full-size, favorite, and delete routes use that same relative path;
filenames with spaces, Unicode, `#`, and `&` are encoded for URLs and HTML.

## CGDream extraction (2026-09-12)

The 29 exports in `/home/edq/Downloads/CGDream_Zips/` were extracted into 25
monthly folders alongside the original ZIPs. Multipart months were combined.
12,748 files (14,594,191,119 bytes) were extracted, with each output checked
against its archive member's size and CRC32. Original ZIPs were preserved and
archive timestamps restored. The Mac view of the same share is
`/Volumes/downloads/CGDream_Zips/`.

Direct link: http://192.168.7.226:8060/?root=downloads&dir=CGDream_Zips

## Verification

Run `venv_dl_gallery/bin/python scripts/test_dl_gallery.py`. Tests create
temporary fixtures and check deep navigation, encoded names, thumbnail/full-size
requests, favorites, isolated deletion, empty folders, root aliases, service
symlinks, blocked traversal, and generated JavaScript syntax (requires Node).
Run `python3 scripts/health_check.py --categories utility` for registry health.
