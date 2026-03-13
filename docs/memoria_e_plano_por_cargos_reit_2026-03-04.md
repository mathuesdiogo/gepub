# Memória Consolidada e Plano por Cargos (REIT) - GEPUB

Data de consolidação: 04/03/2026

## 1. Fontes analisadas

- `/home/matheus/Downloads/008_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/009_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/010_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/013_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/015_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/016_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/018_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/020_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/021_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/025_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/029_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/031_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/033_Suporte_e_Manuais_REIT.pdf`
- `/home/matheus/Downloads/034_Suporte_e_Manuais_REIT.pdf`

Nota técnica: o `025` veio com texto codificado na extração automática; a consolidação foi fechada por leitura visual das páginas convertidas em imagem.

## 2. Memória consolidada por macroprocesso

## 2.1 Ensino Acadêmico (Base Estrutural)

Referências principais: `013`, `015`, `016`, `021`, `025`, `033`.

### Regras de negócio consolidadas

- Para rede municipal (foco infantil/fundamental), a base principal é `matriz curricular + série/ano`.
- Cursos devem ser tratados como trilhas/atividades extracurriculares, não como motor da oferta regular.
- Matriz curricular precisa ficar consistente com carga horária total.
- Componente curricular define: descrição, abreviatura, tipo, nível, CH relógio/aula, créditos.
- Vínculo componente-matriz define: período letivo, tipo (regular/optativo), núcleo, avaliações, CH teórica/prática.
- Pré-requisito e co-requisito precisam ser controlados por vínculo de componente.
- Equivalência de componente não é bidirecional automática.
- Equivalência pode ser 1:1 e também em grupo (exigir conjunto completo de componentes equivalentes).
- Horário do campus é entidade mestre para geração e oferta de diários.
- Diário fora do período da turma pode ser criado e exige inclusão posterior de alunos da turma.
- Renovação de matrícula online depende de sequência operacional:
  - fechar período anterior;
  - gerar turmas e diários;
  - configurar janela de renovação;
  - associar matrizes curriculares e, quando aplicável, atividades extras;
  - tratar pendências de horário/diário;
  - processar pedidos de matrícula no fim do período.

### Estados relevantes

- Renovação de matrícula: `Em aberto` -> `Finalizada`.
- Situação de matrícula por diário/período: precisa suportar controle por período letivo e turma.

## 2.2 Editais, Conteúdo de Portal e Publicações

Referências principais: `010`, `018`, `034`.

### Regras de negócio consolidadas

- Conteúdo de portal unifica publicação de editais e documentos institucionais.
- Arquivos de edital devem ficar no mesmo conteúdo (abertura, retificação, anexos, resultados, recursos, final).
- Upload deve exigir PDF e descrição obrigatória.
- Etapas de edital precisam de datas e links de acompanhamento por etapa.
- Ordem de arquivos afeta prioridade de exibição.
- Projeto de ensino/extensão tem ciclo com abas obrigatórias:
  - caracterização de beneficiários;
  - equipe;
  - metas/atividades;
  - plano de aplicação;
  - plano de desembolso;
  - anexos.
- Projeto inicia em `Em edição`, vai para `Enviado`, depois `Pré-seleção/Seleção`, e se aprovado fica `Em execução`.
- Equipe de projeto deve suportar aluno, servidor, orientador, anexos por participante, certificados na conclusão.

## 2.3 Documento e Processo Eletrônico

Referências principais: `020`, `029`.

### Regras de negócio consolidadas

- Documento eletrônico precisa de ciclo formal:
  - `Rascunho`;
  - `Concluído`;
  - `Assinado` ou `Aguardando assinatura`;
  - `Aguardando revisão`;
  - `Finalizado`.
- Documento só deve ser anexado a processo quando finalizado.
- Assinatura digital por senha (e preparado para token).
- Solicitação de assinatura sequencial deve gerar alerta para o assinante.
- Processo eletrônico exige:
  - interessados;
  - tipo;
  - assunto;
  - nível de acesso;
  - classificação;
  - tramitação com/sem despacho;
  - histórico de trâmites.
