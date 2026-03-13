# GEPUB - Relatorio de Usuarios, Funcoes e Atribuicoes

Gerado em: 2026-02-28

## Regras gerais

- Mesma dashboard por modulo, com visao filtrada por papel e escopo.
- Escopo minimo necessario: municipio, secretaria, unidade e atribuicao pessoal.
- Acoes-base consideradas: ver, criar, editar, excluir, aprovar/homologar, exportar, configurar.
- Gestao de usuarios e relatorios depende de permissao especifica por perfil.

## Perfis por area

### Administracao e Governanca

#### Admin (Sistema) (`ADMIN`)

- Nivel: N1 - Super Admin
- Escopo base: ADMIN
- Dashboard: Dashboard global
- Funcoes:
  - Governanca total da plataforma
  - Parametrizacao estrutural de municipio, secretaria e unidade
  - Administracao tecnica de integracoes e seguranca
- Atribuicoes:
  - Pode ver, criar, editar, excluir, publicar e configurar modulos
  - Pode gerenciar qualquer usuario e permissao
  - Acompanha auditoria e indicadores de todos os modulos

#### Gestor Municipal (`MUNICIPAL`)

- Nivel: N2 - Gestao central da prefeitura
- Escopo base: MUNICIPAL
- Dashboard: Dashboard municipal consolidado
- Funcoes:
  - Conduzir governanca operacional da prefeitura
  - Habilitar fluxos entre secretarias
  - Acompanhar desempenho macro da gestao
- Atribuicoes:
  - Pode gerenciar usuarios e operacao municipal
  - Pode aprovar publicacoes e acompanhar integracoes
  - Nao executa rotinas tecnicas de infraestrutura

#### Gestor de Secretaria (`SECRETARIA`)

- Nivel: N3 - Gestor de secretaria
- Escopo base: SECRETARIA
- Dashboard: Dashboard setorial
- Funcoes:
  - Gerenciar operacao da secretaria
  - Consolidar relatorios setoriais
  - Coordenar unidades vinculadas
- Atribuicoes:
  - Pode gerir unidades e usuarios do escopo
  - Pode aprovar fluxos internos da secretaria
  - Visualiza apenas seu escopo setorial

#### Gestor de Unidade (`UNIDADE`)

- Nivel: N4 - Gestor de unidade
- Escopo base: UNIDADE
- Dashboard: Dashboard da unidade
- Funcoes:
  - Gerenciar operacao local da unidade
  - Acompanhar equipe e execucao diaria
  - Garantir qualidade dos registros
- Atribuicoes:
  - Pode operar e acompanhar indicadores da unidade
  - Pode gerenciar usuarios operacionais locais
  - Nao possui visao global municipal

#### Controladoria / Auditoria (`AUDITORIA`)

- Nivel: Controle interno / fiscalizacao
- Escopo base: MUNICIPAL
- Dashboard: Dashboard de leitura e auditoria
- Funcoes:
  - Fiscalizar conformidade e trilhas de auditoria
  - Avaliar consistencia de dados e processos
  - Emitir pareceres tecnicos de governanca
- Atribuicoes:
  - Permissao de consulta ampla com foco em auditoria
  - Exportacoes orientadas a controle interno
  - Nao executa alteracoes operacionais

#### RH / Gestão de Pessoas (`RH_GESTOR`)

- Nivel: Gestao de pessoas
- Escopo base: MUNICIPAL
- Dashboard: Dashboard RH/Ponto/Folha
- Funcoes:
  - Gerenciar cadastro funcional e lotacao
  - Controlar ponto e folha
  - Acompanhar indicadores de pessoal
- Atribuicoes:
  - Opera RH, Ponto e Folha
  - Nao acessa dados clinicos/pedagogicos sensiveis
  - Trabalha no escopo institucional definido

#### Protocolo / Atendimento Geral (`PROTOCOLO`)

- Nivel: Atendimento e tramitacao
- Escopo base: SECRETARIA
- Dashboard: Dashboard de processos e ouvidoria
- Funcoes:
  - Registrar e tramitar protocolos
  - Acompanhar solicitacoes e encaminhamentos
  - Garantir SLA de atendimento
