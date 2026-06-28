.PHONY: up up-build down down-v seed

# On `up`/`up-build` the backend entrypoint runs `seed_dev` idempotently
# (test users + light dataset). Disable with SEED_DEV=false in .env.

up:
	bash scripts/find-free-ports.sh
	docker compose up -d

up-build:
	bash scripts/find-free-ports.sh
	docker compose up -d --build

seed:
	docker compose exec backend python manage.py seed_dev

down:
	docker compose down

down-v:
	docker compose down -v
