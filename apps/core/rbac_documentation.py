from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from apps.accounts.models import Profile
from apps.core.rbac import ROLE_PERMS_FINE, role_scope_base


MATRIX_MODULES: list[dict[str, str]] = [
    {"key": "org", "label": "Administracao / ORG"},
    {"key": "educacao", "label": "Educacao"},
    {"key": "avaliacoes", "label": "Avaliacoes"},
    {"key": "nee", "label": "NEE"},
    {"key": "saude", "label": "Saude"},
    {"key": "processos", "label": "Processos / Protocolo"},
    {"key": "financeiro", "label": "Financeiro"},
    {"key": "compras", "label": "Compras"},
    {"key": "contratos", "label": "Contratos"},
    {"key": "integracoes", "label": "Integracoes"},
    {"key": "paineis", "label": "Paineis / BI"},
    {"key": "conversor", "label": "Conversor de Documentos"},
    {"key": "rh", "label": "RH"},
    {"key": "ponto", "label": "Ponto"},
    {"key": "folha", "label": "Folha"},
    {"key": "patrimonio", "label": "Patrimonio"},
    {"key": "almoxarifado", "label": "Almoxarifado"},
    {"key": "frota", "label": "Frota"},
    {"key": "ouvidoria", "label": "Ouvidoria"},
    {"key": "tributos", "label": "Tributos"},
    {"key": "billing", "label": "Billing / Contrato SaaS"},
    {"key": "portal", "label": "Portal da Prefeitura"},
]


def _role_item(
    *,
    code: str,
    nivel: str,
    dashboard: str,
    funcoes: list[str],
    atribuicoes: list[str],
) -> dict:
    return {
        "code": code,
        "nivel": nivel,
        "dashboard": dashboard,
        "funcoes": funcoes,
        "atribuicoes": atribuicoes,
    }


