from __future__ import annotations

INSTITUTIONAL_DEFAULT_CONTENT = {
    "marca_nome": "GEPUB",
    "marca_logo_url": "",
    "nav_metodo_label": "Método",
    "nav_planos_label": "Planos",
    "nav_servicos_label": "Serviços",
    "nav_simulador_label": "Simulador",
    "botao_login_label": "Entrar",
    "hero_kicker": "UM SISTEMA SOB MEDIDA PARA PREFEITURAS",
    "hero_titulo": (
        "Elaboramos a estratégia digital da sua gestão para integrar secretarias, "
        "acelerar resultados e ampliar controle público."
    ),
    "hero_descricao": (
        "O GEPUB conecta Educação, Saúde, NEE e estrutura administrativa em uma única "
        "plataforma SaaS, com onboarding automático, auditoria e gestão de planos por município."
    ),
    "hero_cta_primario_label": "SIMULAR PLANO",
    "hero_cta_primario_link": "#simulador",
    "hero_cta_secundario_label": "VISUALIZAR PLANOS",
    "hero_cta_secundario_link": "#planos",
    "oferta_tag": "ESTRUTURA PRONTA PARA LICITAÇÃO",
    "oferta_titulo": (
        "Essa pode ser a virada da sua gestão: um SaaS único para substituir contratos "
        "fragmentados e reduzir retrabalho entre secretarias."
    ),
    "oferta_descricao": (
        "Contratação em formato público com licença SaaS, implantação, migração, treinamento, "
        "suporte e manutenção, com vigência mínima de 12 meses e reajuste anual INPC/IPCA."
    ),
    "metodo_kicker": "MÉTODO GEPUB",
    "metodo_titulo": "Um único fluxo para implantar com governança e escalar com previsibilidade.",
    "metodo_cta_label": "QUERO AVALIAR MEU MUNICÍPIO",
    "metodo_cta_link": "#simulador",
    "planos_kicker": "PLANOS MUNICIPAIS",
    "planos_titulo": "O GEPUB respeita o porte do município e cresce conforme a operação.",
    "planos_descricao": (
        "Você contrata uma base mensal com limites objetivos e adicionais transparentes. "
        "Sem contrato confuso, sem variação imprevisível de custo."
    ),
    "planos_cta_label": "SIMULAR AGORA",
    "planos_cta_link": "#simulador",
    "servicos_kicker": "NOSSOS SERVIÇOS",
    "servicos_titulo": "Tudo que entregamos para operação municipal de ponta a ponta.",
    "servicos_cta_label": "FALE COM O TIME GEPUB",
    "servicos_cta_link": "#simulador",
    "rodape_texto": "© GEPUB • Gestão Estratégica Pública. Todos os direitos reservados.",
}

DEFAULT_INSTITUTIONAL_SLIDES = [
    {
        "titulo": "Time GEPUB",
        "subtitulo": "Especialistas em operação municipal digital",
        "descricao": "Consultoria de implantação e acompanhamento contínuo.",
        "icone": "fa-solid fa-user-tie",
        "imagem_url": "",
        "cta_label": "",
        "cta_link": "",
    },
    {
        "titulo": "Onboarding por secretaria",
        "subtitulo": "Educação, Saúde, NEE e mais",
        "descricao": "Ative módulos com templates e perfis padronizados.",
        "icone": "fa-solid fa-wand-magic-sparkles",
        "imagem_url": "",
        "cta_label": "",
        "cta_link": "",
    },
    {
        "titulo": "Cobrança previsível",
        "subtitulo": "Plano base + limites + overage",
        "descricao": "Fatura mensal por competência e gestão de upgrades.",
        "icone": "fa-solid fa-file-invoice-dollar",
        "imagem_url": "",
        "cta_label": "",
        "cta_link": "",
    },
]

DEFAULT_INSTITUTIONAL_STEPS = [
    {
        "titulo": "1. Diagnóstico municipal",
        "descricao": "Mapeamos secretarias, unidades e metas da prefeitura.",
        "icone": "fa-solid fa-map-location-dot",
    },
    {
        "titulo": "2. Configuração do plano",
        "descricao": "Definimos limites, módulos e política de crescimento.",
        "icone": "fa-solid fa-sliders",
    },
    {
        "titulo": "3. Onboarding assistido",
        "descricao": "Ativamos secretarias, perfis e trilhas de onboarding.",
        "icone": "fa-solid fa-rocket",
    },
    {
        "titulo": "4. Gestão e expansão",
        "descricao": "Monitoramos consumo, BI e upgrades com cálculo claro.",
        "icone": "fa-solid fa-chart-pie",
    },
]

