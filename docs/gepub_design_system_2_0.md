# GEPUB Design System 2.0

## Escopo
- Aplicado apenas ao sistema interno administrativo (área autenticada).
- Portal institucional público e portal público da prefeitura permanecem sem alteração de layout.

## Estrutura
```
static/gepub-design-system/
  core/
  themes/
  components/
  docs/
```

## Temas oficiais
- `kassya`
- `inclusao`
- `institucional`

## Multi-tenant
- Modelo: `org.MunicipioThemeConfig`
- Resolução por: `tenant_id + theme_config`
- Regras:
  - tema padrão por município
  - bloqueio de troca por usuário
  - permissão de override individual
  - override de tokens por tenant (`token_overrides`)

## Preferência por usuário
- Campo `accounts.Profile.ui_theme`
- Respeitado somente quando `allow_user_theme_override=True` e `lock_theme_for_users=False`.

## Tokens universais
- `--gp-primary`
- `--gp-primary-hover`
- `--gp-secondary`
- `--gp-background`
- `--gp-surface`
- `--gp-border`
- `--gp-text-primary`
- `--gp-text-secondary`
- `--gp-success`
- `--gp-warning`
- `--gp-danger`
- `--gp-info`
- `--gp-radius`
- `--gp-spacing-unit`
- `--gp-shadow-1`
- `--gp-shadow-2`
- `--gp-shadow-3`

## Template filters
Biblioteca: `gepub_design_system`
- `gp_currency`
- `gp_format_date`
- `gp_format_document`
- `gp_status_color`
- `gp_truncate`
- `gp_percentage`

## Template tags
Biblioteca: `gepub_design_system`
- `gp_button`
- `gp_card`
- `gp_alert`
- `gp_table`
- `gp_badge`
- `gp_progress`
- `gp_chart`
- `gp_form`
- `gp_modal`

## Documentação interativa
- `/core/sistema/design-system/`
- `/core/sistema/design-system/componentes/`
- `/core/sistema/design-system/temas/`
- `/core/sistema/design-system/tokens.json`

## Versionamento
- Atual: `GEPUB DS v2.0`
- Estrutura preparada para evolução:
  - `GEPUB DS v2.1`
  - `GEPUB DS v3.0`
