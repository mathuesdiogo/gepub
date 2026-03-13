# GEPUB - Módulo Operação: Funções, Integrações e Funcionamento

Gerado em: 01/03/2026

## 1. O que é o "Módulo Operação" no sistema

No GEPUB, "Operação" é o agrupamento de módulos exibido em **Gestão Pública > Operação** no menu lateral.

Inclui:
- Organização (ORG)
- Financeiro
- Processos
- Compras
- Contratos
- RH
- Ponto
- Folha
- Patrimônio
- Almoxarifado
- Frota
- Ouvidoria
- Tributos

Referência de menu:
- `templates/core/partials/components/layout/sidebar_navigation.html`

## 2. Visão de funcionamento geral

O bloco de Operação compartilha as mesmas bases arquiteturais:

1. Escopo institucional:
- Tudo é filtrado por `municipio`, com recortes por `secretaria`, `unidade`, `setor`.

2. Controle de acesso:
- Permissões RBAC com `@require_perm(...)` e flags de menu (`can_financeiro`, `can_processos`, etc.).

3. Rastreabilidade:
- Eventos importantes geram trilha de auditoria (`registrar_auditoria`).

4. Transparência:
- Eventos operacionais relevantes podem ser publicados no portal de transparência (`publicar_evento_transparencia`).

## 3. Mapeamento por módulo

### 3.1 Organização (ORG)

Principais funções:
- `index`
- Onboarding: `onboarding_primeiro_acesso`, `onboarding_painel`
- Governança: `secretaria_governanca_hub`, `secretaria_governanca_detail`
- CRUD institucional:
  - Município: `municipio_list`, `municipio_create`, `municipio_detail`, `municipio_update`
  - Secretaria: `secretaria_list`, `secretaria_create`, `secretaria_detail`, `secretaria_update`
  - Unidade: `unidade_list`, `unidade_create`, `unidade_detail`, `unidade_update`
  - Setor: `setor_list`, `setor_create`, `setor_detail`, `setor_update`
- Endereços/Maps:
  - `address_list`, `address_create`, `address_update`, `address_delete`, `address_reprocess_geocode`

O que faz:
- Define a estrutura institucional do município e os escopos de operação.
- Suporta implantação de secretarias e governança inicial.
- Gerencia localização institucional de secretarias/unidades.

Integrações:
- Billing/Plano (onboarding e ativação).
- Geocode/Maps (endereços e coordenadas).
- Base para todos os outros módulos.

Como funciona:
- Primeiro monta-se o território institucional (município > secretaria > unidade > setor).
- Depois os demais módulos operam sobre essa estrutura.

---

### 3.2 Financeiro

Principais funções:
- Dashboard e cadastros base:
  - `index`, `exercicio_list/create/update`, `ug_list/create`, `conta_list/create`, `fonte_list/create`, `dotacao_list/create`, `credito_list/create`
- Execução:
  - `empenho_list/create/detail`, `liquidacao_create`, `pagamento_create`
  - `receita_list/create`
  - `resto_list/create/detail`, `resto_pagamento_create`
  - `log_list`
- Tesouraria/Conciliação:
  - `extrato_list/create/detail`, `extrato_auto`, `extrato_ajuste`, `extrato_desfazer`

O que faz:
- Gestão orçamentária, despesa, receita e tesouraria.
- Fechamento e conciliação financeira por exercício.

Integrações:
- Compras (empenho gerado por requisição homologada).
- Contratos (liquidação de medições).
- Folha (envio ao financeiro).
- Transparência/Auditoria.

Como funciona:
- Fluxo principal da despesa:
  - Dotação -> Empenho -> Liquidação -> Pagamento
- Fluxo de tesouraria:
  - Importa extrato -> concilia automático/manual -> registra ajustes.

---

### 3.3 Processos

Principais funções:
- `index`, `processo_list`, `processo_create`, `processo_detail`, `andamento_create`

O que faz:
- Protocolo e tramitação administrativa interna.

