# Backlog Técnico — Portal da Transparência (GEPUB)

Atualizado em: 2026-02-26

## Objetivo
Elevar o portal público municipal para um padrão de transparência com:
- dados estruturados dos módulos internos,
- publicação manual assistida para lacunas operacionais,
- cobertura visível por módulo (com alerta de vazio),
- rastreabilidade de atualização.

## Prioridades

### P0 — Qualidade mínima de publicação
- [x] Criar cadastro de `Arquivos de Transparência` por município e categoria.
- [x] Expor CRUD no painel `Portais Públicos`.
- [x] Exibir arquivos publicados no portal público de transparência.
- [x] Exibir painel de cobertura por módulo (`ok`, `baixo`, `sem dados`).
- [x] Aplicar migração e validar integridade (`check` + testes do app core).

### P1 — Cobertura dos módulos críticos
- [x] Licitações: indicadores de total/em curso/homologado.
- [x] Contratos: indicadores de total/ativos/valor total.
- [x] Saúde: bloco de publicações de medicamentos.
- [x] Educação: bloco de listagens públicas (matrícula/creche/alunos).
- [ ] Obras públicas: entidade estruturada (status físico/financeiro, medição, prazo).
- [ ] Obras paralisadas: entidade estruturada + motivo/paralisação/previsão.
- [ ] Diárias: tabela estruturada por cargo/faixa/valor.
- [ ] Dados abertos: catálogo com endpoint e dicionário de dados.

### P2 — Governança e compliance
- [ ] Regra de publicação automática com revisão opcional por módulo.
- [ ] SLA de atualização por categoria (alerta de dado vencido).
- [ ] Trilhas de auditoria de publicação (quem publicou, quando, origem).
- [ ] Selo de qualidade por módulo (completude + atualização).

### P3 — Experiência do cidadão
- [ ] Busca unificada de transparência (evento + arquivo + diário + contrato).
- [ ] Filtros salvos e URLs compartilháveis por painel.
- [ ] Exportações consolidadas (CSV/PDF) por filtro.
- [ ] Página de metodologia de dados (fonte, periodicidade e limitações).

## Mapeamento de categorias manuais (implementado)
- `OBRAS_PUBLICAS`
- `OBRAS_PARALISADAS`
- `MEDICAMENTOS`
- `EDUCACAO_MATRICULAS`
- `EDUCACAO_ESPERA_CRECHE`
- `EDUCACAO_LISTA_ALUNOS`
- `DIARIAS_TABELA_VALORES`
- `DADOS_ABERTOS`
- `PRESTACAO_CONTAS`
- `OUTROS`

## Locais de acesso (admin)
- `Core > Portais Públicos`: hub de publicações.
- `Arquivos de Transparência`: criar/editar/remover publicação por categoria.

## Locais de acesso (público)
- `/transparencia/`: painel geral de eventos + arquivos + cobertura.
- `/saude-publica/`: unidades, indicadores e publicações de medicamentos.
- `/educacao-publica/`: unidades, indicadores e listagens públicas.
