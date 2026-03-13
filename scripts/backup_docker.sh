#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.docker.prod}"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "[backup] compose file não encontrado: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[backup] env file não encontrado: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

mkdir -p "$BACKUP_ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
TARGET_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$TARGET_DIR"

COMPOSE_CMD=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

echo "[backup] gerando dump PostgreSQL..."
"${COMPOSE_CMD[@]}" exec -T db pg_dump -U "${POSTGRES_USER:-gepub}" -d "${POSTGRES_DB:-gepub}" | gzip > "$TARGET_DIR/postgres.sql.gz"

echo "[backup] compactando media..."
"${COMPOSE_CMD[@]}" exec -T web tar -C /app -cf - media | gzip > "$TARGET_DIR/media.tar.gz"

echo "[backup] salvando manifesto..."
cat > "$TARGET_DIR/manifest.txt" <<EOF
created_at=$(date -Iseconds)
compose_file=$COMPOSE_FILE
env_file=$ENV_FILE
retention_days=$RETENTION_DAYS
EOF

ln -sfn "$TARGET_DIR" "$BACKUP_ROOT/latest"

if [[ "$RETENTION_DAYS" -gt 0 ]]; then
  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -exec rm -rf {} +
fi

echo "[backup] finalizado em: $TARGET_DIR"
