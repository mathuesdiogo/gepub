# Docker Setup - GEPUB

## Pré-requisitos

- Docker Engine + Docker Compose plugin
- Arquivo de ambiente local: `.env.docker`
- Arquivo de ambiente produção: `.env.docker.prod`

## Ambiente local

```bash
cp .env.docker.example .env.docker
docker compose up --build -d
```

Logs:

```bash
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f beat
```

Comandos úteis:

```bash
docker compose ps
docker compose run --rm web manage migrate
docker compose run --rm web manage check
docker compose run --rm web manage createsuperuser
docker compose run --rm web shell
docker compose down
```

## Ambiente de produção (HTTPS com Caddy)

Arquivos usados:

- `docker-compose.prod.yml`
- `docker/caddy/Caddyfile`
- `.env.docker.prod`

Pré-requisito DNS:

- O domínio definido em `APP_DOMAIN` deve apontar (registro `A/AAAA`) para o IP do servidor antes do primeiro deploy.

Preparação:

```bash
cp .env.docker.prod.example .env.docker.prod
# edite segredos, domínio e e-mail ACME
```

Deploy:

```bash
./scripts/deploy_prod.sh
```

Ou manual:

```bash
docker compose --env-file .env.docker.prod -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.docker.prod -f docker-compose.prod.yml run --rm web manage migrate
docker compose --env-file .env.docker.prod -f docker-compose.prod.yml run --rm web manage check
```

Logs de produção:

```bash
docker compose --env-file .env.docker.prod -f docker-compose.prod.yml logs -f web
docker compose --env-file .env.docker.prod -f docker-compose.prod.yml logs -f worker
docker compose --env-file .env.docker.prod -f docker-compose.prod.yml logs -f beat
```

## Backup e restore (produção)

Backup (PostgreSQL + media):

```bash
./scripts/backup_docker.sh
```

Variáveis úteis:

- `COMPOSE_FILE` (default `docker-compose.prod.yml`)
- `ENV_FILE` (default `.env.docker.prod`)
- `BACKUP_ROOT` (default `./backups`)
- `RETENTION_DAYS` (default `14`)

Restore:

```bash
./scripts/restore_docker.sh backups/<YYYYMMDD_HHMMSS>
```

## Agendamento diário sugerido (cron)

Exemplo para rodar backup todo dia 02:30:

```bash
crontab -e
```

Linha:

```cron
30 2 * * * cd /home/matheus/Desktop/gepub && ./scripts/backup_docker.sh >> /home/matheus/Desktop/gepub/logs/backup.log 2>&1
```

## Serviços da stack local/prod

- `web`: Django ASGI (Daphne)
- `worker`: Celery worker
- `beat`: Celery scheduler
- `db`: PostgreSQL 16
- `redis`: cache, Celery broker e Channels
- `meilisearch`: engine de busca
- `caddy` (somente prod): reverse proxy com HTTPS automático
