#!/usr/bin/env bash
# Health-gated update for the net_alpha box. Pulls the requested image tag,
# brings the app up, waits for the container HEALTHCHECK to pass, and rolls
# back to the previously-running tag if it does not.
#
# Usage: NEW_TAG=v0.81.0 ./update.sh   (or relies on IMAGE_TAG in secrets.env)
set -euo pipefail

cd "$(dirname "$0")"
ENV_FILE="./secrets.env"
COMPOSE="docker compose --env-file ${ENV_FILE} -f docker-compose.yml"

# shellcheck disable=SC1090
source "${ENV_FILE}"
PREV_TAG="${IMAGE_TAG}"
NEW_TAG="${NEW_TAG:-${IMAGE_TAG}}"

echo "Updating ${IMAGE_REPO}: ${PREV_TAG} -> ${NEW_TAG}"
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${NEW_TAG}/" "${ENV_FILE}"

${COMPOSE} pull app
${COMPOSE} up -d app

cid="$(${COMPOSE} ps -q app)"
for _ in $(seq 1 24); do          # up to 120s
  status="$(docker inspect --format '{{.State.Health.Status}}' "${cid}" 2>/dev/null || echo starting)"
  if [ "${status}" = "healthy" ]; then
    echo "New image ${NEW_TAG} is healthy."
    exit 0
  fi
  sleep 5
done

echo "ERROR: ${NEW_TAG} did not become healthy — rolling back to ${PREV_TAG}." >&2
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${PREV_TAG}/" "${ENV_FILE}"
${COMPOSE} up -d app
exit 1
