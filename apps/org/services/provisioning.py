from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from apps.org.models import (
    Municipio,
    MunicipioModuloAtivo,
    OnboardingStep,
    Secretaria,
    SecretariaCadastroBase,
    SecretariaConfiguracao,
    SecretariaModuloAtivo,
    SecretariaProvisionamento,
    SecretariaTemplate,
    SecretariaTemplateItem,
    Setor,
    Unidade,
)


def _perfis_padrao(prefixo: str, app_labels: list[str]) -> list[dict]:
    apps_base = sorted(set([*app_labels, "org", "accounts", "core"]))
    apps_gestao = sorted(set([*app_labels, "org"]))
    apps_operacao = sorted(set(app_labels))
    return [
        {"nome": f"{prefixo} • Secretário(a)", "app_labels": apps_base},
        {"nome": f"{prefixo} • Diretor(a)", "app_labels": apps_gestao},
        {"nome": f"{prefixo} • Chefe de setor", "app_labels": apps_gestao},
        {"nome": f"{prefixo} • Operador", "app_labels": apps_operacao},
        {"nome": f"{prefixo} • Consulta", "app_labels": apps_operacao},
    ]


def _configuracoes_padrao(
    *,
    prefixo_documento: str,
    tipos_processo: list[str],
    indicadores: list[str],
    relatorios: list[str],
) -> list[dict]:
    return [
        {
            "chave": "numeracao_documentos",
            "descricao": "Configuração padrão de numeração de documentos.",
            "valor": {
                "prefixo": prefixo_documento,
                "sequencia_inicial": 1,
                "ano_corrente": True,
            },
        },
        {
            "chave": "tipos_processo_habilitados",
            "descricao": "Tipos de processos administrativos liberados para a secretaria.",
            "valor": {"tipos": tipos_processo},
        },
        {
            "chave": "indicadores_habilitados",
            "descricao": "Indicadores iniciais habilitados no dashboard.",
            "valor": {"indicadores": indicadores},
        },
        {
            "chave": "relatorios_habilitados",
            "descricao": "Relatórios padrão habilitados para a operação inicial.",
            "valor": {"relatorios": relatorios},
        },
    ]


def _onboarding_padrao(
    *,
    codigo_manual: str,
    titulo_manual: str,
    descricao_manual: str,
    url_manual: str,
) -> list[dict]:
    return [
        {
            "codigo": "estrutura_secretaria",
            "titulo": "Validar estrutura institucional",
            "descricao": "Confirme unidades e setores criados automaticamente no onboarding.",
            "url_name": "org:setor_list",
            "ordem": 1,
        },
        {
            "codigo": "configuracoes_secretaria",
            "titulo": "Revisar configurações padrão",
            "descricao": "Revise numeração, tipos de processo e indicadores habilitados.",
            "url_name": "org:secretaria_list",
            "ordem": 2,
        },
        {
            "codigo": "cadastros_base_secretaria",
            "titulo": "Conferir cadastros-base",
            "descricao": "Valide categorias, motivos, status e tabelas de referência geradas.",
            "url_name": "org:secretaria_list",
            "ordem": 3,
        },
        {
            "codigo": codigo_manual,
            "titulo": titulo_manual,
            "descricao": descricao_manual,
            "url_name": url_manual,
            "ordem": 4,
        },
    ]


def _unidade_item(nome: str, ordem: int, *, ref: str, tipo: str) -> dict:
    return {
        "tipo": SecretariaTemplateItem.Tipo.UNIDADE,
        "nome": nome,
        "ordem": ordem,
        "metadata": {
            "ref": ref,
            "tipo_unidade": tipo,
        },
    }


def _setor_item(nome: str, ordem: int, *, unidade_ref: str = "sede") -> dict:
    return {
        "tipo": SecretariaTemplateItem.Tipo.SETOR,
        "nome": nome,
        "ordem": ordem,
        "metadata": {
            "unidade_ref": unidade_ref,
        },
    }


def _cadastro_item(categoria: str, nome: str, ordem: int, *, codigo: str = "", metadata: dict | None = None) -> dict:
    return {
        "categoria": categoria,
        "nome": nome,
        "codigo": codigo,
        "ordem": ordem,
        "metadata": metadata or {},
    }


