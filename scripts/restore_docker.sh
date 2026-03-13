#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Uso: $0 <backup_dir> [compose_file] [env_file]" >&2
  exit 1
fi

BACKUP_DIR="$1"
COMPOSE_FILE="${2:-docker-compose.prod.yml}"
ENV_FILE="${3:-.env.docker.prod}"

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "[restore] diretório de backup não encontrado: $BACKUP_DIR" >&2
  exit 1
fi

if [[ ! -f "$BACKUP_DIR/postgres.sql.gz" ]]; then
  echo "[restore] arquivo postgres.sql.gz não encontrado em $BACKUP_DIR" >&2
  exit 1
fi

if [[ ! -f "$BACKUP_DIR/media.tar.gz" ]]; then
  echo "[restore] arquivo media.tar.gz não encontrado em $BACKUP_DIR" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[restore] env file não encontrado: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

COMPOSE_CMD=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

echo "[restore] restaurando PostgreSQL..."
gzip -dc "$BACKUP_DIR/postgres.sql.gz" | "${COMPOSE_CMD[@]}" exec -T db psql -U "${POSTGRES_USER:-gepub}" -d "${POSTGRES_DB:-gepub}"

echo "[restore] restaurando media..."
gzip -dc "$BACKUP_DIR/media.tar.gz" | "${COMPOSE_CMD[@]}" exec -T web tar -C /app -xf -

echo "[restore] concluído."
