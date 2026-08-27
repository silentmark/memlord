#!/bin/sh
set -e

# The bundled ONNX model is only needed by the in-process provider.
if [ "${MEMLORD_EMBEDDING_PROVIDER:-onnx}" = "onnx" ]; then
    python scripts/download_model.py
fi

alembic upgrade head

if [ "${REEMBED}" = "true" ] || [ "${REEMBED}" = "True" ] || [ "${REEMBED}" = "1" ]; then
    echo "REEMBED=true: re-embedding all memories..."
    python scripts/reembed.py
fi

exec "$@"
