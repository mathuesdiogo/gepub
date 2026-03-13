# GEPUB - Demais Módulos (Serviços): Funções e Integrações

Gerado em: 01/03/2026

## Educação (`apps.educacao`)

Objetivo:
- Gestão escolar completa: turmas, alunos, diário, notas, horários, períodos, assistência, calendário, boletins e documentos do aluno.

Funções (rotas nomeadas):

### Painel e núcleo
- `index`: dashboard da educação.

### Turmas
- `turma_list`: listagem de turmas.
- `turma_create`: criação de turma.
- `turma_detail`: detalhe da turma.
- `turma_update`: edição de turma.

### Alunos e matrícula
- `aluno_list`: listagem de alunos.
- `aluno_create`: criação de aluno.
- `aluno_detail`: detalhe de aluno.
- `aluno_update`: edição de aluno.
- `historico_aluno`: histórico escolar do aluno.
- `matricula_create`: criação de matrícula.

### Documentos do aluno
- `carteira_emitir_pdf`: emissão de carteira estudantil em PDF.
- `declaracao_vinculo_pdf`: emissão de declaração de vínculo em PDF.
- `carteira_verificar_lookup`: consulta de validação da carteira.
- `carteira_verificar_public`: validação pública da carteira por código.

### Portal educacional
- `portal_professor`: visão portal para professor.
- `portal_aluno`: visão portal para aluno.

### Assistência escolar
- `assistencia_index`: painel de assistência.
- `assist_cardapio_list`, `assist_cardapio_create`, `assist_cardapio_detail`, `assist_cardapio_update`
- `assist_refeicao_list`, `assist_refeicao_create`, `assist_refeicao_detail`, `assist_refeicao_update`
- `assist_rota_list`, `assist_rota_create`, `assist_rota_detail`, `assist_rota_update`
- `assist_transporte_registro_list`, `assist_transporte_registro_create`, `assist_transporte_registro_detail`, `assist_transporte_registro_update`

### APIs de apoio
- `api_alunos_suggest`
- `api_turmas_suggest`
- `api_alunos_turma_suggest`

### Calendário e relatórios gerenciais
- `calendario_index`
- `calendario_evento_create`
- `calendario_evento_update`
- `calendario_evento_delete`
- `relatorio_mensal`
- `indicadores_gerenciais`
- `censo_escolar`

### Diário e frequência
- `meus_diarios`
- `diario_detail`
- `aula_create`
- `aula_update`
- `aula_frequencia`

### Avaliação e notas no diário
- `avaliacao_list`
- `avaliacao_create`
- `notas_lancar`

### Horários
- `horarios_index`
- `horario_turma`
- `horario_aula_create`
- `horario_aula_update`
- `horario_gerar_padrao`
- `horario_duplicar_select`
- `horario_duplicar`
- `horario_limpar`

### Períodos letivos
- `periodo_list`
- `periodo_create`
- `periodo_update`
- `periodo_gerar_bimestres`

### Componentes e catálogos
- `componente_list`, `componente_create`, `componente_detail`, `componente_update`
- `curso_list`, `curso_create`, `curso_update`
- `coordenacao_list`, `coordenacao_create`, `coordenacao_update`

### Boletins e fechamento
- `boletim_turma`
- `boletim_aluno`
- `boletim_turma_periodo`
- `relatorio_geral_turma`
- `fechamento_turma_periodo`

Integrações com outros módulos:
- `nee`: necessidades/apoios vinculados ao aluno.
- `billing`: validação de limites de capacidade (alunos/uso).
- `org`: escopo de unidade/secretaria.
- `core`: exports PDF/CSV e controle RBAC.

Como funciona:
- Base cadastral de alunos/turmas alimenta diário, notas, boletins e documentos oficiais.
- Fechamento por período consolida desempenho e histórico.

---

## Avaliações (`apps.avaliacoes`)

Objetivo:
- Gerar avaliações, gabaritos, correção por folha/token e resultados.

Funções (rotas nomeadas):
- `avaliacao_list`: lista de avaliações.
- `index`: dashboard do módulo.
- `avaliacao_create`: cria avaliação.
- `avaliacao_detail`: detalhe da avaliação.
- `avaliacao_sync`: sincroniza avaliação.
- `questao_create`: cria questão.
- `questao_update`: edita questão.
- `gabarito_update`: atualiza gabarito por versão.
- `resultados`: tela de resultados.
- `resultados_csv`: exporta resultados CSV.
- `prova_pdf`: gera provas em PDF.
- `folha_lookup`: localiza folha por token.
- `folha_corrigir`: corrige folha por token.
- `folha_validar`: valida prova por token público.

