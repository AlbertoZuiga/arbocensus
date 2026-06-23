.PHONY: up up-build down down-v

up:
	bash scripts/find-free-ports.sh
	docker compose up -d

up-build:
	bash scripts/find-free-ports.sh
	docker compose up -d --build

down:
	docker compose down

down-v:
	docker compose down -v
