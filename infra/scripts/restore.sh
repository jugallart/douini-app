#!/bin/bash
set -e
FILE="$1"
if [ -z "$FILE" ]; then
    echo "Usage: restore.sh <backup.sql.gz>"
    exit 1
fi
read -rp "This will OVERWRITE the database. Continue? [yes/no] " confirm
[ "$confirm" = "yes" ] || exit 1
gunzip -c "$FILE" | docker compose -f "$(dirname "$0")/../compose.yml" exec -T postgres \
    psql -U "${POSTGRES_USER:-douini}" "${POSTGRES_DB:-douini}"
echo "Restore done."