TEMPLATE_DEFINITIONS: list[dict] = [
    {
        "slug": "administracao",
        "nome": "Secretaria de Administração",
        "descricao": "Modelo obrigatório para governança institucional, RH, patrimônio e almoxarifado.",
        "modulo": SecretariaTemplate.Modulo.ADMINISTRACAO,
        "modulos_ativos_padrao": ["processos", "rh", "ponto", "folha", "patrimonio", "almoxarifado"],
        "tipo_unidade_base": Unidade.Tipo.ADMINISTRACAO,
        "nome_unidade_base": "Sede Administrativa",
        "perfis_padrao": _perfis_padrao(
            "Administração",
            ["org", "processos", "rh", "ponto", "folha", "patrimonio", "almoxarifado"],
        ),
        "itens": [
            _unidade_item("Recursos Humanos", 1, ref="rh", tipo=Unidade.Tipo.ADMINISTRACAO),
            _unidade_item("Protocolo Geral", 2, ref="protocolo", tipo=Unidade.Tipo.ADMINISTRACAO),
            _unidade_item("Patrimônio e Almoxarifado", 3, ref="patrimonio", tipo=Unidade.Tipo.ADMINISTRACAO),
            _setor_item("Administração", 10),
            _setor_item("Planejamento", 11),
            _setor_item("Financeiro", 12),
            _setor_item("Atendimento", 13),
            _setor_item("Cadastro e Vida Funcional", 20, unidade_ref="rh"),
            _setor_item("Folha de Pagamento", 21, unidade_ref="rh"),
            _setor_item("Ponto e Frequência", 22, unidade_ref="rh"),
            _setor_item("Entrada de Processos", 30, unidade_ref="protocolo"),
            _setor_item("Tramitação e Despachos", 31, unidade_ref="protocolo"),
            _setor_item("Controle Patrimonial", 40, unidade_ref="patrimonio"),
            _setor_item("Estoque e Requisições", 41, unidade_ref="patrimonio"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="ADM",
            tipos_processo=["RH", "PROTOCOLO", "PATRIMONIO", "ALMOXARIFADO", "COMPRAS_INTERNAS"],
            indicadores=["lotacao_total", "movimentacoes_pendentes", "inventario_ativo", "estoque_critico"],
            relatorios=["quadro_lotacao", "folha_por_setor", "inventario_bens", "consumo_almoxarifado"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("CARGO", "Analista Administrativo", 1),
            _cadastro_item("CARGO", "Assistente Administrativo", 2),
            _cadastro_item("PROCESSO_TIPO", "Admissão", 10),
            _cadastro_item("PROCESSO_TIPO", "Férias", 11),
            _cadastro_item("PROCESSO_TIPO", "Afastamento", 12),
            _cadastro_item("DOCUMENTO_TIPO", "Portaria", 20),
            _cadastro_item("DOCUMENTO_TIPO", "Termo", 21),
            _cadastro_item("BEM_CATEGORIA", "Equipamentos de TI", 30),
            _cadastro_item("BEM_CATEGORIA", "Mobiliário", 31),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="fluxo_rh_ativo",
            titulo_manual="Publicar fluxo operacional de RH",
            descricao_manual="Cadastre ao menos uma movimentação funcional e um documento para validar o fluxo.",
            url_manual="rh:index",
        ),
    },
    {
        "slug": "financas",
        "nome": "Secretaria de Finanças e Fazenda",
        "descricao": "Modelo tributário e fiscal para arrecadação, dívida ativa e fiscalização.",
        "modulo": SecretariaTemplate.Modulo.FINANCAS,
        "modulos_ativos_padrao": ["financeiro", "tributos", "processos", "integracoes"],
        "tipo_unidade_base": Unidade.Tipo.FINANCAS,
        "nome_unidade_base": "Sede da Fazenda",
        "perfis_padrao": _perfis_padrao(
            "Finanças",
            ["financeiro", "tributos", "processos", "integracoes"],
        ),
        "itens": [
            _unidade_item("Tributação", 1, ref="tributacao", tipo=Unidade.Tipo.FINANCAS),
            _unidade_item("Arrecadação", 2, ref="arrecadacao", tipo=Unidade.Tipo.FINANCAS),
            _unidade_item("Dívida Ativa", 3, ref="divida_ativa", tipo=Unidade.Tipo.FINANCAS),
            _unidade_item("Fiscalização", 4, ref="fiscalizacao", tipo=Unidade.Tipo.FINANCAS),
            _setor_item("Administração Fazendária", 10),
            _setor_item("Cadastro de Contribuintes", 20, unidade_ref="tributacao"),
            _setor_item("Lançamentos Tributários", 21, unidade_ref="tributacao"),
            _setor_item("Baixas e Cobrança", 30, unidade_ref="arrecadacao"),
            _setor_item("Inscrição em Dívida Ativa", 40, unidade_ref="divida_ativa"),
            _setor_item("Auditoria Fiscal", 50, unidade_ref="fiscalizacao"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="FAZ",
            tipos_processo=["TRIBUTARIO", "ARRECADACAO", "DIVIDA_ATIVA", "FISCALIZACAO"],
            indicadores=["arrecadacao_mensal", "inadimplencia", "lancamentos_emitidos", "divida_ativa_total"],
            relatorios=["arrecadacao_por_tributo", "inadimplentes", "lancamentos_tributarios", "divida_ativa"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("TRIBUTO_TIPO", "IPTU", 1),
            _cadastro_item("TRIBUTO_TIPO", "ISS", 2),
            _cadastro_item("TRIBUTO_TIPO", "ITBI", 3),
            _cadastro_item("FISCAL_EVENTO", "Notificação Fiscal", 10),
            _cadastro_item("FISCAL_EVENTO", "Auto de Infração", 11),
            _cadastro_item("PROCESSO_TIPO", "Parcelamento", 20),
            _cadastro_item("PROCESSO_TIPO", "Cobrança Administrativa", 21),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_lancamento_tributario",
            titulo_manual="Emitir primeiro lançamento tributário",
            descricao_manual="Registre um lançamento no módulo de tributos para validar arrecadação.",
            url_manual="tributos:lancamento_list",
        ),
    },
    {
        "slug": "planejamento",
        "nome": "Secretaria de Planejamento e Controle Interno",
        "descricao": "Modelo para metas, projetos, indicadores e rotinas de controle interno.",
        "modulo": SecretariaTemplate.Modulo.PLANEJAMENTO,
        "modulos_ativos_padrao": ["processos", "financeiro", "integracoes"],
        "tipo_unidade_base": Unidade.Tipo.PLANEJAMENTO,
        "nome_unidade_base": "Sede de Planejamento",
        "perfis_padrao": _perfis_padrao(
            "Planejamento",
            ["processos", "financeiro", "integracoes"],
        ),
        "itens": [
            _unidade_item("Planejamento Estratégico", 1, ref="estrategico", tipo=Unidade.Tipo.PLANEJAMENTO),
            _unidade_item("Projetos e Convênios", 2, ref="projetos", tipo=Unidade.Tipo.PLANEJAMENTO),
            _unidade_item("Controle Interno", 3, ref="controle", tipo=Unidade.Tipo.PLANEJAMENTO),
            _setor_item("Gestão de Metas", 10, unidade_ref="estrategico"),
            _setor_item("Indicadores Municipais", 11, unidade_ref="estrategico"),
            _setor_item("Carteira de Projetos", 20, unidade_ref="projetos"),
            _setor_item("Riscos e Conformidade", 30, unidade_ref="controle"),
            _setor_item("Auditoria Interna", 31, unidade_ref="controle"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="PLAN",
            tipos_processo=["PPA", "LDO", "LOA", "AUDITORIA_INTERNA", "PROJETO"],
            indicadores=["metas_atingidas", "projetos_no_prazo", "riscos_criticos", "auditorias_concluidas"],
            relatorios=["painel_metas", "status_projetos", "matriz_riscos", "achados_auditoria"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("PROGRAMA", "Gestão Institucional", 1),
            _cadastro_item("PROGRAMA", "Eficiência Administrativa", 2),
            _cadastro_item("INDICADOR", "Execução Orçamentária", 10),
            _cadastro_item("INDICADOR", "Entrega de Projetos", 11),
            _cadastro_item("RISCO", "Atraso em Convênios", 20),
            _cadastro_item("RISCO", "Inconsistência de Dados", 21),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_painel_metas",
            titulo_manual="Registrar primeira meta da gestão",
            descricao_manual="Cadastre uma meta e um indicador para iniciar o acompanhamento.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "educacao",
        "nome": "Secretaria de Educação",
        "descricao": "Modelo com estrutura base para gestão educacional municipal.",
        "modulo": SecretariaTemplate.Modulo.EDUCACAO,
        "modulos_ativos_padrao": ["educacao", "avaliacoes", "processos", "rh", "ponto"],
        "tipo_unidade_base": Unidade.Tipo.EDUCACAO,
        "nome_unidade_base": "Sede da Educação",
        "perfis_padrao": _perfis_padrao("Educação", ["educacao", "avaliacoes", "processos", "rh", "ponto"]),
        "itens": [
            _unidade_item("Coordenação Pedagógica", 1, ref="pedagogico", tipo=Unidade.Tipo.EDUCACAO),
            _unidade_item("Transporte Escolar", 2, ref="transporte", tipo=Unidade.Tipo.EDUCACAO),
            _unidade_item("Alimentação Escolar", 3, ref="merenda", tipo=Unidade.Tipo.EDUCACAO),
            _setor_item("Administração Educacional", 10),
            _setor_item("Matrículas e Documentação", 20, unidade_ref="pedagogico"),
            _setor_item("Acompanhamento Pedagógico", 21, unidade_ref="pedagogico"),
            _setor_item("Rotas Escolares", 30, unidade_ref="transporte"),
            _setor_item("Distribuição de Merenda", 40, unidade_ref="merenda"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="EDU",
            tipos_processo=["MATRICULA", "TRANSFERENCIA", "VIDA_ESCOLAR", "TRANSPORTE_ESCOLAR"],
            indicadores=["alunos_ativos", "frequencia_media", "turmas_abertas", "evasao"],
            relatorios=["matriculas_por_turma", "alunos_por_unidade", "frequencia", "historico_escolar"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("NIVEL_ENSINO", "Educação Infantil", 1),
            _cadastro_item("NIVEL_ENSINO", "Ensino Fundamental", 2),
            _cadastro_item("TURNO", "Matutino", 10),
            _cadastro_item("TURNO", "Vespertino", 11),
            _cadastro_item("MOTIVO_TRANSFERENCIA", "Mudança de endereço", 20),
            _cadastro_item("MOTIVO_TRANSFERENCIA", "Solicitação da família", 21),
        ],
        "onboarding": [
            {
                "codigo": "cadastro_unidades",
                "titulo": "Cadastrar escolas e unidades educacionais",
                "descricao": "Garanta pelo menos 1 unidade educacional ativa.",
                "url_name": "org:unidade_create",
                "ordem": 1,
            },
            {
                "codigo": "configurar_calendario",
                "titulo": "Configurar calendário letivo",
                "descricao": "Cadastre feriados, dias letivos e marcos de bimestre.",
                "url_name": "educacao:calendario_index",
                "ordem": 2,
            },
            {
                "codigo": "turmas_iniciais",
                "titulo": "Criar turmas iniciais",
                "descricao": "Abra as primeiras turmas para iniciar matrículas.",
                "url_name": "educacao:turma_create",
                "ordem": 3,
            },
            {
                "codigo": "cadastros_base_secretaria",
                "titulo": "Conferir cadastros-base educacionais",
                "descricao": "Valide níveis, turnos e motivos iniciais de matrícula/transferência.",
                "url_name": "educacao:index",
                "ordem": 4,
            },
        ],
    },
    {
        "slug": "saude",
        "nome": "Secretaria de Saúde",
        "descricao": "Modelo clínico para atenção básica e regulação.",
        "modulo": SecretariaTemplate.Modulo.SAUDE,
        "modulos_ativos_padrao": ["saude", "processos", "frota"],
        "tipo_unidade_base": Unidade.Tipo.SAUDE,
        "nome_unidade_base": "Sede da Saúde",
        "perfis_padrao": _perfis_padrao("Saúde", ["saude", "processos", "frota"]),
        "itens": [
            _unidade_item("Atenção Básica", 1, ref="atencao", tipo=Unidade.Tipo.SAUDE),
            _unidade_item("Regulação", 2, ref="regulacao", tipo=Unidade.Tipo.SAUDE),
            _unidade_item("Vigilância em Saúde", 3, ref="vigilancia", tipo=Unidade.Tipo.SAUDE),
            _setor_item("Gestão da Saúde", 10),
            _setor_item("Atendimento Clínico", 20, unidade_ref="atencao"),
            _setor_item("Agendamento e Marcação", 30, unidade_ref="regulacao"),
            _setor_item("Farmácia", 31, unidade_ref="regulacao"),
            _setor_item("Fiscalização Sanitária", 40, unidade_ref="vigilancia"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="SAU",
            tipos_processo=["ATENDIMENTO", "REGULACAO", "VIGILANCIA", "TRANSPORTE_SANITARIO"],
            indicadores=["atendimentos_mes", "fila_regulacao", "profissionais_ativos", "encaminhamentos"],
            relatorios=["atendimentos_por_unidade", "producao_profissional", "agenda_clinica", "encaminhamentos"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("ATENDIMENTO_TIPO", "Consulta médica", 1),
            _cadastro_item("ATENDIMENTO_TIPO", "Enfermagem", 2),
            _cadastro_item("ATENDIMENTO_TIPO", "Visita domiciliar", 3),
            _cadastro_item("CLASSIFICACAO_RISCO", "Baixo", 10),
            _cadastro_item("CLASSIFICACAO_RISCO", "Moderado", 11),
            _cadastro_item("CLASSIFICACAO_RISCO", "Alto", 12),
        ],
        "onboarding": [
            {
                "codigo": "cadastro_unidades_saude",
                "titulo": "Cadastrar UBS e unidades de saúde",
                "descricao": "Mantenha pelo menos 1 unidade de saúde ativa.",
                "url_name": "org:unidade_create",
                "ordem": 1,
            },
            {
                "codigo": "cadastro_profissionais",
                "titulo": "Cadastrar profissionais",
                "descricao": "Adicione profissionais e vincule especialidades.",
                "url_name": "saude:profissional_create",
                "ordem": 2,
            },
            {
                "codigo": "configurar_agenda_clinica",
                "titulo": "Configurar agenda clínica",
                "descricao": "Crie a agenda para iniciar atendimentos.",
                "url_name": "saude:agenda_create",
                "ordem": 3,
            },
            {
                "codigo": "cadastros_base_secretaria",
                "titulo": "Conferir cadastros-base clínicos",
                "descricao": "Valide tipos de atendimento e classificação de risco inicial.",
                "url_name": "saude:index",
                "ordem": 4,
            },
        ],
    },
    {
        "slug": "obras",
        "nome": "Secretaria de Obras e Engenharia",
        "descricao": "Modelo para engenharia, fiscalização de obras e manutenção urbana de grande porte.",
        "modulo": SecretariaTemplate.Modulo.OBRAS,
        "modulos_ativos_padrao": ["processos", "compras", "contratos", "frota", "almoxarifado"],
        "tipo_unidade_base": Unidade.Tipo.INFRAESTRUTURA,
        "nome_unidade_base": "Sede de Obras",
        "perfis_padrao": _perfis_padrao("Obras", ["processos", "compras", "contratos", "frota", "almoxarifado"]),
        "itens": [
            _unidade_item("Projetos e Engenharia", 1, ref="projetos", tipo=Unidade.Tipo.INFRAESTRUTURA),
            _unidade_item("Fiscalização de Obras", 2, ref="fiscalizacao", tipo=Unidade.Tipo.INFRAESTRUTURA),
            _unidade_item("Manutenção Urbana", 3, ref="manutencao", tipo=Unidade.Tipo.INFRAESTRUTURA),
            _setor_item("Planejamento de Obras", 10, unidade_ref="projetos"),
            _setor_item("Medições e Atestos", 20, unidade_ref="fiscalizacao"),
            _setor_item("Ordem de Serviço", 30, unidade_ref="manutencao"),
            _setor_item("Almoxarifado de Obras", 31, unidade_ref="manutencao"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="OBR",
            tipos_processo=["OBRA", "MEDICAO", "FISCALIZACAO", "MANUTENCAO_URBANA"],
            indicadores=["obras_em_andamento", "medicoes_atestadas", "os_abertas", "custo_obra"],
            relatorios=["status_obras", "medicoes_por_contrato", "os_por_bairro", "custos_execucao"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("OBRA_TIPO", "Pavimentação", 1),
            _cadastro_item("OBRA_TIPO", "Reforma Predial", 2),
            _cadastro_item("SERVICO_TIPO", "Tapa-buraco", 10),
            _cadastro_item("SERVICO_TIPO", "Drenagem", 11),
            _cadastro_item("PROCESSO_TIPO", "Medição de Contrato", 20),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeira_ordem_servico_obras",
            titulo_manual="Registrar primeira ordem de serviço",
            descricao_manual="Abra um processo operacional de obra/manutenção para validar o fluxo.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "agricultura",
        "nome": "Secretaria de Agricultura",
        "descricao": "Modelo para atendimento ao produtor, programas rurais e patrulha mecanizada.",
        "modulo": SecretariaTemplate.Modulo.AGRICULTURA,
        "modulos_ativos_padrao": ["processos", "pessoas", "frota", "almoxarifado"],
        "tipo_unidade_base": Unidade.Tipo.AGRICULTURA,
        "nome_unidade_base": "Sede da Agricultura",
        "perfis_padrao": _perfis_padrao("Agricultura", ["processos", "pessoas", "frota", "almoxarifado"]),
        "itens": [
            _unidade_item("Atendimento ao Produtor", 1, ref="atendimento", tipo=Unidade.Tipo.AGRICULTURA),
            _unidade_item("Programas Rurais", 2, ref="programas", tipo=Unidade.Tipo.AGRICULTURA),
            _unidade_item("Patrulha Mecanizada", 3, ref="patrulha", tipo=Unidade.Tipo.AGRICULTURA),
            _setor_item("Cadastro de Produtores", 10, unidade_ref="atendimento"),
            _setor_item("Assistência Técnica", 11, unidade_ref="atendimento"),
            _setor_item("Distribuição de Insumos", 20, unidade_ref="programas"),
            _setor_item("Agendamento de Máquinas", 30, unidade_ref="patrulha"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="AGR",
            tipos_processo=["ATENDIMENTO_PRODUTOR", "INSUMOS", "PATRULHA_MECANIZADA", "VISITA_TECNICA"],
            indicadores=["produtores_atendidos", "horas_maquina", "insumos_distribuidos", "visitas_tecnicas"],
            relatorios=["atendimentos_por_localidade", "servicos_maquinas", "insumos_por_programa"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("PROGRAMA_RURAL", "Distribuição de Sementes", 1),
            _cadastro_item("PROGRAMA_RURAL", "Assistência Técnica", 2),
            _cadastro_item("SERVICO_MAQUINA", "Gradagem", 10),
            _cadastro_item("SERVICO_MAQUINA", "Aração", 11),
            _cadastro_item("INSUMO_TIPO", "Semente", 20),
            _cadastro_item("INSUMO_TIPO", "Calcário", 21),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_atendimento_produtor",
            titulo_manual="Registrar primeiro atendimento ao produtor",
            descricao_manual="Cadastre um produtor e registre uma solicitação de serviço/insumo.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "tecnologia",
        "nome": "Secretaria de Tecnologia e Inovação",
        "descricao": "Modelo para suporte, infraestrutura, sistemas e governança de TI.",
        "modulo": SecretariaTemplate.Modulo.TECNOLOGIA,
        "modulos_ativos_padrao": ["integracoes", "processos", "patrimonio", "accounts"],
        "tipo_unidade_base": Unidade.Tipo.TECNOLOGIA,
        "nome_unidade_base": "Sede da Tecnologia",
        "perfis_padrao": _perfis_padrao("Tecnologia", ["integracoes", "processos", "patrimonio", "accounts"]),
        "itens": [
            _unidade_item("Suporte Técnico", 1, ref="suporte", tipo=Unidade.Tipo.TECNOLOGIA),
            _unidade_item("Infraestrutura", 2, ref="infra", tipo=Unidade.Tipo.TECNOLOGIA),
            _unidade_item("Sistemas e Integrações", 3, ref="sistemas", tipo=Unidade.Tipo.TECNOLOGIA),
            _setor_item("Service Desk", 10, unidade_ref="suporte"),
            _setor_item("Gestão de Acessos", 11, unidade_ref="suporte"),
            _setor_item("Redes e Servidores", 20, unidade_ref="infra"),
            _setor_item("Integrações Institucionais", 30, unidade_ref="sistemas"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="TI",
            tipos_processo=["CHAMADO_TI", "GESTAO_ACESSO", "MUDANCA", "INTEGRACAO"],
            indicadores=["sla_chamados", "incidentes_abertos", "ativos_ti", "integracoes_falha"],
            relatorios=["chamados_por_secretaria", "inventario_ti", "execucoes_integracao"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("CHAMADO_TIPO", "Incidente", 1),
            _cadastro_item("CHAMADO_TIPO", "Solicitação", 2),
            _cadastro_item("CHAMADO_TIPO", "Mudança", 3),
            _cadastro_item("ATIVO_TI", "Computador", 10),
            _cadastro_item("ATIVO_TI", "Impressora", 11),
            _cadastro_item("ATIVO_TI", "Rede", 12),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_chamado_ti",
            titulo_manual="Registrar primeiro chamado de TI",
            descricao_manual="Abra um chamado para validar o SLA e a fila operacional de suporte.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "assistencia_social",
        "nome": "Secretaria de Assistência Social",
        "descricao": "Modelo para benefícios, famílias, triagem e acompanhamento socioassistencial.",
        "modulo": SecretariaTemplate.Modulo.ASSISTENCIA,
        "modulos_ativos_padrao": ["processos", "pessoas", "ouvidoria"],
        "tipo_unidade_base": Unidade.Tipo.ASSISTENCIA,
        "nome_unidade_base": "Sede da Assistência Social",
        "perfis_padrao": _perfis_padrao("Assistência Social", ["processos", "pessoas", "ouvidoria"]),
        "itens": [
            _unidade_item("CRAS", 1, ref="cras", tipo=Unidade.Tipo.ASSISTENCIA),
            _unidade_item("CREAS", 2, ref="creas", tipo=Unidade.Tipo.ASSISTENCIA),
            _unidade_item("Benefícios e Programas", 3, ref="beneficios", tipo=Unidade.Tipo.ASSISTENCIA),
            _setor_item("Triagem e Cadastro", 10, unidade_ref="cras"),
            _setor_item("Acompanhamento Familiar", 11, unidade_ref="cras"),
            _setor_item("Atendimento Especializado", 20, unidade_ref="creas"),
            _setor_item("Concessão de Benefícios", 30, unidade_ref="beneficios"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="ASS",
            tipos_processo=["TRIAGEM", "BENEFICIO", "ACOMPANHAMENTO", "ENCAMINHAMENTO_SOCIAL"],
            indicadores=["familias_atendidas", "beneficios_concedidos", "atendimentos_cras", "atendimentos_creas"],
            relatorios=["atendimentos_por_unidade", "beneficios_por_programa", "familias_acompanhadas"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("BENEFICIO_TIPO", "Auxílio eventual", 1),
            _cadastro_item("BENEFICIO_TIPO", "Cesta básica", 2),
            _cadastro_item("ATENDIMENTO_TIPO", "Triagem", 10),
            _cadastro_item("ATENDIMENTO_TIPO", "Acompanhamento", 11),
            _cadastro_item("PROGRAMA_SOCIAL", "PAIF", 20),
            _cadastro_item("PROGRAMA_SOCIAL", "SCFV", 21),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_atendimento_social",
            titulo_manual="Registrar primeiro atendimento socioassistencial",
            descricao_manual="Cadastre família/beneficiário e lance um atendimento inicial.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "meio_ambiente",
        "nome": "Secretaria de Meio Ambiente",
        "descricao": "Modelo para licenciamento, fiscalização e educação ambiental.",
        "modulo": SecretariaTemplate.Modulo.MEIO_AMBIENTE,
        "modulos_ativos_padrao": ["processos", "ouvidoria"],
        "tipo_unidade_base": Unidade.Tipo.MEIO_AMBIENTE,
        "nome_unidade_base": "Sede do Meio Ambiente",
        "perfis_padrao": _perfis_padrao("Meio Ambiente", ["processos", "ouvidoria"]),
        "itens": [
            _unidade_item("Licenciamento", 1, ref="licenciamento", tipo=Unidade.Tipo.MEIO_AMBIENTE),
            _unidade_item("Fiscalização Ambiental", 2, ref="fiscalizacao", tipo=Unidade.Tipo.MEIO_AMBIENTE),
            _unidade_item("Educação Ambiental", 3, ref="educacao_ambiental", tipo=Unidade.Tipo.MEIO_AMBIENTE),
            _setor_item("Análise de Licenças", 10, unidade_ref="licenciamento"),
            _setor_item("Vistorias", 20, unidade_ref="fiscalizacao"),
            _setor_item("Denúncias Ambientais", 21, unidade_ref="fiscalizacao"),
            _setor_item("Projetos de Educação", 30, unidade_ref="educacao_ambiental"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="AMB",
            tipos_processo=["LICENCIAMENTO", "VISTORIA", "AUTO_AMBIENTAL", "DENUNCIA"],
            indicadores=["licencas_emitidas", "vistorias_realizadas", "denuncias_em_aberto"],
            relatorios=["licencas_por_status", "fiscalizacoes_periodo", "denuncias_por_bairro"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("LICENCA_TIPO", "Licença Prévia", 1),
            _cadastro_item("LICENCA_TIPO", "Licença de Operação", 2),
            _cadastro_item("VISTORIA_MOTIVO", "Renovação", 10),
            _cadastro_item("VISTORIA_MOTIVO", "Denúncia", 11),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_processo_licenciamento",
            titulo_manual="Abrir primeiro processo de licenciamento",
            descricao_manual="Inicie um processo ambiental para validar fluxos e prazos de análise.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "transporte_mobilidade",
        "nome": "Secretaria de Transporte e Mobilidade",
        "descricao": "Modelo para frota, rotas, manutenção e operação de mobilidade urbana.",
        "modulo": SecretariaTemplate.Modulo.TRANSPORTE,
        "modulos_ativos_padrao": ["frota", "processos", "almoxarifado"],
        "tipo_unidade_base": Unidade.Tipo.TRANSPORTE,
        "nome_unidade_base": "Sede da Mobilidade",
        "perfis_padrao": _perfis_padrao("Mobilidade", ["frota", "processos", "almoxarifado"]),
        "itens": [
            _unidade_item("Operação de Frota", 1, ref="frota", tipo=Unidade.Tipo.TRANSPORTE),
            _unidade_item("Manutenção de Veículos", 2, ref="manutencao", tipo=Unidade.Tipo.TRANSPORTE),
            _unidade_item("Planejamento de Rotas", 3, ref="rotas", tipo=Unidade.Tipo.TRANSPORTE),
            _setor_item("Controle de Viagens", 10, unidade_ref="frota"),
            _setor_item("Abastecimento", 11, unidade_ref="frota"),
            _setor_item("Oficina", 20, unidade_ref="manutencao"),
            _setor_item("Roteirização", 30, unidade_ref="rotas"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="MOB",
            tipos_processo=["ORDEM_SERVICO", "ABASTECIMENTO", "MANUTENCAO", "ROTA"],
            indicadores=["custo_por_veiculo", "consumo_medio", "viagens_abertas", "manutencoes_abertas"],
            relatorios=["consumo_combustivel", "custos_manutencao", "viagens_periodo"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("SERVICO_FROTA", "Transporte escolar", 1),
            _cadastro_item("SERVICO_FROTA", "Transporte administrativo", 2),
            _cadastro_item("MANUTENCAO_TIPO", "Preventiva", 10),
            _cadastro_item("MANUTENCAO_TIPO", "Corretiva", 11),
            _cadastro_item("COMBUSTIVEL_TIPO", "Diesel", 20),
            _cadastro_item("COMBUSTIVEL_TIPO", "Gasolina", 21),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeira_viagem_registrada",
            titulo_manual="Registrar primeira viagem",
            descricao_manual="Cadastre um veículo e registre uma viagem para iniciar monitoramento.",
            url_manual="frota:viagem_list",
        ),
    },
    {
        "slug": "cultura_turismo_esporte",
        "nome": "Secretaria de Cultura, Turismo e Esporte",
        "descricao": "Modelo para eventos, calendário oficial, espaços públicos e projetos culturais/esportivos.",
        "modulo": SecretariaTemplate.Modulo.CULTURA,
        "modulos_ativos_padrao": ["processos", "ouvidoria"],
        "tipo_unidade_base": Unidade.Tipo.CULTURA,
        "nome_unidade_base": "Sede de Cultura e Esporte",
        "perfis_padrao": _perfis_padrao("Cultura/Turismo/Esporte", ["processos", "ouvidoria"]),
        "itens": [
            _unidade_item("Eventos e Calendário", 1, ref="eventos", tipo=Unidade.Tipo.CULTURA),
            _unidade_item("Projetos Culturais", 2, ref="projetos", tipo=Unidade.Tipo.CULTURA),
            _unidade_item("Espaços e Equipamentos", 3, ref="espacos", tipo=Unidade.Tipo.CULTURA),
            _setor_item("Programação Cultural", 10, unidade_ref="eventos"),
            _setor_item("Agenda Turística", 11, unidade_ref="eventos"),
            _setor_item("Editais e Apoios", 20, unidade_ref="projetos"),
            _setor_item("Gestão de Espaços", 30, unidade_ref="espacos"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="CUL",
            tipos_processo=["EVENTO", "EDITAL", "USO_ESPACO", "PROJETO_CULTURAL"],
            indicadores=["eventos_realizados", "publico_estimado", "espacos_ocupados"],
            relatorios=["eventos_por_periodo", "projetos_apoiados", "ocupacao_espacos"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("EVENTO_TIPO", "Evento cultural", 1),
            _cadastro_item("EVENTO_TIPO", "Evento esportivo", 2),
            _cadastro_item("ESPACO_TIPO", "Praça", 10),
            _cadastro_item("ESPACO_TIPO", "Ginásio", 11),
            _cadastro_item("APOIO_TIPO", "Apoio logístico", 20),
            _cadastro_item("APOIO_TIPO", "Apoio financeiro", 21),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_evento_cadastrado",
            titulo_manual="Cadastrar primeiro evento oficial",
            descricao_manual="Registre um evento com local e estimativa de público para iniciar calendário.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "desenvolvimento_economico",
        "nome": "Secretaria de Desenvolvimento Econômico",
        "descricao": "Modelo para atendimento ao empreendedor, feiras e programas de incentivo.",
        "modulo": SecretariaTemplate.Modulo.DESENVOLVIMENTO,
        "modulos_ativos_padrao": ["processos", "tributos", "pessoas"],
        "tipo_unidade_base": Unidade.Tipo.DESENVOLVIMENTO,
        "nome_unidade_base": "Sede do Desenvolvimento Econômico",
        "perfis_padrao": _perfis_padrao("Desenvolvimento Econômico", ["processos", "tributos", "pessoas"]),
        "itens": [
            _unidade_item("Atendimento ao Empreendedor", 1, ref="atendimento", tipo=Unidade.Tipo.DESENVOLVIMENTO),
            _unidade_item("Programas e Incentivos", 2, ref="programas", tipo=Unidade.Tipo.DESENVOLVIMENTO),
            _unidade_item("Feiras e Eventos", 3, ref="feiras", tipo=Unidade.Tipo.DESENVOLVIMENTO),
            _setor_item("Formalização e Orientação", 10, unidade_ref="atendimento"),
            _setor_item("Incentivos Fiscais", 20, unidade_ref="programas"),
            _setor_item("Gestão de Feiras", 30, unidade_ref="feiras"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="DES",
            tipos_processo=["ATENDIMENTO_EMPRESA", "INCENTIVO", "FEIRA", "ALVARA"],
            indicadores=["empresas_cadastradas", "atendimentos_empreendedor", "programas_ativos"],
            relatorios=["atendimentos_por_tipo", "empresas_por_segmento", "programas_incentivo"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("SEGMENTO_EMPRESA", "Comércio", 1),
            _cadastro_item("SEGMENTO_EMPRESA", "Serviços", 2),
            _cadastro_item("SEGMENTO_EMPRESA", "Indústria", 3),
            _cadastro_item("INCENTIVO_TIPO", "Capacitação", 10),
            _cadastro_item("INCENTIVO_TIPO", "Crédito assistido", 11),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_atendimento_empresarial",
            titulo_manual="Registrar primeiro atendimento ao empreendedor",
            descricao_manual="Cadastre empresa/MEI e registre atendimento inicial para ativar o fluxo.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "habitacao_urbanismo",
        "nome": "Secretaria de Habitação e Urbanismo",
        "descricao": "Modelo para cadastros habitacionais, regularização e acompanhamento de projetos.",
        "modulo": SecretariaTemplate.Modulo.HABITACAO,
        "modulos_ativos_padrao": ["processos", "pessoas"],
        "tipo_unidade_base": Unidade.Tipo.HABITACAO,
        "nome_unidade_base": "Sede da Habitação",
        "perfis_padrao": _perfis_padrao("Habitação", ["processos", "pessoas"]),
        "itens": [
            _unidade_item("Cadastro Habitacional", 1, ref="cadastro", tipo=Unidade.Tipo.HABITACAO),
            _unidade_item("Projetos Habitacionais", 2, ref="projetos", tipo=Unidade.Tipo.HABITACAO),
            _unidade_item("Regularização Urbana", 3, ref="regularizacao", tipo=Unidade.Tipo.HABITACAO),
            _setor_item("Inscrição e Triagem", 10, unidade_ref="cadastro"),
            _setor_item("Acompanhamento de Obras", 20, unidade_ref="projetos"),
            _setor_item("Vistorias e Regularização", 30, unidade_ref="regularizacao"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="HAB",
            tipos_processo=["CADASTRO_HABITACIONAL", "SELECAO", "VISTORIA", "REGULARIZACAO"],
            indicadores=["familias_na_fila", "unidades_entregues", "vistorias_realizadas"],
            relatorios=["fila_habitacional", "atendimento_por_territorio", "vistorias"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("DEMANDA_TIPO", "Moradia nova", 1),
            _cadastro_item("DEMANDA_TIPO", "Melhoria habitacional", 2),
            _cadastro_item("SITUACAO_CADASTRO", "Aguardando análise", 10),
            _cadastro_item("SITUACAO_CADASTRO", "Apto", 11),
            _cadastro_item("SITUACAO_CADASTRO", "Inapto", 12),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeiro_cadastro_habitacional",
            titulo_manual="Registrar primeira demanda habitacional",
            descricao_manual="Cadastre uma família e uma demanda para iniciar a fila oficial.",
            url_manual="processos:list",
        ),
    },
    {
        "slug": "servicos_publicos",
        "nome": "Secretaria de Serviços Públicos",
        "descricao": "Modelo para limpeza, iluminação e manutenção urbana por ordem de serviço.",
        "modulo": SecretariaTemplate.Modulo.SERVICOS_PUBLICOS,
        "modulos_ativos_padrao": ["processos", "frota", "almoxarifado", "ouvidoria"],
        "tipo_unidade_base": Unidade.Tipo.SERVICOS_PUBLICOS,
        "nome_unidade_base": "Sede de Serviços Públicos",
        "perfis_padrao": _perfis_padrao("Serviços Públicos", ["processos", "frota", "almoxarifado", "ouvidoria"]),
        "itens": [
            _unidade_item("Limpeza Urbana", 1, ref="limpeza", tipo=Unidade.Tipo.SERVICOS_PUBLICOS),
            _unidade_item("Iluminação Pública", 2, ref="iluminacao", tipo=Unidade.Tipo.SERVICOS_PUBLICOS),
            _unidade_item("Manutenção Urbana", 3, ref="manutencao", tipo=Unidade.Tipo.SERVICOS_PUBLICOS),
            _setor_item("Planejamento de Equipes", 10),
            _setor_item("Execução de Limpeza", 20, unidade_ref="limpeza"),
            _setor_item("Atendimento de Iluminação", 30, unidade_ref="iluminacao"),
            _setor_item("OS de Manutenção", 40, unidade_ref="manutencao"),
        ],
        "configuracoes_padrao": _configuracoes_padrao(
            prefixo_documento="SEP",
            tipos_processo=["OS_LIMPEZA", "OS_ILUMINACAO", "OS_MANUTENCAO", "PODA"],
            indicadores=["os_abertas", "os_fechadas", "tempo_medio_atendimento", "os_por_bairro"],
            relatorios=["os_status", "os_por_tipo", "atendimento_bairros"],
        ),
        "cadastros_base_padrao": [
            _cadastro_item("OS_TIPO", "Iluminação", 1),
            _cadastro_item("OS_TIPO", "Buraco na via", 2),
            _cadastro_item("OS_TIPO", "Poda", 3),
            _cadastro_item("PRIORIDADE", "Baixa", 10),
            _cadastro_item("PRIORIDADE", "Média", 11),
            _cadastro_item("PRIORIDADE", "Alta", 12),
        ],
        "onboarding": _onboarding_padrao(
            codigo_manual="primeira_os_servicos",
            titulo_manual="Registrar primeira ordem de serviço",
            descricao_manual="Abra uma OS por bairro para iniciar monitoramento operacional.",
            url_manual="processos:list",
        ),
    },
]


@dataclass(slots=True)
class ProvisionResult:
    provisionamento: SecretariaProvisionamento
    secretaria: Secretaria | None
    unidade_base: Unidade | None
    gestor_username: str
    gestor_temp_password: str
    created: bool


def seed_secretaria_templates() -> list[SecretariaTemplate]:
    templates: list[SecretariaTemplate] = []
    for data in TEMPLATE_DEFINITIONS:
        template, _ = SecretariaTemplate.objects.update_or_create(
            slug=data["slug"],
            defaults={
                "nome": data["nome"],
                "descricao": data["descricao"],
                "modulo": data["modulo"],
                "ativo": True,
                "criar_unidade_base": True,
                "nome_unidade_base": data["nome_unidade_base"],
                "tipo_unidade_base": data["tipo_unidade_base"],
                "perfis_padrao": data.get("perfis_padrao") or [],
                "onboarding_padrao": data.get("onboarding") or [],
                "modulos_ativos_padrao": data.get("modulos_ativos_padrao") or [],
                "configuracoes_padrao": data.get("configuracoes_padrao") or [],
                "cadastros_base_padrao": data.get("cadastros_base_padrao") or [],
            },
        )
        templates.append(template)

        existing = {(it.tipo, it.nome): it for it in template.itens.all()}
        keep_keys: set[tuple[str, str]] = set()
        for raw_item in data.get("itens", []):
            key = (raw_item["tipo"], raw_item["nome"])
            keep_keys.add(key)
            if key in existing:
                item = existing[key]
                item.ordem = int(raw_item.get("ordem") or 1)
                item.ativo = True
                item.metadata = raw_item.get("metadata", {})
                item.save(update_fields=["ordem", "ativo", "metadata"])
                continue
            SecretariaTemplateItem.objects.create(
                template=template,
                tipo=raw_item["tipo"],
                nome=raw_item["nome"],
                ordem=int(raw_item.get("ordem") or 1),
                ativo=True,
                metadata=raw_item.get("metadata", {}),
            )

        for key, item in existing.items():
            if key not in keep_keys and item.ativo:
                item.ativo = False
                item.save(update_fields=["ativo"])

    return templates


def _username_base_from_secretaria(secretaria_nome: str) -> str:
    base = slugify(secretaria_nome or "secretaria").replace("-", ".")
    base = base[:24].strip(".") or "gestor.secretaria"
    if not base.startswith("gestor."):
        base = f"gestor.{base}"
    return base[:30]


def _next_available_username(base: str) -> str:
    User = get_user_model()
    if not User.objects.filter(username=base).exists():
        return base
    idx = 2
    while True:
        cand = f"{base}.{idx}"
        if not User.objects.filter(username=cand).exists():
            return cand
        idx += 1


def _create_secretaria_gestor(
    municipio: Municipio,
    secretaria: Secretaria,
    unidade_base: Unidade | None,
    perfis_padrao: Iterable[dict],
) -> tuple[str, str]:
    User = get_user_model()
    from apps.accounts.models import Profile

    username = _next_available_username(_username_base_from_secretaria(secretaria.nome))
    domain = "prefeitura.local"
    if municipio.email_prefeitura and "@" in municipio.email_prefeitura:
        domain = municipio.email_prefeitura.split("@", 1)[1]
    email = f"{username}@{domain}"
    password = get_random_string(12)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name="Gestor",
        last_name=secretaria.nome[:120],
    )

    profile = getattr(user, "profile", None)
    if not profile:
        profile = Profile.objects.create(user=user)

    profile.role = Profile.Role.SECRETARIA
    profile.ativo = True
    profile.must_change_password = True
    profile.municipio = municipio
    profile.secretaria = secretaria
    if unidade_base:
        profile.unidade = unidade_base
    profile.save(
        update_fields=[
            "role",
            "ativo",
            "must_change_password",
            "municipio",
            "secretaria",
            "unidade",
        ]
    )

    group_names = [item.get("nome") for item in perfis_padrao if item.get("nome")]
    if group_names:
        groups = Group.objects.filter(name__in=group_names)
        if groups:
            user.groups.add(*groups)

    return username, password


def _ensure_group_permissions(group_name: str, app_labels: list[str]) -> None:
    group, _ = Group.objects.get_or_create(name=group_name)
    perms = Permission.objects.filter(content_type__app_label__in=app_labels)
    if perms.exists():
        group.permissions.set(perms)


def ensure_template_groups(template: SecretariaTemplate) -> None:
    for perfil in template.perfis_padrao or []:
        group_name = (perfil or {}).get("nome")
        app_labels = (perfil or {}).get("app_labels") or []
        if group_name and app_labels:
            _ensure_group_permissions(group_name, app_labels)


def ensure_municipio_modulo_ativo(municipio: Municipio, modulo: str) -> MunicipioModuloAtivo:
    mod, _ = MunicipioModuloAtivo.objects.update_or_create(
        municipio=municipio,
        modulo=modulo,
        defaults={"ativo": True},
    )
    return mod


def ensure_secretaria_modulo_ativo(secretaria: Secretaria, modulo: str) -> SecretariaModuloAtivo:
    mod, _ = SecretariaModuloAtivo.objects.update_or_create(
        secretaria=secretaria,
        modulo=modulo,
        defaults={"ativo": True},
    )
    return mod


def _modules_for_template(template: SecretariaTemplate) -> list[str]:
    raw = [template.modulo, *(template.modulos_ativos_padrao or [])]
    ordered: list[str] = []
    for item in raw:
        mod = (item or "").strip().lower()
        if not mod or mod in ordered:
            continue
        ordered.append(mod)
    return ordered


def _ensure_onboarding_steps_for_template(
    municipio: Municipio,
    secretaria: Secretaria | None,
    template: SecretariaTemplate,
) -> None:
    default_steps = template.onboarding_padrao or []
    for idx, step in enumerate(default_steps, start=1):
        OnboardingStep.objects.update_or_create(
            municipio=municipio,
            secretaria=secretaria,
            modulo=template.modulo,
            codigo=step.get("codigo") or f"step_{idx}",
            defaults={
                "titulo": step.get("titulo") or "Etapa de configuração",
                "descricao": step.get("descricao") or "",
                "ordem": int(step.get("ordem") or idx),
                "status": OnboardingStep.Status.PENDENTE,
                "url_name": step.get("url_name") or "",
            },
        )


def _ensure_secretaria_configuracoes(secretaria: Secretaria, template: SecretariaTemplate, usuario) -> None:
    for item in template.configuracoes_padrao or []:
        chave = str((item or {}).get("chave") or "").strip()
        if not chave:
            continue
        SecretariaConfiguracao.objects.update_or_create(
            secretaria=secretaria,
            chave=chave,
            defaults={
                "descricao": (item or {}).get("descricao") or "",
                "valor": (item or {}).get("valor") or {},
                "atualizado_por": usuario,
            },
        )


def _ensure_secretaria_cadastros_base(secretaria: Secretaria, template: SecretariaTemplate) -> None:
    for idx, item in enumerate(template.cadastros_base_padrao or [], start=1):
        nome = str((item or {}).get("nome") or "").strip()
        if not nome:
            continue
        SecretariaCadastroBase.objects.update_or_create(
            secretaria=secretaria,
            categoria=str((item or {}).get("categoria") or "GERAL").strip().upper(),
            nome=nome,
            defaults={
                "codigo": str((item or {}).get("codigo") or "").strip(),
                "ordem": int((item or {}).get("ordem") or idx),
                "ativo": bool((item or {}).get("ativo", True)),
                "metadata": (item or {}).get("metadata") or {},
            },
        )

    for item in template.itens.filter(ativo=True, tipo=SecretariaTemplateItem.Tipo.CARGO).order_by("ordem", "id"):
        SecretariaCadastroBase.objects.update_or_create(
            secretaria=secretaria,
            categoria="CARGO_FUNCAO",
            nome=item.nome,
            defaults={
                "codigo": str((item.metadata or {}).get("codigo") or "").strip(),
                "ordem": item.ordem,
                "ativo": True,
                "metadata": item.metadata or {},
            },
        )


def _ensure_template_structure(
    secretaria: Secretaria,
    template: SecretariaTemplate,
    unidade_base: Unidade | None,
) -> None:
    unidades_ref: dict[str, Unidade] = {}

    if unidade_base:
        for ref in {
            "sede",
            "base",
            slugify(unidade_base.nome),
        }:
            if ref:
                unidades_ref[str(ref).strip().lower()] = unidade_base

    unidade_items = list(template.itens.filter(ativo=True, tipo=SecretariaTemplateItem.Tipo.UNIDADE).order_by("ordem", "id"))
    for item in unidade_items:
        meta = item.metadata or {}
        unidade, _ = Unidade.objects.get_or_create(
            secretaria=secretaria,
            nome=item.nome,
            defaults={
                "tipo": (meta.get("tipo_unidade") or template.tipo_unidade_base),
                "ativo": True,
            },
        )
        if not unidade.ativo:
            unidade.ativo = True
            unidade.save(update_fields=["ativo"])

        refs = {
            slugify(unidade.nome),
            str(meta.get("ref") or "").strip().lower(),
        }
        for ref in refs:
            if ref:
                unidades_ref[ref] = unidade

    unidade_fallback = unidade_base
    if not unidade_fallback:
        unidade_fallback = Unidade.objects.filter(secretaria=secretaria, ativo=True).order_by("nome").first()

    setor_items = list(template.itens.filter(ativo=True, tipo=SecretariaTemplateItem.Tipo.SETOR).order_by("ordem", "id"))
    for item in setor_items:
        meta = item.metadata or {}
        unidade_ref = str(meta.get("unidade_ref") or "").strip().lower()
        unidade_destino = unidades_ref.get(unidade_ref) if unidade_ref else None

        if not unidade_destino:
            unidade_nome = str(meta.get("unidade_nome") or "").strip()
            if unidade_nome:
                unidade_destino = Unidade.objects.filter(secretaria=secretaria, nome=unidade_nome).first()

        if not unidade_destino:
            unidade_destino = unidade_fallback

        if not unidade_destino:
            continue

        setor, _ = Setor.objects.get_or_create(
            unidade=unidade_destino,
            nome=item.nome,
            defaults={"ativo": True},
        )
        if not setor.ativo:
            setor.ativo = True
            setor.save(update_fields=["ativo"])


def refresh_onboarding_progress(municipio: Municipio) -> None:
    try:
        from apps.educacao.models import Turma
    except Exception:  # pragma: no cover - proteção para deploy parcial
        Turma = None
    try:
        from apps.educacao.models_calendario import CalendarioEducacionalEvento
    except Exception:  # pragma: no cover - proteção para deploy parcial
        CalendarioEducacionalEvento = None
    try:
        from apps.saude.models import ProfissionalSaude
    except Exception:  # pragma: no cover - proteção para deploy parcial
        ProfissionalSaude = None

    checks: dict[str, callable] = {
        "cadastro_unidades": lambda st: Unidade.objects.filter(
            secretaria__municipio=municipio,
            tipo=Unidade.Tipo.EDUCACAO,
            ativo=True,
        ).exists(),
        "configurar_calendario": lambda st: bool(CalendarioEducacionalEvento)
        and CalendarioEducacionalEvento.objects.filter(
            secretaria__municipio=municipio,
            ativo=True,
        ).exists(),
        "turmas_iniciais": lambda st: bool(Turma)
        and Turma.objects.filter(
            unidade__secretaria__municipio=municipio
        ).exists(),
        "cadastro_unidades_saude": lambda st: Unidade.objects.filter(
            secretaria__municipio=municipio,
            tipo=Unidade.Tipo.SAUDE,
            ativo=True,
        ).exists(),
        "cadastro_profissionais": lambda st: bool(ProfissionalSaude)
        and ProfissionalSaude.objects.filter(
            unidade__secretaria__municipio=municipio,
            ativo=True,
        ).exists(),
        "configurar_agenda_clinica": lambda st: False,
        "estrutura_obras": lambda st: Secretaria.objects.filter(
            municipio=municipio,
            nome__icontains="obras",
            ativo=True,
        ).exists(),
        "equipes_obras": lambda st: False,
        "estrutura_secretaria": lambda st: bool(st.secretaria_id)
        and Unidade.objects.filter(secretaria_id=st.secretaria_id, ativo=True).exists()
        and Setor.objects.filter(unidade__secretaria_id=st.secretaria_id, ativo=True).exists(),
        "configuracoes_secretaria": lambda st: bool(st.secretaria_id)
        and SecretariaConfiguracao.objects.filter(secretaria_id=st.secretaria_id).exists(),
        "cadastros_base_secretaria": lambda st: bool(st.secretaria_id)
        and SecretariaCadastroBase.objects.filter(secretaria_id=st.secretaria_id, ativo=True).exists(),
    }

    all_steps = list(
        OnboardingStep.objects.filter(municipio=municipio)
        .select_related("secretaria")
        .order_by("modulo", "ordem", "id")
    )
    grouped: dict[tuple[str, int | None], list[OnboardingStep]] = {}
    for step in all_steps:
        key = (step.modulo, step.secretaria_id)
        grouped.setdefault(key, []).append(step)

    for _, steps in grouped.items():
        first_pending: OnboardingStep | None = None
        for step in steps:
            checker = checks.get(step.codigo)
            done = False
            if checker:
                try:
                    done = bool(checker(step))
                except Exception:
                    done = False
            if done:
                if step.status != OnboardingStep.Status.CONCLUIDO:
                    step.status = OnboardingStep.Status.CONCLUIDO
                    step.save(update_fields=["status", "atualizado_em"])
                continue

            if not first_pending:
                first_pending = step

            if step.status == OnboardingStep.Status.CONCLUIDO:
                step.status = OnboardingStep.Status.PENDENTE
                step.save(update_fields=["status", "atualizado_em"])

        if first_pending and first_pending.status == OnboardingStep.Status.PENDENTE:
            first_pending.status = OnboardingStep.Status.EM_PROGRESSO
            first_pending.save(update_fields=["status", "atualizado_em"])


@transaction.atomic
def provision_secretaria_from_template(
    *,
    municipio: Municipio,
    template: SecretariaTemplate,
    solicitado_por,
    nome_secretaria: str | None = None,
    sigla: str = "",
) -> ProvisionResult:
    modelo_ref = (template.slug or template.modulo or "").strip()
    provisionamento = SecretariaProvisionamento.objects.create(
        municipio=municipio,
        template=template,
        solicitado_por=solicitado_por,
        status=SecretariaProvisionamento.Status.EM_PROCESSAMENTO,
        log="Iniciado provisionamento.",
    )
    created = False
    secretaria = None
    unidade_base = None
    username = ""
    temp_password = ""

    try:
        secretaria_nome = (nome_secretaria or template.nome).strip() or template.nome
        secretaria, created = Secretaria.objects.get_or_create(
            municipio=municipio,
            nome=secretaria_nome,
            defaults={
                "sigla": (sigla or "")[:30],
                "tipo_modelo": modelo_ref,
                "ativo": True,
            },
        )
        if not created:
            update_fields: list[str] = []
            if sigla and secretaria.sigla != sigla[:30]:
                secretaria.sigla = sigla[:30]
                update_fields.append("sigla")
            if modelo_ref and secretaria.tipo_modelo != modelo_ref:
                secretaria.tipo_modelo = modelo_ref
                update_fields.append("tipo_modelo")
            if not secretaria.ativo:
                secretaria.ativo = True
                update_fields.append("ativo")
            if update_fields:
                secretaria.save(update_fields=update_fields)

        if template.criar_unidade_base:
            unidade_base, _ = Unidade.objects.get_or_create(
                secretaria=secretaria,
                nome=template.nome_unidade_base,
                defaults={
                    "tipo": template.tipo_unidade_base,
                    "ativo": True,
                },
            )
            update_fields: list[str] = []
            if unidade_base.tipo != template.tipo_unidade_base:
                unidade_base.tipo = template.tipo_unidade_base
                update_fields.append("tipo")
            if not unidade_base.ativo:
                unidade_base.ativo = True
                update_fields.append("ativo")
            if update_fields:
                unidade_base.save(update_fields=update_fields)

        _ensure_template_structure(secretaria, template, unidade_base)
        ensure_template_groups(template)
        _ensure_secretaria_configuracoes(secretaria, template, solicitado_por)
        _ensure_secretaria_cadastros_base(secretaria, template)

        for modulo in _modules_for_template(template):
            ensure_municipio_modulo_ativo(municipio, modulo)
            ensure_secretaria_modulo_ativo(secretaria, modulo)

        _ensure_onboarding_steps_for_template(municipio, secretaria, template)
        username, temp_password = _create_secretaria_gestor(
            municipio=municipio,
            secretaria=secretaria,
            unidade_base=unidade_base,
            perfis_padrao=template.perfis_padrao or [],
        )
        refresh_onboarding_progress(municipio)

        provisionamento.secretaria = secretaria
        provisionamento.status = SecretariaProvisionamento.Status.CONCLUIDO
        provisionamento.log = (
            f"Provisionamento concluído. Secretaria={secretaria.nome}. "
            f"Gestor={username}. Modulos={','.join(_modules_for_template(template))}."
        )
        provisionamento.save(update_fields=["secretaria", "status", "log", "atualizado_em"])
        return ProvisionResult(
            provisionamento=provisionamento,
            secretaria=secretaria,
            unidade_base=unidade_base,
            gestor_username=username,
            gestor_temp_password=temp_password,
            created=created,
        )
    except Exception as exc:
        provisionamento.status = SecretariaProvisionamento.Status.ERRO
        provisionamento.log = f"Erro no provisionamento: {exc}"
        provisionamento.save(update_fields=["status", "log", "atualizado_em"])
        raise
