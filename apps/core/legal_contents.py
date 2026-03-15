"""Conteúdo institucional jurídico das páginas públicas do GEPUB.

Os textos desta base seguem a estrutura de exibição do template
`core/legal_public.html` (seções com parágrafos e listas).
"""

TERMS_OF_SERVICE_LAST_UPDATE = "14 de março de 2026"

TERMS_OF_SERVICE_SECTIONS = [
    {
        "title": "1. Apresentação e escopo de aplicação",
        "paragraphs": [
            "Os presentes Termos de Uso regulam o acesso, navegação e utilização da plataforma GEPUB – Gestão Pública Integrada, incluindo ambientes web, painéis administrativos, portais públicos, APIs e integrações técnicas disponibilizadas ao cliente institucional.",
            "Ao acessar ou utilizar qualquer ambiente do GEPUB, o usuário declara ciência e concordância com estes Termos, com a Política de Privacidade, com a Política de Cookies e com os instrumentos contratuais firmados com o ente público contratante.",
        ],
        "items": [
            "Última atualização: 14 de março de 2026",
            "Base legal principal: Lei nº 13.709/2018 (LGPD) e Lei nº 12.965/2014 (Marco Civil da Internet)",
            "Aplicável a usuários internos, agentes públicos, prestadores autorizados e usuários externos habilitados",
        ],
    },
    {
        "title": "2. Natureza da plataforma e papel institucional",
        "paragraphs": [
            "O GEPUB consiste em solução tecnológica de apoio à gestão pública, com módulos para educação, saúde, administração, atendimento ao cidadão, indicadores, documentos e processos.",
            "Salvo disposição contratual diversa, o GEPUB atua como fornecedor de tecnologia e suporte técnico, sem substituir a autonomia normativa e decisória do órgão público contratante.",
        ],
        "items": [
            "Operação em ambiente multiunidade e multientidade",
            "Disponibilização por contratação, convênio, parceria ou projeto de implantação",
            "Escopo condicionado ao plano contratado e à parametrização institucional",
        ],
    },
    {
        "title": "3. Definições essenciais",
        "paragraphs": [
            "Para fins destes Termos, aplicam-se os conceitos de Plataforma, Usuário, Cliente Institucional, Administrador Institucional, Dados Institucionais, Credenciais e Incidente de Segurança.",
        ],
        "items": [
            "Usuário: toda pessoa natural autorizada a operar ou acessar o sistema",
            "Cliente institucional: prefeitura, secretaria, autarquia, fundação ou entidade contratante",
            "Credenciais: login, senha, MFA, token, certificados e chaves de API",
            "Incidente de segurança: evento confirmado ou suspeito com risco à confidencialidade, integridade, disponibilidade ou rastreabilidade",
        ],
    },
    {
        "title": "4. Elegibilidade, aceite e vinculação",
        "paragraphs": [
            "O uso do GEPUB é restrito a usuários autorizados pelo cliente institucional ou pelo próprio GEPUB, conforme perfil e finalidade do ambiente.",
            "O aceite poderá ocorrer por clique, uso continuado, assinatura contratual, fluxo de primeiro acesso, ordem de serviço ou instrumento equivalente.",
        ],
        "items": [
            "Uso por menores de idade exige observância de regras institucionais e salvaguardas legais",
            "Aceite vincula usuário e cliente institucional na extensão aplicável",
            "A gestão de autorização e revogação de acesso é responsabilidade compartilhada",
        ],
    },
    {
        "title": "5. Cadastro, autenticação e controle de acesso",
        "paragraphs": [
            "O acesso a áreas restritas depende de informações cadastrais válidas e autenticação segura. As credenciais são pessoais, intransferíveis e devem ser protegidas pelo usuário.",
            "O GEPUB pode adotar controles adicionais para segurança operacional e prevenção de uso indevido.",
        ],
        "items": [
            "Autenticação multifator (MFA), quando habilitada",
            "Política de senha, expiração de sessão e bloqueio por tentativas inválidas",
            "Restrição contextual por IP, dispositivo ou perfil",
            "Trilha de auditoria de eventos críticos",
        ],
    },
    {
        "title": "6. Perfis, permissões e segregação de funções",
        "paragraphs": [
            "A plataforma opera com segregação lógica por órgão, secretaria, unidade, setor, escola, estabelecimento de saúde, turma, contrato ou estrutura equivalente.",
            "A atribuição de permissões segue o princípio do menor privilégio: cada usuário acessa apenas o necessário ao exercício de suas atribuições.",
        ],
        "items": [
            "Designação de administradores institucionais",
            "Revisão periódica de perfis sensíveis",
            "Bloqueio e revogação tempestiva em desligamentos ou mudanças de função",
        ],
    },
    {
        "title": "7. Obrigações dos usuários",
        "paragraphs": [
            "Os usuários devem utilizar o GEPUB para finalidades legítimas, institucionais e autorizadas, observando legislação vigente e normas internas do cliente institucional.",
        ],
        "items": [
            "Manter sigilo sobre dados pessoais e informações sensíveis",
            "Não compartilhar credenciais ou acessar contas de terceiros",
            "Não inserir software malicioso, automações abusivas ou conteúdo ilícito",
            "Preservar integridade, rastreabilidade e veracidade dos registros",
        ],
    },
    {
        "title": "8. Condutas vedadas",
        "paragraphs": [
            "É vedada qualquer tentativa de violar a segurança da plataforma, acessar áreas não autorizadas, extrair dados em massa sem base legal ou manipular indevidamente informações institucionais.",
        ],
        "items": [
            "Falsificação de identidade ou vínculo institucional",
            "Scraping abusivo e mineração incompatível com a finalidade pública do serviço",
            "Engenharia reversa, descompilação e remoção de avisos de propriedade intelectual",
            "Uso do sistema para assédio, discriminação, fraude ou vantagem indevida",
        ],
    },
    {
        "title": "9. Conteúdo inserido, integrações e comunicações",
        "paragraphs": [
            "O cliente institucional e seus usuários são responsáveis pela legalidade, legitimidade e atualização dos conteúdos inseridos na plataforma.",
            "O GEPUB pode integrar-se a serviços de terceiros (e-mail, mensageria, autenticação, armazenamento, analytics, APIs públicas) conforme escopo contratado.",
        ],
        "items": [
            "Disponibilidade de integração pode depender de terceiros",
            "Uso de canais de comunicação com cidadão deve observar base legal e proporcionalidade",
            "Registros operacionais podem ser mantidos para segurança, suporte e conformidade",
        ],
    },
    {
        "title": "10. Disponibilidade, manutenção e suporte",
        "paragraphs": [
            "O GEPUB buscará níveis adequados de disponibilidade e continuidade, observadas limitações técnicas, estágio de implantação, dependências externas e eventos fora de controle razoável.",
            "Manutenções programadas serão comunicadas com antecedência razoável sempre que possível.",
        ],
        "items": [
            "Atualizações corretivas, evolutivas ou emergenciais",
            "Tratamento de incidentes e resposta técnica",
            "Suporte conforme plano, edital, contrato ou anexo técnico aplicável",
        ],
    },
    {
        "title": "11. Propriedade intelectual",
        "paragraphs": [
            "Todos os direitos sobre software, interface, arquitetura, fluxos, documentação, marca e ativos tecnológicos do GEPUB pertencem ao GEPUB ou a seus licenciantes.",
            "A contratação não implica cessão de propriedade intelectual, salvo cláusula expressa em instrumento específico.",
        ],
        "items": [
            "Vedada reprodução, sublicenciamento ou exploração econômica sem autorização",
            "Vedada engenharia reversa, desmontagem e redistribuição não autorizada",
        ],
    },
    {
        "title": "12. Proteção de dados, segurança e responsabilidade",
        "paragraphs": [
            "O tratamento de dados pessoais observará a LGPD, o Marco Civil da Internet e as orientações públicas da ANPD, respeitando papéis de controlador e operador conforme o contexto contratual e decisório.",
            "O GEPUB adota medidas técnicas e organizacionais compatíveis com a natureza da operação, sem garantia de risco zero em ambiente digital.",
        ],
        "items": [
            "Controle de acesso, logs de auditoria, backups e monitoramento",
            "Resposta a incidentes com contenção, investigação e comunicação apropriada",
            "Cooperação com o cliente institucional para governança e conformidade",
            "Limitações de responsabilidade aplicáveis a falhas de terceiros e uso indevido pelo usuário",
        ],
    },
    {
        "title": "13. Suspensão, bloqueio, alterações e encerramento",
        "paragraphs": [
            "O acesso de usuários pode ser suspenso ou bloqueado por violação destes Termos, determinação do cliente institucional, suspeita de fraude, contenção de risco ou término de vínculo.",
            "A plataforma e estes Termos poderão ser atualizados para refletir mudanças legais, contratuais, operacionais e tecnológicas.",
        ],
        "items": [
            "Vigência e suspensão conforme contrato",
            "Tolerância a descumprimento não implica renúncia de direitos",
            "Cláusulas inválidas não invalidam o restante do instrumento",
        ],
    },
    {
        "title": "14. Aviso jurídico e operacional",
        "paragraphs": [
            "Os documentos jurídicos e institucionais do GEPUB refletem o compromisso da plataforma com conformidade, transparência, proteção de dados, segurança da informação e governança digital.",
            "As versões publicadas poderão ser atualizadas periodicamente para adequação contratual, operacional, técnica ou legal.",
        ],
        "items": [
            "Recomenda-se revisão jurídica final para contratação pública e módulos com dados sensíveis",
            "Especialmente relevante para contextos de educação, saúde e dados de cidadãos",
        ],
    },
    {
        "title": "15. Documentos complementares recomendados de governança",
        "paragraphs": [
            "Para fortalecimento contratual, compliance e segurança operacional em contratações públicas, recomenda-se manter documentação complementar atualizada e integrada ao ciclo de implantação.",
        ],
        "items": [
            "Contrato de prestação de serviços/licença SaaS para prefeituras",
            "Acordo de Tratamento de Dados Pessoais (DPA/LGPD)",
            "Política de Governança, Compliance e Resposta a Incidentes",
            "Termo de nomeação do Encarregado e canal de privacidade",
            "Termo de confidencialidade para equipe interna e parceiros",
            "Política de backup, retenção e recuperação de desastres",
            "Política de controle de acesso e gestão de perfis",
            "Política de uso aceitável por usuários internos",
            "Termo específico do Portal do Cidadão",
            "Termos setoriais para módulos educacionais e de saúde",
        ],
    },
    {
        "title": "16. Lei aplicável e foro",
        "paragraphs": [
            "Estes Termos são regidos pela legislação da República Federativa do Brasil. Sem prejuízo de regras específicas da contratação pública, aplica-se o foro previsto no instrumento contratual ou, na ausência, o foro do domicílio do contratante institucional.",
        ],
        "items": [
            "LGPD (Lei nº 13.709/2018): https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/L13709compilado.htm",
            "Marco Civil da Internet (Lei nº 12.965/2014): https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm",
            "Direitos dos titulares (ANPD): https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares",
        ],
    },
]


