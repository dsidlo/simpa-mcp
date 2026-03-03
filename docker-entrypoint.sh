#!/bin/bash
set -e

# SIMPA MCP Service Entrypoint

# Run database migrations if SKIP_MIGRATIONS is not set
if [ -z "$SKIP_MIGRATIONS" ]; then
    echo "Running database migrations..."
    alembic upgrade head
fi

# Execute the main command
exec "$@"
