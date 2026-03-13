# Revisão de Estrutura, Segurança e Escalabilidade (GEPUB)

Data da revisão: 28/02/2026
Escopo: refatoração de views extensas, hardening de entradas HTTP e padronização de configuração para produção.

## 1. Melhorias aplicadas

### 1.1 Refatoração estrutural (views extensas)
- Arquivo alvo principal: `apps/core/views_portal.py`.
- Extraído conteúdo estático e catálogos para `apps/core/portal_specs.py`.
- Redução de complexidade em:
  - Conteúdo institucional padrão.
  - Fallbacks de slides/steps/services.
  - Mapeamento das seções de transparência.
  - Conteúdo estático da documentação pública.
- Benefício:
  - Menos acoplamento entre regra de renderização e conteúdo estático.
  - Menor risco de regressão ao editar textos/catálogos.
  - Melhor manutenção para crescimento de módulos.

### 1.2 Hardening das APIs do módulo de comunicação
- Arquivo alvo: `apps/comunicacao/views.py`.
- Controles adicionados:
  - Limite de payload JSON por requisição (`COMUNICACAO_API_MAX_JSON_BODY_BYTES`).
  - Tratamento explícito para JSON inválido e payload acima do limite.
  - Parse seguro de inteiros (`_safe_int`) para evitar `500` por parâmetros inválidos.
  - Validação de `event_key` por regex (`^[a-z0-9_.:-]{3,80}$`).
  - Normalização de prioridade para valores válidos do enum.
  - Limitação de tamanho de assunto/corpo em envios manuais.
- Benefício:
  - Redução de risco de DoS por payload excessivo.
  - Evita erros de execução por entrada malformada.
  - Padroniza contratos de API para integrações futuras.

### 1.3 Hardening de URL pública por domínio customizado
- Arquivo alvo: `apps/core/views_public_admin.py`.
- `_portal_public_url` agora sanitiza host (remove protocolo, barra e valida caracteres permitidos).
- Em caso de domínio inválido, fallback para rota institucional interna.
- Benefício:
  - Evita geração de URLs malformadas em ações administrativas.

### 1.4 Segurança por configuração
- Arquivo alvo: `config/settings.py`.
- Novos parâmetros:
  - `SECURE_CROSS_ORIGIN_OPENER_POLICY` (default `same-origin`).
  - `SECURE_CROSS_ORIGIN_RESOURCE_POLICY` (default `same-origin`).
  - `COMUNICACAO_API_MAX_JSON_BODY_BYTES` (default `262144`).
- Arquivo alvo: `.env.example`.
  - `DJANGO_DEBUG=false` como padrão seguro.
  - Variáveis de segurança e limite da API documentadas.

## 2. Validação executada

Comandos executados:
- `python manage.py check`
- `python manage.py test apps.comunicacao.tests`
- `python manage.py test apps.core.tests.RBACTestCase`
- `python manage.py test apps.core.tests --failfast`

Resultado:
- Todos os testes acima passaram.
- `check` sem erros.

## 3. Observações de produção

No ambiente local atual, `check --deploy` ainda indica alertas quando `DJANGO_DEBUG=true` e cookies/SSL não forçados via ambiente.

Para produção, garantir:
- `DJANGO_DEBUG=false`
- `DJANGO_SECURE_SSL_REDIRECT=true`
- `DJANGO_SESSION_COOKIE_SECURE=true`
- `DJANGO_CSRF_COOKIE_SECURE=true`
- `DJANGO_SECURE_HSTS_SECONDS=31536000`
- Proxy reverso enviando `X-Forwarded-Proto=https`

## 4. Próximos passos recomendados

1. Refatorar `apps/core/views_public_admin.py` para serviços de domínio (CRUD genérico por entidade + serializers de saída).
2. Introduzir rate limit por IP/usuário nos endpoints de comunicação.
3. Adicionar testes de segurança para payload inválido e limites de body na API de comunicação.
4. Adotar checklist de release com `manage.py check --deploy` obrigatório em CI para ambiente de produção.
