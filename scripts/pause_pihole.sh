#!/bin/bash
# Pause Pi-hole ad blocking for 5 minutes (it re-enables itself). Runs on udragon.
# Used by the "Pause Pi-hole (5 min)" desktop launcher; the Mac apps run the same
# docker command over SSH (scripts/mac/pause_pihole.applescript).
if docker exec pihole pihole disable 5m >/dev/null 2>&1; then
    notify-send "Pi-hole paused" "Ad blocking is off for 5 minutes, then it turns back on by itself."
else
    notify-send "Pi-hole" "Could not pause"
    exit 1
fi