Integrações:
- Compras (requisição pode vincular processo administrativo).
- Estrutura ORG (setores de origem/destino).
- Transparência/Auditoria.

Como funciona:
- Processo nasce com dados básicos e evolui por andamentos (encaminhamento/despacho/conclusão).

---

### 3.4 Compras

Principais funções:
- `requisicao_list/create/detail`
- `item_create`
- `aprovar`
- `gerar_empenho`
- `licitacao_list/create`

O que faz:
- Opera requisições de compra e processos licitatórios.

Integrações:
- Processos (vínculo opcional de processo administrativo).
- Financeiro (gera `DespEmpenho` ao homologar).
- Contratos (origem contratual pode vir de requisição/licitação).
- Transparência/Auditoria.

Como funciona:
- Requisição passa por status (rascunho/aprovação/homologação).
- Após aprovação e validações de saldo/dotação, pode gerar empenho automaticamente.

---

### 3.5 Contratos

Principais funções:
- `contrato_list/create/detail`
- `aditivo_create`
- `medicao_create`, `medicao_atestar`, `medicao_liquidar`

O que faz:
- Gestão de contratos, aditivos e medições.

Integrações:
- Compras (processo licitatório/requisição origem).
- Financeiro (usa empenho do contrato e gera liquidação da medição).
- Transparência/Auditoria.

Como funciona:
- Contrato pode receber aditivos (prazo/valor/escopo).
- Medição: criar -> atestar -> liquidar no financeiro.

---

### 3.6 RH

Principais funções:
- `index`
- `servidor_list/create/update`
- `movimentacao_list/create/aprovar/recusar`
- `documento_list/create`

O que faz:
- Cadastro funcional, movimentações e documentos do servidor.

Integrações:
- Base para Ponto e Folha.
- Estrutura ORG (lotação por secretaria/unidade/setor).
- Transparência/Auditoria.

Como funciona:
- Cada servidor possui status, regime e situação funcional.
- Movimentações alteram estado e podem exigir aprovação.

---

### 3.7 Ponto

Principais funções:
- `index`
- `escala_list/create/update`
- `vinculo_list/create/toggle`
- `ocorrencia_list/create/aprovar/recusar`
- `competencia_list/create/fechar/reabrir`

O que faz:
- Controle de jornada, escalas e ocorrências por competência.

Integrações:
- RH/usuários (vínculo servidor-escala).
- Folha (base operacional para reflexos).

Como funciona:
- Cria escalas e vincula servidores.
- Registra ocorrências.
- Fecha competência mensal para consolidar.

---

### 3.8 Folha

Principais funções:
- `index`
- `rubrica_list/create/update`
- `competencia_list/create/processar/fechar/reabrir`
- `lancamento_list/create`
- `enviar_financeiro`
- `holerite_pdf`

O que faz:
- Processamento da folha por competência e integração com financeiro.

Integrações:
- RH/usuários (servidores).
- Financeiro (integração de total da folha).
- Transparência/Auditoria.

Como funciona:
- Define rubricas e lança eventos.
- Processa competência, calcula totais e fecha.
- Envia integração para financeiro.

---

### 3.9 Patrimônio

Principais funções:
- `index`
- `bem_list/create/update`
- `movimentacao_list/create`
- `inventario_list/create/concluir`

O que faz:
- Controle de bens, movimentações patrimoniais e inventários.

Integrações:
- ORG (unidade/setor de lotação).
- Transparência/Auditoria.

Como funciona:
- Bem é cadastrado, movimentado e conferido por inventários periódicos.

---

### 3.10 Almoxarifado

Principais funções:
- `index`
- `item_list/create/update`
- `movimento_list/create`
- `requisicao_list/create/aprovar/atender`

O que faz:
- Gestão de estoque e atendimento de requisições internas.

Integrações:
- ORG (setores/unidades solicitantes).
- Transparência/Auditoria.

Como funciona:
- Mantém saldo por item.
- Requisições passam por aprovação e atendimento com baixa de estoque.

