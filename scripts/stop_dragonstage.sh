#!/bin/bash
set -euo pipefail
ssh -o BatchMode=yes -o ConnectTimeout=8 odragon 'bash /Users/edq/Documents/DragonStage/tools/stop-macos.sh'
