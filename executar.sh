#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
PORT="${STAGEFLOW_PORT:-8501}"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Ambiente virtual não encontrado em $PROJECT_DIR/.venv" >&2
    echo "Crie-o e instale as dependências antes de iniciar o StageFlow." >&2
    exit 1
fi

if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1024 || PORT > 65535 )); then
    echo "Porta inválida: $PORT" >&2
    exit 1
fi

URL="http://localhost:$PORT"
echo "StageFlow será aberto em $URL"
echo "Mantenha este terminal aberto. Use Ctrl+C para encerrar."

if command -v powershell.exe >/dev/null 2>&1; then
    (
        sleep 2
        powershell.exe -NoProfile -Command "Start-Process '$URL'" >/dev/null 2>&1
    ) &
fi

cd "$PROJECT_DIR"
exec env PYTHONPATH="$PROJECT_DIR/src" "$PYTHON_BIN" -m streamlit run \
    "$PROJECT_DIR/src/stageflow/ui.py" \
    --server.address=127.0.0.1 \
    --server.port="$PORT" \
    --server.headless=true \
    --browser.gatherUsageStats=false