- Ações complementares: solicitar ciência, remover último trâmite (antes de recebimento), solicitar despacho, verificar integridade, finalizar processo.
- Substituição de servidor precisa transferir permissões por período e módulo.
- Substituição possui status: `Agendada`, `Vigente`, `Concluída`.
- Edição de substituição só em `Agendada`.

## 2.4 Gestão de Pessoas e Governança de Capacitação

Referências principais: `008`, `009`, `031`.

### Regras de negócio consolidadas

- Remanejamento docente e técnico-administrativo com:
  - inscrição em janela do edital;
  - anexos obrigatórios;
  - registro de preferência de campus;
  - comprovante de inscrição;
  - cancelamento/desistência;
  - recurso ao edital em período próprio.
- No caso docente, há regras específicas por disciplina/vaga ofertada.
- PDP (Plano de Desenvolvimento de Pessoas) precisa de fluxo descentralizado + consolidação central:
  - submissão individual/institucional;
  - classificação por área estratégica/temática/objeto;
  - definição de competência associada;
  - tipo e modalidade de aprendizagem;
  - estimativa de carga horária/custo;
  - aprovação local;
  - aprovação da autoridade máxima;
  - lançamento final no SIPEC.

## 3. Entidades e integrações necessárias no GEPUB

## 3.1 Entidades de domínio prioritárias

- `matriz_curricular`, `componente`, `vinculo_matriz_componente`.
- `atividade_extracurricular` (modelo derivado de curso) para trilhas complementares.
- `equivalencia_componente`, `grupo_equivalencia`.
- `horario_campus`, `aula_horario`.
- `turma`, `diario`, `matricula_diario`, `matricula_periodo`.
- `janela_renovacao_matricula`, `config_renovacao`, `pedido_renovacao`, `processamento_renovacao`.
- `edital`, `etapa_edital`, `arquivo_edital`, `categoria_documento_portal`.
- `projeto_ensino`, `projeto_extensao`, `equipe_projeto`, `meta_projeto`, `atividade_projeto`, `orcamento_projeto`, `desembolso_projeto`, `anexo_projeto`, `avaliacao_projeto`.
- `documento_eletronico`, `assinatura_documento`, `revisao_documento`.
- `processo_eletronico`, `tramite_processo`, `despacho_processo`, `ciencia_processo`, `integridade_documento`.
- `substituicao_servidor`, `substituicao_modulo`, `substituicao_setor`.
- `pdp_submissao`, `pdp_necessidade`, `pdp_aprovacao_local`, `pdp_aprovacao_central`, `pdp_export_sipec`.

## 3.2 Integrações obrigatórias

- Portal público (editais/documentos/etapas/arquivos).
- Assinatura e auditoria de documento/processo.
- RBAC por módulo + escopo por setor/campus.
- Alertas de pendência por usuário (assinatura, revisão, prazo, recurso, renovação).

## 4. Lista de implementação por cargos

## 4.1 Aluno

- Ver e atualizar dados permitidos.
- Renovação de matrícula online (janela, pendências, confirmação).
- Visualizar turmas/diários/boletim conforme período e matrícula.
- Solicitar/acompanhar documentos e processos próprios.
- Participar de projetos/editais quando permitido.

## 4.2 Professor

- Lançar/gerir diário da turma.
- Validar presença/nota conforme componente e etapa.
- Atuar em projetos de ensino/extensão como coordenador/orientador/membro.
- Atender solicitações acadêmicas vinculadas à disciplina/turma.

## 4.3 Coordenação Pedagógica (Infantil/Fundamental)

- Gerir matrizes, componentes e vínculos por etapa/série.
- Definir pré/co-requisitos e equivalências.
- Acompanhar consistência de matriz e oferta de componentes.
- Autorizar ajustes acadêmicos dentro da sua diretoria.

## 4.4 Secretaria Acadêmica (Registro Escolar)

