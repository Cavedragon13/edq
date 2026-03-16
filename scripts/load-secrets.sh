#!/bin/bash
# load-secrets.sh — Sources API keys from Vaultwarden into the current shell
# Usage: source /srv/containers/edq/scripts/load-secrets.sh

_LS_NODE="$HOME/.nvm/versions/node/v20.20.0/bin/node"
_LS_BW_JS="$HOME/.nvm/versions/node/v20.20.0/lib/node_modules/@bitwarden/cli/build/bw.js"
_LS_BW() { NODE_TLS_REJECT_UNAUTHORIZED=0 "$_LS_NODE" "$_LS_BW_JS" "$@"; }
_LS_SESSION_FILE="$HOME/.bw_session"

# Validate or establish a Vaultwarden session
if [ -f "$_LS_SESSION_FILE" ]; then
    BW_SESSION=$(cat "$_LS_SESSION_FILE")
    export BW_SESSION
fi

if [ -n "$BW_SESSION" ]; then
    _LS_STATUS=$(_LS_BW status --session "$BW_SESSION" 2>/dev/null)
    if ! echo "$_LS_STATUS" | grep -q '"status":"unlocked"'; then
        BW_SESSION=""
    fi
fi

if [ -z "$BW_SESSION" ]; then
    _LS_PASS=$(awk '/^Password:/{print $2}' "$HOME/.vault_emergency" 2>/dev/null)
    if [ -z "$_LS_PASS" ]; then
        echo "⚠️  Vaultwarden: can't read master password, falling back to .env" >&2
        # shellcheck source=/srv/containers/edq/.env
        source /srv/containers/edq/.env 2>/dev/null
        return 0
    fi
    BW_SESSION=$(_LS_BW unlock "$_LS_PASS" --raw 2>/dev/null)
    export BW_SESSION
    if [ -z "$BW_SESSION" ]; then
        echo "⚠️  Vaultwarden unlock failed, falling back to .env" >&2
        # shellcheck source=/srv/containers/edq/.env
        source /srv/containers/edq/.env 2>/dev/null
        return 0
    fi
    echo "$BW_SESSION" > "$_LS_SESSION_FILE"
    chmod 600 "$_LS_SESSION_FILE"
fi

# Fetch the dragonsuite-env secure note and source it
_LS_TMP=$(mktemp)
_LS_BW get notes "dragonsuite-env" --session "$BW_SESSION" 2>/dev/null > "$_LS_TMP"

if [ -s "$_LS_TMP" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$_LS_TMP"
    set +a
else
    echo "⚠️  Vaultwarden note missing or empty, falling back to .env" >&2
    # shellcheck source=/srv/containers/edq/.env
    source /srv/containers/edq/.env 2>/dev/null
fi

rm -f "$_LS_TMP"
unset -f _LS_BW
unset _LS_NODE _LS_BW_JS _LS_SESSION_FILE _LS_STATUS _LS_PASS _LS_TMP
