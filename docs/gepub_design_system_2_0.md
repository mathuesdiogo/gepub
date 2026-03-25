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

## Padrões web
- Utilizar 4 espaços ao invés de tabs.
- Não utilizar atributo `style` inline em tags HTML.
- Não utilizar tags deprecadas no HTML5 (`center`, `font` etc.).
- Toda página deve possuir apenas uma `h1`; demais títulos devem seguir hierarquia `h2` -> `h3` -> `h4`...

## Botões e ações

### Botões (padrões)
- `btn success`: ações principais de confirmação/fluxo.
- `btn primary`: ações de edição/alteração.
- `btn`: ações secundárias (imprimir/exportar/relatórios).
- `btn default`: visualização/informação neutra.
- `btn danger`: remoção.
- `btn warning`: ação de cautela.

### Equivalentes no DS atual
- `gp-button gp-button--success`
- `gp-button gp-button--primary`
- `gp-button` (base)
- `gp-button gp-button--default`
- `gp-button gp-button--danger`
- `gp-button gp-button--warning`

### Comportamentos de botão
- `disable_on_click` com `data-href`: desabilita no clique e redireciona.
- `disabled`: exibe indisponível.
- `popup`: abre destino em popup.
- `confirm` com `data-confirm`: exige confirmação.
- Botão com ícone: usar `icone` e manter texto (ou `span.visually-hidden` em ícone-only).

### Barra de ações
- Estrutura padrão:
  - `ul.action-bar > li > a.btn`
- Dropdown em ação:
  - `li.child > ul.child > li > a`

### Ícones de ação
- Preferir template tag:
  - `{% icon "view" "url" "title" "extra_class" "confirm" %}`
  - `{% icon "edit" "url" "title" "extra_class" "confirm" %}`
  - `{% icon "delete" "url" "title" "extra_class" "confirm" %}`

## Formulários

### Regra principal
- Utilizar preferencialmente `{% render_form form %}` para render padrão de campos.

### Avaliação com estrelas
- Estrutura:
  - `ul.stars > li > a > span.fa-star`
- Estado inativo:
  - classe `disabled` no ícone da estrela.

### Barra de busca e filtros
- Estrutura:
  - `.search-and-filters` (container)
  - `.filter` (cada campo)
- Variações:
  - `.large-filters` (aumenta todos os filtros)
  - `.large` (aumenta filtro específico)
  - `.separator` (separador visual)
  - `.show-condition-or` (insere "ou" entre filtros)

### Switch
- Estrutura:
  - `label.switch > input[type=checkbox] + span.slider`

### Marcar todos
- Estrutura:
  - `.markall-container` com checkbox mestre.
- Comportamento:
  - usar `data-markall-target` para selecionar checkboxes-alvo.

## Tabelas e listas

### Tabelas
- Estrutura base:
  - `.table-responsive > table`
- Comentários de cabeçalho:
  - `.text.hint.bottom` + `aria-label`.
- Estados de linha:
  - `.highlight`, `.error`, `.extra`, `.disabled`, `.total`.
- Regra:
  - `tr.total` deve destacar totalização com negrito e alinhamento à direita.

### Lista de definições
- Estrutura:
  - `dl.definition-list > dt/dd`
- Variações:
  - `.inline`, `.compact`, `.large`, `.small-items`
  - itens com largura por classe: `.xs-cols-100`, `.sm-cols-50`, `.md-cols-50`, `.lg-cols-33`.

### Listas de links
- Ordenada com contador:
  - `ol.counter-container > li.counter-item`.
- Numerada com ícone:
  - `ol.numbered-list > li.list-item` + `{% icone "file-alt" %}`.

### Lista com botão de ação
- Estrutura:
  - `ul.action-list > li`.
- Uso preferencial:
  - ações contextualizadas em listagens/tabelas.

## Navegação

### Abas (formato padrão)
- Estrutura:
  - `ul.nav.nav-tabs` com `li > a`.
  - Ativo com `li.active` e/ou `a.is-active` + `aria-current="page"`.
- Contador por aba:
  - `span.tabs__badge` dentro do link.
- Variação:
  - Classe opcional `disabled` no container para exibir abas desabilitadas.

### Abas (formato dinâmico)
- Cada seção usa `div.tab-pane` com:
  - `data-title` (ou `data-title-tab`, obrigatório no modo dinâmico),
  - `data-tab` (slug opcional),
  - `data-counter` (contador opcional),
  - `data-checked` (`true|false`, indicador visual),
  - `data-hide-tab-on-counter-zero` (`true|false`).
- O JS oficial (`static/js/gepub-design-system.js`) gera automaticamente a barra de abas.

### Âncoras
- Estrutura:
  - `ul.ancoras` para índice interno da página.
- Variação:
  - `ul.ancoras.three-digits` para marcador 001, 002, 003...

### Pills
- Estrutura:
  - `ul.pills` com `li > a` para navegação compacta.
- Estado ativo:
  - `li.active` e/ou `a.is-active` + `aria-current="page"`.
- Compatibilidade:
  - `gp-pills` e `gp-pills__item` continuam suportados.

## Nomenclaturas
- Títulos e labels com primeira inicial maiúscula (exceto nomes próprios).
- Mensagens ao usuário devem ser pontuadas corretamente.
- Preferências:
  - `Adicionar` (evitar `Cadastrar`)
  - `Editar` (evitar `Atualizar`, `Alterar`)
  - `Remover` (evitar `Excluir`, `Apagar`, `Deletar`)
  - `Visualizar` (evitar `Ver`, `Abrir`)

## Template filters
Biblioteca: `gepub_design_system`
- `format` (novo padrão de formatação de data/usuário)
- `status` (novo padrão com `span` e classe por slug)
- `text_small` (novo padrão para metadados/comentário lateral)
- `gp_currency`
- `gp_format_date`
- `gp_format_document`
- `gp_status_color`
- `gp_truncate`
- `gp_percentage`

## Template tags
Biblioteca: `gepub_design_system`
- `icon` (ações de visualizar/editar/remover; aceita `title`, `extra_class`, `confirm`)
- `icone` (novo padrão para render de Font Awesome)
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
