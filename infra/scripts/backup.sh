#!/bin/bash
# usage: backup.sh <prod|ppe>
set -e
ENV_NAME="${1:?usage: backup.sh prod|ppe}"
cd "$(dirname "$0")/.."
export ENV_NAME
FILE="backup_${ENV_NAME}_$(date +%Y%m%d_%H%M%S).sql.gz"
docker compose -p "douini-$ENV_NAME" --env-file ".env.$ENV_NAME" exec -T postgres \
    sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$FILE"
echo "Backup saved: $FILE"
