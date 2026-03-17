#!/bin/bash
# infrastructure/scripts/deploy.sh
# Called by Jenkins (Deploy stage) or manually via SSH.
# Usage: ./infrastructure/scripts/deploy.sh [git-commit-sha]
set -e

APP_DIR="/home/ubuntu/FindMyRent-API"
CONTAINER_NAME="findmyrent-api"
IMAGE_NAME="findmyrent-api"
ENV_FILE="/home/ubuntu/.env"
HEALTH_URL="http://localhost:8000/docs"

# Use provided commit SHA or default to latest master
COMMIT="${1:-latest}"

echo "==> Pulling latest code..."
cd "$APP_DIR"
git fetch origin master
git reset --hard origin/master

echo "==> Building Docker image (tag: ${COMMIT})..."
docker build -t "${IMAGE_NAME}:${COMMIT}" .
docker tag "${IMAGE_NAME}:${COMMIT}" "${IMAGE_NAME}:latest"

echo "==> Stopping old container..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

echo "==> Starting new container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --env-file "$ENV_FILE" \
    --network host \
    "${IMAGE_NAME}:latest"

echo "==> Health check (waiting up to 30s for app to start)..."
RETRIES=6
DELAY=5
for i in $(seq 1 $RETRIES); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        echo "==> Health check passed on attempt $i"
        break
    fi
    if [ "$i" -eq "$RETRIES" ]; then
        echo "Health check failed after ${RETRIES} attempts! Rolling back..."
        docker logs "$CONTAINER_NAME" 2>&1 | tail -30
        docker stop "$CONTAINER_NAME"
        docker rm "$CONTAINER_NAME"
        exit 1
    fi
    echo "    Attempt $i/$RETRIES failed, retrying in ${DELAY}s..."
    sleep $DELAY
done

echo "==> Pruning old images..."
docker image prune -f

echo "==> Deployment successful!"
echo "==> Live at: https://ground-shakers.xyz"