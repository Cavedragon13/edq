# FreshRSS (udragon)

RSS reader. Listed on the Dragonsuite dashboard as an `always_on` entry (like Pi-hole), with no launch or stop buttons: Docker keeps it running (`restart: unless-stopped`).

- URL: http://192.168.7.226:8087/ on the LAN, or http://udragon.tailabdedc.ts.net:8087/ over Tailscale (published on all interfaces; the login is the only protection, so don't port-forward it on the router)
- User: `admin`; password in `.env` (git-ignored, mode 600) as `ADMIN_PASSWORD`
- Image: `freshrss/freshrss:latest` (Debian, SQLite), data in Docker volumes `freshrss_freshrss_data` / `freshrss_freshrss_extensions`
- Auto-refresh: built-in cron at :13 and :43 (`CRON_MIN`), TZ America/New_York
- Feeds: 21 imported 2026-11-12 from cdragon's DragonRSS `imported.opml` (same 4 categories), plus FreshRSS's own default releases feed
- Same setup as cdragon (`~/.local/share/DragonRSS`, PHP built-in server on :8087), but via Docker here

## Operate

```bash
cd /srv/containers/edq/docker/freshrss
docker compose up -d          # start
docker compose pull && docker compose up -d   # update
docker exec --user www-data freshrss cli/actualize-user.php --user admin   # refresh now
docker exec --user www-data freshrss cli/export-opml-for-user.php --user admin > backup.opml   # feed backup
```

`FRESHRSS_INSTALL` / `FRESHRSS_USER` in the compose file only apply on the very first start with an empty data volume.
Docs: https://github.com/FreshRSS/FreshRSS/blob/edge/Docker/README.md