- Atribuicoes:
  - Pode gerenciar fluxos de processos no escopo
  - Acessa somente dados necessarios ao tramite
  - Nao acessa detalhes clinicos e NEE sensiveis

#### Gestor de Cadastros (`CAD_GESTOR`)

- Nivel: Gestao de cadastros-base
- Escopo base: MUNICIPAL
- Dashboard: Dashboard de administracao cadastral
- Funcoes:
  - Padronizar cadastros municipais
  - Tratar duplicidades e qualidade de dados
  - Suportar secretaria/unidade na base mestra
- Atribuicoes:
  - Pode atuar em estrutura e usuarios conforme governanca
  - Garante coerencia entre secretaria/unidade/servidor
  - Nao substitui administracao tecnica

#### Operador de Cadastros (`CAD_OPER`)

- Nivel: Operacao cadastral setorial
- Escopo base: SECRETARIA
- Dashboard: Dashboard cadastral setorial
- Funcoes:
  - Executar cadastros e atualizacoes
  - Anexar documentos permitidos
  - Manter dados atualizados por secretaria
- Atribuicoes:
  - Acesso limitado ao proprio escopo
  - Nao gerencia seguranca/perfis globais
  - Atua como operador de dados

#### Somente leitura (`LEITURA`)

- Nivel: Leitura institucional
- Escopo base: LEITURA
- Dashboard: Dashboard de consulta
- Funcoes:
  - Consultar dados e indicadores liberados
  - Apoiar auditoria e monitoramento
  - Acompanhar metas e resultados
- Atribuicoes:
  - Nao cria/edita/exclui registros operacionais
  - Acesso controlado por escopo
  - Permissao orientada a transparencia interna

### Saude

#### Secretário de Saúde (`SAU_SECRETARIO`)

- Nivel: Gestao setorial da saude
- Escopo base: SECRETARIA
- Dashboard: Dashboard Saude (escopo secretaria)
- Funcoes:
  - Acompanhar producao e indicadores da rede
  - Definir diretrizes operacionais
  - Conduzir governanca setorial da saude
- Atribuicoes:
  - Visao macro da secretaria de saude
  - Nao opera configuracoes tecnicas de infraestrutura
  - Acesso por escopo setorial

#### Diretor de Unidade de Saúde (`SAU_DIRETOR`)

- Nivel: Gestao de unidade de saude
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (escopo unidade)
- Funcoes:
  - Gerenciar operacao da unidade
  - Supervisionar equipe e filas locais
  - Validar relatorios da unidade
- Atribuicoes:
  - Acesso integral da unidade
  - Sem visao municipal completa por padrao
  - Pode gerir fluxo operacional local

#### Coordenador de Saúde (`SAU_COORD`)

- Nivel: Coordenacao assistencial
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (unidades atribuídas)
- Funcoes:
  - Coordenar protocolos e equipe assistencial
  - Acompanhar atendimento e producao
  - Padronizar rotina clinica
- Atribuicoes:
  - Gerencia operacao no escopo atribuido
  - Sem administracao global de usuarios
  - Atuacao focada na assistencia

#### Médico (`SAU_MEDICO`)

- Nivel: Profissional assistencial
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (casos atribuídos)
- Funcoes:
  - Registrar evolucao e conduta clinica
  - Executar atendimentos no proprio escopo
  - Contribuir com acompanhamento multiprofissional
- Atribuicoes:
  - Acesso por unidade/atribuicao
  - Nao administra plataforma
  - Permissoes focadas em atendimento

#### Enfermeiro (`SAU_ENFERMEIRO`)

- Nivel: Profissional assistencial
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (casos atribuídos)
- Funcoes:
  - Realizar triagem e evolucao de enfermagem
  - Executar registros permitidos de cuidado
  - Apoiar fluxos assistenciais da unidade
- Atribuicoes:
  - Acesso por escopo da unidade
  - Sem governanca tecnica de plataforma
  - Atuacao operacional assistencial

#### Técnico de Enfermagem (`SAU_TEC_ENF`)

- Nivel: Equipe tecnica
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (rotina operacional)
- Funcoes:
  - Executar registros tecnicos permitidos
  - Apoiar atendimento diario
  - Atualizar informacoes assistenciais basicas
