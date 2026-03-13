# Checkpoint de bibliotecas do GEPUB

Data: 2026-03-13

## Backend Django

### Ja existiam no projeto
- Django
- Celery
- Redis (client)
- PyMemcache
- WeasyPrint
- OpenPyXL
- Pillow
- pypdf

### Instaladas e configuradas neste checkpoint
- djangorestframework
- django-filter
- django-guardian
- djangorestframework-simplejwt
- channels
- channels-redis
- meilisearch (client Python)

## Configuracoes aplicadas
- API base com JWT:
  - `/api/auth/token/`
  - `/api/auth/token/refresh/`
  - `/api/auth/token/verify/`
- `REST_FRAMEWORK` com autenticacao, filtros e paginacao padrao.
- `SIMPLE_JWT` com tempo de vida configuravel por variavel de ambiente.
- `django-guardian` habilitado em `AUTHENTICATION_BACKENDS`.
- `ASGI_APPLICATION` + `CHANNEL_LAYERS` (in-memory em dev e Redis opcional).
- Variaveis novas no `.env.example` para DRF/JWT/Channels/Meilisearch.

## Frontend moderno (React/Vite/Tailwind/shadcn etc.)

### Instalado neste checkpoint
- React + TypeScript + Vite em `frontend/`
- TailwindCSS (base utilitaria para UI)
- Componentes estilo shadcn com `class-variance-authority`, `clsx` e `tailwind-merge`
- Radix UI (Tabs, Select, Dialog, Tooltip)
- TanStack Query + TanStack Table
- React Hook Form + Zod
- Recharts + Chart.js + Plotly
- Tiptap (editor rich-text)

### Integracao com Django
- Build frontend gera assets em `static/frontend/`
- Tela de laboratorio: `/sistema/frontend-lab/`
- APIs usadas pelo laboratorio:
  - `/api/frontend/overview/`
  - `/api/frontend/secretarias/`

## Docker pronto

- `Dockerfile` multi-stage (build frontend + runtime python)
- `docker-compose.yml` com:
  - web (Django + Daphne)
  - worker (Celery)
  - beat (Celery Beat)
  - postgres
  - redis
  - meilisearch
- `docker/entrypoint.sh` com:
  - espera ativa de PostgreSQL/Redis
  - `migrate` automático
  - `collectstatic` automático
