#!/usr/bin/env bash
# Postgres backup — produces a timestamped gzipped pg_dump of fnu_portal.
# Run daily via cron. See docs/TROUBLESHOOTING.md for restore procedure.
#
# Env:
#   DB_NAME      (default: fnu_portal)
#   DB_USER      (default: fnu)
#   DB_HOST      (default: localhost)
#   DB_PORT      (default: 5432)
#   BACKUP_DIR   (default: ./backups)
#   RETENTION_DAYS (default: 14)
#
# Example cron (2am daily):
#   0 2 * * * /path/to/FNU\ Web\ Portal\ MVP/scripts/backup.sh >> /var/log/fnu-backup.log 2>&1

set -euo pipefail

DB_NAME="${DB_NAME:-fnu_portal}"
DB_USER="${DB_USER:-fnu}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "[backup] dumping ${DB_NAME} to ${OUT}"
pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --format=plain \
    --no-owner \
    --no-privileges \
    "$DB_NAME" \
  | gzip -9 > "$OUT"

SIZE=$(du -h "$OUT" | cut -f1)
echo "[backup] ok size=${SIZE}"

find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -type f -mtime +"$RETENTION_DAYS" -delete
echo "[backup] pruned backups older than ${RETENTION_DAYS}d"