Integrações com outros módulos:
- `educacao`: vínculo com turmas/alunos/notas.
- `core`: exportações e permissões.

Como funciona:
- Avaliação é criada com questões/gabarito, gera prova, recebe correções e publica resultados.

---

## NEE (`apps.nee`)

Objetivo:
- Gestão de necessidades educacionais especiais com plano, laudos, recursos, apoios e acompanhamentos.

Funções (rotas nomeadas):

### Entrada e busca
- `index`
- `buscar_aluno`
- `buscar_aluno_autocomplete`
- `aluno_search`

### Alertas e relatórios
- `alertas_index`
- `alertas_lista`
- `relatorios_index`
- `relatorios_por_tipo`
- `relatorios_por_municipio`
- `relatorios_por_unidade`
- `relatorios_alunos`

### Tipos NEE
- `tipo_list`
- `tipo_create`
- `tipo_detail`
- `tipo_update`

### Hub do aluno NEE
- `aluno_hub`
- `aluno_relatorio_clinico_pdf`
- `aluno_plano_clinico`
- `aluno_objetivos`
- `aluno_necessidades`
- `aluno_laudos`
- `aluno_recursos`
- `aluno_apoios`
- `aluno_acompanhamentos`
- `aluno_timeline`

### Objetivos/evoluções
- `objetivo_create`
- `objetivo_detail`
- `objetivo_update`
- `evolucao_create`

### Necessidades
- `necessidade_create`
- `necessidade_detail`
- `necessidade_update`

### Laudos
- `laudo_create`
- `laudo_detail`
- `laudo_update`

### Recursos
- `recurso_create`
- `recurso_detail`
- `recurso_update`

### Acompanhamentos
- `acompanhamento_create`
- `acompanhamento_detail`
- `acompanhamento_update`

### Apoios
- `apoio_create`
- `apoio_detail`
- `apoio_update`

Integrações com outros módulos:
- `educacao`: base de aluno/matrícula e acompanhamento pedagógico.
- `saude`: formulários com profissionais de saúde e contexto clínico autorizado.
- `core`: exports e RBAC por escopo.

Como funciona:
- Caso NEE é gerido por aluno, com histórico técnico e trilha por atribuição/equipe.

---

## Saúde (`apps.saude`)

Objetivo:
- Operação clínica municipal: unidades, profissionais, agenda/regulação, atendimentos, prontuário, documentos e complementos assistenciais.

Funções (rotas nomeadas):

### Painel e estrutura
- `index`
- `unidade_list`, `unidade_create`, `unidade_detail`, `unidade_update`
- `profissional_list`, `profissional_create`, `profissional_detail`, `profissional_update`
- `especialidade_list`, `especialidade_create`, `especialidade_detail`, `especialidade_update`

### Agenda e regulação
- `agenda_list`, `agenda_create`, `agenda_detail`, `agenda_update`
- `grade_list`, `grade_create`, `grade_detail`, `grade_update`
- `bloqueio_list`, `bloqueio_create`, `bloqueio_detail`, `bloqueio_update`
- `fila_list`, `fila_create`, `fila_detail`, `fila_update`

### Atendimento e prontuário
- `atendimento_list`, `atendimento_create`, `atendimento_detail`, `atendimento_update`
- `prontuario_hub`
- `documento_list`, `documento_create`, `documento_detail`
- `auditoria_prontuario_list`

### Expansão assistencial
- `procedimento_list`, `procedimento_create`, `procedimento_detail`, `procedimento_update`
- `vacinacao_list`, `vacinacao_create`, `vacinacao_detail`, `vacinacao_update`
- `encaminhamento_list`, `encaminhamento_create`, `encaminhamento_detail`, `encaminhamento_update`

### Cadastros complementares e fluxos
- `cid_list`, `cid_create`, `cid_detail`, `cid_update`
- `programa_list`, `programa_create`, `programa_detail`, `programa_update`
- `paciente_list`, `paciente_create`, `paciente_detail`, `paciente_update`
- `checkin_list`, `checkin_create`, `checkin_detail`, `checkin_update`
- `medicamento_uso_list`, `medicamento_uso_create`, `medicamento_uso_detail`, `medicamento_uso_update`
- `dispensacao_list`, `dispensacao_create`, `dispensacao_detail`, `dispensacao_update`
- `exame_coleta_list`, `exame_coleta_create`, `exame_coleta_detail`, `exame_coleta_update`
- `internacao_list`, `internacao_create`, `internacao_detail`, `internacao_update`