DEFAULT_INSTITUTIONAL_SERVICES = [
    {
        "titulo": "Organização",
        "descricao": "Municípios, secretarias, unidades e setores com governança.",
        "icone": "fa-solid fa-sitemap",
    },
    {
        "titulo": "Educação",
        "descricao": "Matrícula, turmas, diário, indicadores e relatórios.",
        "icone": "fa-solid fa-school",
    },
    {
        "titulo": "Saúde",
        "descricao": "Unidades, profissionais, agenda e atendimentos clínicos.",
        "icone": "fa-solid fa-notes-medical",
    },
    {
        "titulo": "NEE",
        "descricao": "Planos de acompanhamento e relatórios institucionais.",
        "icone": "fa-solid fa-universal-access",
    },
    {
        "titulo": "Planos e cobrança",
        "descricao": "Assinatura municipal, overage e fatura por competência.",
        "icone": "fa-solid fa-file-invoice-dollar",
    },
    {
        "titulo": "Auditoria e LGPD",
        "descricao": "Controle de acesso, trilhas críticas e rastreabilidade.",
        "icone": "fa-solid fa-shield-halved",
    },
]

TRANSPARENCIA_SECTION_SPECS = [
    {
        "titulo": "INFORMAÇÕES INSTITUCIONAIS",
        "descricao": "Normas próprias e publicações oficiais do município.",
        "itens": [
            {
                "titulo": "Atos Normativos Próprios",
                "descricao": "Leis, decretos, portarias e atos institucionais.",
                "capacidade_origem": "MANUAL",
                "categorias": ["ATOS_NORMATIVOS"],
            },
            {
                "titulo": "Diário Oficial",
                "descricao": "Edições oficiais publicadas pelo município.",
                "capacidade_origem": "MISTA",
                "auto_key": "diarios",
                "categorias": ["DIARIO_OFICIAL"],
                "url_name": "core:portal_diario_public",
            },
        ],
    },
    {
        "titulo": "EXECUÇÃO ORÇAMENTÁRIA",
        "descricao": "Execução de despesas e informações de dívida ativa.",
        "itens": [
            {
                "titulo": "Execução Orçamentária Geral 2025",
                "descricao": "Movimentações de empenho/liquidação/pagamento do exercício de 2025.",
                "capacidade_origem": "MISTA",
                "auto_key": "exec_2025",
                "categorias": ["EXEC_ORC_GERAL_2025"],
            },
            {
                "titulo": "Execução Orçamentária 2024",
                "descricao": "Histórico da execução orçamentária do exercício de 2024.",
                "capacidade_origem": "MISTA",
                "auto_key": "exec_2024",
                "categorias": ["EXEC_ORC_2024"],
            },
            {
                "titulo": "Empresas Com Dívida Ativa",
                "descricao": "Contribuintes com lançamentos tributários pendentes.",
                "capacidade_origem": "MISTA",
                "auto_key": "divida_ativa",
                "categorias": ["EMPRESAS_DIVIDA_ATIVA"],
            },
        ],
    },
    {
        "titulo": "CONVÊNIOS, TRANSFERÊNCIAS E EMENDAS",
        "descricao": "Publicações sobre recursos recebidos, repassados e acordos firmados.",
        "itens": [
            {
                "titulo": "Emendas Parlamentares",
                "descricao": "Emendas cadastradas e sua aplicação.",
                "capacidade_origem": "MANUAL",
                "categorias": ["EMENDAS_PARLAMENTARES"],
            },
            {
                "titulo": "Convênios E Transferências Recebidas",
                "descricao": "Termos e repasses recebidos de outros entes.",
                "capacidade_origem": "MANUAL",
                "categorias": ["CONVENIOS_RECEBIDOS"],
            },
            {
                "titulo": "Convênios E Transferências Realizadas",
                "descricao": "Transferências e convênios concedidos pelo município.",
                "capacidade_origem": "MANUAL",
                "categorias": ["CONVENIOS_REALIZADOS"],
            },
            {
                "titulo": "Acordos Firmados Sem Transferências De Recursos",
                "descricao": "Instrumentos de cooperação sem repasse financeiro.",
                "capacidade_origem": "MANUAL",
                "categorias": ["ACORDOS_SEM_TRANSFERENCIA"],
            },
        ],
    },
    {
        "titulo": "RECURSOS HUMANOS",
        "descricao": "Quadro de pessoal e informações de folha e vínculos.",
        "itens": [
            {
                "titulo": "Folha De Pagamento",
                "descricao": "Competências processadas no módulo de Folha.",
                "capacidade_origem": "MISTA",
                "auto_key": "folha",
                "categorias": ["RH_FOLHA_PAGAMENTO"],
            },
            {
                "titulo": "Cargos",
                "descricao": "Estrutura de cargos em uso no quadro funcional.",
                "capacidade_origem": "MISTA",
                "auto_key": "cargos",
                "categorias": ["RH_CARGOS"],
            },
            {
                "titulo": "Estagiários",
                "descricao": "Registros de estagiários identificados no cadastro funcional.",
                "capacidade_origem": "MISTA",
                "auto_key": "estagiarios",
                "categorias": ["RH_ESTAGIARIOS"],
            },
            {
                "titulo": "Terceirizados",
                "descricao": "Vínculos com regime CLT/terceirização registrados.",
                "capacidade_origem": "MISTA",
                "auto_key": "terceirizados",
                "categorias": ["RH_TERCEIRIZADOS"],
            },
            {
                "titulo": "Concursos",
                "descricao": "Concursos e seletivos publicados no portal.",
                "capacidade_origem": "MISTA",
                "auto_key": "concursos",
                "categorias": ["RH_CONCURSOS"],
                "url_name": "core:portal_concursos_public",
            },
            {
                "titulo": "Servidores",
                "descricao": "Servidores cadastrados no módulo de RH.",
                "capacidade_origem": "MISTA",
                "auto_key": "servidores",
                "categorias": ["RH_SERVIDORES"],
            },
        ],
    },
    {
        "titulo": "DIÁRIAS",
        "descricao": "Pagamentos de diárias e tabela de referência vigente.",
        "itens": [
            {
                "titulo": "Diárias",
                "descricao": "Relação de concessões e pagamentos de diárias.",
                "capacidade_origem": "MANUAL",
                "categorias": ["DIARIAS"],
            },
            {
                "titulo": "Tabelas De Valores Da Diária",
                "descricao": "Tabela oficial de valores e regras de concessão.",
                "capacidade_origem": "MANUAL",
                "categorias": ["DIARIAS_TABELA_VALORES"],
            },
        ],
    },
    {
        "titulo": "LICITAÇÕES E CONTRATOS",
        "descricao": "Contratações públicas, aditivos, fiscalização e sanções.",
        "itens": [
            {
                "titulo": "Licitações",
                "descricao": "Processos licitatórios do módulo de Compras.",
                "capacidade_origem": "MISTA",
                "auto_key": "licitacoes",
                "categorias": ["LICITACOES"],
                "url_name": "core:portal_licitacoes_public",
            },
            {
                "titulo": "Contratos",
                "descricao": "Contratos administrativos vinculados ao município.",
                "capacidade_origem": "MISTA",
                "auto_key": "contratos",
                "categorias": ["CONTRATOS"],
                "url_name": "core:portal_contratos_public",
            },
            {
                "titulo": "Aditivos De Contratos",
                "descricao": "Aditivos de prazo, valor e escopo.",
                "capacidade_origem": "MISTA",
                "auto_key": "aditivos",
                "categorias": ["ADITIVOS_CONTRATOS"],
                "url_name": "core:portal_contratos_public",
            },
            {
                "titulo": "Licitantes E/ou Contratados Sancionados",
                "descricao": "Registros de sanções administrativas aplicadas.",
                "capacidade_origem": "MANUAL",
                "categorias": ["LICITANTES_SANCIONADOS"],
            },
            {
                "titulo": "Fiscal De Contratos",
                "descricao": "Designações de fiscais vinculadas aos contratos.",
                "capacidade_origem": "MISTA",
                "auto_key": "fiscal",
                "categorias": ["FISCAL_CONTRATOS"],
                "url_name": "core:portal_contratos_public",
            },
            {
                "titulo": "Empresas Inidôneas E Suspensas",
                "descricao": "Cadastro de empresas impedidas de contratar.",
                "capacidade_origem": "MANUAL",
                "categorias": ["EMPRESAS_INIDONEAS"],
            },
        ],
    },
    {
        "titulo": "OBRAS PÚBLICAS",
        "descricao": "Execução de obras, andamento e paralisações.",
        "itens": [
            {
                "titulo": "Obras Públicas",
                "descricao": "Publicações de obras em execução e concluídas.",
                "capacidade_origem": "MANUAL",
                "categorias": ["OBRAS_PUBLICAS"],
            },
            {
                "titulo": "Obras Paralisadas",
                "descricao": "Relatórios de obras interrompidas e seus motivos.",
                "capacidade_origem": "MANUAL",
                "categorias": ["OBRAS_PARALISADAS"],
            },
        ],
    },
    {
        "titulo": "PLANEJAMENTO E PRESTAÇÃO DE CONTAS",
        "descricao": "Instrumentos de planejamento e relatórios oficiais de controle.",
        "itens": [
            {
                "titulo": "Prestação De Contas Anos Anteriores",
                "descricao": "Acervo de prestações de contas de exercícios anteriores.",
                "capacidade_origem": "MANUAL",
                "categorias": ["PRESTACAO_CONTAS_ANTERIORES"],
            },
            {
                "titulo": "Balanço Geral",
                "descricao": "Balanço geral anual do município.",
                "capacidade_origem": "MANUAL",
                "categorias": ["BALANCO_GERAL"],
            },
            {
                "titulo": "Relatório De Gestão Ou Atividade",
                "descricao": "Relatórios de atividades e resultados da gestão.",
                "capacidade_origem": "MANUAL",
                "categorias": ["RELATORIO_GESTAO_ATIVIDADE"],
            },
            {
                "titulo": "Julgamento Das Contas Pelo TCE Parecer Prévio",
                "descricao": "Parecer prévio emitido pelo Tribunal de Contas.",
                "capacidade_origem": "MANUAL",
                "categorias": ["PARECER_PREVIO_TCE"],
            },
            {
                "titulo": "Resultado De Julgamento Das Contas Legislativo",
                "descricao": "Resultado do julgamento das contas pelo Legislativo.",
                "capacidade_origem": "MANUAL",
                "categorias": ["RESULTADO_JULGAMENTO_LEGISLATIVO"],
            },
            {
                "titulo": "Relatório De Gestão Fiscal RGF",
                "descricao": "Relatórios fiscais oficiais da gestão municipal.",
                "capacidade_origem": "MANUAL",
                "categorias": ["RGF"],
            },
            {
                "titulo": "Rel. Res. De Execução Orçamentária RREO",
                "descricao": "Relatórios resumidos de execução orçamentária.",
                "capacidade_origem": "MANUAL",
                "categorias": ["RREO"],
            },
            {
                "titulo": "Plano Estratégico Institucional PEI",
                "descricao": "Planejamento estratégico institucional vigente.",
                "capacidade_origem": "MANUAL",
                "categorias": ["PEI"],
            },
            {
                "titulo": "Plano Plurianual PPA",
                "descricao": "Plano plurianual em vigor.",
                "capacidade_origem": "MANUAL",
                "categorias": ["PPA"],
            },
            {
                "titulo": "Lei De Diretrizes Orçamentárias LDO",
                "descricao": "Lei de diretrizes orçamentárias vigente.",
                "capacidade_origem": "MANUAL",
                "categorias": ["LDO"],
            },
            {
                "titulo": "Lei Orçamentária Anual LOA",
                "descricao": "Lei orçamentária anual vigente.",
                "capacidade_origem": "MANUAL",
                "categorias": ["LOA"],
            },
        ],
    },
]

