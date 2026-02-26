#!/bin/bash
# Wrapper to run npx with Node 20 (nvm) as the active runtime
export PATH="/home/edq/.nvm/versions/node/v20.20.0/bin:$PATH"
exec npx "$@"
