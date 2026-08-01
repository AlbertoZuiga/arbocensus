#!/usr/bin/env bash
set -euo pipefail

# Creates a compressed pg_dump of the production database plus a tarball of the
# media volume (TreeObservation photos), which the dump does not contain.
# Keeps the last 7 daily copies of each; older ones are deleted.
# Intended to be run from a host cron (e.g. daily at 03:00):
#   0 3 * * * /srv/arbocensus/scripts/pg-backup.sh >> /var/log/arbocensus-backup.log 2>&1

COMPOSE_FILE="/srv/arbocensus/docker-compose.production.yml"
BACKUP_DIR="/srv/arbocensus/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUT="$BACKUP_DIR/arbocensus_$TIMESTAMP.dump"
MEDIA_OUT="$BACKUP_DIR/media_$TIMESTAMP.tar.gz"
RETAIN_DAYS=7

mkdir -p "$BACKUP_DIR"
rm -f "$BACKUP_DIR"/*.part

# Credentials come from the container's own POSTGRES_* so they cannot drift from .env.
# Dump to a .part file so a failed pg_dump never leaves a truncated dump behind.
docker compose -f "$COMPOSE_FILE" exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$OUT.part"
mv "$OUT.part" "$OUT"

echo "Backup written: $OUT ($(du -sh "$OUT" | cut -f1))"

docker compose -f "$COMPOSE_FILE" exec -T backend \
  tar -cz -C /app/media . > "$MEDIA_OUT.part"
mv "$MEDIA_OUT.part" "$MEDIA_OUT"

echo "Media written: $MEDIA_OUT ($(du -sh "$MEDIA_OUT" | cut -f1))"

find "$BACKUP_DIR" \( -name "arbocensus_*.dump" -o -name "media_*.tar.gz" \) \
  -mtime +$RETAIN_DAYS -delete
echo "Pruned backups older than $RETAIN_DAYS days."