- Atribuicoes:
  - Acesso restrito a campos autorizados
  - Sem visao estrategica municipal
  - Sem permissao de administracao

#### ACS (`SAU_ACS`)

- Nivel: Campo / territorio
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (microarea)
- Funcoes:
  - Acompanhar familias da microarea
  - Registrar visitas e ocorrencias
  - Atualizar dados basicos de acompanhamento
- Atribuicoes:
  - Acesso territorial restrito
  - Sem prontuario completo por padrao
  - Acesso minimo necessario

#### Recepção de Saúde (`SAU_RECEPCAO`)

- Nivel: Atendimento administrativo
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (atendimento)
- Funcoes:
  - Recepcionar e organizar fluxo de pacientes
  - Atualizar cadastro basico
  - Controlar agenda/check-in
- Atribuicoes:
  - Sem acesso ao conteudo clinico detalhado
  - Atuacao administrativa de entrada
  - Escopo restrito a unidade

#### Regulação de Saúde (`SAU_REGULACAO`)

- Nivel: Regulacao e fila
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (regulacao)
- Funcoes:
  - Gerenciar encaminhamentos e prioridades
  - Monitorar filas de atendimento
  - Garantir rastreabilidade de regulacao
- Atribuicoes:
  - Acesso focado em fluxo regulatorio
  - Sem detalhamento clinico alem do necessario
  - Acoes com rastreabilidade operacional

#### Farmácia (`SAU_FARMACIA`)

- Nivel: Farmacia municipal/unidade
- Escopo base: UNIDADE
- Dashboard: Dashboard Saude (dispensacao)
- Funcoes:
  - Controlar dispensacao permitida
  - Acompanhar estoque (quando habilitado)
  - Registrar movimentacoes de farmacia
- Atribuicoes:
  - Acesso ao necessario para dispensacao
  - Sem historico clinico completo por padrao
  - Escopo restrito a unidade

### Educacao

#### Secretário de Educação (`EDU_SECRETARIO`)

- Nivel: Gestao setorial da educacao
- Escopo base: SECRETARIA
- Dashboard: Dashboard Educacao + NEE (escopo secretaria)
- Funcoes:
  - Conduzir politicas educacionais da rede
  - Monitorar matriculas e desempenho
  - Gerir indicadores e relatorios setoriais
- Atribuicoes:
  - Visao ampla da secretaria de educacao
  - Acesso integrado a dados NEE do escopo
  - Sem administracao tecnica global

#### Diretor Escolar (`EDU_DIRETOR`)

- Nivel: Gestao escolar
- Escopo base: UNIDADE
- Dashboard: Dashboard Educacao (escopo unidade escolar)
- Funcoes:
  - Gerenciar operacao da escola
  - Acompanhar turmas, diario e matriculas
  - Validar consistencia dos registros escolares
- Atribuicoes:
  - Acesso integral da escola
  - Sem visao global municipal por padrao
  - Foco operacional e pedagogico

#### Coordenador Pedagógico (`EDU_COORD`)

- Nivel: Coordenacao pedagogica
- Escopo base: UNIDADE
- Dashboard: Dashboard Educacao (turmas/escola)
- Funcoes:
  - Acompanhar planejamento e execucao pedagogica
  - Apoiar professores e evolucao das turmas
  - Monitorar qualidade de lancamentos
- Atribuicoes:
  - Opera no escopo da unidade
  - Sem governanca global da plataforma
  - Atuacao orientada ao processo pedagogico

#### Professor (`PROFESSOR`)

- Nivel: Docencia operacional
- Escopo base: PROFESSOR
- Dashboard: Dashboard Educacao (turmas atribuidas)
- Funcoes:
  - Registrar frequencia, conteudo e avaliacoes
  - Acompanhar alunos da propria turma
  - Executar rotina de diario e notas
- Atribuicoes:
  - Acesso restrito a turmas vinculadas
  - Sem visao da rede completa
  - Nao gerencia configuracoes e usuarios

#### Professor (Educação) (`EDU_PROF`)

