# Módulo de Comunicação Automática (GEPUB)

## Visão geral
Módulo para envio automatizado e auditável de comunicações por:
- E-mail
- SMS
- WhatsApp oficial (fluxo compatível com provider oficial, com envio mock no ambiente atual)

Suporta:
- templates por evento/canal
- fila de jobs com tentativas
- fallback entre canais
- logs de entrega e falha
- permissões por perfil e escopo

## Rotas do módulo
- Painel: `GET /comunicacao/`
- Processar fila: `POST /comunicacao/jobs/processar/`

## Endpoints API
- `POST /comunicacao/notifications/send`
  - Disparo manual/campanha.
- `POST /comunicacao/notifications/trigger`
  - Disparo por evento interno.
- `GET /comunicacao/notifications/logs`
  - Consulta de logs de entrega.
- `GET /comunicacao/templates`
  - Lista templates.
- `POST /comunicacao/templates`
  - Cria template.
- `PUT|POST /comunicacao/templates/{id}`
  - Atualiza template.
- `GET /comunicacao/channels/config`
  - Lista configurações de canal.
- `POST /comunicacao/channels/config`
  - Cria/atualiza configuração de canal.

## Modelo de dados
- `NotificationChannelConfig`: configuração de provedor por escopo.
- `NotificationTemplate`: template por `event_key` + canal.
- `NotificationPreference`: preferências por usuário/aluno/contato.
- `NotificationJob`: fila assíncrona com fallback e tentativas.
- `NotificationLog`: trilha de envio por tentativa.

## Permissões RBAC
- `comunicacao.view`
- `comunicacao.manage`
- `comunicacao.send`
- `comunicacao.audit`
- `comunicacao.admin`

## Observações
- Para `SMS` e `WhatsApp`, o envio atual usa dispatcher mock para operação sem credenciais reais.
- Para `EMAIL`, usa `send_mail` do Django.
- Eventos sensíveis (`nee_sensitive=true`) forçam corpo neutro para evitar exposição de dados clínicos/NEE.
