#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATOR="/home/matheus/.codex/skills/.system/skill-creator/scripts/quick_validate.py"

if [[ ! -f "$VALIDATOR" ]]; then
  echo "Validador nao encontrado em: $VALIDATOR"
  exit 1
fi

echo "[1/4] Validando skills..."
for d in "$ROOT_DIR"/skills/gepub-*; do
  python3 "$VALIDATOR" "$d" >/dev/null
  echo "  - OK $(basename "$d")"
done

echo "[2/4] Gerando catalogo de Educacao..."
python3 "$ROOT_DIR"/skills/gepub-educacao-content-ingestion/scripts/build_catalog.py >/dev/null

echo "[3/4] Gerando backlog tecnico de Educacao..."
python3 "$ROOT_DIR"/skills/gepub-educacao-content-ingestion/scripts/build_backlog.py >/dev/null

echo "[4/4] Gerando catalogos/backlogs de conhecimento para todos os apps..."
python3 "$ROOT_DIR"/scripts/gepub_materials.py build --all >/dev/null

echo "Pipeline concluido com sucesso."