DOCUMENTATION_MODULES = [
    {
        "nome": "Organização (ORG)",
        "icone": "fa-solid fa-sitemap",
        "descricao": "Base estrutural da prefeitura com município, secretarias, unidades, setores e onboarding.",
        "features": [
            "Cadastro completo de município e estrutura administrativa",
            "Templates de secretaria com provisionamento automático",
            "Painel de onboarding por etapas",
            "Escopo por município/secretaria/unidade",
        ],
    },
    {
        "nome": "Accounts / Acesso",
        "icone": "fa-solid fa-user-shield",
        "descricao": "Gestão de usuários, perfis, permissões e segurança operacional.",
        "features": [
            "RBAC por função (ADMIN, MUNICIPAL, SECRETARIA, UNIDADE, etc.)",
            "Código de acesso e troca obrigatória de senha no primeiro login",
            "Auditoria de ações de usuários",
            "Bloqueio/ativação com controle de limite contratual",
        ],
    },
    {
        "nome": "Educação",
        "icone": "fa-solid fa-school",
        "descricao": "Gestão educacional completa: alunos, matrículas, turmas, diário, calendário e relatórios.",
        "features": [
            "Cadastro e ciclo de vida de alunos e matrículas",
            "Turmas, diário, frequência, notas e boletins",
            "Calendário educacional e indicadores gerenciais",
            "Relatórios operacionais com exportação CSV/PDF",
        ],
    },
    {
        "nome": "Saúde",
        "icone": "fa-solid fa-notes-medical",
        "descricao": "Operação clínica municipal com unidades, profissionais, agenda e atendimentos.",
        "features": [
            "Gestão de profissionais e especialidades",
            "Agendamento e registro de atendimentos",
            "Documentos clínicos e auditoria de prontuário",
            "Relatórios mensais e exports institucionais",
        ],
    },
    {
        "nome": "NEE",
        "icone": "fa-solid fa-universal-access",
        "descricao": "Necessidades Educacionais Especiais com acompanhamento técnico e relatórios.",
        "features": [
            "Planos e objetivos por aluno",
            "Acompanhamentos, laudos e apoios",
            "Timeline unificada",
            "Relatórios por tipo, unidade e município",
        ],
    },
    {
        "nome": "Financeiro Público",
        "icone": "fa-solid fa-landmark",
        "descricao": "Execução orçamentária municipal com dotação, empenho, liquidação, pagamento e arrecadação.",
        "features": [
            "Exercício financeiro, UGs, contas bancárias e fontes de recurso",
            "Fluxo de despesa: empenho → liquidação → pagamento",
            "Receita por rubrica com reflexo em conta bancária",
            "Trilha de auditoria e logs por evento financeiro",
        ],
    },
    {
        "nome": "Billing / Planos SaaS",
        "icone": "fa-solid fa-file-invoice-dollar",
        "descricao": "Gestão comercial/contratual por município com limites, upgrades e fatura.",
        "features": [
            "Planos (Starter, Municipal, Gestão Total, Consórcio)",
            "Assinatura por município com preço base congelado",
            "Overage por secretarias, usuários, alunos e addons",
            "Solicitação/aprovação de upgrade e fatura por competência",
        ],
    },
]

