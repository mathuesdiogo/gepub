# GEPUB - Demais Módulos (Plataforma, Acesso e Site): Funções e Integrações

Gerado em: 01/03/2026

## Accounts (`apps.accounts`)

Objetivo:
- Autenticação por código de acesso, segurança de login e gestão de usuários internos.

Funções (rotas nomeadas):
- `login`: autentica usuário por código/senha.
- `logout`: encerra sessão.
- `alterar_senha`: troca de senha (inclui primeiro acesso).
- `meu_perfil`: edição de perfil do usuário logado.
- `usuarios_list`: lista de usuários do escopo.
- `usuario_create`: criação de usuário.
- `usuario_detail`: detalhe de usuário.
- `usuario_update`: edição de usuário.
- `usuario_toggle_ativo`: ativa/desativa usuário.
- `usuario_toggle_bloqueio`: bloqueia/desbloqueia usuário.
- `usuario_reset_codigo`: regenera código de acesso.
- `usuario_reset_senha`: redefine senha.
- `users_autocomplete`: sugestão/autocomplete de usuários.

Integrações com outros módulos:
- `core` (dashboard, RBAC, middleware de troca obrigatória de senha).
- Todos os módulos que dependem de usuário/perfil/escopo.

Como funciona:
- Login valida limites de tentativa e lock temporário.
- Perfil define escopo (município/secretaria/unidade) e permissões operacionais.

---

## Billing (`apps.billing`)

Objetivo:
- Gestão da assinatura municipal, limites de uso, upgrades e faturamento.

Funções (rotas nomeadas):
- `index`: roteia para visão de plano (ou admin).
- `meu_plano`: painel da assinatura ativa e métricas de consumo.
- `solicitar_upgrade`: abre solicitação de upgrade/addon/troca de plano.
- `simulador`: simulação de plano/custo.
- `assinaturas_admin`: lista administrativa de assinaturas.
- `assinatura_admin_detail`: detalhe administrativo com aprovações e bônus de quota.
- `fatura_pdf`: exportação da fatura em PDF.

Integrações com outros módulos:
- `org` (município e onboarding).
- `educacao` e demais módulos que consomem limites de plano.
- `core` (exports e controle de permissão).

Como funciona:
- Assinatura define limites efetivos (secretarias/usuários/alunos/atendimentos).
- Upgrade aprovado altera capacidade e afeta cobrança/fatura.

---

## Core (`apps.core`)

Objetivo:
- Núcleo da plataforma: portal público, dashboard interno, administração institucional e editor do site público.

### 1) Portal e páginas públicas

Funções:
- `institucional_public`
- `home`
- `portal_pagina_public`
- `portal_noticias_public`
- `portal_noticia_detail_public`
- `portal_ouvidoria_public`
- `portal_licitacoes_public`
- `portal_contratos_public`
- `portal_diario_public`
- `portal_concursos_public`
- `portal_camara_public`
- `portal_saude_public`
- `portal_educacao_public`
- `sobre_public`
- `funcionalidades_public`
- `por_que_usar_public`
- `documentacao_public`
- `transparencia_public`

O que fazem:
- Entregam o portal público institucional e páginas de transparência/documentação.

### 2) Dashboard e utilidades internas

Funções:
- `dashboard`
- `dashboard_aluno`
- `aviso_create`
- `arquivo_create`
- `go_code`
- `go_code_path`
- `guia_telas`

O que fazem:
- Dashboard dinâmico por perfil (admin, municipal, professor, aluno etc.).
- Criação de avisos/arquivos para painéis.
- Navegação por código de tela.

### 3) Administração institucional (site comercial/institucional)

Funções:
- `institutional_admin`
- `institutional_slide_create`
- `institutional_slide_update`
- `institutional_slide_delete`
- `institutional_method_step_create`
- `institutional_method_step_update`
- `institutional_method_step_delete`
- `institutional_service_card_create`
- `institutional_service_card_update`
- `institutional_service_card_delete`

O que fazem:
- Gerenciam conteúdo institucional do GEPUB (hero, método, serviços).

### 4) Administração do portal da prefeitura (CMS)

Funções:
- `publicacoes_admin`
- `publicacoes_theme_editor`
- `publicacoes_theme_autosave`
- `publicacoes_theme_preview`
- `publicacoes_config_edit`
- `noticia_create`
- `noticia_update`
- `noticia_delete`
- `banner_create`
- `banner_update`
- `banner_delete`
- `pagina_create`
- `pagina_update`
- `pagina_delete`
- `menu_create`
- `menu_update`
- `menu_delete`
- `home_bloco_create`
- `home_bloco_update`
- `home_bloco_delete`
- `transparencia_arquivo_create`
- `transparencia_arquivo_update`
- `transparencia_arquivo_delete`
- `diario_create`
- `diario_update`
- `diario_delete`
- `concurso_create`
- `concurso_update`
- `concurso_delete`
- `concurso_etapa_create`
- `concurso_etapa_delete`
- `camara_materia_create`
- `camara_materia_update`
- `camara_materia_delete`
- `camara_sessao_create`
- `camara_sessao_update`
- `camara_sessao_delete`