---

### 3.11 Frota

Principais funções:
- `index`
- `veiculo_list/create/update`
- `abastecimento_list/create`
- `manutencao_list/create/concluir`
- `viagem_list/create/concluir`

O que faz:
- Operação de veículos oficiais.

Integrações:
- ORG (lotação institucional).
- Transparência/Auditoria.

Como funciona:
- Ciclo operacional do veículo: cadastro -> abastecimento/manutenção/viagem -> conclusão.

---

### 3.12 Ouvidoria

Principais funções:
- `index`
- `chamado_list/create/concluir`
- `tramitacao_list/create`
- `resposta_list/create`

O que faz:
- Atendimento ao cidadão e gestão de chamados.

Integrações:
- Estrutura por setor/unidade.
- Transparência/Auditoria.

Como funciona:
- Chamado é aberto, tramitado internamente e respondido/concluído.

---

### 3.13 Tributos

Principais funções:
- `index`
- `contribuinte_list/create/update`
- `lancamento_list/create/baixar`

O que faz:
- Cadastro de contribuintes e lançamentos tributários.

Integrações:
- Financeiro (visão arrecadatória).
- Transparência/Auditoria.

Como funciona:
- Lançamento é emitido e depois baixado (pagamento/regularização).

## 4. Integrações-chave entre módulos de Operação

1. ORG -> Todos:
- ORG define o escopo institucional usado por todos os módulos.

2. Processos -> Compras:
- Requisição pode vincular processo administrativo.

3. Compras -> Financeiro:
- Requisição homologada pode gerar empenho.

4. Compras -> Contratos:
- Contratos podem nascer de requisição/licitação.

5. Contratos -> Financeiro:
- Medição atestada pode gerar liquidação.

6. RH -> Ponto/Folha:
- RH fornece base de servidores e lotação.

7. Folha -> Financeiro:
- Competência de folha pode ser enviada para integração financeira.

8. Todos -> Auditoria/Transparência:
- Eventos operacionais podem gerar logs e publicação pública.

## 5. Observações de segurança e escalabilidade

- Padrão de proteção de dados relacionais usa `on_delete=PROTECT` em chaves críticas de escopo.
- Permissões por ação (`view`, `manage`, etc.) evitam exposição indevida.
- Restrição por município/escopo local reduz risco de acesso cruzado.
- Trilha de auditoria melhora rastreabilidade e conformidade.

## 6. Backlog Avançado de Aprimoramento (Benchmark ERP Público)

Esta seção consolida recomendações de evolução para aproximar o GEPUB do padrão de mercado em ERP público, preservando a arquitetura atual de escopo, RBAC, auditoria e transparência.

### 6.1 Padrão transversal (aplicar em todas as funções)

1. Contrato de usabilidade (todas as telas `list/detail/create/update`):
- Busca simples e avançada (status, período, unidade, responsável, tags).
- Filtros persistentes por usuário.
- Ações rápidas por status (aprovar, recusar, devolver, imprimir, exportar).
- Timeline do registro (eventos, anexos, comentários).
- Checklist mínimo de conformidade antes de avançar status.

2. Contrato de governança (toda ação de mudança de status):
- Validação de permissão + escopo + consistência.
- Auditoria detalhada (quem, quando, o que mudou).
- Transparência opcional/publicável conforme regra.
- Notificação por canal (e-mail, WhatsApp, SMS, app).

3. Contrato de integração (toda entidade principal):
- ID único, status, responsável, tags e vínculos.
- Vínculos entre processo, contrato, empenho, servidor e unidade.
- Anexos tipificados (edital, parecer, laudo, nota, recibo etc.).
- Exportação padrão (PDF, CSV, XLSX).

### 6.2 Roadmap recomendado (dependência + impacto)

1. ORG + Endereços/Maps.
2. Processos (espinha dorsal de tramitação).
3. Compras + Contratos + Financeiro (incluindo PNCP).
4. RH + Ponto + Folha.
5. Almoxarifado + Frota.
6. Ouvidoria + Portal do Cidadão + App.
7. Tributos (com camada territorial/GIS).
8. Camada premium: BI, custos, indicadores e painéis.

