#!/bin/bash
# Format Python code with ruff
set -e
cd "$(dirname "$0")/../.."
echo "Running ruff format..."
ruff format .
echo "✓ Formatting complete"
