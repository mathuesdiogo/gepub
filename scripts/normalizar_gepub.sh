#!/usr/bin/env bash
set -euo pipefail

echo "== GEPUB • Normalização total =="
echo "Pasta atual: $(pwd)"
echo

echo "[1/4] Verificando duplicidades..."
for p in nee gepub/apps/nee gepub/templates/nee apps__bak_* templates__bak_* static__bak_*; do
  if compgen -G "$p" > /dev/null; then
    echo " - encontrado: $p"
  fi
done
echo

echo "[2/4] Ações recomendadas (SEGURAS):"
echo "  - Remover app duplicado:   rm -rf nee/"
echo "  - Remover cópia de app:    rm -rf gepub/apps/nee/"
echo "  - Remover templates dup.:  rm -rf gepub/templates/nee/"
echo "  - Remover backups no repo: rm -rf apps__bak_* templates__bak_* static__bak_*"
echo

read -r -p "Deseja EXECUTAR as remoções agora? (s/N) " ans
if [[ "${ans}" != "s" && "${ans}" != "S" ]]; then
  echo "Abortado. Rode manualmente quando quiser."
  exit 0
fi

rm -rf nee/ || true
rm -rf gepub/apps/nee/ || true
rm -rf gepub/templates/nee/ || true
rm -rf apps__bak_* templates__bak_* static__bak_* || true

echo "[3/4] Limpando __pycache__..."
find . -name "__pycache__" -type d -exec rm -rf {} + || true

echo "[4/4] Feito."
echo "Agora rode:"
echo "  python manage.py check"
echo "  python manage.py migrate"
echo "  python manage.py runserver"