## 7. Melhorias por função (Módulo Operação)

### 7.1 ORG

- `index`:
- Painel de saúde institucional (cadastros faltantes e pendências).
- Atalhos para criar secretaria, importar unidades e corrigir endereços.
- `onboarding_primeiro_acesso`, `onboarding_painel`:
- Checklist obrigatório com progresso:
  - município,
  - secretarias,
  - unidades e setores,
  - usuários e perfis,
  - geocodificação,
  - parâmetros financeiros.
- Assistente de importação CSV para estrutura ORG.
- `secretaria_governanca_hub`, `secretaria_governanca_detail`:
- Matriz RACI simplificada por tipo de aprovação.
- Indicadores por secretaria (atrasos, contratos vencendo, chamados etc.).
- CRUD institucional (`municipio_*`, `secretaria_*`, `unidade_*`, `setor_*`):
- Código interno, sigla, CNPJ/UG (quando aplicável), responsável e contato.
- Status ativo/inativo com motivo e data.
- Importação/exportação CSV.
- Histórico de mudanças por registro.
- Endereços/Maps (`address_*`):
- Campos completos de endereço + lat/lng + precisão + fonte.
- Regra para impedir unidade de atendimento sem endereço válido.
- Botões de mapa: abrir, marcar pin manual, rota até local.
- Fila de reprocessamento de geocode com status e relatório de erro.

### 7.2 Processos

- `index`:
- Painel por status e atrasos.
- Ação rápida para protocolar.
- `processo_list`:
- Busca por número, interessado, assunto, setor e tags.
- Visões salvas: meus, do setor, atrasados.
- `processo_create`:
- Templates por tipo (compras, contrato, ambiental, ouvidoria, RH).
- Anexos obrigatórios por tipo.
- SLA padrão por tipo.
- `processo_detail`:
- Timeline completa.
- Vinculação com requisição, licitação, contrato, chamado e licença.
- Geração de capa/folha de rosto PDF.
- `andamento_create`:
- Tipos de andamento padronizados.
- Destinatário obrigatório por setor/servidor.
- Alerta de processo parado por dias configuráveis.

### 7.3 Compras

- `requisicao_list`:
- Visões por fase e indicadores de valor/prazo.
- `requisicao_create`:
- Catálogo padronizado de itens/serviços.
- Centro de custo/programa/ação.
- Sugestão de dotação por histórico.
- Banco de preços (mínimo/médio/máximo) com anexos.
- Justificativa e finalidade pública obrigatórias.
- `requisicao_detail`:
- Timeline com checklist documental.
- Vínculo assistido com processo.
- `item_create`:
- Unidade de medida, quantidade, especificação, marca/modelo opcional, lote.
- Validação de duplicidade.
- Cotação por fornecedor quando aplicável.
- `aprovar`:
- Fluxo multi-nível parametrizável por valor.
- Aprovar/devolver/recusar com motivo obrigatório.
- Travas por ausência de anexos críticos.
- `gerar_empenho`:
- Pré-validação de dotação, saldo, exercício, UG, fonte.
- Simulação prévia de empenho.
- Vínculo automático com financeiro e log.
- `licitacao_list`, `licitacao_create`:
- Modalidades e fases completas.
- Gestão de comissão e agenda.
- Ata de registro, contratos e aditivos vinculados.
- Publicação com integração PNCP (status, erro, reenvio).

### 7.4 Contratos

