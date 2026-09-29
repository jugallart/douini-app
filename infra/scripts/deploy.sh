#!/bin/bash
set -e
cd "$(dirname "$0")/.."
docker compose -f compose.yml pull
docker compose -f compose.yml up -d
sleep 3
curl -sf http://localhost:8000/api/v1/health || echo "WARN: health check failed"
echo "Deploy done."