### APIs e relatórios
- `api_profissionais_por_unidade`
- `api_alunos_suggest`
- `api_pacientes_suggest`
- `api_atendimentos_suggest`
- `api_agendamentos_suggest`
- `api_profissionais_suggest`
- `api_unidades_suggest`
- `relatorio_mensal`

Integrações com outros módulos:
- `educacao`: sugestão de alunos/integração de contexto (quando aplicável).
- `nee`: troca de contexto técnico por atribuição/privacidade.
- `org`: escopo de unidades/setores.
- `core`: exportação, auditoria e permissões.

Como funciona:
- Paciente entra por cadastro/check-in/agenda.
- Atendimento alimenta prontuário e documentos.
- Regulação organiza fila, grade e bloqueios.

---

## Backlog de Evolução (Padrão ERP Público)

Diretriz transversal aplicada a todas as funções deste documento:
- Busca avançada + filtros salvos + ações rápidas por status.
- Timeline auditável por registro e anexos tipificados.
- Eventos disparáveis para comunicação automática.
- Exportação estruturada e consumo por BI.
- Georreferenciamento quando houver componente territorial.

## Educação (`apps.educacao`) - evolução por função

Painel e núcleo:
- `index` - Aprimorar:
- KPIs de turmas ativas, faltas altas, pendências de fechamento, turmas sem horário e alertas NEE.
- Central de pendências por perfil (direção, coordenação, professor, secretaria).

Turmas:
- `turma_list` - Aprimorar:
- Filtros por ano letivo, unidade, turno, série e status; visões salvas.
- `turma_create` - Aprimorar:
- Assistente de criação (curso/série/turno/componentes/professores/períodos/capacidade).
- Validação de conflito de horário e capacidade.
- `turma_detail` - Adicionar:
- Abas integradas para Diário, Avaliações e NEE.
- `turma_update` - Adicionar:
- Controle de mudança de professor/horário com evento e auditoria.

Alunos e matrícula:
- `aluno_list` - Aprimorar:
- Busca por nome, CPF, matrícula, NIS; filtros NEE/transporte/alimentação/risco.
- `aluno_create` - Adicionar:
- Cadastro rápido e completo com validação de duplicidade.
- `aluno_detail` - Adicionar:
- Hub único com matrícula, frequência, notas, NEE, documentos e saúde por permissão.
- `aluno_update` - Aprimorar:
- Auditoria detalhada para alteração de dados sensíveis.
- `historico_aluno` - Adicionar:
- Timeline escolar consolidada.
- `matricula_create` - Aprimorar:
- Regras de vaga/série/período/documentação e fluxo de transferência.

Documentos do aluno:
- `carteira_emitir_pdf` - Aprimorar:
- QR code, hash e validação pública robusta.
- `declaracao_vinculo_pdf` - Adicionar:
- Modelos por finalidade (transporte, benefício, estágio e outros).
- `carteira_verificar_lookup`, `carteira_verificar_public` - Aprimorar:
- Página pública com status (válida, expirada, cancelada), rate limit e antifraude.

Portal educacional:
- `portal_professor` - Adicionar:
- Visão Meu Dia (aulas, chamadas pendentes, avaliações e alertas NEE).
- `portal_aluno` - Adicionar:
- Boletim, frequência, documentos, avisos e calendário.

Assistência escolar:
- `assistencia_index` - Aprimorar:
- KPIs de refeições, transporte e cobertura.
- `assist_cardapio_*`, `assist_refeicao_*` - Adicionar:
- Controle nutricional básico com sinalização de restrições.
- `assist_rota_*`, `assist_transporte_registro_*` - Aprimorar:
- Rotas georreferenciadas, paradas, alunos por parada e ocorrências.

APIs de apoio:
- `api_alunos_suggest`, `api_turmas_suggest`, `api_alunos_turma_suggest` - Aprimorar:
- Cache, paginação e payload padronizado (`id`, `label`, `meta`).

Calendário e relatórios:
- `calendario_*` - Adicionar:
- Tipos de evento e permissão por unidade.
- `relatorio_mensal`, `indicadores_gerenciais`, `censo_escolar` - Aprimorar:
- Exportação PDF/CSV e validação de qualidade de dado antes do fechamento.

Diário e frequência:
- `meus_diarios`, `diario_detail`, `aula_create`, `aula_update`, `aula_frequencia` - Aprimorar:
- Lançamento mobile-first, travas por período, justificativa com anexo.

Avaliação e notas:
- `avaliacao_list`, `avaliacao_create`, `notas_lancar` - Aprimorar:
- Peso por avaliação, recuperação, média automática e regras por período.

Horários:
- `horarios_index`, `horario_*` - Aprimorar:
- Detecção de conflito (professor/turma/sala), geração padrão e duplicação anual.