- `contrato_list`:
- Alertas de vencimento (30/15/7 dias) e saldo crítico.
- Visões por status (vigente/encerrado/rescindido/suspenso).
- `contrato_create`:
- Campos de gestor/fiscal, garantia e fonte de recurso.
- Vínculo com origem (requisição/licitação/processo).
- Anexos obrigatórios do instrumento.
- `contrato_detail`:
- Timeline de aditivos, medições, pagamentos e ocorrências.
- Painel de valor total, executado, saldo e prazo.
- `aditivo_create`:
- Tipos: prazo, valor, quantitativo, reajuste, reequilíbrio, supressão/acréscimo.
- Justificativa e anexos obrigatórios.
- Recalcular vigência e saldo automaticamente.
- `medicao_create`, `medicao_atestar`, `medicao_liquidar`:
- Medição por item/quantidade com evidência.
- Atesto por fiscal/gestor com assinatura interna.
- Liquidação bloqueada sem atesto.
- Evento financeiro rastreável.

### 7.5 Financeiro

- `index`:
- Painel de indicadores fiscais.
- Alertas de inconsistência entre compra/contrato/empenho/extrato.
- Cadastros base (`exercicio_*`, `ug_*`, `conta_*`, `fonte_*`, `dotacao_*`, `credito_*`):
- Importação CSV com validação.
- Travas de fechamento por exercício.
- Configuração por município/entidade.
- Execução (`empenho_*`, `liquidacao_create`, `pagamento_create`, `receita_*`, `resto_*`, `log_list`):
- Origem explícita do empenho (compras/contrato/folha/manual).
- Anexos obrigatórios por tipo de despesa.
- Checklist de medição atestada para liquidação contratual.
- Conciliação assistida em pagamento.
- Log legível com diff antes/depois.
- Tesouraria (`extrato_*`):
- Importação OFX/CSV.
- Regras de conciliação por valor/data/documento.
- Trilhas de ajuste/desfazer com motivo obrigatório.

### 7.6 RH

- `index`:
- Painel de efetivo por secretaria/unidade.
- Alertas de lotação/documentação/escala pendentes.
- `servidor_list`, `servidor_create`, `servidor_update`:
- Dados funcionais completos (vínculo, cargo, regime, lotação, jornada).
- Banco de horas (quando aplicável).
- Documentos tipificados e histórico de movimentação.
- `movimentacao_list`, `movimentacao_create`, `movimentacao_aprovar`, `movimentacao_recusar`:
- Tipos padronizados (remoção, cessão, designação, exoneração, férias, licenças).
- Workflow parametrizável.
- Ao aprovar, refletir automaticamente em Ponto e Folha.
- `documento_list`, `documento_create`:
- Modelos de documentos oficiais.
- Preparação para assinatura digital.

### 7.7 Ponto

- `index`:
- Situação da competência e pendências por gestor.
- `escala_list`, `escala_create`, `escala_update`:
- Tipos de escala (6x1, 12x36, administrativo, plantão).
- Regras de descanso mínimo e carga semanal.
- `vinculo_list`, `vinculo_create`, `vinculo_toggle`:
- Vínculo por período (início/fim).
- Bloquear vínculo para servidor inativo.
- `ocorrencia_list`, `ocorrencia_create`, `ocorrencia_aprovar`, `ocorrencia_recusar`:
- Tipos padronizados (falta, atraso, atestado, hora extra, abono).
- Anexos obrigatórios conforme tipo.
- Aprovação multi-nível quando necessário.
- `competencia_list`, `competencia_create`, `competencia_fechar`, `competencia_reabrir`:
- Travas de fechamento por pendência crítica.
- Relatórios por servidor/unidade/tipo.

### 7.8 Folha

- `index`:
- Status de processamento da competência atual.
- Alertas de rubrica e base inconsistente.
- `rubrica_list`, `rubrica_create`, `rubrica_update`:
- Tipo (provento/desconto) e base (fixo/percentual/fórmula).
- Preparação para integrações fiscais futuras.
- `competencia_list`, `competencia_create`, `competencia_processar`, `competencia_fechar`, `competencia_reabrir`:
- Simulação antes do processamento.
- Logs de cálculo por servidor.
- Travas fortes no fechamento.
- `lancamento_list`, `lancamento_create`:
- Lançamento em lote por unidade/cargo.
- Importação CSV.
- `enviar_financeiro`:
- Mapa de integração conta/dotação.
- Reenvio com versionamento.
- `holerite_pdf`:
- Assinatura/validação por hash.
- Histórico no portal do servidor.

