# GEPUB (Gestao Estrategica Publica)

Monolito modular com apps:
- `core`
- `accounts`
- `pessoas`
- `org`
- `educacao`
- `nee`
- `saude`
- `financeiro`

## Rodar local

```bash
source venv/bin/activate
python manage.py migrate
python manage.py runserver
```

## Frontend (React + Vite)

```bash
# se o node nao estiver no PATH do sistema
export PATH="$HOME/.local/node/bin:$PATH"

cd frontend
npm install
npm run build
```

## Docker (stack completa)

Serviços incluídos no `docker-compose.yml`:
- `web` (Django ASGI com Daphne)
- `worker` (Celery worker)
- `beat` (Celery beat)
- `db` (PostgreSQL)
- `redis` (cache/broker/channels)
- `meilisearch` (busca)

Passos:

```bash
cp .env.docker.example .env.docker
docker compose up --build -d
docker compose logs -f web
```

Endpoints:
- App: `http://127.0.0.1:8000`
- Frontend Lab: `http://127.0.0.1:8000/sistema/frontend-lab/`

## Docker produção (HTTPS)

Arquivos:
- `docker-compose.prod.yml`
- `docker/caddy/Caddyfile`
- `.env.docker.prod.example`

Passos:

```bash
cp .env.docker.prod.example .env.docker.prod
# ajustar domínio, e-mail ACME e segredos
./scripts/deploy_prod.sh
```

Operação:

```bash
# backup (PostgreSQL + media)
./scripts/backup_docker.sh

# restore
./scripts/restore_docker.sh backups/<YYYYMMDD_HHMMSS>
```

## UI Core

- Layout base: `templates/core/base.html`
- Mensagens globais (success/error) no layout base
- Templates de erro:
  - `templates/404.html`
  - `templates/500.html`

## Navegação (UI Core)
- Breadcrumbs: definido por página via `{% block breadcrumbs %}`.
- Menu ativo: baseado em `request.resolver_match.namespace`.
- Título: `base.html` usa `{% block header %}`.
## Módulo ORG
Entidades base do sistema:
- Município → Secretarias → Unidades → Setores

Regras:
- Relacionamentos usam `on_delete=PROTECT` para evitar exclusões acidentais.
- Unicidade:
  - Secretaria única por município (nome)
  - Unidade única por secretaria (nome)
  - Setor único por unidade (nome)

## ORG - CRUD (fora do admin)
Rotas iniciais:
- /org/municipios/ (lista + busca + paginação)
- /org/municipios/novo/
- /org/municipios/<id>/
- /org/municipios/<id>/editar/

## Documentação adicional
- Declaração de vínculo escolar (PDF): `docs/educacao_declaracao_vinculo.md`
- Comunicação automática (E-mail/SMS/WhatsApp): `docs/comunicacao_automatica_gepub.md`
- Revisão técnica (estrutura, segurança e escalabilidade): `docs/revisao_estrutura_seguranca_escalabilidade.md`
- Módulo Operação (funções e integrações): `docs/modulo_operacao_funcoes_integracoes.md`
- Plataforma/Acesso/Site (funções e integrações): `docs/modulos_demais_plataforma_acesso_site_funcoes_integracoes.md`
- Serviços (Educação, Avaliações, NEE e Saúde): `docs/modulos_demais_servicos_funcoes_integracoes.md`
- Ferramentas (Integrações, Comunicação, Painéis e Conversor): `docs/modulos_demais_ferramentas_funcoes_integracoes.md`
- Departamentalização e skills por app/módulo: `docs/gepub_departamentalizacao_apps_modulos_skills_2026-03-07.md`
- Catálogo de owners por app/skill: `docs/gepub_owners_catalogo_2026-03-07.csv`
- Guia operacional de uso das skills: `docs/gepub_skills_operacao_2026-03-07.md`

## Skills do ecossistema GEPUB
- Skills estão em `skills/` (uma skill por pasta, com `SKILL.md`, `agents/openai.yaml` e `references/`).
- Modo padrão: `gepub-auto-orchestrator` seleciona automaticamente as skills por demanda.
- Existem skills por app (`gepub-app-*`) e skills transversais (`gepub-system-design`, `gepub-security-hardening`, etc.).
- Intake de materiais para qualquer app:
  - Script universal: `python3 scripts/gepub_materials.py`
  - Inicialização: `python3 scripts/gepub_materials.py init --all`
  - Ingestão de arquivo físico: `python3 scripts/gepub_materials.py add-file --app <app> --file /caminho/arquivo.pdf`
  - Auditoria/aprimoramento de padrão e completude: `python3 scripts/gepub_materials.py audit --all`
  - Geração de catálogo/backlog: `python3 scripts/gepub_materials.py build --all`
- Skill de curadoria de conteúdo para Educação (complementar):
  - Fonte CSV: `skills/gepub-educacao-content-ingestion/references/fontes_educacao_template.csv`
