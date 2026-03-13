# GEPUB - Demais Módulos (Ferramentas): Funções e Integrações

Gerado em: 01/03/2026

## Integracoes (`apps.integracoes`)

Objetivo:
- Operar conectores e registrar execuções de integração com sistemas externos.

Funções (rotas nomeadas):
- `index`: painel com conectores e execuções.
- `conector_create`: criação de novo conector de integração.
- `execucao_create`: registro manual de execução (status/direção/volume).

Integrações com outros módulos:
- `org`: escopo por município.
- `core`: auditoria e transparência (`registrar_auditoria`, `publicar_evento_transparencia`).

Como funciona:
- Cadastra conector -> executa/sincroniza -> registra execução com status e rastreabilidade.

---

## Comunicação (`apps.comunicacao`)

Objetivo:
- Centralizar comunicação automática por E-mail/SMS/WhatsApp com templates, fila e logs.

Funções (rotas nomeadas):
- `index`: painel de jobs, templates, canais e logs.
- `processar_fila`: processa lote de jobs pendentes.
- `notifications_send`: enfileira envio manual/campanha.
- `notifications_trigger`: dispara envio baseado em evento.
- `notifications_logs`: consulta logs de entrega/falha.
- `templates_api`: lista/cria templates.
- `template_update_api`: atualiza template específico.
- `channels_config_api`: lista/cria/atualiza configuração de canais.

Integrações com outros módulos:
- `org`: escopo municipal/setorial/unidade.
- `core`: permissão RBAC, auditoria.
- `educacao/saude/nee/processos`: consumidores de eventos notificados.

Como funciona:
- Evento ou envio manual -> fila de `NotificationJob` -> worker/processador -> log por tentativa e fallback de canal.

---

## Paineis BI (`apps.paineis`)

Objetivo:
- Ingestão de datasets e geração de dashboards analíticos no padrão executivo.

Funções (rotas nomeadas):
- `index`: redireciona para lista de datasets.
- `dataset_list`: catálogo de datasets por status/categoria.
- `dataset_create`: upload/criação de dataset e versão.
- `dataset_detail`: detalhamento de dataset, colunas e versões.
- `dataset_publish`: publicação de dataset para consumo.
- `dataset_package`: exportação/empacotamento do dataset.
- `dashboard`: visualização analítica com filtros e KPIs.

Integrações com outros módulos:
- `org`: escopo institucional do dataset.
- `core`: exportações, auditoria, RBAC.
- Pode consumir dados oriundos de módulos operacionais (educação, saúde, financeiro etc.).

Como funciona:
- Cria dataset -> processa versão -> valida colunas/qualidade -> publica -> disponibiliza dashboard e pacote.

---

## Conversor (`apps.conversor`)

Objetivo:
- Conversão de documentos com fila de jobs e download do resultado.

Funções (rotas nomeadas):
- `index`: tela principal de criação/listagem de jobs.
- `download`: baixa arquivo de saída da conversão concluída.
- `job_status`: endpoint de status do job (polling frontend).

Integrações com outros módulos:
- `org`: escopo por município.
- `core`: auditoria e controle de permissão.

Como funciona:
- Usuário envia arquivos -> cria `ConversionJob` -> processa assíncrono/síncrono -> disponibiliza download quando concluído.

Tipos de conversão suportados pela camada de serviço/UI:
- `DOCX_TO_PDF`
- `XLSX_TO_PDF`
- `IMG_TO_PDF`
- `PDF_MERGE`
- `PDF_SPLIT`
- `PDF_TO_IMAGES`
- `PDF_TO_TEXT`
- `PDF_TO_DOCX`
- `PDF_TO_XLSX`

---

## Backlog de Evolução (Padrão ERP Público)

Diretriz transversal aplicada a todas as funções deste documento:
- Fila assíncrona robusta, retries, reprocessamento e observabilidade.
- Registro técnico e funcional de erro com rastreabilidade.
- Integração com comunicação automática e auditoria.
- Exportações padronizadas e consumo em BI.

## Integrações (`apps.integracoes`) - evolução por função

- `index` - Adicionar:
- Painel de saúde de conectores (ok/erro/atrasado), taxa de sucesso e últimas execuções.
- `conector_create` - Aprimorar:
- Catálogo de conectores (SMTP, WhatsApp, PNCP, GIS, storage, SSO).
- Campos avançados (timeout, retries, limites, políticas de fallback).
- `execucao_create` - Aprimorar:
- Registro de direção (`in/out`), volume, latência, erro detalhado e referência da entidade.
- Ação de reprocessamento para execução falha.

Central PNCP:
- Padronizar integração PNCP como central:
- fila dedicada de publicação,
- validação de payload,
- reenvio controlado,
- logs por tentativa,
- consulta de espelho PNCP para confirmação de publicação.

## Comunicação (`apps.comunicacao`) - evolução por função

- `index` - Adicionar:
- KPIs operacionais (enviados, entregues, falhas, latência média, custo por canal).
- `processar_fila` - Aprimorar:
- Rate limit por canal, retries com backoff e dead-letter queue.
- `notifications_send` - Adicionar:
- Campanhas segmentadas (secretaria, unidade, turma, fila de atendimento).
- `notifications_trigger` - Aprimorar:
- Catálogo de eventos por módulo (Educação, NEE, Saúde, Processos, Operação).
- `notifications_logs` - Aprimorar:
- Motivo de falha estruturado (provedor, destinatário inválido, limite, template).
- `templates_api`, `template_update_api`, `channels_config_api` - Adicionar:
- Validador de template com preview por canal.
- Catálogo de variáveis padronizadas por módulo.

## Paineis BI (`apps.paineis`) - evolução por função

- `dataset_list` - Aprimorar:
- Status formal (rascunho/processando/publicado/arquivado) e qualidade de dado.
- `dataset_create` - Adicionar:
- Conectores de origem (módulos internos + upload) com versionamento obrigatório.
- `dataset_detail` - Aprimorar:
- Dicionário de dados e permissões por perfil.
- `dataset_publish` - Adicionar:
- Checklist de privacidade (dados sensíveis e publicação segura).
- `dataset_package` - Aprimorar:
- Pacote com metadados, esquema e README técnico.
- `dashboard` - Adicionar:
- Layout executivo, filtros cruzados, compartilhamento interno e exportações.

## Conversor (`apps.conversor`) - evolução por função

- `index` - Aprimorar:
- Modelos rápidos (juntar PDF, converter DOCX para PDF, extrair texto).
- Histórico por usuário e escopo.
- `job_status` - Adicionar:
- Status detalhado por etapa (fila, processando, convertido, erro, pronto para download).
- `download` - Aprimorar:
- Link com expiração, controle de permissão (criador/admin) e trilha de auditoria.
