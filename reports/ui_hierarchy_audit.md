# Auditoria de Hierarquia UI

Critérios auditados por app:
- quantidade de templates HTML
- cobertura de `module_content`, `page_head`, `table_shell`, `form-shell`
- ocorrências de classes de espaçamento legadas (`mt-*`, `mb-*`, `pt-*`, `pb-*`, etc.)
- ocorrências de `style="...margin/padding..."`

| App | HTML | Module | Page Head | Table Shell | Form Shell | Legacy Spacing | Inline Style Spacing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `404.html` | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `500.html` | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `accounts` | 10 | 1 | 6 | 1 | 7 | 0 | 0 |
| `almoxarifado` | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| `avaliacoes` | 8 | 0 | 6 | 0 | 3 | 0 | 0 |
| `billing` | 7 | 0 | 7 | 0 | 6 | 0 | 0 |
| `camara` | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| `compras` | 3 | 0 | 2 | 0 | 1 | 0 | 0 |
| `comunicacao` | 1 | 0 | 1 | 0 | 1 | 0 | 0 |
| `contratos` | 2 | 0 | 1 | 0 | 0 | 0 | 0 |
| `conversor` | 1 | 0 | 1 | 0 | 1 | 0 | 0 |
| `core` | 89 | 0 | 12 | 2 | 14 | 0 | 0 |
| `educacao` | 153 | 139 | 138 | 53 | 72 | 0 | 0 |
| `financeiro` | 15 | 0 | 13 | 0 | 0 | 0 | 0 |
| `folha` | 4 | 0 | 4 | 0 | 0 | 0 | 0 |
| `frota` | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| `integracoes` | 1 | 0 | 1 | 0 | 1 | 0 | 0 |
| `nee` | 50 | 45 | 44 | 9 | 1 | 0 | 0 |
| `org` | 24 | 0 | 15 | 5 | 3 | 0 | 0 |
| `ouvidoria` | 4 | 0 | 4 | 0 | 0 | 0 | 0 |
| `paineis` | 5 | 0 | 4 | 0 | 3 | 0 | 0 |
| `patrimonio` | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| `ponto` | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| `processos` | 2 | 0 | 1 | 0 | 0 | 0 | 0 |
| `rh` | 10 | 0 | 10 | 0 | 2 | 0 | 0 |
| `saude` | 49 | 48 | 47 | 16 | 2 | 0 | 0 |
| `tributos` | 3 | 0 | 3 | 0 | 0 | 0 | 0 |

## Arquivos com mais classes de espaçamento legado
- Nenhum arquivo com classes legadas de espaçamento detectado.

## Arquivos com style inline de margin/padding
- Nenhum style inline de espaçamento detectado.
