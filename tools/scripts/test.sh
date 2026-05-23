#!/bin/bash
# Run pytest
set -e
cd "$(dirname "$0")/../.."
echo "Running tests with pytest..."
pytest
echo "✓ Tests complete"