DOCUMENTATION_FUNCIONALIDADES = [
    {
        "grupo": "Onboarding e implantação",
        "itens": [
            "Primeiro acesso com troca obrigatória de senha",
            "Onboarding com seleção de plano e ativação de secretarias",
            "Templates por secretaria para acelerar configuração inicial",
        ],
    },
    {
        "grupo": "Governança e segurança",
        "itens": [
            "RBAC por papel com escopo municipal",
            "Trilhas de auditoria para ações críticas",
            "Controle de limites por assinatura e fair use nos planos altos",
        ],
    },
    {
        "grupo": "Operação e performance",
        "itens": [
            "Relatórios operacionais e executivos por módulo",
            "Simulador de plano para proposta/licitação",
            "Faturamento por competência com adicionais aprovados",
        ],
    },
]

DOCUMENTATION_INTEGRACOES = [
    {
        "titulo": "Importação de dados",
        "texto": "Importação inicial assistida (CSV/XLSX) para acelerar entrada em produção.",
        "status": "Disponível",
    },
    {
        "titulo": "Exports institucionais",
        "texto": "Exportação padronizada de relatórios em CSV e PDF em diversos módulos.",
        "status": "Disponível",
    },
    {
        "titulo": "Validação de documentos",
        "texto": "Registro e rastreio de documentos emitidos com mecanismo de validação pública.",
        "status": "Disponível",
    },
    {
        "titulo": "Integrações especiais",
        "texto": "Conectores específicos (ex.: e-SUS e outros legados) sob proposta técnica/comercial.",
        "status": "Sob proposta",
    },
]

