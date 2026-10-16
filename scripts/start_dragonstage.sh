#!/bin/bash
# DragonStage native desktop on odragon; status port 8073.
# No CUDA/Python/model dependency; remote process owns its normal GUI quit flow.
set -euo pipefail
cd /srv/containers/edq
source scripts/dragonsuite_lib.sh
mkdir -p /home/edq/ai_generated/dragonstage
service_header 'DragonStage (odragon desktop)' 8073
ssh -o BatchMode=yes -o ConnectTimeout=8 odragon 'bash /Users/edq/Documents/DragonStage/tools/launch-macos.sh'
curl -fsS --max-time 3 http://192.168.7.133:8073/ >/dev/null
echo 'DragonStage is open on odragon. Native exports are mirrored to /home/edq/ai_generated/dragonstage.'
