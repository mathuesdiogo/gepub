# GEPUB - Endereços e Localização (Maps)

Gerado em: 2026-03-01

## Objetivo

Padronizar enderecos de Secretarias e Unidades para permitir operacao, localizacao e rastreabilidade institucional em todos os modulos.

## Escopo implementado

- Entidades atendidas: `SECRETARIA` e `UNIDADE`.
- Tabela central: `org.Address` (modelo polimorfico por `entity_type` + `entity_id`).
- Campos principais:
  - Endereco completo (`logradouro`, `numero`, `bairro`, `cidade`, `estado`, `cep`, `pais`)
  - Contexto operacional (`reference_point`, `coverage_area`, `opening_hours`)
  - Geolocalizacao (`latitude`, `longitude`, `geocode_provider`, `geocode_status`)
  - Governanca (`is_primary`, `is_public`, `is_active`, `created_by`, `updated_by`)
- Regra estrutural: apenas 1 endereco principal ativo por entidade.

## APIs

- `GET /org/addresses?entity_type=...&entity_id=...`
- `POST /org/addresses/novo/`
- `PUT /org/addresses/{id}/`
- `DELETE /org/addresses/{id}/remover/` (soft delete)
- `POST /org/addresses/{id}/geocode/`

## Geocodificacao e Maps

- Endereco e normalizado no backend antes de salvar.
- Sem coordenadas manuais, o sistema tenta geocode automatico.
- Provedor configuravel via ambiente:
  - `GEPUB_GEOCODE_PROVIDER=google|osm`
  - `GOOGLE_GEOCODING_API_KEY` (quando provider google)
  - `GEPUB_GEOCODE_TIMEOUT_SECONDS`
  - `GEPUB_GEOCODE_USER_AGENT`
- URLs padrao:
  - Maps: `https://www.google.com/maps?q=lat,lng` ou `.../search/?query=...`
  - Rota: `https://www.google.com/maps/dir/?api=1&destination=...`

## Regras de acesso

### Visualizacao

- Perfil interno com `org.view`: pode consultar endereco da entidade dentro do escopo RBAC.
- Coordenadas (lat/lng): exibidas somente para perfis com capacidade de edicao da entidade.

### Edicao

- `ADMIN`: pode editar qualquer endereco no escopo.
- Perfis com `org.manage_secretaria`/`org.manage_unidade`: editam conforme escopo RBAC.
- Perfil com escopo `UNIDADE`: edita somente o endereco da propria unidade.
- Perfis operacionais sem permissao de gestao: apenas consulta.

### Auditoria

- Eventos gravados em `core.AuditoriaEvento`:
  - `ADDRESS_CREATED`
  - `ADDRESS_UPDATED`
  - `ADDRESS_DEACTIVATED`
  - `ADDRESS_GEOCODE_REPROCESS`
- Cada evento registra usuario, antes/depois, entidade e timestamp.

## Interface

- Tela de detalhe de Secretaria: novo bloco **Localizacao** com acao de cadastro/edicao.
- Tela de detalhe de Unidade: mesmo bloco, com suporte a referencia, cobertura e horario.
- Acoes disponiveis no card:
  - Abrir no Maps
  - Ver rota
  - Copiar endereco
  - Copiar link
  - Reprocessar geocode (para quem pode editar)

## Resumo de perfis e atribuicoes na funcionalidade

- Gestao central (`ADMIN`, `MUNICIPAL`, `CAD_GESTOR`): governanca completa de endereco no escopo.
- Gestao setorial (`SECRETARIA`, `EDU_SECRETARIO`, `SAU_SECRETARIO`): consulta ampla do escopo e edicao quando habilitada por permissao.
- Gestao local (`UNIDADE`, diretores e coordenadores de unidade): consulta local e edicao da propria unidade.
- Operacionais (profissionais de saude/educacao/NEE, operadores comuns): consulta contextual para operacao diaria.
- Controle (`AUDITORIA`, `LEITURA`, `INT_LEITOR`, `DADOS_ANALISTA`): consulta e exportacao sob regras de escopo.
- Externo (`CIDADAO`): apenas consumo de enderecos publicos, sem alteracao.
