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
