# GEPUB - Recapitulação de Planos e Implantação do App Câmara

Data: 07/03/2026

## 1. Recapitulação dos planos (acessos por maturidade)

### GEPUB Essencial
- Gestão interna da prefeitura.
- Estrutura administrativa, usuários/perfis, protocolo e operação interna.

### GEPUB Gestão Integrada
- Tudo do Essencial.
- Portal oficial da prefeitura (páginas, notícias, banners, mídia, menu, downloads).

### GEPUB Transformação Digital
- Tudo do Gestão Integrada.
- Portal da Transparência (publicações, consultas, histórico, e-SIC).

### GEPUB Governo Completo
- Tudo do Transformação Digital.
- Portal/App da Câmara Municipal integrado ao ecossistema.

## 2. O que já existia no código antes desta entrega

- Catálogo comercial dos planos já alinhado com os 4 níveis (incluindo Câmara no plano Governo Completo) em `apps/billing/services.py`.
- Portal público da Câmara já disponível em `/camara/` (host público), com dados de:
  - matérias legislativas (`core.CamaraMateria`)
  - sessões (`core.CamaraSessao`)
- Central de publicações já permitia CRUD básico de matérias e sessões da Câmara dentro do app `core`.

## 3. O que foi implementado nesta entrega (novo App Câmara)

### 3.1 Novo app dedicado
- Criado `apps/camara` com:
  - `models.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, `apps.py`
  - migração inicial `apps/camara/migrations/0001_initial.py`
- Rota administrativa do app: `/camara-admin/`

### 3.2 Entidades novas (tabelas)
Foram criadas as estruturas pedidas para o novo domínio legislativo:
- `camara_config`
- `vereadores`
- `mesa_diretora`
- `comissoes`
- `comissao_membros`
- `sessoes`
- `sessao_documentos`
- `proposicoes`
- `proposicao_autores`
- `proposicao_tramitacoes`
- `atas`
- `pautas`
- `noticias_camara`
- `agenda_legislativa`
- `transmissoes`
- `transparencia_camara_items`
- `documentos_camara`
- complementar: `camara_ouvidoria_manifestacoes`

### 3.3 Campos de escopo/padrão
- Base comum aplicada nas entidades do app:
  - `tenant_id` (via FK de município com `db_column='tenant_id'`)
  - `contexto` (`prefeitura`/`camara`)
  - `created_by`
  - `updated_by`
  - `status`
  - `published_at`

### 3.4 Permissões da Câmara
Adicionadas permissões granulares no RBAC:
- `camara.view`
- `camara.manage`
- `camara.sessoes.manage`
- `camara.proposicoes.manage`
- `camara.cms.manage`
- `camara.transparencia.manage`
- `camara.transmissoes.manage`

Além disso:
- Namespace `camara` integrado no middleware de RBAC.
- Perfis especializados de Câmara adicionados (admin, secretaria, comunicação, transparência, vereador, auditor).

### 3.5 Integração com plano e módulos
- App Câmara integrado ao controle de módulo/plano (`module_access`):
  - módulo `camara` incluído em `MANAGED_MODULES`
  - gate por features do plano CAMARA ativado
- Views do app Câmara verificam disponibilidade do plano antes de liberar acesso.

### 3.6 UI e navegação
- Dashboard do app Câmara com cards por módulo.
- CRUD modular (lista + criar + editar + remover) para os módulos legislativos.
- Link da Câmara adicionado ao menu lateral administrativo.
- Card do módulo Câmara adicionado ao portal interno de módulos (`core/portal`).

### 3.7 Portal público da Câmara
- `portal_camara_public` evoluído para ler dados do novo app (`apps.camara`) com fallback para legado `core`.
- Página pública da Câmara atualizada para também exibir:
  - vereadores
  - comissões
  - transmissões
  - busca textual

### 3.8 Edição intuitiva por portal
- Sidebar reorganizada em `Portais Públicos` com atalhos separados para:
  - `Portal da Prefeitura`
  - `Portal da Transparência`
  - `Portal da Câmara`
- `publicacoes_admin` passou a mostrar foco de edição (`prefeitura`, `transparencia`, `todos`) para indicar claramente onde o conteúdo será publicado.
- Seções de Câmara no `publicacoes_admin` ficaram sinalizadas como legado e com atalho direto para o novo `App Câmara`.
- Telas do `App Câmara` exibem aviso explícito de contexto de publicação legislativa.

## 4. Compatibilidade e não quebra

- O legado de Câmara em `core` foi preservado.
- O novo app foi adicionado de forma paralela e compatível.
- Fallback mantém comportamento anterior caso o novo conteúdo ainda não tenha sido cadastrado.

## 5. Validação executada

- `python manage.py makemigrations camara` (migração gerada)
- `python manage.py migrate camara` (migração aplicada)
- `python manage.py check` (sem erros)
- `python manage.py test apps.camara` (0 testes, sem falhas de carregamento)
- `python manage.py sqlmigrate camara 0001` (SQL gerado)
