#!/bin/bash
# Start Docker Compose services
#
# Starts services defined in docker-compose.yml if the file exists.
# Useful for projects that require databases or other services.

set -e

if [ -f "docker-compose.yml" ] || [ -f "compose.yml" ]; then
    echo "Starting Docker services..."
    docker compose up -d

    echo "✓ Docker services started"
    echo "  Stop with: docker compose down"
fi
