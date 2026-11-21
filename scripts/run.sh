#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .venv/bin/python ]]; then
  .venv/bin/python -m shortsfactory.cli
else
  python3 -m shortsfactory.cli
fi