PRIVACY_POLICY_LAST_UPDATE = "14 de março de 2026"

PRIVACY_POLICY_SECTIONS = [
    {
        "title": "1. Compromisso com privacidade e proteção de dados",
        "paragraphs": [
            "O GEPUB reconhece que privacidade, proteção de dados e governança informacional são elementos centrais para a confiança institucional na administração pública.",
            "Esta Política descreve como dados pessoais são tratados no site institucional, áreas autenticadas e módulos contratados da plataforma.",
        ],
        "items": [
            "Base legal principal: LGPD (Lei nº 13.709/2018)",
            "Aplicação a prefeituras, secretarias, unidades, servidores, alunos, responsáveis e cidadãos",
        ],
    },
    {
        "title": "2. Abrangência e conceitos relevantes",
        "paragraphs": [
            "Esta Política se aplica aos dados pessoais tratados em cadastros, atendimentos, integrações, suporte, implantação, comunicações e rotinas operacionais vinculadas ao GEPUB.",
        ],
        "items": [
            "Dado pessoal e dado pessoal sensível",
            "Titular de dados",
            "Controlador, operador e tratamento",
        ],
    },
    {
        "title": "3. Papéis de tratamento no ecossistema GEPUB",
        "paragraphs": [
            "Em regra, o cliente institucional (órgão público contratante) atua como controlador nas operações sob sua esfera decisória, e o GEPUB atua como operador tecnológico.",
            "Em atividades próprias do fornecedor (segurança, suporte, faturamento, prevenção a fraudes e obrigações legais), o GEPUB poderá atuar como controlador autônomo ou conjunto, conforme o caso concreto.",
        ],
        "items": [
            "Definição de papéis depende da finalidade e da tomada de decisão",
            "Matriz de responsabilidades pode ser formalizada em contrato ou anexo de proteção de dados",
        ],
    },
    {
        "title": "4. Categorias de dados tratados",
        "paragraphs": [
            "O GEPUB pode tratar dados de identificação, contato, vínculo profissional, dados educacionais, dados de saúde (quando aplicável), dados de navegação, anexos documentais, dados contratuais e dados oriundos de integrações.",
        ],
        "items": [
            "Dados cadastrais e institucionais",
            "Registros de autenticação, sessão e trilhas de auditoria",
            "Dados acadêmicos e assistenciais conforme módulos habilitados",
            "Dados financeiros e de relacionamento contratual",
        ],
    },
    {
        "title": "5. Formas de coleta e origens dos dados",
        "paragraphs": [
            "Os dados podem ser coletados diretamente do titular, do cliente institucional, por administradores autorizados, por importação em lote, por integração sistêmica e por registros técnicos de uso e segurança.",
        ],
        "items": [
            "Formulários eletrônicos e processos administrativos",
            "Cadastros operacionais (educação, saúde, administração)",
            "Logs técnicos, eventos de segurança e chamados de suporte",
        ],
    },
    {
        "title": "6. Finalidades do tratamento",
        "paragraphs": [
            "O tratamento ocorre para operação da plataforma, autenticação, controle de acesso, execução de rotinas institucionais, emissão de documentos, comunicação operacional, suporte técnico, prevenção a fraude, auditoria e cumprimento legal/contratual.",
        ],
        "items": [
            "Prestação do serviço e continuidade operacional",
            "Segurança da informação e gestão de incidentes",
            "Geração de relatórios, indicadores e evidências de operação",
        ],
    },
    {
        "title": "7. Bases legais aplicáveis",
        "paragraphs": [
            "Conforme o contexto, o tratamento poderá fundamentar-se em obrigação legal/regulatória, execução de políticas públicas, execução contratual, exercício regular de direitos, tutela da saúde, proteção da vida, legítimo interesse e consentimento quando cabível.",
        ],
        "items": [
            "Regras específicas para poder público previstas na LGPD",
            "Análise de base legal conforme finalidade e fluxo de dados",
        ],
    },
    {
        "title": "8. Dados de crianças e adolescentes",
        "paragraphs": [
            "Quando houver tratamento de dados de crianças e adolescentes (especialmente em contextos educacionais), serão observadas as salvaguardas legais e institucionais apropriadas, com especial cautela quanto à finalidade, necessidade e segurança.",
        ],
        "items": [
            "Aplicação reforçada de controles em ambientes educacionais",
            "Respeito às normas de representação legal e proteção do menor",
        ],
    },
    {
        "title": "9. Compartilhamento e transferência internacional",
        "paragraphs": [
            "Dados pessoais podem ser compartilhados com o cliente institucional, unidades autorizadas, suboperadores, provedores técnicos e autoridades competentes quando necessário e legalmente aplicável.",
            "Quando houver transferência internacional, serão adotadas salvaguardas contratuais e técnicas compatíveis com os requisitos legais.",
        ],
        "items": [
            "Compartilhamento orientado por necessidade, adequação e minimização",
            "Uso de infraestrutura de nuvem conforme medidas de proteção aplicáveis",
        ],
    },
    {
        "title": "10. Retenção, descarte e conservação",
        "paragraphs": [
            "Os dados são mantidos pelo tempo necessário ao cumprimento da finalidade, da relação contratual e das obrigações legais, regulatórias e de prestação de contas.",
            "Encerrada a necessidade legítima, poderão ser eliminados, anonimizados ou bloqueados, ressalvadas hipóteses legais de retenção.",
        ],
        "items": [
            "Retenção para auditoria, segurança e exercício regular de direitos",
            "Descarte seguro e controle de ciclo de vida da informação",
        ],
    },
    {
        "title": "11. Direitos dos titulares",
        "paragraphs": [
            "Nos termos da LGPD, os titulares podem solicitar confirmação de tratamento, acesso, correção, anonimização, bloqueio, eliminação quando cabível, informação sobre compartilhamento, portabilidade e revisão de decisões automatizadas nos casos previstos em lei.",
            "Quando o GEPUB atuar apenas como operador, as solicitações poderão ser tratadas em cooperação com o controlador competente.",
        ],
        "items": [
            "Canal de exercício de direitos sujeito à validação de identidade",
            "Possibilidade de exigência de documentos mínimos para prevenção a fraude",
            "ANPD – Direitos dos titulares: https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares",
        ],
    },
    {
        "title": "12. Segurança da informação e incidentes",
        "paragraphs": [
            "O GEPUB adota medidas administrativas e técnicas proporcionais para proteção de dados, incluindo controle de acesso, monitoramento, logs, backup, gestão de vulnerabilidades e resposta a incidentes.",
            "Em caso de incidente com potencial risco relevante, serão adotadas ações de contenção, investigação, remediação e comunicação apropriada.",
        ],
        "items": [
            "Guia ANPD de segurança da informação: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-sobre-seguranca-da-informacao-para-agentes-de-tratamento-de-pequeno-porte",
            "Notificação e cooperação com cliente institucional conforme contexto",
        ],
    },
    {
        "title": "13. Cookies, terceiros e atualizações da política",
        "paragraphs": [
            "O uso de cookies e tecnologias correlatas está detalhado em Política própria. Ambientes de terceiros integrados ao GEPUB possuem regras próprias e devem ser consultados diretamente.",
            "Esta Política pode ser atualizada para refletir mudanças legais, técnicas e operacionais.",
        ],
        "items": [
            "Canal de privacidade: privacidade@gepub.com.br",
            "Canal alternativo (DPO): dpo@gepub.com.br",
            "Canal institucional: formulário de contato no portal oficial do GEPUB",
        ],
    },
]