ROLE_REPORT_SECTIONS: list[dict[str, object]] = [
    {
        "area": "Administracao e Governanca",
        "roles": [
            _role_item(
                code="ADMIN",
                nivel="N1 - Super Admin",
                dashboard="Dashboard global",
                funcoes=[
                    "Governanca total da plataforma",
                    "Parametrizacao estrutural de municipio, secretaria e unidade",
                    "Administracao tecnica de integracoes e seguranca",
                ],
                atribuicoes=[
                    "Pode ver, criar, editar, excluir, publicar e configurar modulos",
                    "Pode gerenciar qualquer usuario e permissao",
                    "Acompanha auditoria e indicadores de todos os modulos",
                ],
            ),
            _role_item(
                code="MUNICIPAL",
                nivel="N2 - Gestao central da prefeitura",
                dashboard="Dashboard municipal consolidado",
                funcoes=[
                    "Conduzir governanca operacional da prefeitura",
                    "Habilitar fluxos entre secretarias",
                    "Acompanhar desempenho macro da gestao",
                ],
                atribuicoes=[
                    "Pode gerenciar usuarios e operacao municipal",
                    "Pode aprovar publicacoes e acompanhar integracoes",
                    "Nao executa rotinas tecnicas de infraestrutura",
                ],
            ),
            _role_item(
                code="SECRETARIA",
                nivel="N3 - Gestor de secretaria",
                dashboard="Dashboard setorial",
                funcoes=[
                    "Gerenciar operacao da secretaria",
                    "Consolidar relatorios setoriais",
                    "Coordenar unidades vinculadas",
                ],
                atribuicoes=[
                    "Pode gerir unidades e usuarios do escopo",
                    "Pode aprovar fluxos internos da secretaria",
                    "Visualiza apenas seu escopo setorial",
                ],
            ),
            _role_item(
                code="UNIDADE",
                nivel="N4 - Gestor de unidade",
                dashboard="Dashboard da unidade",
                funcoes=[
                    "Gerenciar operacao local da unidade",
                    "Acompanhar equipe e execucao diaria",
                    "Garantir qualidade dos registros",
                ],
                atribuicoes=[
                    "Pode operar e acompanhar indicadores da unidade",
                    "Pode gerenciar usuarios operacionais locais",
                    "Nao possui visao global municipal",
                ],
            ),
            _role_item(
                code="AUDITORIA",
                nivel="Controle interno / fiscalizacao",
                dashboard="Dashboard de leitura e auditoria",
                funcoes=[
                    "Fiscalizar conformidade e trilhas de auditoria",
                    "Avaliar consistencia de dados e processos",
                    "Emitir pareceres tecnicos de governanca",
                ],
                atribuicoes=[
                    "Permissao de consulta ampla com foco em auditoria",
                    "Exportacoes orientadas a controle interno",
                    "Nao executa alteracoes operacionais",
                ],
            ),
            _role_item(
                code="RH_GESTOR",
                nivel="Gestao de pessoas",
                dashboard="Dashboard RH/Ponto/Folha",
                funcoes=[
                    "Gerenciar cadastro funcional e lotacao",
                    "Controlar ponto e folha",
                    "Acompanhar indicadores de pessoal",
                ],
                atribuicoes=[
                    "Opera RH, Ponto e Folha",
                    "Nao acessa dados clinicos/pedagogicos sensiveis",
                    "Trabalha no escopo institucional definido",
                ],
            ),
            _role_item(
                code="PROTOCOLO",
                nivel="Atendimento e tramitacao",
                dashboard="Dashboard de processos e ouvidoria",
                funcoes=[
                    "Registrar e tramitar protocolos",
                    "Acompanhar solicitacoes e encaminhamentos",
                    "Garantir SLA de atendimento",
                ],
                atribuicoes=[
                    "Pode gerenciar fluxos de processos no escopo",
                    "Acessa somente dados necessarios ao tramite",
                    "Nao acessa detalhes clinicos e NEE sensiveis",
                ],
            ),
            _role_item(
                code="CAD_GESTOR",
                nivel="Gestao de cadastros-base",
                dashboard="Dashboard de administracao cadastral",
                funcoes=[
                    "Padronizar cadastros municipais",
                    "Tratar duplicidades e qualidade de dados",
                    "Suportar secretaria/unidade na base mestra",
                ],
                atribuicoes=[
                    "Pode atuar em estrutura e usuarios conforme governanca",
                    "Garante coerencia entre secretaria/unidade/servidor",
                    "Nao substitui administracao tecnica",
                ],
            ),
            _role_item(
                code="CAD_OPER",
                nivel="Operacao cadastral setorial",
                dashboard="Dashboard cadastral setorial",
                funcoes=[
                    "Executar cadastros e atualizacoes",
                    "Anexar documentos permitidos",
                    "Manter dados atualizados por secretaria",
                ],
                atribuicoes=[
                    "Acesso limitado ao proprio escopo",
                    "Nao gerencia seguranca/perfis globais",
                    "Atua como operador de dados",
                ],
            ),
            _role_item(
                code="LEITURA",
                nivel="Leitura institucional",
                dashboard="Dashboard de consulta",
                funcoes=[
                    "Consultar dados e indicadores liberados",
                    "Apoiar auditoria e monitoramento",
                    "Acompanhar metas e resultados",
                ],
                atribuicoes=[
                    "Nao cria/edita/exclui registros operacionais",
                    "Acesso controlado por escopo",
                    "Permissao orientada a transparencia interna",
                ],
            ),
        ],
    },
    {
        "area": "Saude",
        "roles": [
            _role_item(
                code="SAU_SECRETARIO",
                nivel="Gestao setorial da saude",
                dashboard="Dashboard Saude (escopo secretaria)",
                funcoes=[
                    "Acompanhar producao e indicadores da rede",
                    "Definir diretrizes operacionais",
                    "Conduzir governanca setorial da saude",
                ],
                atribuicoes=[
                    "Visao macro da secretaria de saude",
                    "Nao opera configuracoes tecnicas de infraestrutura",
                    "Acesso por escopo setorial",
                ],
            ),
            _role_item(
                code="SAU_DIRETOR",
                nivel="Gestao de unidade de saude",
                dashboard="Dashboard Saude (escopo unidade)",
                funcoes=[
                    "Gerenciar operacao da unidade",
                    "Supervisionar equipe e filas locais",
                    "Validar relatorios da unidade",
                ],
                atribuicoes=[
                    "Acesso integral da unidade",
                    "Sem visao municipal completa por padrao",
                    "Pode gerir fluxo operacional local",
                ],
            ),
            _role_item(
                code="SAU_COORD",
                nivel="Coordenacao assistencial",
                dashboard="Dashboard Saude (unidades atribuídas)",
                funcoes=[
                    "Coordenar protocolos e equipe assistencial",
                    "Acompanhar atendimento e producao",
                    "Padronizar rotina clinica",
                ],
                atribuicoes=[
                    "Gerencia operacao no escopo atribuido",
                    "Sem administracao global de usuarios",
                    "Atuacao focada na assistencia",
                ],
            ),
            _role_item(
                code="SAU_MEDICO",
                nivel="Profissional assistencial",
                dashboard="Dashboard Saude (casos atribuídos)",
                funcoes=[
                    "Registrar evolucao e conduta clinica",
                    "Executar atendimentos no proprio escopo",
                    "Contribuir com acompanhamento multiprofissional",
                ],
                atribuicoes=[
                    "Acesso por unidade/atribuicao",
                    "Nao administra plataforma",
                    "Permissoes focadas em atendimento",
                ],
            ),
            _role_item(
                code="SAU_ENFERMEIRO",
                nivel="Profissional assistencial",
                dashboard="Dashboard Saude (casos atribuídos)",
                funcoes=[
                    "Realizar triagem e evolucao de enfermagem",
                    "Executar registros permitidos de cuidado",
                    "Apoiar fluxos assistenciais da unidade",
                ],
                atribuicoes=[
                    "Acesso por escopo da unidade",
                    "Sem governanca tecnica de plataforma",
                    "Atuacao operacional assistencial",
                ],
            ),
            _role_item(
                code="SAU_TEC_ENF",
                nivel="Equipe tecnica",
                dashboard="Dashboard Saude (rotina operacional)",
                funcoes=[
                    "Executar registros tecnicos permitidos",
                    "Apoiar atendimento diario",
                    "Atualizar informacoes assistenciais basicas",
                ],
                atribuicoes=[
                    "Acesso restrito a campos autorizados",
                    "Sem visao estrategica municipal",
                    "Sem permissao de administracao",
                ],
            ),
            _role_item(
                code="SAU_ACS",
                nivel="Campo / territorio",
                dashboard="Dashboard Saude (microarea)",
                funcoes=[
                    "Acompanhar familias da microarea",
                    "Registrar visitas e ocorrencias",
                    "Atualizar dados basicos de acompanhamento",
                ],
                atribuicoes=[
                    "Acesso territorial restrito",
                    "Sem prontuario completo por padrao",
                    "Acesso minimo necessario",
                ],
            ),
            _role_item(
                code="SAU_RECEPCAO",
                nivel="Atendimento administrativo",
                dashboard="Dashboard Saude (atendimento)",
                funcoes=[
                    "Recepcionar e organizar fluxo de pacientes",
                    "Atualizar cadastro basico",
                    "Controlar agenda/check-in",
                ],
                atribuicoes=[
                    "Sem acesso ao conteudo clinico detalhado",
                    "Atuacao administrativa de entrada",
                    "Escopo restrito a unidade",
                ],
            ),
            _role_item(
                code="SAU_REGULACAO",
                nivel="Regulacao e fila",
                dashboard="Dashboard Saude (regulacao)",
                funcoes=[
                    "Gerenciar encaminhamentos e prioridades",
                    "Monitorar filas de atendimento",
                    "Garantir rastreabilidade de regulacao",
                ],
                atribuicoes=[
                    "Acesso focado em fluxo regulatorio",
                    "Sem detalhamento clinico alem do necessario",
                    "Acoes com rastreabilidade operacional",
                ],
            ),
            _role_item(
                code="SAU_FARMACIA",
                nivel="Farmacia municipal/unidade",
                dashboard="Dashboard Saude (dispensacao)",
                funcoes=[
                    "Controlar dispensacao permitida",
                    "Acompanhar estoque (quando habilitado)",
                    "Registrar movimentacoes de farmacia",
                ],
                atribuicoes=[
                    "Acesso ao necessario para dispensacao",
                    "Sem historico clinico completo por padrao",
                    "Escopo restrito a unidade",
                ],
            ),
        ],
    },
    {
        "area": "Educacao",
        "roles": [
            _role_item(
                code="EDU_SECRETARIO",
                nivel="Gestao setorial da educacao",
                dashboard="Dashboard Educacao + NEE (escopo secretaria)",
                funcoes=[
                    "Conduzir politicas educacionais da rede",
                    "Monitorar matriculas e desempenho",
                    "Gerir indicadores e relatorios setoriais",
                ],
                atribuicoes=[
                    "Visao ampla da secretaria de educacao",
                    "Acesso integrado a dados NEE do escopo",
                    "Sem administracao tecnica global",
                ],
            ),
            _role_item(
                code="EDU_DIRETOR",
                nivel="Gestao escolar",
                dashboard="Dashboard Educacao (escopo unidade escolar)",
                funcoes=[
                    "Gerenciar operacao da escola",
                    "Acompanhar turmas, diario e matriculas",
                    "Validar consistencia dos registros escolares",
                ],
                atribuicoes=[
                    "Acesso integral da escola",
                    "Sem visao global municipal por padrao",
                    "Foco operacional e pedagogico",
                ],
            ),
            _role_item(
                code="EDU_COORD",
                nivel="Coordenacao pedagogica",
                dashboard="Dashboard Educacao (turmas/escola)",
                funcoes=[
                    "Acompanhar planejamento e execucao pedagogica",
                    "Apoiar professores e evolucao das turmas",
                    "Monitorar qualidade de lancamentos",
                ],
                atribuicoes=[
                    "Opera no escopo da unidade",
                    "Sem governanca global da plataforma",
                    "Atuacao orientada ao processo pedagogico",
                ],
            ),
            _role_item(
                code="PROFESSOR",
                nivel="Docencia operacional",
                dashboard="Dashboard Educacao (turmas atribuidas)",
                funcoes=[
                    "Registrar frequencia, conteudo e avaliacoes",
                    "Acompanhar alunos da propria turma",
                    "Executar rotina de diario e notas",
                ],
                atribuicoes=[
                    "Acesso restrito a turmas vinculadas",
                    "Sem visao da rede completa",
                    "Nao gerencia configuracoes e usuarios",
                ],
            ),
            _role_item(
                code="EDU_PROF",
                nivel="Docencia operacional",
                dashboard="Dashboard Educacao (turmas atribuidas)",
                funcoes=[
                    "Mesmo papel operacional de professor",
                    "Lancar diario e avaliacoes das turmas",
                    "Acompanhar progresso dos alunos vinculados",
                ],
                atribuicoes=[
                    "Escopo por atribuicao",
                    "Sem acesso global da secretaria",
                    "Permissoes pedagogicas operacionais",
                ],
            ),
            _role_item(
                code="EDU_SECRETARIA",
                nivel="Secretaria escolar",
                dashboard="Dashboard Educacao (cadastro/matricula)",
                funcoes=[
                    "Executar matricula e documentacao escolar",
                    "Atualizar cadastro de aluno",
                    "Apoiar fluxo administrativo da escola",
                ],
                atribuicoes=[
                    "Acesso a operacoes administrativas da escola",
                    "Nao substitui atribuicoes pedagogicas do professor",
                    "Escopo restrito a unidade",
                ],
            ),
            _role_item(
                code="EDU_TRANSPORTE",
                nivel="Transporte escolar",
                dashboard="Dashboard Educacao (rotas e apoio)",
                funcoes=[
                    "Acompanhar rotas e alunos vinculados",
                    "Registrar ocorrencias de transporte",
                    "Suportar gestao de deslocamento escolar",
                ],
                atribuicoes=[
                    "Acesso limitado ao contexto de transporte",
                    "Sem acesso a avaliacoes/notas",
                    "Escopo restrito a operacao local",
                ],
            ),
            _role_item(
                code="ALUNO",
                nivel="Portal educacional",
                dashboard="Dashboard do aluno",
                funcoes=[
                    "Consultar avisos, arquivos e informacoes pessoais",
                    "Acompanhar vida escolar liberada",
                    "Interagir em fluxos do portal",
                ],
                atribuicoes=[
                    "Nao acessa dados de outros alunos",
                    "Sem acoes administrativas",
                    "Escopo individual",
                ],
            ),
        ],
    },
    {
        "area": "NEE (Inclusao)",
        "roles": [
            _role_item(
                code="NEE",
                nivel="Tecnico NEE (legado)",
                dashboard="Dashboard NEE",
                funcoes=[
                    "Registrar e acompanhar casos NEE",
                    "Consolidar informacoes tecnicas",
                    "Apoiar a equipe multiprofissional",
                ],
                atribuicoes=[
                    "Acesso focado no modulo NEE",
                    "Opera com escopo definido",
                    "Sem governanca global de plataforma",
                ],
            ),
            _role_item(
                code="NEE_COORD_MUN",
                nivel="Coordenacao municipal NEE",
                dashboard="Dashboard NEE (municipio)",
                funcoes=[
                    "Coordenar politica municipal de inclusao",
                    "Acompanhar indicadores consolidados",
                    "Padronizar fluxos NEE na rede",
                ],
                atribuicoes=[
                    "Visao municipal do NEE",
                    "Acesso integrado com Educacao e Saude (conforme escopo)",
                    "Trilha de auditoria obrigatoria",
                ],
            ),
            _role_item(
                code="NEE_COORD_ESC",
                nivel="Coordenacao NEE da escola",
                dashboard="Dashboard NEE (escola)",
                funcoes=[
                    "Acompanhar casos NEE da unidade",
                    "Consolidar plano de apoio individual",
                    "Apoiar equipe pedagogica no escopo da escola",
                ],
                atribuicoes=[
                    "Acesso restrito aos casos da escola",
                    "Sem visao municipal completa",
                    "Registros com rastreabilidade",
                ],
            ),
            _role_item(
                code="NEE_MEDIADOR",
                nivel="Mediador / professor de apoio",
                dashboard="Dashboard NEE (alunos atribuídos)",
                funcoes=[
                    "Registrar intervencoes e acompanhamento",
                    "Apoiar execucao do plano individual",
                    "Contribuir com evolucao do aluno",
                ],
                atribuicoes=[
                    "Acesso somente a alunos atribuidos",
                    "Sem acesso a casos externos ao escopo",
                    "Regra de minimo privilegio",
                ],
            ),
            _role_item(
                code="NEE_TECNICO",
                nivel="Equipe tecnica multiprofissional",
                dashboard="Dashboard NEE (casos atribuídos)",
                funcoes=[
                    "Emitir pareceres tecnicos",
                    "Consolidar relatorios de acompanhamento",
                    "Apoiar tomada de decisao intersetorial",
                ],
                atribuicoes=[
                    "Acesso por atribuicao e escopo",
                    "Integracao controlada com Educacao/Saude",
                    "Logs obrigatorios de acesso",
                ],
            ),
        ],
    },
    {
        "area": "Dados, Integracoes e Portal",
        "roles": [
            _role_item(
                code="DADOS_GESTOR",
                nivel="Gestao de dados/BI",
                dashboard="Dashboard de paineis e indicadores",
                funcoes=[
                    "Consolidar indicadores gerenciais",
                    "Publicar paineis e visoes executivas",
                    "Apoiar decisoes baseadas em dados",
                ],
                atribuicoes=[
                    "Opera paineis e relatorios",
                    "Nao altera diretamente dado-fonte operacional",
                    "Escopo municipal por governanca",
                ],
            ),
            _role_item(
                code="DADOS_ANALISTA",
                nivel="Analise setorial",
                dashboard="Dashboard de paineis setoriais",
                funcoes=[
                    "Analisar indicadores do setor",
                    "Consolidar relatorios e exportacoes",
                    "Apoiar auditoria e gestao",
                ],
                atribuicoes=[
                    "Escopo limitado ao setor autorizado",
                    "Sem administracao de conectores tecnicos",
                    "Foco analitico",
                ],
            ),
            _role_item(
                code="INT_TI",
                nivel="Integracoes tecnicas",
                dashboard="Dashboard de integracoes",
                funcoes=[
                    "Configurar conectores, chaves e filas",
                    "Monitorar sincronizacoes e falhas",
                    "Administrar integracoes criticas",
                ],
                atribuicoes=[
                    "Permissao tecnica de integracoes (admin)",
                    "Acesso a configuracoes sensiveis de conector",
                    "Escopo controlado por governanca",
                ],
            ),
            _role_item(
                code="INT_GESTAO",
                nivel="Gestao de integracoes",
                dashboard="Dashboard de status de integracoes",
                funcoes=[
                    "Acompanhar status dos conectores",
                    "Gerenciar habilitacao funcional de integrações",
                    "Apoiar governanca entre negocio e TI",
                ],
                atribuicoes=[
                    "Permissao de gestao sem admin tecnico total",
                    "Acesso a relatorios de integracao",
                    "Sem manutencao profunda de segredos",
                ],
            ),
            _role_item(
                code="INT_LEITOR",
                nivel="Leitura de integracoes",
                dashboard="Dashboard de integracoes (somente leitura)",
                funcoes=[
                    "Acompanhar saude dos conectores",
                    "Consultar relatorios e eventos",
                    "Apoiar monitoramento institucional",
                ],
                atribuicoes=[
                    "Sem permissao de alterar conectores",
                    "Acesso apenas de consulta",
                    "Escopo definido por governanca",
                ],
            ),
            _role_item(
                code="PORTAL_ADMIN",
                nivel="Administracao de portal publico",
                dashboard="Dashboard de publicacoes/portal",
                funcoes=[
                    "Gerenciar publicacoes institucionais",
                    "Coordenar conteudo publico municipal",
                    "Supervisionar operacao editorial",
                ],
                atribuicoes=[
                    "Acesso ao fluxo de publicacao no escopo",
                    "Governanca editorial da prefeitura",
                    "Sem papel tecnico de infraestrutura",
                ],
            ),
            _role_item(
                code="PORTAL_EDITOR",
                nivel="Edicao de conteudo",
                dashboard="Dashboard de publicacoes/portal",
                funcoes=[
                    "Criar e editar conteudos publicos",
                    "Preparar noticias, paginas e banners",
                    "Organizar material para aprovacao",
                ],
                atribuicoes=[
                    "Atua no fluxo editorial",
                    "Publicacao pode depender de aprovador",
                    "Escopo restrito a conteudo",
                ],
            ),
            _role_item(
                code="PORTAL_APROV",
                nivel="Aprovacao editorial",
                dashboard="Dashboard de publicacoes/portal",
                funcoes=[
                    "Revisar conteudos e aprovar publicacao",
                    "Garantir conformidade institucional",
                    "Aplicar padrao comunicacional oficial",
                ],
                atribuicoes=[
                    "Foco em homologacao/publicacao",
                    "Sem gestao tecnica de infraestrutura",
                    "Escopo por governanca de comunicacao",
                ],
            ),
            _role_item(
                code="PORTAL_DESIGN",
                nivel="Design e tema",
                dashboard="Dashboard de publicacoes/portal",
                funcoes=[
                    "Ajustar tema visual e estrutura do portal",
                    "Gerenciar identidade visual institucional",
                    "Versionar alteracoes de layout",
                ],
                atribuicoes=[
                    "Foco em tema e apresentacao",
                    "Sem administracao tecnica da plataforma",
                    "Escopo de comunicacao institucional",
                ],
            ),
            _role_item(
                code="CIDADAO",
                nivel="Usuario externo",
                dashboard="Portal do cidadao",
                funcoes=[
                    "Consultar conteudo e servicos publicos",
                    "Abrir solicitacoes quando habilitado",
                    "Acompanhar protocolos no proprio contexto",
                ],
                atribuicoes=[
                    "Acesso somente aos proprios dados/solicitacoes",
                    "Nao possui permissao administrativa interna",
                    "Escopo externo e individual",
                ],
            ),
        ],
    },
]


