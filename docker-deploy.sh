#!/usr/bin/env bash
set -euo pipefail

echo "Starting RankJee one-command Docker deployment..."

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: docker compose plugin is not available."
  exit 1
fi

# Stop old containers (safe if not running)
docker compose down

# Build and start all services
docker compose up --build -d

# Wait a bit for healthchecks/migrations
sleep 6

echo
docker compose ps
echo
echo "Done."
echo "App:   http://localhost:8000"
echo "Admin: http://localhost:8000/sd/"