- Nivel: Docencia operacional
- Escopo base: PROFESSOR
- Dashboard: Dashboard Educacao (turmas atribuidas)
- Funcoes:
  - Mesmo papel operacional de professor
  - Lancar diario e avaliacoes das turmas
  - Acompanhar progresso dos alunos vinculados
- Atribuicoes:
  - Escopo por atribuicao
  - Sem acesso global da secretaria
  - Permissoes pedagogicas operacionais

#### Secretaria Escolar (`EDU_SECRETARIA`)

- Nivel: Secretaria escolar
- Escopo base: UNIDADE
- Dashboard: Dashboard Educacao (cadastro/matricula)
- Funcoes:
  - Executar matricula e documentacao escolar
  - Atualizar cadastro de aluno
  - Apoiar fluxo administrativo da escola
- Atribuicoes:
  - Acesso a operacoes administrativas da escola
  - Nao substitui atribuicoes pedagogicas do professor
  - Escopo restrito a unidade

#### Transporte Escolar (`EDU_TRANSPORTE`)

- Nivel: Transporte escolar
- Escopo base: UNIDADE
- Dashboard: Dashboard Educacao (rotas e apoio)
- Funcoes:
  - Acompanhar rotas e alunos vinculados
  - Registrar ocorrencias de transporte
  - Suportar gestao de deslocamento escolar
- Atribuicoes:
  - Acesso limitado ao contexto de transporte
  - Sem acesso a avaliacoes/notas
  - Escopo restrito a operacao local

#### Aluno (`ALUNO`)

- Nivel: Portal educacional
- Escopo base: ALUNO
- Dashboard: Dashboard do aluno
- Funcoes:
  - Consultar avisos, arquivos e informacoes pessoais
  - Acompanhar vida escolar liberada
  - Interagir em fluxos do portal
- Atribuicoes:
  - Nao acessa dados de outros alunos
  - Sem acoes administrativas
  - Escopo individual

### NEE (Inclusao)

#### Técnico NEE (`NEE`)

- Nivel: Tecnico NEE (legado)
- Escopo base: NEE
- Dashboard: Dashboard NEE
- Funcoes:
  - Registrar e acompanhar casos NEE
  - Consolidar informacoes tecnicas
  - Apoiar a equipe multiprofissional
- Atribuicoes:
  - Acesso focado no modulo NEE
  - Opera com escopo definido
  - Sem governanca global de plataforma

#### Coordenador Municipal NEE (`NEE_COORD_MUN`)

- Nivel: Coordenacao municipal NEE
- Escopo base: MUNICIPAL
- Dashboard: Dashboard NEE (municipio)
- Funcoes:
  - Coordenar politica municipal de inclusao
  - Acompanhar indicadores consolidados
  - Padronizar fluxos NEE na rede
- Atribuicoes:
  - Visao municipal do NEE
  - Acesso integrado com Educacao e Saude (conforme escopo)
  - Trilha de auditoria obrigatoria

#### Coordenador NEE da Escola (`NEE_COORD_ESC`)

- Nivel: Coordenacao NEE da escola
- Escopo base: UNIDADE
- Dashboard: Dashboard NEE (escola)
- Funcoes:
  - Acompanhar casos NEE da unidade
  - Consolidar plano de apoio individual
  - Apoiar equipe pedagogica no escopo da escola
- Atribuicoes:
  - Acesso restrito aos casos da escola
  - Sem visao municipal completa
  - Registros com rastreabilidade

#### Mediador / Apoio NEE (`NEE_MEDIADOR`)

- Nivel: Mediador / professor de apoio
- Escopo base: UNIDADE
- Dashboard: Dashboard NEE (alunos atribuídos)
- Funcoes:
  - Registrar intervencoes e acompanhamento
  - Apoiar execucao do plano individual
  - Contribuir com evolucao do aluno
- Atribuicoes:
  - Acesso somente a alunos atribuidos
  - Sem acesso a casos externos ao escopo
  - Regra de minimo privilegio

#### Equipe Técnica NEE (`NEE_TECNICO`)

- Nivel: Equipe tecnica multiprofissional
- Escopo base: UNIDADE
- Dashboard: Dashboard NEE (casos atribuídos)
- Funcoes:
  - Emitir pareceres tecnicos
  - Consolidar relatorios de acompanhamento
  - Apoiar tomada de decisao intersetorial
