#!/usr/bin/env bash
set -euo pipefail

PY="python3.12"
if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
fi

"$PY" -m teleportdog \
  --state ./.teleportdog-demo-state.json \
  --corpus "./teleportdog/data/*.txt" <<'EOF'
what can you do
/mode t9
43556
/mode text
If I say my name starts with Time and ends with less, what is my name?
/quit
EOF
