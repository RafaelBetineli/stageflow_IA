#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Ambiente virtual não encontrado em $PROJECT_DIR/.venv" >&2
    exit 1
fi

cd "$PROJECT_DIR"
exec env PYTHONPATH="$PROJECT_DIR/src" "$PYTHON_BIN" -m stageflow.cli "$@"
