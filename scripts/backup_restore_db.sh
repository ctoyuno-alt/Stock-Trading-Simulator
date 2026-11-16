#!/usr/bin/env bash
# ==============================================================================
# PostgreSQL Backup and Restore Management Utility
# Usage:
#   ./scripts/backup_restore_db.sh backup
#   ./scripts/backup_restore_db.sh restore backups/paper_trading_db_YYYYMMDD_HHMMSS.sql.gz
# ==============================================================================

set -euo pipefail

CONTAINER_NAME="paper_trading_postgres"
BACKUP_DIR="./backups"
DB_USER="${POSTGRES_USER:-trader_user}"
DB_NAME="${POSTGRES_DB:-paper_trading_db}"

mkdir -p "${BACKUP_DIR}"

usage() {
    echo "Usage:"
    echo "  $0 backup                      - Create compressed database backup"
    echo "  $0 restore <backup_file.sql.gz> - Restore database from compressed backup"
    exit 1
}

backup() {
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

    echo "==> Initiating PostgreSQL backup for database: ${DB_NAME}..."

    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "ERROR: Container ${CONTAINER_NAME} is not currently running."
        exit 1
    fi

    docker exec -t "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists | gzip > "${BACKUP_FILE}"

    FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "==> Backup successfully created:"
    echo "    File: ${BACKUP_FILE}"
    echo "    Size: ${FILE_SIZE}"
}

restore() {
    if [ $# -lt 1 ]; then
        echo "ERROR: Please specify the backup file to restore."
        usage
    fi

    RESTORE_FILE="$1"
    if [ ! -f "${RESTORE_FILE}" ]; then
        echo "ERROR: File '${RESTORE_FILE}' does not exist."
        exit 1
    fi

    echo "WARNING: Restoring will overwrite existing data in '${DB_NAME}'!"
    read -rp "Are you sure you want to proceed with restore? (yes/no): " CONFIRM
    if [ "${CONFIRM}" != "yes" ]; then
        echo "Restore operation aborted by user."
        exit 0
    fi

    echo "==> Restoring from ${RESTORE_FILE}..."
    gunzip -c "${RESTORE_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}"
    echo "==> Database restore completed successfully."
}

case "${1:-}" in
    backup)
        backup
        ;;
    restore)
        shift
        restore "$@"
        ;;
    *)
        usage
        ;;
esac
