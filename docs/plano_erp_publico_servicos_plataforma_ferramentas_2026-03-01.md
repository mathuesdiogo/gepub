# GEPUB - Plano ERP Público (Serviços, Plataforma e Ferramentas)

Atualizado em: 01/03/2026

## 1) Objetivo

Aplicar o padrão único de evolução (UX + governança + integração + checklist + automação) em todos os módulos:

- Serviços: `educacao`, `avaliacoes`, `nee`, `saude`
- Plataforma/Acesso/Site: `accounts`, `billing`, `core`
- Ferramentas: `integracoes`, `comunicacao`, `paineis`, `conversor`

## 2) Critérios obrigatórios (para toda função)

### 2.1 UX padrão

- Busca simples e avançada
- Filtros persistentes
- Ações rápidas por status
- Exportação CSV/PDF
- Timeline com auditoria
- Checklists de conformidade antes de transição de status

### 2.2 Governança padrão

- Trilha de auditoria (quem, quando, o que)
- Validação de escopo e permissão
- Regras de transição de status por perfil
- Publicação em transparência quando aplicável

### 2.3 Integração padrão

- Vínculos entre entidades (aluno/paciente/processo/unidade/servidor)
- Eventos de comunicação disparáveis por status
- Preparação para BI e integrações externas

## 3) Roadmap (ordem de implementação)

1. `accounts` + `core` (segurança, RBAC e experiência pública)
2. `org` + `processos` (espinha dorsal de escopo e tramitação)
3. `educacao` + `nee` + `saude` (núcleo de serviços)
4. `comunicacao` + `integracoes` (automação e conectividade)
5. `paineis` + `conversor` (camada executiva e apoio operacional)
6. Ajustes contínuos de Operação (compras/contratos/financeiro etc.)

## 4) Backlog função por função (execução)

## 4.1 Educação (`apps.educacao`)

- `index`: central de pendências por perfil, KPIs (evasão, faltas, fechamento, NEE)
- `turma_list`: filtros por ano/unidade/turno/série/status, visões salvas
- `turma_create`: assistente com validação de conflito e capacidade
- `turma_detail`: abas Diário/Avaliações/NEE com atalhos
- `turma_update`: trilha de mudança de professor/horário + evento
- `aluno_list`: busca por matrícula/CPF/NIS, filtros de risco
- `aluno_create`: modo rápido/completo + deduplicação
- `aluno_detail`: hub único do aluno (matrícula/frequência/notas/NEE/documentos)
- `aluno_update`: auditoria de campos sensíveis
- `historico_aluno`: timeline acadêmica consolidada
- `matricula_create`: validação de vaga/série/documentos + transferência assistida
- `carteira_emitir_pdf`: QR + hash de validação
- `declaracao_vinculo_pdf`: modelos por finalidade
- `carteira_verificar_lookup`, `carteira_verificar_public`: validação pública com rate limit e antifraude
- `portal_professor`: painel “Meu dia”
- `portal_aluno`: boletim, frequência, calendário, documentos
- `assistencia_index`: KPIs de alimentação/transporte
- `assist_cardapio_*`, `assist_refeicao_*`: controle nutricional e restrições
- `assist_rota_*`, `assist_transporte_registro_*`: rotas georreferenciadas e ocorrências
- `api_alunos_suggest`, `api_turmas_suggest`, `api_alunos_turma_suggest`: padronização, paginação e cache
- `calendario_*`: tipologia de eventos e escopo por unidade
- `relatorio_mensal`, `indicadores_gerenciais`, `censo_escolar`: exportação e validação de qualidade do dado
- `meus_diarios`, `diario_detail`, `aula_create/update`, `aula_frequencia`: lançamento rápido mobile e travas por período
- `avaliacao_list/create`, `notas_lancar`: pesos, recuperação e média automática
- `horarios_*`: detecção de conflito, duplicação de ano e alertas de vazio
- `periodo_*`: integração com calendário e travas
- `componente_*`, `curso_*`, `coordenacao_*`: import/export e versionamento curricular
- `boletim_*`, `relatorio_geral_turma`, `fechamento_turma_periodo`: checklist de fechamento + PDF oficial

## 4.2 Avaliações (`apps.avaliacoes`)

- `index`: KPIs de aplicação/correção/desempenho
- `avaliacao_list`: filtros de unidade/turma/componente/período/status
- `avaliacao_create`: modelos diagnósticos e banco de questões
- `avaliacao_detail`: versões A/B, parametrização por versão
- `avaliacao_sync`: logs de sincronização legíveis
- `questao_create/update`: tipos de questão + anexos
- `gabarito_update`: auditoria por versão e travas pós-publicação
- `resultados`, `resultados_csv`: relatórios por habilidade/descritor/evolução
- `prova_pdf`: QR/token por aluno/turma
- `folha_lookup`, `folha_corrigir`, `folha_validar`: controles antifraude

## 4.3 NEE (`apps.nee`)

