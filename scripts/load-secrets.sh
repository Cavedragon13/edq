#!/bin/bash
# load-secrets.sh — Sources API keys from Vaultwarden into the current shell
# Usage: source /srv/containers/edq/scripts/load-secrets.sh

_LS_BW_PATH="$HOME/.nvm/versions/node/v20.20.0/bin/bw"
_LS_SESSION_FILE="$HOME/.bw_session"

# Validate or establish a Vaultwarden session
if [ -f "$_LS_SESSION_FILE" ]; then
    export BW_SESSION=$(cat "$_LS_SESSION_FILE")
fi

if [ -n "$BW_SESSION" ]; then
    _LS_STATUS=$(NODE_TLS_REJECT_UNAUTHORIZED=0 "$_LS_BW_PATH" status --session "$BW_SESSION" 2>/dev/null)
    if ! echo "$_LS_STATUS" | grep -q '"status":"unlocked"'; then
        BW_SESSION=""
    fi
fi

if [ -z "$BW_SESSION" ]; then
    _LS_PASS=$(awk '/^Password:/{print $2}' "$HOME/.vault_emergency" 2>/dev/null)
    if [ -z "$_LS_PASS" ]; then
        echo "⚠️  Vaultwarden: can't read master password, falling back to .env" >&2
        source /srv/containers/edq/.env 2>/dev/null
        return 0
    fi
    export BW_SESSION=$(NODE_TLS_REJECT_UNAUTHORIZED=0 "$_LS_BW_PATH" unlock "$_LS_PASS" --raw 2>/dev/null)
    if [ -z "$BW_SESSION" ]; then
        echo "⚠️  Vaultwarden unlock failed, falling back to .env" >&2
        source /srv/containers/edq/.env 2>/dev/null
        return 0
    fi
    echo "$BW_SESSION" > "$_LS_SESSION_FILE"
    chmod 600 "$_LS_SESSION_FILE"
fi

# Fetch the dragonsuite-env secure note and source it
_LS_TMP=$(mktemp)
NODE_TLS_REJECT_UNAUTHORIZED=0 "$_LS_BW_PATH" get notes "dragonsuite-env" \
    --session "$BW_SESSION" 2>/dev/null > "$_LS_TMP"

if [ -s "$_LS_TMP" ]; then
    set -a
    source "$_LS_TMP"
    set +a
else
    echo "⚠️  Vaultwarden note missing or empty, falling back to .env" >&2
    source /srv/containers/edq/.env 2>/dev/null
fi

rm -f "$_LS_TMP"
unset _LS_BW_PATH _LS_SESSION_FILE _LS_STATUS _LS_PASS _LS_TMP
