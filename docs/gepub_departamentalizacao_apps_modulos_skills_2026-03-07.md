# GEPUB - Departamentalizacao de Apps, Modulos e Skills

Data: 07/03/2026

## 1. Objetivo
Organizar o ecossistema GEPUB por dominio, app e modulo para acelerar implementacao com previsibilidade.

## 2. Dominios oficiais
- Plataforma e Governanca: accounts, core, org, billing.
- Servicos Finalisticos: educacao, avaliacoes, nee, saude.
- Operacao Administrativa: financeiro, processos, compras, contratos, rh, ponto, folha, patrimonio, almoxarifado, frota, ouvidoria, tributos.
- Ferramentas e Inteligencia: integracoes, comunicacao, paineis, conversor.
- Legislativo: camara.

## 3. Ordem de implementacao direcionada
1. Plataforma e Governanca.
2. Portais Publicos (prefeitura, camara, transparencia) e experiencia de edicao.
3. Servicos Finalisticos.
4. Operacao Administrativa.
5. Ferramentas e Integracoes.
6. Otimizacoes transversais (seguranca, dados, performance/cache, observabilidade, release).

## 4. Mapa por plano comercial
- GEPUB Essencial: gestao interna da prefeitura.
- GEPUB Gestao Integrada: gestao interna + portal da prefeitura.
- GEPUB Transformacao Digital: gestao interna + portal prefeitura + transparencia.
- GEPUB Governo Completo: gestao interna + portal prefeitura + transparencia + camara.

## 5. Governanca de responsaveis
Use o arquivo docs/gepub_owners_catalogo_2026-03-07.csv para definir:
- owner de produto (responsavel funcional)
- owner tecnico (responsavel de implementacao)
- status de prontidao por app/skill

## 6. Skills criadas neste ciclo

### 6.1 Skills por app
- gepub-app-accounts
- gepub-app-almoxarifado
- gepub-app-avaliacoes
- gepub-app-billing
- gepub-app-camara
- gepub-app-compras
- gepub-app-comunicacao
- gepub-app-contratos
- gepub-app-conversor
- gepub-app-core
- gepub-app-educacao
- gepub-app-financeiro
- gepub-app-folha
- gepub-app-frota
- gepub-app-integracoes
- gepub-app-nee
- gepub-app-org
- gepub-app-ouvidoria
- gepub-app-paineis
- gepub-app-patrimonio
- gepub-app-ponto
- gepub-app-processos
- gepub-app-rh
- gepub-app-saude
- gepub-app-tributos

### 6.2 Skills transversais
- gepub-auto-orchestrator
- gepub-system-design
- gepub-system-architecture
- gepub-ai-architect
- gepub-permission-system
- gepub-module-generator
- gepub-database-pattern
- gepub-layout-design-patterns
- gepub-ui-system
- gepub-api-pattern
- gepub-security-hardening
- gepub-audit-system
- gepub-data-governance
- gepub-performance-cache
- gepub-performance-rules
- gepub-testing-quality
- gepub-release-migrations
- gepub-integrations-observability
- gepub-educacao-content-ingestion
- gepub-document-system
- gepub-report-system
- gepub-notification-system
- gepub-workflow-system
- gepub-municipal-portal

### 6.3 Aliases por dominio (conveniencia)
- gepub-education-module (alias do app `gepub-app-educacao`)
- gepub-health-module (alias do app `gepub-app-saude`)

## 7. Padrão operacional para novas features
1. Acionar o modo automatico via gepub-auto-orchestrator (padrao).
2. Confirmar app principal identificado.
3. Permitir que o orquestrador anexe skills transversais por risco.
4. Executar implementacao incremental com checklist da skill.
5. Registrar decisao tecnica em docs/ quando houver impacto cross-app.

## 8. Curadoria de conteudo para Educacao
A skill gepub-educacao-content-ingestion foi criada para tratar videos, PDFs e paginas:
- preencher skills/gepub-educacao-content-ingestion/references/fontes_educacao_template.csv
- rodar skills/gepub-educacao-content-ingestion/scripts/build_catalog.py
- usar o catalogo gerado para transformar fontes em backlog tecnico

## 9. Guia de operacao
- Uso pratico das skills e comandos:
  - docs/gepub_skills_operacao_2026-03-07.md
- Intake universal de materiais por app:
  - scripts/gepub_materials.py
