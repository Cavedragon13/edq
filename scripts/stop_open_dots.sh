#!/bin/bash
set -euo pipefail

LOG_DIR=/srv/containers/edq/logs/open-dots

for component in web api; do
    pid_file="$LOG_DIR/$component.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)
        if [[ "$component" == "api" && "$cwd" == "/srv/containers/edq/projects/open-dots/server" ]] || \
           [[ "$component" == "web" && "$cwd" == "/srv/containers/edq/projects/open-dots/client" ]]; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
        rm "$pid_file"
    fi
done

docker ps -q --filter label=open-dots.runtime=computer | xargs -r docker stop >/dev/null

echo "Open Dots stopped"
