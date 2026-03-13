# GEPUB - Matriz de Usuários, Hierarquia e Permissões

Este documento consolida o modelo RBAC do GEPUB com foco em:
- dashboard única por módulo, com dados/ações filtrados por perfil;
- escopo por município, secretaria, unidade e atribuição;
- papéis profissionais para Administração, Saúde, Educação e NEE.

## 1. Princípios

- Mesmo módulo e mesma dashboard para perfis da área.
- O que muda por perfil: dados visíveis, ações permitidas e escopo.
- Controle por ação: `view`, `manage`, `approve/homolog`, `export`, `manage_users`, `configure`.
- Escopo mínimo necessário:
- `municipio`
- `secretaria`
- `unidade`
- `atribuicao_pessoal`

## 1.1 Faixas de capacidade (modelo prático)

- Porte P: até 300 usuários internos ativos / 1.000 cadastrados
- Porte M: até 2.000 usuários internos ativos / 10.000 cadastrados
- Porte G: até 10.000 usuários internos ativos / 50.000 cadastrados
- Portal do cidadão: acesso público escalável (sem vínculo ao limite de usuários internos)

Definições:
- Usuário ativo: autentica e executa ações no sistema.
- Usuário cadastrado: existe no cadastro, com ou sem login operacional.

## 1.2 Tipos de usuário

- Operacional (com login): executa rotinas e fluxos.
- Cadastral (sem login): entidade de vínculo/rastreabilidade.
- Externo (cidadão/portal): acesso a serviços e consultas públicas.

## 1.3 Hierarquia funcional

- Super Admin / Admin Sistema
- Admin Prefeitura / Gestão Central
- Secretário
- Diretor / Coordenador
- Operador / Servidor
- Leitor / Auditoria
- Cidadão

## 2. Famílias de Escopo (base técnica)

As contas especializadas mapeiam para uma família de escopo já usada no sistema:

- `ADMIN`
- `MUNICIPAL`
- `SECRETARIA`
- `UNIDADE`
- `PROFESSOR`
- `ALUNO`
- `NEE`
- `LEITURA`

Esse mapeamento permite padronizar filtros de queryset em todos os módulos sem duplicar regra por tela.

## 3. Papéis profissionais cadastráveis

Além dos papéis legados (`ADMIN`, `MUNICIPAL`, `SECRETARIA`, `UNIDADE`, `PROFESSOR`, `ALUNO`, `NEE`, `LEITURA`), o sistema suporta:

- Governança: `AUDITORIA`, `RH_GESTOR`, `PROTOCOLO`, `CAD_GESTOR`, `CAD_OPER`
- Saúde: `SAU_SECRETARIO`, `SAU_DIRETOR`, `SAU_COORD`, `SAU_MEDICO`, `SAU_ENFERMEIRO`, `SAU_TEC_ENF`, `SAU_ACS`, `SAU_RECEPCAO`, `SAU_REGULACAO`, `SAU_FARMACIA`
- Educação: `EDU_SECRETARIO`, `EDU_DIRETOR`, `EDU_COORD`, `EDU_PROF`, `EDU_SECRETARIA`, `EDU_TRANSPORTE`
- NEE: `NEE_COORD_MUN`, `NEE_COORD_ESC`, `NEE_MEDIADOR`, `NEE_TECNICO`
- Dados/BI: `DADOS_GESTOR`, `DADOS_ANALISTA`
- Integrações: `INT_TI`, `INT_GESTAO`, `INT_LEITOR`
- Portal: `PORTAL_ADMIN`, `PORTAL_EDITOR`, `PORTAL_APROV`, `PORTAL_DESIGN`
- Externo: `CIDADAO`

## 4. Regra de dashboard por módulo

- Educação: secretário/diretor/coordenador/professor usam o mesmo painel de Educação, com escopo filtrado por papel e vínculo.
- Saúde: secretário/diretor/equipe assistencial usam o mesmo painel de Saúde, com visibilidade e ações por perfil.
- NEE: coordenação e equipe técnica usam o mesmo módulo NEE com controle rígido por escopo.
- Demais módulos: mesmo padrão (dashboard única + permissão/escopo).

## 5. Governança de atribuição de usuários

Atribuição de papéis por hierarquia:

- `ADMIN`: pode atribuir qualquer papel.
- `MUNICIPAL`: atribui perfis setoriais/especializados e operacionais.
- `SECRETARIA`: atribui perfis de unidade e operacionais.
- `UNIDADE`: atribui perfis operacionais locais.

## 6. Observações de segurança

- Perfis de leitura/auditoria não recebem permissões de alteração.
- Perfis clínicos/pedagógicos não recebem administração de plataforma por padrão.
- `module_enabled_for_user` continua sendo aplicado para bloquear módulo fora do catálogo ativo do escopo.
- Todas as rotas continuam protegidas por `require_perm(...)` + middleware RBAC.
