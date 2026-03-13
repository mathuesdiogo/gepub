#!/usr/bin/env bash
set -euo pipefail

role="${1:-web}"
if [ "$#" -gt 0 ]; then
  shift
fi

wait_for_port() {
  local host="$1"
  local port="$2"
  local label="$3"
  local retries="${4:-120}"

  python - "$host" "$port" "$label" "$retries" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
label = sys.argv[3]
retries = int(sys.argv[4])

for _ in range(retries):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] {label} pronto em {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(1)

print(f"[entrypoint] timeout aguardando {label} em {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
}

if [ "${DJANGO_DB_ENGINE:-}" = "postgres" ] || [ "${DJANGO_DB_ENGINE:-}" = "postgresql" ]; then
  wait_for_port "${DJANGO_DB_HOST:-db}" "${DJANGO_DB_PORT:-5432}" "PostgreSQL"
fi

if [ "${WAIT_FOR_REDIS:-1}" = "1" ]; then
  wait_for_port "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" "Redis"
fi

case "$role" in
  web)
    if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
      python manage.py migrate --noinput
    fi

    if [ "${COLLECTSTATIC_ON_START:-1}" = "1" ]; then
      python manage.py collectstatic --noinput
    fi

    exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
    ;;

  worker)
    exec celery -A config worker -l "${CELERY_LOGLEVEL:-INFO}" --concurrency="${CELERY_WORKER_CONCURRENCY:-2}"
    ;;

  beat)
    exec celery -A config beat -l "${CELERY_LOGLEVEL:-INFO}"
    ;;

  manage)
    exec python manage.py "$@"
    ;;

  shell)
    exec python manage.py shell
    ;;

  *)
    exec "$role" "$@"
    ;;
esac
