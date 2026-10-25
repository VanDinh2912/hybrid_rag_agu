#!/usr/bin/env sh
# Chạy một chuỗi round từ spec JSON (T7) — wrapper mỏng quanh tools/loop/run_chain.py.
# Dùng: tools/loop/run_chain.sh tools/loop/chains/t5a_reranker.json [--dry-run] [--resume]
# Không tự export biến nào: mọi biến của từng bước nằm trong spec và được in ra trước khi chạy.
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$HERE/../.." && pwd)

if [ -x "$REPO/venv/bin/python" ]; then
    PY="$REPO/venv/bin/python"
elif [ -f "$REPO/venv/Scripts/python.exe" ]; then
    PY="$REPO/venv/Scripts/python.exe"
else
    PY="${PYTHON:-python3}"
fi

PYTHONIOENCODING=utf-8 "$PY" "$HERE/run_chain.py" "$@"
