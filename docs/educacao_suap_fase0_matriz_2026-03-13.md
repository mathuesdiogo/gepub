# GEPUB Educação — Fase 0 (Matriz SUAP → GEPUB)

Data de referência: **13/03/2026**

## Objetivo
Consolidar o mapeamento funcional do material de referência SUAP para telas/fluxos do GEPUB, com status de implantação e regra operacional.

Legenda de status:
- **JA_EXISTE**: funcional e acessível no produto.
- **PARCIAL**: existe, mas ainda demanda ajustes de regra/UX/processo.
- **NOVO**: entregue nesta rodada.

---

## Matriz por tema

| Tema SUAP | Tela/Fluxo GEPUB | Status | Regra operacional consolidada |
|---|---|---|---|
| Procedimentos de matrícula (cancelar, trancar, transferir, desfazer) | Aluno detalhado + serviços de movimentação | JA_EXISTE | Toda alteração gera `MatriculaMovimentacao` com trilha completa e suporte a desfazer seguro. |
| Histórico unificado de procedimentos | Timeline de movimentações da matrícula | JA_EXISTE | Ações de criação/remanejamento/transferência/trancamento/cancelamento ficam auditáveis. |
| Renovação por chamadas | Renovação de matrícula (lista/detalhe) | NOVO | Processamento por prioridade de chamada (`<=1`, `<=2`, `<=3`) mantendo pendências fora do corte. |
| Matrícula de ingressantes por processo seletivo | Cadastro de aluno com matrícula inicial | NOVO | Origem `PROCESSO_SELETIVO` exige número/assunto de processo; cria processo administrativo e movimento de matrícula. |
| Gerar turmas e diários em lote | Wizard de turmas e diários | NOVO | Geração por matriz/ano/período com setup automático de fluxo anual. |
| Manutenção/remanejamento com trilha | Gestão de turma/matrícula + movimentações | JA_EXISTE | Mudança de turma preserva vínculo acadêmico e registra origem/destino. |
| Fechamento/reabertura de período letivo em lote | `periodos/fechamento-lote/` | NOVO | Fechamento por secretaria/unidade com prévia; reabertura remove fechamento por escopo. |
| Evasão em lote com rollback | `matriculas/evasao-lote/` | NOVO | Execução em massa com token de rollback para reversão segura. |
| Justificativa de faltas centralizada | `diario/justificativas/` | NOVO | Fila centralizada por perfil com mensagens orientativas e acesso direto no dashboard. |
| Certificado/validação pública | Certificados + validação pública de documentos | PARCIAL | Emissão e código já existem; integração de fluxo completo por contexto ainda evolutiva. |
| Carômetro e etiquetas em lote | `alunos/operacoes-lote/` | NOVO | Geração PDF por turma para operação escolar e conferência de sala. |
| Atualização de fotos em lote | `alunos/operacoes-lote/` | NOVO | Import ZIP por ID/CPF; valida extensão e aplica foto no cadastro do aluno. |
| Minicursos (cadastro) | `minicursos/cadastro/` | NOVO | Cadastro em modalidade FIC/Livre para trilhas complementares. |
| Minicursos (turmas) | `minicursos/turmas/nova/` | NOVO | Turma em modalidade complementar, sem matriz curricular principal. |
| Minicursos (matrículas) | `minicursos/matriculas/nova/` | NOVO | Matrícula de aluno em curso/turma complementar com prevenção de duplicidade ativa. |
| Minicursos (certificados) | `minicursos/certificados/emitir/` | NOVO | Emissão de `AlunoCertificado` tipo curso com código de validação. |

---

## Entregas por fase do plano

### Fase 1 — Procedimentos de matrícula
- Consolidada com trilha de movimentação e regras de desfazer.

### Fase 2 — Turmas e diários avançado
- Wizard de geração em lote e manutenção com trilha operacional.

### Fase 3 — Procedimentos de apoio
- Fechamento/reabertura em lote.
- Renovação por chamadas.
- Evasão em lote com rollback.
- Justificativas centralizadas.

### Fase 4 — Documentos e conclusão
- Carômetro e etiquetas em lote.
- Atualização de fotos em lote.
- Certificação/validação pública: base existente, evolução contínua.

### Fase 5 — Minicursos
- Cadastro, turmas, matrículas e certificados implantados.

---

## Decisões de regra fechadas
- Renovação processa por prioridade de chamada sem perder pedidos pendentes.
- Ingresso por processo seletivo precisa de metadados mínimos do processo.
- Fechamento em lote respeita escopo secretaria/unidade e permite reabertura limpa.
- Evasão em lote exige rastreabilidade e rollback por token.
- Operações em lote de foto aceitam somente imagens válidas em ZIP.

