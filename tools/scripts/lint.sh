#!/bin/bash
# Lint Python code with ruff
set -e
cd "$(dirname "$0")/../.."
echo "Running ruff lint check..."
ruff check . --fix
echo "✓ Linting complete"