def role_label_map() -> dict[str, str]:
    return {value: label for value, label in Profile.Role.choices}


def role_details_map() -> dict[str, dict]:
    details: dict[str, dict] = {}
    labels = role_label_map()
    for section in ROLE_REPORT_SECTIONS:
        area = str(section.get("area") or "")
        for raw in section.get("roles", []):
            item = dict(raw)
            code = str(item.get("code") or "").upper()
            if not code:
                continue
            item["label"] = labels.get(code, code)
            item["area"] = area
            details[code] = item
    return details


def _role_order() -> list[str]:
    return [value for value, _ in Profile.Role.choices]


def _bool(v: bool) -> str:
    return "SIM" if v else "NAO"


def _has(perms: set[str], perm: str) -> bool:
    return perm in perms


def _portal_ops(role_code: str, perms: set[str]) -> dict[str, bool]:
    role = (role_code or "").upper()
    editorial = {
        "PORTAL_ADMIN",
        "PORTAL_EDITOR",
        "PORTAL_APROV",
        "PORTAL_DESIGN",
        "ADMIN",
        "MUNICIPAL",
        "SECRETARIA",
    }
    approve_set = {"PORTAL_APROV", "PORTAL_ADMIN", "ADMIN", "MUNICIPAL", "SECRETARIA"}
    design_set = {"PORTAL_DESIGN", "PORTAL_ADMIN", "ADMIN", "MUNICIPAL"}
    can_view_portal = _has(perms, "org.view") and role in editorial
    can_manage_portal = can_view_portal and role in editorial
    return {
        "view": can_view_portal,
        "create": can_manage_portal,
        "edit": can_manage_portal,
        "delete": can_manage_portal and role in {"PORTAL_ADMIN", "ADMIN", "MUNICIPAL", "SECRETARIA"},
        "approve": role in approve_set,
        "export": _has(perms, "reports.view") or _has(perms, "paineis.view"),
        "configure_module": role in design_set,
    }