COOKIES_POLICY_LAST_UPDATE = "14 de março de 2026"

COOKIES_POLICY_SECTIONS = [
    {
        "title": "1. Introdução",
        "paragraphs": [
            "Esta Política de Cookies explica como o GEPUB utiliza cookies e tecnologias similares em ambientes públicos e autenticados da plataforma para garantir funcionamento, segurança e melhoria contínua da experiência.",
        ],
        "items": [
            "Aplicável ao site institucional, painéis administrativos, portais públicos e módulos conectados",
        ],
    },
    {
        "title": "2. O que são cookies e tecnologias correlatas",
        "paragraphs": [
            "Cookies são pequenos arquivos armazenados no navegador/dispositivo para lembrar contexto de uso, manter sessão e suportar controles de segurança.",
            "Além de cookies, podem ser utilizados identificadores técnicos como local storage, session storage, pixels, tokens de sessão e logs operacionais.",
        ],
        "items": [
            "Cookies de sessão e cookies persistentes",
            "Identificadores de autenticação e estado de navegação",
        ],
    },
    {
        "title": "3. Finalidades de uso",
        "paragraphs": [
            "Os cookies podem ser utilizados para autenticação, continuidade de sessão, proteção contra fraude, preferência de interface, análise de desempenho e estabilidade dos serviços digitais do GEPUB.",
        ],
        "items": [
            "Login e segurança de sessão",
            "Desempenho técnico e monitoramento",
            "Personalização de interface e usabilidade",
        ],
    },
    {
        "title": "4. Categorias de cookies",
        "paragraphs": [
            "As categorias adotadas incluem cookies estritamente necessários, de desempenho/análise, de funcionalidade, de segurança e, quando aplicável, cookies de terceiros.",
        ],
        "items": [
            "Necessários: essenciais para funcionamento do serviço",
            "Desempenho: métricas agregadas e melhoria operacional",
            "Funcionalidade: preferências e contexto do usuário",
            "Segurança: prevenção a abuso, validação e integridade de sessão",
            "Terceiros: componentes externos integrados ao ambiente",
        ],
    },
    {
        "title": "5. Bases e governança de uso",
        "paragraphs": [
            "Cookies estritamente necessários podem ser utilizados para viabilizar segurança e funcionamento do serviço. Cookies não estritamente necessários, quando aplicáveis, podem estar sujeitos a mecanismos de transparência e gestão de preferências.",
        ],
        "items": [
            "Aplicação de critérios de necessidade e proporcionalidade",
            "Governança alinhada às políticas institucionais e legais",
        ],
    },
    {
        "title": "6. Dados coletados por cookies",
        "paragraphs": [
            "Conforme a finalidade, podem ser tratados identificadores de sessão, IP, informações de navegador/dispositivo, preferências, páginas acessadas, tempo de navegação, eventos de interação e indicadores técnicos de desempenho.",
        ],
        "items": [
            "Alguns dados podem ser dados pessoais, conforme contexto de identificação",
            "Tratamento orientado por finalidade e minimização",
        ],
    },
    {
        "title": "7. Prazo de retenção",
        "paragraphs": [
            "A duração varia por tipo de cookie: sessão (expira ao fechar o navegador), persistente (prazo determinado), temporário (funcionalidade específica) ou renovável (conforme continuidade de uso).",
        ],
        "items": [
            "Retenção definida conforme finalidade técnica e de segurança",
            "Revisão periódica de necessidade de manutenção",
        ],
    },
    {
        "title": "8. Gestão de preferências pelo usuário",
        "paragraphs": [
            "O usuário pode configurar o navegador para bloquear ou excluir cookies. Contudo, a desativação de cookies necessários pode comprometer autenticação, sessão, segurança e acesso a funcionalidades essenciais.",
        ],
        "items": [
            "Bloqueio de cookies de terceiros no navegador",
            "Exclusão de cookies previamente armazenados",
            "Uso de navegação privada com limitações funcionais possíveis",
        ],
    },
    {
        "title": "9. Ambientes autenticados e cookies obrigatórios",
        "paragraphs": [
            "Em áreas autenticadas, determinados cookies/identificadores técnicos são indispensáveis para manter sessão, validar permissões, prevenir requisições maliciosas e garantir rastreabilidade operacional.",
        ],
        "items": [
            "Sem esses cookies, partes do serviço podem ficar indisponíveis",
            "Controles voltados à integridade transacional e segurança do usuário",
        ],
    },
    {
        "title": "10. Cookies de terceiros e responsabilidade compartilhada",
        "paragraphs": [
            "Quando houver integração com serviços externos, o tratamento realizado por terceiros seguirá também as políticas desses provedores.",
            "O GEPUB busca selecionar integrações compatíveis com critérios técnicos e de segurança, recomendando leitura das políticas específicas dos serviços conectados.",
        ],
        "items": [
            "Análise de provedores com requisitos mínimos de governança",
            "Responsabilidades distribuídas conforme papel de cada agente",
        ],
    },
    {
        "title": "11. Atualizações e contato",
        "paragraphs": [
            "Esta Política pode ser atualizada para refletir mudanças legais, tecnológicas e operacionais. A versão vigente permanece disponível nos canais oficiais do GEPUB.",
        ],
        "items": [
            "Contato de privacidade: privacidade@gepub.com.br",
            "Contato alternativo: dpo@gepub.com.br",
            "Canal institucional de suporte e conformidade no portal oficial",
        ],
    },
]
