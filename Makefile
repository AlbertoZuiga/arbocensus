.PHONY: up up-build down logs seed shared-up shared-down

# Shared-db model: heavy infra (db + osrm) runs under ONE fixed compose project
# so any worktree can be the first to start it; the rest attach. Only one postgres
# process ever touches the external `arbocensus_postgres_data` volume → no WAL
# PANIC; one OSRM (shared matrix cache in Postgres). redis + celery are NOT shared
# (a shared broker would let one worktree steal another's tasks): each worktree
# runs its OWN backend/frontend/celery/redis from docker-compose.yml.
# See docs/SHARED_DB_WORKTREES.md.

SHARED_PROJECT ?= arbocensus
SHARED := -p $(SHARED_PROJECT) -f docker-compose.shared.yml
SHARED_LOCK := /tmp/$(SHARED_PROJECT)-shared-up.lock

# Bring up shared infra if it is not already running. Idempotent, and serialized
# across worktrees by a mkdir lock: `docker compose up` takes no cross-invocation
# lock of its own, so two simultaneous `make up` would both see no db and both
# try to create it. `--no-recreate` starts only the services that are missing and
# leaves whatever another worktree already owns untouched, so this must check db
# and osrm independently (one can be up without the other). `--wait` blocks until
# the healthchecks pass, so the migrate step never races postgres initdb on a
# fresh volume.
#
# The migrate+seed step runs whenever the infra was found down — not only on the
# very first bring-up — so a host reboot replays it. Both migrate and seed_dev
# are idempotent, so that is correct, just not free. It goes through the
# entrypoint (`backend true`) rather than calling migrate directly because the
# entrypoint also creates the DJANGO_SUPERUSER_* admin between migrate and seed.
shared-up:
	@until mkdir $(SHARED_LOCK) 2>/dev/null; do \
		echo "[shared] another worktree is running shared-up, waiting..."; \
		sleep 2; \
	done; \
	trap 'rmdir $(SHARED_LOCK) 2>/dev/null || true' EXIT; \
	fresh=""; \
	if [ -z "$$(docker compose $(SHARED) ps -q --status=running db 2>/dev/null)" ]; then \
		owner="$$(docker ps --filter volume=arbocensus_postgres_data --format '{{.Names}}')"; \
		if [ -n "$$owner" ]; then \
			echo "[shared] ABORT: container '$$owner' already holds arbocensus_postgres_data"; \
			echo "[shared] starting a second postgres on that volume WAL-PANICs it."; \
			echo "[shared] stop it first, or set SHARED_PROJECT to its compose project."; \
			exit 1; \
		fi; \
		fresh=1; \
	fi; \
	echo "[shared] ensuring db+osrm under project '$(SHARED_PROJECT)'"; \
	docker compose $(SHARED) up -d --wait --no-recreate db osrm; \
	if [ -n "$$fresh" ]; then \
		echo "[shared] migrating + seeding shared db"; \
		docker compose run --rm --no-deps -e RUN_MIGRATIONS=true -e SEED_DEV=true backend true; \
	fi
	@echo "[shared] ready"

up: shared-up
	@if [ -z "$$(docker compose ps -q)" ]; then bash scripts/find-free-ports.sh; fi
	docker compose up -d

up-build: shared-up
	@if [ -z "$$(docker compose ps -q)" ]; then bash scripts/find-free-ports.sh; fi
	docker compose up -d --build

# Stops ONLY this worktree's app services. Shared infra keeps running for the
# other worktrees.
down:
	docker compose down

logs:
	docker compose logs -f

seed:
	docker compose run --rm --no-deps backend python manage.py seed_dev

# DANGER: stops shared infra for ALL worktrees. Never pass -v: the postgres
# volume is external and holds every worktree's data. `stop`, not `down`: `down`
# removes the `arbocensus_default` network, which every other worktree declares
# as external — their compose files stop resolving until the infra is back up.
shared-down:
	docker compose $(SHARED) stop db osrm
