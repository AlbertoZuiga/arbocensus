.PHONY: up

up:
	bash scripts/find-free-ports.sh
	docker compose up $(ARGS)
