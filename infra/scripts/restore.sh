#!/bin/bash
# usage: restore.sh <prod|ppe> <backup.sql.gz>
set -e
ENV_NAME="${1:?usage: restore.sh prod|ppe <backup.sql.gz>}"
FILE="${2:?usage: restore.sh prod|ppe <backup.sql.gz>}"
FILE="$(realpath "$FILE")"
cd "$(dirname "$0")/.."
export ENV_NAME
read -rp "This will OVERWRITE the $ENV_NAME database. Continue? [yes/no] " confirm
[ "$confirm" = "yes" ] || exit 1
gunzip -c "$FILE" | docker compose -p "douini-$ENV_NAME" --env-file ".env.$ENV_NAME" exec -T postgres \
    sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
echo "Restore done."
