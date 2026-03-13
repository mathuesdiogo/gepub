# Docker Setup - GEPUB

## Pré-requisitos

- Docker Engine + Docker Compose plugin
- Arquivo de ambiente: `.env.docker`

```bash
cp .env.docker.example .env.docker
```

## Subir stack completa

```bash
docker compose up --build -d
```

## Ver logs

```bash
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f beat
```

## Comandos úteis

```bash
# status dos containers
docker compose ps

# rodar comando Django dentro do web
docker compose run --rm web manage check
docker compose run --rm web manage createsuperuser

# shell Django
docker compose run --rm web shell

# parar stack
docker compose down
```

## Serviços

- `web`: Django ASGI (Daphne)
- `worker`: Celery worker
- `beat`: Celery scheduler
- `db`: PostgreSQL 16
- `redis`: cache, Celery broker e Channels
- `meilisearch`: engine de busca
