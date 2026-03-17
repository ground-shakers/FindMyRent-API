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

echo "==> Waiting for container to stabilise..."
sleep 5

echo "==> Health check..."
curl -sf "$HEALTH_URL" \
    || (echo "Health check failed! Rolling back..." && \
        docker stop "$CONTAINER_NAME" && \
        docker rm "$CONTAINER_NAME" && \
        echo "Container stopped. Check logs: docker logs ${CONTAINER_NAME}" && \
        exit 1)

echo "==> Pruning old images..."
docker image prune -f

echo "==> Deployment successful!"
echo "==> Live at: https://ground-shakers.xyz"