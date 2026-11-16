#!/usr/bin/env bash
# ==============================================================================
# Database Migrations Runner (Alembic)
# Usage:
#   ./scripts/run_migrations.sh upgrade head
#   ./scripts/run_migrations.sh downgrade -1
# ==============================================================================

set -euo pipefail

COMMAND="${1:-upgrade}"
TARGET="${2:-head}"

echo "==> Executing Alembic migration: ${COMMAND} ${TARGET}..."

# If inside container or local python environment with alembic
if command -v alembic &> /dev/null; then
    alembic "${COMMAND}" "${TARGET}"
else
    # Execute within running backend container
    CONTAINER_NAME="paper_trading_backend"
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker exec -t "${CONTAINER_NAME}" alembic "${COMMAND}" "${TARGET}"
    else
        echo "ERROR: Neither local alembic nor container ${CONTAINER_NAME} found."
        echo "Please run: docker compose up -d"
        exit 1
    fi
fi

echo "==> Migration completed successfully."