- Gerar turmas e diários.
- Configurar calendário e horários de campus.
- Executar renovação de matrícula por janela.
- Gerar diários fora do período e adicionar alunos da turma.
- Emitir documentos acadêmicos e acompanhar processos escolares.

## 4.5 Coordenação/Diretoria de Ensino

- Homologar regras de calendário, oferta e renovação.
- Supervisionar projetos de ensino e critérios de edital.
- Aprovar fluxos acadêmicos e indicadores de execução.

## 4.6 Coordenação de Extensão

- Configurar editais de extensão.
- Acompanhar submissões, equipe, metas, orçamento e anexos.
- Gerir pré-seleção/seleção e execução dos projetos aprovados.

## 4.7 Comunicação Social

- Publicar editais e documentos no portal.
- Gerenciar etapas e links de acompanhamento.
- Organizar ordem, versão e visibilidade dos arquivos.

## 4.8 Protocolo / Tramitador

- Criar documentos eletrônicos, solicitar revisão/assinatura e finalizar.
- Abrir processo eletrônico, anexar documentos e tramitar.
- Solicitar ciência, despacho, receber/finalizar processo.
- Verificar integridade e rastreabilidade.

## 4.9 Gestão de Pessoas / Chefias

- Operar remanejamento por edital (inscrição, documentos, recursos).
- Configurar substituição de servidor por período/módulo/setor.
- Monitorar status da substituição e revogação automática de acessos.

## 4.10 Comissão Local do PDP

- Divulgar metodologia e orientar servidores.
- Consolidar submissões da unidade.
- Revisar e encaminhar para aprovação da autoridade local.

## 4.11 Comissão Central do PDP

- Consolidar dados de todos os campi/unidades.
- Revisar necessidades transversais e não transversais.
- Preparar pacote institucional para aprovação final.

## 4.12 Reitor/Autoridade Máxima

- Aprovar PDP institucional.
- Autorizar envio para lançamento no SIPEC.

## 4.13 Admin GEPUB (SaaS)

- Governança de tenant, plano, módulos e feature flags.
- Auditoria de segurança, trilha de ações e parametrização global.
- Gestão de integrações e versionamento de regras.

## 5. Sequência recomendada de implementação (funil)

1. Cadastro estrutural do Ensino: matrizes, componentes, equivalências e horários.
2. Cadastro de atividades extracurriculares (complementares).
3. Operação acadêmica: turmas, diários, matrícula/renovação e pendências.
4. Documento/processo eletrônico com assinatura e tramitação.
5. Conteúdo de portal (editais/documentos/etapas/arquivos) integrado ao público.
6. Projetos de ensino e extensão com ciclo completo (submissão -> seleção -> execução).
7. Gestão de pessoas: remanejamento e substituição de servidor.
8. PDP completo com aprovação local/central e exportação SIPEC.

## 6. Backlog inicial por fase (executável)

### Fase 1 - Ensino estrutural

- Modelar entidades acadêmicas e regras de consistência.
- Criar telas administrativas para matriz/componente/equivalência/horário.
- Criar telas administrativas de atividades extracurriculares (catálogo complementar).
- Implementar validações automáticas de CH, pré/co-requisito e status de matriz.

### Fase 2 - Ensino operacional

- Geração de turma/diário por período.
- Cadastro de diário fora de período + inclusão de alunos.
- Renovação online com processamento final e painel de pendências.

### Fase 3 - Processo eletrônico

- Fluxo completo de documento eletrônico e assinaturas.
- Abertura/tramitação/finalização de processo eletrônico.
- Trilha de auditoria e verificação de integridade.

### Fase 4 - Portal e editais

- CRUD de edital/documento/etapa/arquivo.
- Publicação automática no portal público com controle de visibilidade e ordem.

### Fase 5 - Projetos e RH

- Projetos de ensino/extensão (submissão, avaliação, execução).
- Remanejamento docente/TAE e substituição de servidor.
- PDP institucional com fluxo de aprovação e exportação.
