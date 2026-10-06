#!/bin/bash
# usage: deploy.sh <prod|ppe>  (needs infra/.env.<env>; one-time: docker network create edge)
set -e
ENV_NAME="${1:?usage: deploy.sh prod|ppe}"
cd "$(dirname "$0")/.."
export ENV_NAME
PROFILE=""; [ "$ENV_NAME" = prod ] && PROFILE="--profile edge"
C="docker compose -p douini-$ENV_NAME --env-file .env.$ENV_NAME -f compose.yml $PROFILE"
$C pull
$C up -d --build
echo "Deploy $ENV_NAME done."