### 7.9 Patrimônio

- `index`:
- Visão por unidade/setor.
- Alertas de bem sem responsável/localização.
- `bem_list`, `bem_create`, `bem_update`:
- Plaqueta/QR Code, fotos, documentos e depreciação (quando aplicável).
- `movimentacao_list`, `movimentacao_create`:
- Motivos padronizados (transferência, baixa, cessão).
- Termo automático PDF para assinatura.
- `inventario_list`, `inventario_create`, `inventario_concluir`:
- Inventário por setor com checklist.
- Controle de divergência (encontrado/não encontrado/sucata).
- Relatório final exportável.

### 7.10 Almoxarifado

- `index`:
- Alertas de mínimo e vencimento.
- Curva ABC opcional.
- `item_list`, `item_create`, `item_update`:
- Unidade de medida, categoria, código, mínimo/máximo e ponto de reposição.
- `movimento_list`, `movimento_create`:
- Tipos: entrada, saída, ajuste, devolução.
- Anexo de documento fiscal/termo.
- `requisicao_list`, `requisicao_create`, `requisicao_aprovar`, `requisicao_atender`:
- Aprovação por gestor.
- Atendimento parcial com rastreio.
- Baixa automática por setor solicitante.

### 7.11 Frota

- `index`:
- Painel de custo por veículo (combustível/manutenção).
- Alertas de revisão e documentação.
- `veiculo_list`, `veiculo_create`, `veiculo_update`:
- Documentos do veículo, lotação ORG, hodômetro e consumo médio.
- `abastecimento_list`, `abastecimento_create`:
- Validação de odômetro crescente.
- Integração de custo para BI.
- `manutencao_list`, `manutencao_create`, `manutencao_concluir`:
- Ordem de serviço com anexos (orçamento, nota, fotos).
- Classificação preventiva/corretiva.
- `viagem_list`, `viagem_create`, `viagem_concluir`:
- Rota, objetivo e diário de bordo PDF.
- Geolocalização opcional.

### 7.12 Ouvidoria

- `index`:
- Painel por status e SLA.
- `chamado_list`, `chamado_create`, `chamado_concluir`:
- Atendimento multicanal com anexos (foto, vídeo, áudio).
- Geolocalização de chamado.
- Classificação por tipo, secretaria e urgência.
- `tramitacao_list`, `tramitacao_create`:
- Encaminhamento obrigatório para setor responsável.
- Notificação automática e prazo por tipo.
- `resposta_list`, `resposta_create`:
- Modelos de resposta.
- Pesquisa de satisfação.
- Publicação no portal quando aplicável.

### 7.13 Tributos

- `index`:
- Painel de arrecadação, inadimplência e dívida ativa.
- `contribuinte_list`, `contribuinte_create`, `contribuinte_update`:
- Vínculo com imóvel/atividade.
- Reuso de endereço georreferenciado.
- `lancamento_list`, `lancamento_create`, `lancamento_baixar`:
- Parcelamento, desconto, multa/juros, guia.
- Baixa manual e por importação.
- Integração automática com receitas do financeiro.
- Camada GIS futura:
- mapas de fiscalização/cadastro técnico/planejamento arrecadatório.

## 8. Camadas estratégicas complementares

1. Central PNCP:
- Fila, erros, reenvio, logs e consulta histórica.

2. Ecossistema digital de usuário:
- Portal de assinaturas.
- Portal do servidor.
- App do cidadão.
- Integração oficial com WhatsApp.

3. Camada BI:
- Indicadores executivos, custos, análises e exportações.

4. Camada GIS:
- Território, fiscalização, saúde, meio ambiente, ouvidoria e tributos.

5. Diretriz de software público:
- Auditoria, interoperabilidade e redução de dependência de fornecedor.
