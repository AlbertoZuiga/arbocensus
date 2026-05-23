#!/bin/bash
# Type check with pyright
set -e
cd "$(dirname "$0")/../.."
echo "Running type checking with pyright..."
pyright .
echo "✓ Type checking complete"
