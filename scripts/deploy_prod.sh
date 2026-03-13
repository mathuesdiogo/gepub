#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.docker.prod}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[deploy] arquivo $ENV_FILE não encontrado." >&2
  echo "[deploy] copie .env.docker.prod.example para $ENV_FILE e preencha os segredos." >&2
  exit 1
fi

COMPOSE_CMD=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

echo "[deploy] build + up"
"${COMPOSE_CMD[@]}" up -d --build

echo "[deploy] migrations"
"${COMPOSE_CMD[@]}" run --rm web manage migrate

echo "[deploy] health check"
"${COMPOSE_CMD[@]}" run --rm web manage check

echo "[deploy] status"
"${COMPOSE_CMD[@]}" ps

echo "[deploy] concluído"