- Atribuicoes:
  - Acesso por atribuicao e escopo
  - Integracao controlada com Educacao/Saude
  - Logs obrigatorios de acesso

### Dados, Integracoes e Portal

#### Gestor de Dados / BI (`DADOS_GESTOR`)

- Nivel: Gestao de dados/BI
- Escopo base: MUNICIPAL
- Dashboard: Dashboard de paineis e indicadores
- Funcoes:
  - Consolidar indicadores gerenciais
  - Publicar paineis e visoes executivas
  - Apoiar decisoes baseadas em dados
- Atribuicoes:
  - Opera paineis e relatorios
  - Nao altera diretamente dado-fonte operacional
  - Escopo municipal por governanca

#### Analista Setorial (`DADOS_ANALISTA`)

- Nivel: Analise setorial
- Escopo base: SECRETARIA
- Dashboard: Dashboard de paineis setoriais
- Funcoes:
  - Analisar indicadores do setor
  - Consolidar relatorios e exportacoes
  - Apoiar auditoria e gestao
- Atribuicoes:
  - Escopo limitado ao setor autorizado
  - Sem administracao de conectores tecnicos
  - Foco analitico

#### Admin TI (Integrações) (`INT_TI`)

- Nivel: Integracoes tecnicas
- Escopo base: MUNICIPAL
- Dashboard: Dashboard de integracoes
- Funcoes:
  - Configurar conectores, chaves e filas
  - Monitorar sincronizacoes e falhas
  - Administrar integracoes criticas
- Atribuicoes:
  - Permissao tecnica de integracoes (admin)
  - Acesso a configuracoes sensiveis de conector
  - Escopo controlado por governanca

#### Admin Gestão (Integrações) (`INT_GESTAO`)

- Nivel: Gestao de integracoes
- Escopo base: MUNICIPAL
- Dashboard: Dashboard de status de integracoes
- Funcoes:
  - Acompanhar status dos conectores
  - Gerenciar habilitacao funcional de integrações
  - Apoiar governanca entre negocio e TI
- Atribuicoes:
  - Permissao de gestao sem admin tecnico total
  - Acesso a relatorios de integracao
  - Sem manutencao profunda de segredos

#### Leitor (Integrações) (`INT_LEITOR`)

- Nivel: Leitura de integracoes
- Escopo base: MUNICIPAL
- Dashboard: Dashboard de integracoes (somente leitura)
- Funcoes:
  - Acompanhar saude dos conectores
  - Consultar relatorios e eventos
  - Apoiar monitoramento institucional
- Atribuicoes:
  - Sem permissao de alterar conectores
  - Acesso apenas de consulta
  - Escopo definido por governanca

#### Admin Portal (`PORTAL_ADMIN`)

- Nivel: Administracao de portal publico
- Escopo base: MUNICIPAL
- Dashboard: Dashboard de publicacoes/portal
- Funcoes:
  - Gerenciar publicacoes institucionais
  - Coordenar conteudo publico municipal
  - Supervisionar operacao editorial
- Atribuicoes:
  - Acesso ao fluxo de publicacao no escopo
  - Governanca editorial da prefeitura
  - Sem papel tecnico de infraestrutura

#### Editor de Conteúdo (`PORTAL_EDITOR`)

- Nivel: Edicao de conteudo
- Escopo base: SECRETARIA
- Dashboard: Dashboard de publicacoes/portal
- Funcoes:
  - Criar e editar conteudos publicos
  - Preparar noticias, paginas e banners
  - Organizar material para aprovacao
- Atribuicoes:
  - Atua no fluxo editorial
  - Publicacao pode depender de aprovador
  - Escopo restrito a conteudo

#### Aprovador de Conteúdo (`PORTAL_APROV`)

- Nivel: Aprovacao editorial
- Escopo base: SECRETARIA
- Dashboard: Dashboard de publicacoes/portal
- Funcoes:
  - Revisar conteudos e aprovar publicacao
  - Garantir conformidade institucional
  - Aplicar padrao comunicacional oficial
