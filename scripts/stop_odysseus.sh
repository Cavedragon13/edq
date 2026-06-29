#!/bin/bash
set -e

cd /srv/containers/edq/projects/odysseus
docker compose \
    -f docker-compose.yml \
    -f docker-compose.dragonsuite.yml \
    --env-file .env \
    down