- `index`, `buscar_aluno_autocomplete`, `aluno_search`: filtros avançados, perfis por sensibilidade
- `alertas_*`, `relatorios_*`: SLA de acompanhamento, vencimento de laudo e capacidade de atendimento
- `tipo_*`: nível de suporte e recomendações padrão
- `aluno_hub`, `aluno_plano_clinico`, `aluno_timeline` e demais subrotas: timeline única com próxima ação e checklist de plano
- `objetivo_*`, `evolucao_create`: metas SMART e alerta de estagnação
- `necessidade_*`, `laudo_*`, `recurso_*`, `acompanhamento_*`, `apoio_*`: catálogo estruturado com prioridade/custo e integrações de aviso

## 4.4 Saúde (`apps.saude`)

- `index`, `unidade_*`, `profissional_*`, `especialidade_*`: georreferenciamento da unidade e vínculo de agenda
- `agenda_*`, `grade_*`, `bloqueio_*`, `fila_*`: prioridade regulatória, SLA de fila, remarcação automática
- `atendimento_*`, `prontuario_hub`, `documento_*`, `auditoria_prontuario_list`: trilha completa de acesso/edição
- `procedimento_*`, `vacinacao_*`, `encaminhamento_*`: status fim-a-fim e integração de estoque quando aplicável
- `cid_*`, `programa_*`, `paciente_*`, `checkin_*`, `medicamento_uso_*`, `dispensacao_*`, `exame_coleta_*`, `internacao_*`: padronização de fluxo e indicadores
- `api_*`, `relatorio_mensal`: datasets executivos prontos para BI

## 4.5 Accounts (`apps.accounts`)

- `login`: MFA opcional + proteção de risco
- `logout`: trilha de saída
- `alterar_senha`: política de força/histórico/expiração
- `meu_perfil`: preferências de notificação
- `usuarios_list`, `usuario_create/detail/update`, `usuario_toggle_*`, `usuario_reset_*`, `users_autocomplete`: presets RBAC por função e auditoria administrativa total

## 4.6 Billing (`apps.billing`)

- `meu_plano`: medidores por módulo
- `solicitar_upgrade`: fluxo completo com estados e rastreabilidade
- `simulador`: add-ons (WhatsApp, GIS, BI avançado, integrações)
- `assinaturas_admin`, `assinatura_admin_detail`, `fatura_pdf`: histórico de mudanças e governança de concessões

## 4.7 Core (`apps.core`)

- `home`, `portal_*_public`, `documentacao_public`, `transparencia_public`, `institucional_public`: SEO, acessibilidade, performance, hash de publicação
- `dashboard`, `dashboard_aluno`, `aviso_create`, `arquivo_create`, `go_code*`, `guia_telas`: central global de pendências e ajuda contextual
- `institutional_*`: builder de seções com versionamento/preview
- `publicacoes_admin`, `publicacoes_theme_*`, `publicacoes_config_edit`, `noticia_*`, `banner_*`, `pagina_*`, `menu_*`, `home_bloco_*`, `transparencia_arquivo_*`, `diario_*`, `concurso_*`, `concurso_etapa_*`, `camara_materia_*`, `camara_sessao_*`: workflow editorial completo com auditoria

## 4.8 Integrações (`apps.integracoes`)

- `index`: monitor de saúde e sucesso por conector
- `conector_create`: catálogo por tipo e parâmetros de resiliência
- `execucao_create`: rastreio técnico completo + reprocessamento
- Camada PNCP: fila dedicada, validação, reenvio e logs

## 4.9 Comunicação (`apps.comunicacao`)

- `index`: KPIs operacionais por canal
- `processar_fila`: rate limit, retry, backoff, dead-letter
- `notifications_send`: campanhas segmentadas
- `notifications_trigger`: catálogo de eventos por módulo
- `notifications_logs`: motivos estruturados de falha
- `templates_api`, `template_update_api`, `channels_config_api`: preview e validador de templates

## 4.10 Paineis (`apps.paineis`)

- `dataset_list`: status formal e qualidade de dado
- `dataset_create`: conectores e versionamento
- `dataset_detail`: dicionário e permissão por perfil
- `dataset_publish`: checklist de privacidade
- `dataset_package`: pacote com metadados e esquema
- `dashboard`: KPIs, filtros, exportação e compartilhamento interno

## 4.11 Conversor (`apps.conversor`)

- `index`: modelos rápidos e histórico por usuário/escopo
- `job_status`: status detalhado por etapa
- `download`: link com expiração e controle estrito de permissão

## 5) Camadas transversais de produto (diferenciais)

- Atendimento georreferenciado (chamados com ponto no mapa e evidência multimídia)
- BI executivo com compartilhamento e exportações
- Integração PNCP com fila/reenvio/logs

## 6) Definição de pronto por entrega

Uma função só é considerada concluída quando:

1. UI com filtros, ações rápidas e exportação.
2. Regras de permissão e escopo testadas.
3. Auditoria e (quando aplicável) transparência publicável.
4. Eventos de comunicação integráveis.
5. Testes automatizados cobrindo fluxo crítico.
6. Documentação atualizada no `docs/`.