DOCUMENTATION_ARQUITETURA = [
    "Apps especializados por domínio: ORG, Accounts, Educação, Saúde, NEE e Billing.",
    "Base única por município com segregação por secretaria/unidade.",
    "Camada de permissão centralizada (RBAC) aplicada em middleware e views.",
    "Admin operacional próprio no dashboard (sem depender do admin padrão do Django).",
]

DOCUMENTATION_FLUXOS = [
    "1. Contratação SaaS municipal com vigência mínima e regra de reajuste.",
    "2. Primeiro acesso com troca de senha obrigatória e onboarding inicial.",
    "3. Definição do plano municipal e ativação de secretarias por template.",
    "4. Operação diária por módulo com auditoria, indicadores e relatórios.",
    "5. Controle de consumo, upgrades e faturamento mensal por competência.",
]

DOCUMENTATION_PILARES = [
    "Segurança e LGPD: campos sensíveis protegidos, controle de acesso e trilha de auditoria.",
    "Escalabilidade municipal: base única multi-secretaria com crescimento por limites e addons.",
    "Governança pública: linguagem e estrutura aderentes ao cenário de licitação e contrato.",
    "Operação orientada a dados: indicadores, relatórios e histórico para tomada de decisão.",
]

DOCUMENTATION_KPIS = [
    {"label": "Módulos principais", "value": "7"},
    {"label": "Planos SaaS", "value": "4"},
    {"label": "Formato de cobrança", "value": "Mensal + overage"},
    {"label": "Modelo contratual", "value": "SaaS municipal"},
]