def build_operational_matrix_rows() -> list[dict[str, str]]:
    details = role_details_map()
    rows: list[dict[str, str]] = []
    for role_code in _role_order():
        role_norm = (role_code or "").upper()
        perms = set(ROLE_PERMS_FINE.get(role_norm, set()))
        role_detail = details.get(role_norm, {})
        for module in MATRIX_MODULES:
            module_key = module["key"]
            if module_key == "portal":
                ops = _portal_ops(role_norm, perms)
            else:
                module_manage = _has(perms, f"{module_key}.manage")
                module_admin = _has(perms, f"{module_key}.admin")
                module_publish = _has(perms, f"{module_key}.publish")
                module_view = _has(perms, f"{module_key}.view")
                if module_key == "org":
                    module_view = module_view or any(
                        _has(perms, p)
                        for p in ("org.manage_municipio", "org.manage_secretaria", "org.manage_unidade")
                    )
                    module_manage = module_manage or any(
                        _has(perms, p)
                        for p in ("org.manage_municipio", "org.manage_secretaria", "org.manage_unidade")
                    )
                ops = {
                    "view": module_view,
                    "create": module_manage,
                    "edit": module_manage,
                    "delete": module_manage,
                    "approve": module_publish,
                    "export": _has(perms, "reports.view") or module_key in {"paineis", "conversor"},
                    "configure_module": module_admin or (module_key == "org" and module_manage),
                }

            reports_access = _has(perms, "reports.view") or _has(perms, "paineis.view")
            manage_users = _has(perms, "accounts.manage_users")
            row = {
                "role_code": role_norm,
                "role_name": role_detail.get("label", role_norm),
                "area": role_detail.get("area", "Nao classificado"),
                "scope_base": role_scope_base(role_norm),
                "module_key": module_key,
                "module_name": module["label"],
                "view": _bool(bool(ops["view"])),
                "create": _bool(bool(ops["create"])),
                "edit": _bool(bool(ops["edit"])),
                "delete": _bool(bool(ops["delete"])),
                "approve": _bool(bool(ops["approve"])),
                "export": _bool(bool(ops["export"])),
                "manage_users": _bool(manage_users),
                "configure_module": _bool(bool(ops["configure_module"])),
                "reports": _bool(reports_access),
            }
            rows.append(row)
    return rows


