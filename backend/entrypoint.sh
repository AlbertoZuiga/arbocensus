#!/usr/bin/env bash
set -euo pipefail

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-arbocensus}"

echo "[entrypoint] waiting for postgres at ${DB_HOST}:${DB_PORT}..."
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
  sleep 1
done
echo "[entrypoint] postgres ready"

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] applying migrations"
  python manage.py migrate --noinput

  if [ "${COLLECT_STATIC:-false}" = "true" ]; then
    echo "[entrypoint] collecting static files"
    python manage.py collectstatic --noinput
  fi

  if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "[entrypoint] ensuring admin user '${DJANGO_SUPERUSER_USERNAME}'"
    python manage.py shell <<'PYEOF'
import os

from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ["DJANGO_SUPERUSER_USERNAME"]
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
password = os.environ["DJANGO_SUPERUSER_PASSWORD"]

user, created = User.objects.get_or_create(
    username=username,
    defaults={
        "email": email,
        "is_staff": True,
        "is_superuser": True,
        "role": User.Role.ADMIN,
    },
)
if created:
    user.set_password(password)
    user.save()
    print(f"[entrypoint] superuser '{username}' created")
else:
    print(f"[entrypoint] superuser '{username}' already exists, skipping")
PYEOF
  fi

  if [ "${SEED_DEV:-true}" = "true" ]; then
    echo "[entrypoint] running idempotent dev seed"
    python manage.py seed_dev
  fi
fi

exec "$@"
