#!/bin/bash
set -e

TRASH="$HOME/.local/share/Trash"

zenity --question --title="Empty Trash" \
  --text="Permanently delete everything in Trash?\nThis cannot be undone." \
  --width=300 2>/dev/null

SIZE=$(du -sh "$TRASH" 2>/dev/null | cut -f1)

shopt -s nullglob dotglob
rm -rf "$TRASH"/files/* "$TRASH"/info/*
shopt -u nullglob dotglob

notify-send "🗑️ Trash Emptied" "Freed ${SIZE:-0} of space"