def build_site_role_sections() -> list[dict[str, object]]:
    labels = role_label_map()
    output: list[dict[str, object]] = []
    for section in ROLE_REPORT_SECTIONS:
        roles_render: list[dict[str, object]] = []
        for role in section.get("roles", []):
            code = str(role.get("code") or "").upper()
            role_copy = dict(role)
            role_copy["label"] = labels.get(code, code)
            role_copy["scope_base"] = role_scope_base(code)
            roles_render.append(role_copy)
        output.append(
            {
                "area": section.get("area", ""),
                "roles": roles_render,
            }
        )
    return output


def export_operational_matrix(docs_dir: str | Path) -> tuple[Path, Path]:
    target = Path(docs_dir)
    target.mkdir(parents=True, exist_ok=True)
    rows = build_operational_matrix_rows()

    json_path = target / "rbac_matriz_operacional_gepub.json"
    csv_path = target / "rbac_matriz_operacional_gepub.csv"

    payload = {
        "generated_at": date.today().isoformat(),
        "source": "apps/core/rbac.py (ROLE_PERMS_FINE + ROLE_SCOPE_BASE)",
        "columns": [
            "role_code",
            "role_name",
            "area",
            "scope_base",
            "module_key",
            "module_name",
            "view",
            "create",
            "edit",
            "delete",
            "approve",
            "export",
            "manage_users",
            "configure_module",
            "reports",
        ],
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=payload["columns"])
        writer.writeheader()
        writer.writerows(rows)

    return json_path, csv_path


