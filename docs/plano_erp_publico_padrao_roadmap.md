# GEPUB - Padrão ERP Público e Roadmap de Evolução

Gerado em: 01/03/2026

## 1. Padrão transversal (obrigatório em todos os módulos)

### 1.1 Central PNCP
- Manter uma central única de integração PNCP com:
- fila de envio,
- status por lote,
- reenvio automático/manual,
- log técnico e funcional,
- trilha de auditoria por registro.
- PNCP como fonte e espelho de tudo que foi publicado (consulta histórica e validação).

### 1.2 Ecossistema de acesso do usuário
- Integrar três frentes como padrão de produto:
- Portal de Assinaturas,
- Portal do Servidor,
- App do Cidadão.
- Integração oficial com WhatsApp para notificações e fluxo de atendimento.

### 1.3 Camada BI e exportações
- BI 100% web com:
- compartilhamento de dashboards,
- exportação de gráficos e relatórios (PDF/CSV/XLSX e formatos avançados por política de módulo),
- filtros por secretaria, unidade e período,
- pacote de dataset com metadados.

### 1.4 Camada GIS (inteligência territorial)
- Suportar mapas para:
- fiscalização,
- saúde e vigilância,
- ouvidoria,
- ativos municipais,
- transparência geográfica.
- Todo módulo com entidade territorial deve consumir endereço georreferenciado (ORG/Maps).

### 1.5 Diretriz de software público e código aberto
- Manter arquitetura auditável, interoperável e com baixa dependência de fornecedor.
- Priorizar documentação técnica, padrões abertos e trilha de mudança.

## 2. Roadmap de aprimoramento (ordem de execução)

1. `Accounts + Core` (RBAC, segurança, portal público, CMS e experiência institucional).
2. `ORG + Processos` (estrutura institucional, escopo, governança e tramitação).
3. `Educação + NEE + Saúde` (integração de dados sensíveis por perfil/atribuição).
4. `Comunicação + Integrações` (eventos, conectores, filas e observabilidade).
5. `Paineis BI + Conversor` (camada executiva analítica e produtividade documental).
6. `Operação contínua` (Compras, Contratos, Financeiro, RH e demais módulos operacionais).

## 3. Padrão único para todas as funções CRUD

Aplicar em toda rota `list/detail/create/update`:

### 3.1 UX
- Busca simples e avançada.
- Filtros salvos por usuário/perfil.
- Ações rápidas por status.
- Exportação mínima: PDF e CSV (ou superior por módulo).
- Timeline auditável por registro.
- Anexos tipificados por categoria.

### 3.2 Governança
- Status funcionais claros e padronizados.
- Trilhas de auditoria para criação, edição, aprovação, publicação e exportação.
- Publicação no portal quando aplicável.

### 3.3 Integração
- Todo registro deve suportar vínculo com pessoa/aluno/paciente/processo/unidade.
- Todo evento relevante deve poder disparar comunicação automática.
- Toda entidade territorial deve integrar com ORG/Maps.

## 4. Documentos de execução por domínio

- Plataforma/Acesso/Site: `docs/modulos_demais_plataforma_acesso_site_funcoes_integracoes.md`
- Serviços (Educação, Avaliações, NEE, Saúde): `docs/modulos_demais_servicos_funcoes_integracoes.md`
- Ferramentas (Integrações, Comunicação, BI, Conversor): `docs/modulos_demais_ferramentas_funcoes_integracoes.md`
- Operação (ORG, Processos, Compras, Contratos, Financeiro etc.): `docs/modulo_operacao_funcoes_integracoes.md`
