#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "python3.12 is required but not found in PATH" >&2
  exit 1
fi

python3.12 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

echo "Development environment is ready."
echo "Activate with: source .venv/bin/activate"