def build_role_report_markdown() -> str:
    lines: list[str] = []
    lines.append("# GEPUB - Relatorio de Usuarios, Funcoes e Atribuicoes")
    lines.append("")
    lines.append(f"Gerado em: {date.today().isoformat()}")
    lines.append("")
    lines.append("## Regras gerais")
    lines.append("")
    lines.append("- Mesma dashboard por modulo, com visao filtrada por papel e escopo.")
    lines.append("- Escopo minimo necessario: municipio, secretaria, unidade e atribuicao pessoal.")
    lines.append("- Acoes-base consideradas: ver, criar, editar, excluir, aprovar/homologar, exportar, configurar.")
    lines.append("- Gestao de usuarios e relatorios depende de permissao especifica por perfil.")
    lines.append("")
    lines.append("## Perfis por area")
    lines.append("")

    labels = role_label_map()
    for section in ROLE_REPORT_SECTIONS:
        area = str(section.get("area") or "")
        lines.append(f"### {area}")
        lines.append("")
        for role in section.get("roles", []):
            code = str(role.get("code") or "").upper()
            nome = labels.get(code, code)
            scope = role_scope_base(code)
            nivel = str(role.get("nivel") or "")
            dashboard = str(role.get("dashboard") or "")
            lines.append(f"#### {nome} (`{code}`)")
            lines.append("")
            lines.append(f"- Nivel: {nivel}")
            lines.append(f"- Escopo base: {scope}")
            lines.append(f"- Dashboard: {dashboard}")
            lines.append("- Funcoes:")
            for item in role.get("funcoes", []):
                lines.append(f"  - {item}")
            lines.append("- Atribuicoes:")
            for item in role.get("atribuicoes", []):
                lines.append(f"  - {item}")
            lines.append("")
    lines.append("## Entregaveis")
    lines.append("")
    lines.append("- Matriz JSON: `docs/rbac_matriz_operacional_gepub.json`")
    lines.append("- Matriz CSV: `docs/rbac_matriz_operacional_gepub.csv`")
    lines.append("- Relatorio textual: `docs/rbac_relatorio_usuarios_gepub.md`")
    lines.append("")
    return "\n".join(lines)


def export_role_report_markdown(docs_dir: str | Path) -> Path:
    target = Path(docs_dir)
    target.mkdir(parents=True, exist_ok=True)
    md_path = target / "rbac_relatorio_usuarios_gepub.md"
    md_path.write_text(build_role_report_markdown(), encoding="utf-8")
    return md_path
