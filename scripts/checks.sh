#!/usr/bin/env bash
# Lint, type-check and complexity gate; run by the global pre-push dispatcher.
set -euo pipefail
cd "$(dirname "$0")/.."

poetry run ruff check
poetry run ruff format --check
poetry run pyright
# The Windows and macOS backends only type-check under their own platform.
poetry run pyright -p scripts/pyright-windows.json
poetry run pyright -p scripts/pyright-darwin.json
# Fail on anything above cyclomatic complexity grade B.
if poetry run radon cc darkdetect -n C | grep -q .; then
    poetry run radon cc darkdetect -n C -s
    exit 1
fi
