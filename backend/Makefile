.PHONY: install install-dev compile compile-upgrade clean test

install:
	pip install -r requirements.txt

test:
	cd .. && docker compose run --rm --build -e RUN_MIGRATIONS=false backend pytest $(ARGS)

install-dev:
	pip install -r dev-requirements.txt

compile:
	pip-compile requirements.in -o requirements.txt
	pip-compile dev-requirements.in -o dev-requirements.txt

compile-upgrade:
	pip-compile --upgrade requirements.in -o requirements.txt
	pip-compile --upgrade dev-requirements.in -o dev-requirements.txt

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