O que fazem:
- Operam o CMS público do município: notícias, banners, páginas, menus, transparência, diário, concursos e câmara.

Integrações com outros módulos:
- `org` (escopo municipal e domínio público).
- `accounts`/RBAC para permissão de edição/publicação.
- `compras`, `contratos`, `financeiro`, `rh` para dados exibidos no portal de transparência.

Como funciona:
- `core` recebe dados de módulos setoriais e publica visão pública/gestão central.
- A experiência pública e a experiência interna compartilham governança de conteúdo.

Observação:
- `validar_documento` aparece como comentário histórico em `urls.py`, sem rota ativa no momento.

---

## App Pessoas (`apps.pessoas`)

Status atual:
- App existente no repositório, sem `urls.py` ativo no roteamento principal.
- Não possui funções públicas expostas por rota neste momento.

---

## Backlog de Evolução (Padrão ERP Público)

Diretriz transversal aplicada a todas as funções deste documento:
- Central PNCP com fila, reenvio, tratamento de erros e logs.
- Ecossistema integrado: Portal de Assinaturas, Portal do Servidor, App do Cidadão e WhatsApp oficial.
- Camada BI e exportações padronizadas por perfil.
- Camada GIS para visão territorial dos serviços.
- Princípios de software público/código aberto (auditoria, interoperabilidade e independência).

### Accounts (`apps.accounts`) - função por função

- `login` - Aprimorar:
- MFA opcional por e-mail/WhatsApp.
- Detecção de risco (tentativas anômalas, bloqueio progressivo, challenge adicional).
- `logout` - Adicionar:
- Log estruturado de saída de sessão (usuário, horário, IP, device hash).
- `alterar_senha` - Aprimorar:
- Política de senha forte, histórico de senhas e expiração opcional por perfil.
- `meu_perfil` - Adicionar:
- Preferências de notificação (canal e janela de horário).
- `usuarios_list`, `usuario_create`, `usuario_detail`, `usuario_update`, `usuario_toggle_ativo`, `usuario_toggle_bloqueio`, `usuario_reset_codigo`, `usuario_reset_senha`, `users_autocomplete` - Aprimorar:
- Presets RBAC por função (admin municipal, secretário, diretor, professor, profissional de saúde, operador).
- Matriz de permissão com escopo por município/secretaria/unidade.
- Auditoria total de administração de contas e permissões.

### Billing (`apps.billing`) - função por função

- `meu_plano` - Aprimorar:
- Medidores por módulo (Educação, Saúde, NEE, BI, Comunicação, Integrações).
- `solicitar_upgrade` - Adicionar:
- Fluxo completo: solicitado -> em análise -> aprovado -> aplicado -> refletido em fatura.
- `simulador` - Aprimorar:
- Simulação de add-ons (WhatsApp oficial, GIS, BI avançado e integrações PNCP).
- `assinaturas_admin`, `assinatura_admin_detail`, `fatura_pdf` - Adicionar:
- Histórico de alterações de plano com trilha de auditoria.
- Política de bônus por município e controle de governança financeira.

### Core (`apps.core`) - função por função

Portal público e páginas institucionais:
- `home`, `portal_*_public`, `sobre_public`, `funcionalidades_public`, `por_que_usar_public`, `documentacao_public`, `transparencia_public`, `institucional_public` - Aprimorar:
- SEO técnico, acessibilidade, cache e performance.
- Transparência com filtros, exportações e hash de integridade da publicação.
- Publicação de eventos internos por módulos operacionais.

Dashboard e utilidades:
- `dashboard`, `dashboard_aluno`, `aviso_create`, `arquivo_create`, `go_code`, `go_code_path`, `guia_telas` - Adicionar:
- Central global de pendências por perfil.
- Guia de telas como documentação viva (help contextual por página).

Admin institucional:
- `institutional_admin`, `institutional_slide_*`, `institutional_method_step_*`, `institutional_service_card_*` - Aprimorar:
- Builder de seções em blocos com preview e versionamento.

CMS do portal municipal:
- `publicacoes_admin`, `publicacoes_theme_editor`, `publicacoes_theme_autosave`, `publicacoes_theme_preview`, `publicacoes_config_edit`, `noticia_*`, `banner_*`, `pagina_*`, `menu_*`, `home_bloco_*`, `transparencia_arquivo_*`, `diario_*`, `concurso_*`, `concurso_etapa_*`, `camara_materia_*`, `camara_sessao_*` - Aprimorar:
- Workflow editorial: rascunho -> revisão -> publicado -> arquivado.
- Permissões por seção, agendamento de publicação e trilha de versão/publicação.
- Integração automática com módulos de compras, contratos e diário oficial quando aplicável.
