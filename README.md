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