- Atribuicoes:
  - Foco em homologacao/publicacao
  - Sem gestao tecnica de infraestrutura
  - Escopo por governanca de comunicacao

#### Designer / Tema (`PORTAL_DESIGN`)

- Nivel: Design e tema
- Escopo base: SECRETARIA
- Dashboard: Dashboard de publicacoes/portal
- Funcoes:
  - Ajustar tema visual e estrutura do portal
  - Gerenciar identidade visual institucional
  - Versionar alteracoes de layout
- Atribuicoes:
  - Foco em tema e apresentacao
  - Sem administracao tecnica da plataforma
  - Escopo de comunicacao institucional

#### Cidadão (Portal) (`CIDADAO`)

- Nivel: Usuario externo
- Escopo base: ALUNO
- Dashboard: Portal do cidadao
- Funcoes:
  - Consultar conteudo e servicos publicos
  - Abrir solicitacoes quando habilitado
  - Acompanhar protocolos no proprio contexto
- Atribuicoes:
- Acesso somente aos proprios dados/solicitacoes
- Nao possui permissao administrativa interna
- Escopo externo e individual

## Funcionalidade Enderecos e Localizacao (Maps)

### Escopo funcional

- Disponivel para `SECRETARIA` e `UNIDADE` no modulo Organizacao.
- Cada entidade pode ter multiplos enderecos ativos, com apenas um principal ativo.
- Campos padronizados: logradouro, numero, bairro, cidade, estado, cep, referencia, area de cobertura e horario.
- Geocodificacao: automatica via provedor configuravel (Google/OSM), com fallback manual.
- Acoes na tela: abrir no Maps, ver rota, copiar endereco e copiar link.

### Regras de permissao por perfil

- Visualizacao:
  - Perfis com `org.view` podem consultar endereco dentro do escopo permitido por municipio/secretaria/unidade.
  - Coordenadas (lat/lng) ficam restritas a perfis com permissao de edicao da entidade.
- Edicao:
  - `ADMIN` e perfis com `org.manage_secretaria`/`org.manage_unidade` podem editar conforme escopo.
  - Perfil com escopo `UNIDADE` pode editar endereco somente da propria unidade.
  - Operadores sem permissao de gestao nao alteram endereco.
- Auditoria:
  - Toda criacao, alteracao, desativacao e reprocessamento de geocode gera evento em `AuditoriaEvento`.
  - Registro inclui usuario, antes/depois, data/hora e entidade afetada.

### Resumo por perfis da matriz RBAC

- `ADMIN`, `MUNICIPAL`, `CAD_GESTOR`:
  - Visao ampla no escopo permitido, com edicao e governanca de endereco.
- `SECRETARIA`, `EDU_SECRETARIO`, `SAU_SECRETARIO`, `CAD_OPER`:
  - Consulta de endereco no escopo setorial; edicao depende de permissao de gestao da entidade.
- `UNIDADE`, `EDU_DIRETOR`, `SAU_DIRETOR`, `EDU_COORD`, `SAU_COORD`:
  - Consulta no escopo da unidade; edicao da propria unidade quando aplicavel.
- Operacionais (`PROFESSOR`, `EDU_PROF`, `SAU_MEDICO`, `SAU_ENFERMEIRO`, `SAU_TEC_ENF`, `SAU_ACS`, `SAU_RECEPCAO`, `SAU_FARMACIA`, `NEE_MEDIADOR`, `NEE_TECNICO`):
  - Uso prioritario de consulta de localizacao para operacao; sem gestao estrutural de endereco.
- Controle e leitura (`AUDITORIA`, `LEITURA`, `INT_LEITOR`, `DADOS_ANALISTA`):
  - Consulta conforme escopo e regras de exposicao; alteracao bloqueada.
- Externo (`CIDADAO`):
  - Consome apenas enderecos publicos expostos no portal, sem acesso a enderecos internos.

## Entregaveis

- Matriz JSON: `docs/rbac_matriz_operacional_gepub.json`
- Matriz CSV: `docs/rbac_matriz_operacional_gepub.csv`
- Relatorio textual: `docs/rbac_relatorio_usuarios_gepub.md`
- Documento funcional Maps: `docs/enderecos_localizacao_maps.md`