Períodos:
- `periodo_*` - Aprimorar:
- Calendário integrado, bimestre/trimestre e travas de fechamento.

Componentes e catálogos:
- `componente_*`, `curso_*`, `coordenacao_*` - Aprimorar:
- Versionamento de matriz curricular por ano e importação/exportação.

Boletins e fechamento:
- `boletim_*`, `relatorio_geral_turma`, `fechamento_turma_periodo` - Aprimorar:
- Checklist de fechamento e PDF oficial com assinatura quando habilitado.

## Avaliações (`apps.avaliacoes`) - evolução por função

- `index` - Adicionar:
- KPIs de aplicação, correção e desempenho por turma/unidade.
- `avaliacao_list` - Aprimorar:
- Filtros por unidade, turma, componente, período e status.
- `avaliacao_create` - Adicionar:
- Modelos (diagnóstica/externa) e banco de questões por habilidade.
- `avaliacao_detail` - Adicionar:
- Versões de prova e parametrização por versão.
- `avaliacao_sync` - Aprimorar:
- Log claro do que sincronizou com Educação.
- `questao_create`, `questao_update` - Adicionar:
- Tipos objetivos/dissertativos e anexos por questão.
- `gabarito_update` - Aprimorar:
- Trava após publicação e auditoria por versão.
- `resultados`, `resultados_csv` - Adicionar:
- Relatórios por habilidade, descritor e evolução temporal.
- `prova_pdf` - Aprimorar:
- Layout com identificação, QR e token por aluno/turma.
- `folha_lookup`, `folha_corrigir`, `folha_validar` - Aprimorar:
- Controles antifraude (expiração de token e limite de tentativas).

## NEE (`apps.nee`) - evolução por função

Entrada e busca:
- `index`, `buscar_aluno`, `buscar_aluno_autocomplete`, `aluno_search` - Aprimorar:
- Filtros por tipo NEE, unidade, status do plano e alertas.
- Escopo por perfil (professor x equipe NEE x gestão).

Alertas e relatórios:
- `alertas_*`, `relatorios_*` - Adicionar:
- SLA de acompanhamento e alertas de documentos vencendo.
- Relatório de capacidade por profissional/mediador.

Tipos:
- `tipo_*` - Adicionar:
- Campos de suporte técnico e recomendações padrão.

Hub NEE:
- `aluno_hub`, `aluno_relatorio_clinico_pdf`, `aluno_plano_clinico`, `aluno_objetivos`, `aluno_necessidades`, `aluno_laudos`, `aluno_recursos`, `aluno_apoios`, `aluno_acompanhamentos`, `aluno_timeline` - Aprimorar:
- Modelo de caso com timeline única, checklist de plano e evidências.
- Separação de plano pedagógico e plano clínico por privacidade.

Objetivos e evoluções:
- `objetivo_*`, `evolucao_create` - Aprimorar:
- Metas SMART com escala de progresso e alertas de estagnação.

Demais cadastros do caso:
- `necessidade_*`, `laudo_*`, `recurso_*`, `acompanhamento_*`, `apoio_*` - Adicionar:
- Catálogo de recursos, prioridade, custo estimado e gatilho de comunicação.

## Saúde (`apps.saude`) - evolução por função

Estrutura:
- `index`, `unidade_*`, `profissional_*`, `especialidade_*` - Aprimorar:
- Unidade georreferenciada (reuso ORG/Maps) e vínculo profissional com carga horária.

Agenda e regulação:
- `agenda_*`, `grade_*`, `bloqueio_*`, `fila_*` - Adicionar:
- Regras de prioridade, SLA de fila, alertas e remarcação automatizada.

Atendimento e prontuário:
- `atendimento_*`, `prontuario_hub`, `documento_*`, `auditoria_prontuario_list` - Aprimorar:
- Trilha completa de acesso/alteração e modelos clínicos padronizados.
- Consentimento para compartilhamento com Educação/NEE por atribuição.

Expansão assistencial:
- `procedimento_*`, `vacinacao_*`, `encaminhamento_*` - Aprimorar:
- Vínculo de estoque/lote, status de encaminhamento e fila assistencial.

Cadastros e fluxos:
- `cid_*`, `programa_*`, `paciente_*`, `checkin_*`, `medicamento_uso_*`, `dispensacao_*`, `exame_coleta_*`, `internacao_*` - Adicionar:
- Protocolos de dispensação, alertas de ruptura e gestão de leitos/internação.

APIs e relatórios:
- `api_*`, `relatorio_mensal` - Aprimorar:
- Indicadores de fila média, absenteísmo, produção por unidade e dataset pronto para BI.
