# GEPUB - Operacao de Skills (Guia Pratico)

Data: 07/03/2026

## 1. Como usar as skills no dia a dia

## Regra simples
- Modo padrao: selecao automatica via `gepub-auto-orchestrator`.
- Voce nao precisa informar skills manualmente; basta descrever a demanda e o app/contexto (ex.: \"vamos colocar isso em educacao\").
- O orquestrador seleciona skill principal + skills transversais necessarias.

## Modo automatico (padrao)
1. Identificar app principal.
2. Acoplar `gepub-app-<app>`.
3. Adicionar skills transversais por risco.
4. Executar implementacao com validacao.

## Combos recomendados
- Feature nova em app: `gepub-app-<app>` + `gepub-data-governance` + `gepub-testing-quality`
- Refatoracao de tela/menu/portal: `gepub-app-core` + `gepub-layout-design-patterns`
- Mudanca sensivel (acesso/dados): `gepub-security-hardening` + skill do app
- Lentidao/performance: `gepub-performance-cache` + skill do app
- Integracao externa: `gepub-integrations-observability` + skill do app

## 2. Como adicionar materiais de estudo em qualquer app

## Estrutura usada
- Por app, em `skills/gepub-app-<app>/references/`:
  - `fontes_estudo.csv`
  - `fontes_estudo_bulk_template.csv`
  - `conhecimento_catalogo.md`
  - `conhecimento_backlog.md`
- Script universal:
  - `scripts/gepub_materials.py`

## Fluxo rapido (recomendado)
1. Adicionar materiais (um a um ou em lote) no app alvo.
2. O sistema verifica automaticamente se ja existe material equivalente:
   - se existir, atualiza/completa e padroniza (sem duplicar)
   - se nao existir, cria novo registro
3. Gerar catalogo e backlog do app.
4. Priorizar backlog e iniciar implementacao no app alvo.

## Comandos prontos

### Inicializar estrutura para todos os apps (uma vez)
```bash
python3 scripts/gepub_materials.py init --all
```

### Adicionar 1 material (ex.: educacao)
```bash
python3 scripts/gepub_materials.py add \
  --app educacao \
  --source "https://www.youtube.com/watch?v=abc123" \
  --titulo "Aula sobre Diario Escolar" \
  --tema "diario de classe" \
  --prioridade alta \
  --owner "time-educacao"
```

Obs.: `--titulo` e `--objetivo` sao opcionais; se omitidos, o script infere titulo e define objetivo padrao.

### Adicionar arquivo fisico (PDF, DOC, etc.)
```bash
python3 scripts/gepub_materials.py add-file \
  --app camara \
  --file "/caminho/local/ata-sessao.pdf" \
  --tema "sessoes" \
  --owner "time-camara"
```

O arquivo e copiado para `skills/gepub-app-<app>/assets/materiais/` e registrado com hash para evitar duplicidade.

### Adicionar varios links de uma vez
```bash
python3 scripts/gepub_materials.py add-links \
  --app financeiro \
  --tema "arrecadacao" \
  --links "https://link-1" "https://link-2" "https://link-3"
```

### Importar em lote via CSV
```bash
python3 scripts/gepub_materials.py bulk \
  --app saude \
  --input skills/gepub-app-saude/references/fontes_estudo_bulk_template.csv
```

### Gerar catalogo + backlog de um app
```bash
python3 scripts/gepub_materials.py build --app camara
```

### Gerar catalogo + backlog de todos os apps
```bash
python3 scripts/gepub_materials.py build --all
```

### Auditar e aprimorar o que ja existe (padrao/completude/dedup)
```bash
python3 scripts/gepub_materials.py audit --all
```

## 3. Validacao basica
- Validar skills: quick_validate.py em cada pasta de skill.
- Validar app Django: `python manage.py check`.

## 4. Governanca
- Departamentalizacao oficial: `docs/gepub_departamentalizacao_apps_modulos_skills_2026-03-07.md`
- Owners e responsaveis: `docs/gepub_owners_catalogo_2026-03-07.csv`
