#!/bin/bash
set -e
CONTAINER="${1:-postgres}"
FILE="backup_$(date +%Y%m%d_%H%M%S).sql.gz"
docker compose -f "$(dirname "$0")/../compose.yml" exec -T "$CONTAINER" \
    pg_dump -U "${POSTGRES_USER:-douini}" "${POSTGRES_DB:-douini}" | gzip > "$FILE"
echo "Backup saved: $FILE"
