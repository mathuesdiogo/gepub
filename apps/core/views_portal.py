from decimal import Decimal
from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.billing.forms import SimuladorPlanoForm
from apps.billing.models import PlanoMunicipal
from apps.billing.services import simular_plano
from apps.compras.models import ProcessoLicitatorio
from apps.contratos.models import AditivoContrato, ContratoAdministrativo
from apps.core.module_access import module_enabled_for_user
from apps.core.models import (
    ConcursoPublico,
    DiarioOficialEdicao,
    InstitutionalMethodStep,
    InstitutionalPageConfig,
    InstitutionalServiceCard,
    InstitutionalSlide,
    PortalBanner,
    PortalTransparenciaArquivo,
    PortalHomeBloco,
    PortalMunicipalConfig,
    PortalNoticia,
    PortalPaginaPublica,
    TransparenciaEventoPublico,
)
from apps.core.portal_public_utils import build_menu_items
from apps.core.rbac import can
from apps.financeiro.models import DespEmpenho
from apps.folha.models import FolhaCompetencia
from apps.org.models import Municipio, Unidade
from apps.rh.models import RhCadastro
from apps.tributos.models import TributoLancamento


@login_required
def portal(request):
    u = request.user
    modules = [
        {
            "key": "educacao",
            "title": "Educação",
            "desc": "Escolas, turmas, alunos, matrículas e relatórios.",
            "icon": "fa-solid fa-graduation-cap",
            "url": "educacao:index",
            "enabled": can(u, "educacao.view") and module_enabled_for_user(u, "educacao"),
            "color": "kpi-blue",
        },
        {
            "key": "avaliacoes",
            "title": "Provas e Gabarito",
            "desc": "Geração de provas com QR, correção assistida e lançamento automático de notas.",
            "icon": "fa-solid fa-file-circle-check",
            "url": "avaliacoes:avaliacao_list",
            "enabled": can(u, "avaliacoes.view") and module_enabled_for_user(u, "avaliacoes"),
            "color": "kpi-green",
        },
        {
            "key": "nee",
            "title": "NEE",
            "desc": "Necessidades Educacionais Especiais e relatórios institucionais.",
            "icon": "fa-solid fa-wheelchair",
            "url": "nee:relatorios_index",
            "enabled": can(u, "nee.view") and module_enabled_for_user(u, "nee"),
            "color": "kpi-purple",
        },
        {
            "key": "saude",
            "title": "Saúde",
            "desc": "Unidades, profissionais e atendimentos.",
            "icon": "fa-solid fa-heart-pulse",
            "url": "saude:index",
            "enabled": can(u, "saude.view") and module_enabled_for_user(u, "saude"),
            "color": "kpi-green",
        },
        {
            "key": "financeiro",
            "title": "Financeiro",
            "desc": "Orçamento, empenhos, liquidações, pagamentos e receitas.",
            "icon": "fa-solid fa-landmark",
            "url": "financeiro:index",
            "enabled": can(u, "financeiro.view") and module_enabled_for_user(u, "financeiro"),
            "color": "kpi-blue",
        },
        {
            "key": "processos",
            "title": "Processos",
            "desc": "Protocolo, tramitacao administrativa e andamentos oficiais.",
            "icon": "fa-solid fa-folder-tree",
            "url": "processos:index",
            "enabled": can(u, "processos.view") and module_enabled_for_user(u, "processos"),
            "color": "kpi-blue",
        },
        {
            "key": "compras",
            "title": "Compras",
            "desc": "Requisicoes, itens, licitacoes e geracao de empenho.",
            "icon": "fa-solid fa-cart-shopping",
            "url": "compras:index",
            "enabled": can(u, "compras.view") and module_enabled_for_user(u, "compras"),
            "color": "kpi-green",
        },
        {
            "key": "contratos",
            "title": "Contratos",
            "desc": "Gestao contratual, aditivos, medicoes e liquidacao.",
            "icon": "fa-solid fa-file-signature",
            "url": "contratos:index",
            "enabled": can(u, "contratos.view") and module_enabled_for_user(u, "contratos"),
            "color": "kpi-purple",
        },
        {
            "key": "rh",
            "title": "RH",
            "desc": "Servidores, movimentações funcionais, documentos e lotação por unidade.",
            "icon": "fa-solid fa-id-badge",
            "url": "rh:index",
            "enabled": can(u, "rh.view") and module_enabled_for_user(u, "rh"),
            "color": "kpi-blue",
        },
        {
            "key": "ponto",
            "title": "Ponto",
            "desc": "Escalas e turnos, ocorrências, vínculos e fechamento por competência.",
            "icon": "fa-solid fa-clock",
            "url": "ponto:index",
            "enabled": can(u, "ponto.view") and module_enabled_for_user(u, "ponto"),
            "color": "kpi-green",
        },
        {
            "key": "folha",
            "title": "Folha",
            "desc": "Rubricas, competências, lançamentos e integração com financeiro.",
            "icon": "fa-solid fa-money-check-dollar",
            "url": "folha:index",
            "enabled": can(u, "folha.view") and module_enabled_for_user(u, "folha"),
            "color": "kpi-blue",
        },
        {
            "key": "patrimonio",
            "title": "Patrimonio",
            "desc": "Bens, inventários, movimentações e rastreabilidade patrimonial.",
            "icon": "fa-solid fa-building-columns",
            "url": "patrimonio:index",
            "enabled": can(u, "patrimonio.view") and module_enabled_for_user(u, "patrimonio"),
            "color": "kpi-purple",
        },
        {
            "key": "almoxarifado",
            "title": "Almoxarifado",
            "desc": "Controle de estoque, movimentações e requisições com aprovação.",
            "icon": "fa-solid fa-boxes-stacked",
            "url": "almoxarifado:index",
            "enabled": can(u, "almoxarifado.view") and module_enabled_for_user(u, "almoxarifado"),
            "color": "kpi-green",
        },
        {
            "key": "frota",
            "title": "Frota",
            "desc": "Veículos, abastecimentos, manutenções e controle de viagens.",
            "icon": "fa-solid fa-truck",
            "url": "frota:index",
            "enabled": can(u, "frota.view") and module_enabled_for_user(u, "frota"),
            "color": "kpi-blue",
        },
        {
            "key": "ouvidoria",
            "title": "Ouvidoria",
            "desc": "Chamados, tramitações setoriais, SLA e respostas ao cidadão.",
            "icon": "fa-solid fa-comments",
            "url": "ouvidoria:index",
            "enabled": can(u, "ouvidoria.view") and module_enabled_for_user(u, "ouvidoria"),
            "color": "kpi-purple",
        },
        {
            "key": "tributos",
            "title": "Tributos",
            "desc": "Contribuintes, emissão de lançamentos e baixa de arrecadação.",
            "icon": "fa-solid fa-receipt",
            "url": "tributos:index",
            "enabled": can(u, "tributos.view") and module_enabled_for_user(u, "tributos"),
            "color": "kpi-green",
        },
        {
            "key": "paineis",
            "title": "Painéis BI",
            "desc": "Ingestão de dados, dashboards, filtros e exportações executivas.",
            "icon": "fa-solid fa-chart-simple",
            "url": "paineis:dataset_list",
            "enabled": can(u, "paineis.view") and module_enabled_for_user(u, "paineis"),
            "color": "kpi-purple",
        },
        {
            "key": "conversor",
            "title": "Conversor",
            "desc": "Transformação de documentos e utilidades de PDF para rotinas operacionais.",
            "icon": "fa-solid fa-file-waveform",
            "url": "conversor:index",
            "enabled": can(u, "conversor.view") and module_enabled_for_user(u, "conversor"),
            "color": "kpi-green",
        },
        {
            "key": "integracoes",
            "title": "Integracoes",
            "desc": "Hub de conectores, execucoes e rastreabilidade.",
            "icon": "fa-solid fa-plug-circle-bolt",
            "url": "integracoes:index",
            "enabled": can(u, "integracoes.view") and module_enabled_for_user(u, "integracoes"),
            "color": "kpi-blue",
        },
    ]

    modules = [m for m in modules if m["enabled"]]
    return render(request, "core/portal.html", {"modules": modules})


def _format_money(value: Decimal | None) -> str:
    if value is None:
        return "Sob proposta"
    val = Decimal(value)
    if val <= 0:
        return "Sob proposta"
    return f"R$ {val.quantize(Decimal('0.01'))}"


def _format_currency_br(value: Decimal | None) -> str:
    amount = Decimal(value or 0).quantize(Decimal("0.01"))
    formatted = f"{amount:,.2f}"
    return f"R$ {formatted.replace(',', '_').replace('.', ',').replace('_', '.')}"


def _planos_para_site() -> list[dict]:
    planos = list(PlanoMunicipal.objects.filter(ativo=True).order_by("preco_base_mensal", "nome"))
    if not planos:
        return [
            {
                "id": 0,
                "codigo": "STARTER",
                "nome": "Starter",
                "descricao": "Plano de entrada para prefeituras pequenas.",
                "preco": "R$ 2.990,00",
                "destaque": "Entrada",
                "features": ["Educação, Saúde e NEE", "Onboarding automático", "Relatórios operacionais"],
                "limits": ["Secretarias: até 4", "Usuários: até 60", "Alunos: até 2.000", "Atendimentos/ano: até 10.000"],
                "overages": ["Secretaria extra: R$ 250/mês", "Usuário extra: R$ 8/mês", "Aluno extra: R$ 0,60/mês"],
            },
            {
                "id": 1,
                "codigo": "MUNICIPAL",
                "nome": "Municipal",
                "descricao": "Plano recomendado por equilíbrio entre escala e custo.",
                "preco": "R$ 6.990,00",
                "destaque": "Recomendado",
                "features": ["BI de gestão municipal", "Importação assistida", "Auditoria de ações críticas"],
                "limits": ["Secretarias: até 8", "Usuários: até 200", "Alunos: até 8.000", "Atendimentos/ano: até 50.000"],
                "overages": ["Secretaria extra: R$ 220/mês", "Usuário extra: R$ 6/mês", "Aluno extra: R$ 0,45/mês"],
            },
            {
                "id": 2,
                "codigo": "GESTAO_TOTAL",
                "nome": "Gestão Total",
                "descricao": "Plano para operação municipal de maior porte.",
                "preco": "R$ 14.900,00",
                "destaque": "Escala",
                "features": ["BI avançado executivo", "SLA prioritário", "Treinamento contínuo"],
                "limits": ["Secretarias: ilimitadas", "Usuários: ilimitados (fair use)", "Alunos: ilimitados (fair use)", "Atendimentos/ano: ilimitados (fair use)"],
                "overages": ["Integrações especiais: sob proposta", "Ambiente extra: sob proposta", "Migração avançada: sob proposta"],
            },
        ]

    cards: list[dict] = []
    for plano in planos:
        limits = [
            f"Secretarias: {plano.limite_secretarias if plano.limite_secretarias is not None else 'ilimitadas (fair use)'}",
            f"Usuários: {plano.limite_usuarios if plano.limite_usuarios is not None else 'ilimitados (fair use)'}",
            f"Alunos: {plano.limite_alunos if plano.limite_alunos is not None else 'ilimitados (fair use)'}",
            f"Atendimentos/ano: {plano.limite_atendimentos_ano if plano.limite_atendimentos_ano is not None else 'ilimitados (fair use)'}",
        ]
        features = [
            "Onboarding automático por secretaria",
            "Implantação, suporte e manutenção inclusos",
        ]
        if plano.feature_importacao_assistida:
            features.append("Importação assistida de dados")
        if plano.feature_bi_municipal:
            features.append("BI municipal de gestão")
        if plano.feature_bi_avancado:
            features.append("BI executivo com metas")
        if plano.feature_sla_prioritario:
            features.append("SLA prioritário")
        if plano.feature_treinamento_continuo:
            features.append("Treinamento contínuo")

        destaque = ""
        if plano.codigo == PlanoMunicipal.Codigo.MUNICIPAL:
            destaque = "Recomendado"
        elif plano.codigo == PlanoMunicipal.Codigo.STARTER:
            destaque = "Entrada"
        elif plano.codigo == PlanoMunicipal.Codigo.GESTAO_TOTAL:
            destaque = "Escala"

        cards.append(
            {
                "id": plano.pk,
                "codigo": plano.codigo,
                "nome": plano.nome,
                "descricao": plano.descricao,
                "preco": _format_money(plano.preco_base_mensal),
                "destaque": destaque,
                "features": features,
                "limits": limits,
                "overages": [
                    f"Secretaria extra: {_format_money(plano.valor_secretaria_extra)}/mês",
                    f"Usuário extra: {_format_money(plano.valor_usuario_extra)}/mês",
                    f"Aluno extra: {_format_money(plano.valor_aluno_extra)}/mês",
                ],
            }
        )
    return cards


def _default_institutional_content() -> dict:
    return {
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
        "hero_cta_secundario_label": "VER PLANOS",
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


def _get_institutional_content() -> tuple[dict, list[dict], list[dict], list[dict]]:
    content = _default_institutional_content()

    page = InstitutionalPageConfig.objects.filter(ativo=True).order_by("-atualizado_em", "-id").first()
    if not page:
        page = InstitutionalPageConfig.objects.order_by("-atualizado_em", "-id").first()

    if page:
        for key in content.keys():
            if hasattr(page, key):
                content[key] = getattr(page, key)

        if page.marca_logo:
            try:
                content["marca_logo_url"] = page.marca_logo.url
            except Exception:
                content["marca_logo_url"] = ""

    slides = []
    steps = []
    services = []

    if page:
        slides = [
            {
                "titulo": s.titulo,
                "subtitulo": s.subtitulo,
                "descricao": s.descricao,
                "icone": s.icone or "fa-solid fa-user-tie",
                "imagem_url": (s.imagem.url if s.imagem else ""),
                "cta_label": s.cta_label,
                "cta_link": s.cta_link,
            }
            for s in InstitutionalSlide.objects.filter(pagina=page, ativo=True).order_by("ordem", "id")
        ]

        steps = [
            {
                "titulo": st.titulo,
                "descricao": st.descricao,
                "icone": st.icone or "fa-solid fa-circle-check",
            }
            for st in InstitutionalMethodStep.objects.filter(pagina=page, ativo=True).order_by("ordem", "id")
        ]

        services = [
            {
                "titulo": sv.titulo,
                "descricao": sv.descricao,
                "icone": sv.icone or "fa-solid fa-square",
            }
            for sv in InstitutionalServiceCard.objects.filter(pagina=page, ativo=True).order_by("ordem", "id")
        ]

    if not slides:
        slides = [
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

    if not steps:
        steps = [
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

    if not services:
        services = [
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

    return content, slides, steps, services


def _resolve_public_municipio(request):
    municipio = getattr(request, "current_municipio", None)
    if municipio is not None:
        return municipio
    return None


def _app_login_url(request) -> str:
    explicit = (getattr(settings, "GEPUB_APP_CANONICAL_HOST", "") or "").strip().lower()
    app_hosts = list(getattr(settings, "GEPUB_APP_HOSTS", []) or [])
    host = explicit or ((app_hosts[0] if app_hosts else "") or "").strip().lower()
    if not host:
        return reverse("accounts:login")
    scheme = "https" if (request.is_secure() or not settings.DEBUG) else "http"
    return f"{scheme}://{host}{reverse('accounts:login')}"


def _render_municipio_public_home(request, municipio: Municipio):
    portal_cfg = PortalMunicipalConfig.objects.filter(municipio=municipio).first()
    menu_items_header = build_menu_items(municipio, posicao="HEADER")
    menu_items_footer = build_menu_items(municipio, posicao="FOOTER")

    secretarias = (
        municipio.secretarias.filter(ativo=True)
        .only("id", "nome", "sigla")
        .order_by("nome")[:16]
    )

    summary = {
        "secretarias": municipio.secretarias.filter(ativo=True).count(),
        "unidades": Unidade.objects.filter(secretaria__municipio=municipio, ativo=True).count(),
        "eventos_publicos": TransparenciaEventoPublico.objects.filter(
            municipio=municipio,
            publico=True,
        ).count(),
    }

    links_rapidos_default = [
        {
            "titulo": "Portal da Transparência",
            "descricao": "Consulte receitas, despesas e eventos publicados.",
            "url": reverse("core:transparencia_public"),
            "icon": "fa-solid fa-scale-balanced",
        },
        {
            "titulo": "Diário Oficial",
            "descricao": "Edições e publicações oficiais do município.",
            "url": reverse("core:portal_diario_public"),
            "icon": "fa-regular fa-file-lines",
        },
        {
            "titulo": "Educação",
            "descricao": "Portal da educação com unidades, cursos e calendário.",
            "url": reverse("core:portal_educacao_public"),
            "icon": "fa-solid fa-graduation-cap",
        },
        {
            "titulo": "Saúde",
            "descricao": "Informações de unidades, notícias e serviços de saúde.",
            "url": reverse("core:portal_saude_public"),
            "icon": "fa-solid fa-heart-pulse",
        },
        {
            "titulo": "Assistência Social",
            "descricao": "Canais de atendimento e políticas públicas ao cidadão.",
            "url": reverse("core:portal_ouvidoria_public"),
            "icon": "fa-solid fa-hand-holding-heart",
        },
        {
            "titulo": "e-SIC / Ouvidoria",
            "descricao": "Acesso a solicitações e atendimento ao cidadão.",
            "url": reverse("core:portal_ouvidoria_public"),
            "icon": "fa-solid fa-comments",
        },
        {
            "titulo": "Licitações e Contratos",
            "descricao": "Publicações oficiais de compras e contratos.",
            "url": reverse("core:portal_licitacoes_public"),
            "icon": "fa-solid fa-file-contract",
        },
    ]

    blocks_qs = PortalHomeBloco.objects.filter(municipio=municipio, ativo=True).order_by("ordem", "id")
    links_rapidos = list(blocks_qs.values("titulo", "descricao", "link", "icone"))
    if links_rapidos:
        links_rapidos = [
            {
                "titulo": item["titulo"],
                "descricao": item["descricao"],
                "url": item["link"] or "#",
                "icon": item["icone"] or "fa-solid fa-circle-info",
            }
            for item in links_rapidos
        ]
    else:
        links_rapidos = list(links_rapidos_default)

    if len(links_rapidos) < 6:
        existentes = {(item.get("titulo") or "").strip().lower() for item in links_rapidos}
        for fallback in links_rapidos_default:
            chave = (fallback.get("titulo") or "").strip().lower()
            if chave in existentes:
                continue
            links_rapidos.append(fallback)
            existentes.add(chave)
            if len(links_rapidos) >= 6:
                break

    servicos_cards = links_rapidos[:6]
    servicos_secundarios = links_rapidos[6:]

    diarios_recentes = DiarioOficialEdicao.objects.filter(
        municipio=municipio,
        publicado=True,
    ).order_by("-data_publicacao", "-id")[:5]

    noticias_recentes = list(
        PortalNoticia.objects.filter(
            municipio=municipio,
            publicado=True,
        ).order_by("-publicado_em", "-id")[:6]
    )

    noticias_home = noticias_recentes[:3]
    noticia_principal = noticias_home[0] if noticias_home else None

    banners_home = list(
        PortalBanner.objects.filter(
            municipio=municipio,
            ativo=True,
        ).order_by("ordem", "-id")[:4]
    )

    hero_image_url = ""
    for banner in banners_home:
        if banner.imagem:
            hero_image_url = banner.imagem.url
            break
    if not hero_image_url:
        for noticia in noticias_home:
            if noticia.imagem:
                hero_image_url = noticia.imagem.url
                break

    receita_total = (
        TributoLancamento.objects.filter(
            municipio=municipio,
            status=TributoLancamento.Status.PAGO,
        ).aggregate(total=Sum("valor_total")).get("total")
        or Decimal("0.00")
    )
    despesa_total = (
        DespEmpenho.objects.filter(municipio=municipio).aggregate(total=Sum("valor_pago")).get("total")
        or Decimal("0.00")
    )
    if despesa_total <= 0:
        despesa_total = (
            DespEmpenho.objects.filter(municipio=municipio).aggregate(total=Sum("valor_empenhado")).get("total")
            or Decimal("0.00")
        )

    ultima_licitacao = (
        ProcessoLicitatorio.objects.filter(municipio=municipio)
        .order_by("-data_abertura", "-id")
        .first()
    )
    servidores_municipais = RhCadastro.objects.filter(
        municipio=municipio,
        status=RhCadastro.Status.ATIVO,
    ).count()

    transparencia_cards = [
        {
            "icone": "fa-solid fa-arrow-trend-up",
            "titulo": "Receita acumulada",
            "valor": _format_currency_br(receita_total),
            "subtitulo": "Arrecadação tributária paga",
            "cor": "sky",
        },
        {
            "icone": "fa-solid fa-arrow-trend-down",
            "titulo": "Despesa atual",
            "valor": _format_currency_br(despesa_total),
            "subtitulo": "Empenhos e pagamentos",
            "cor": "navy",
        },
        {
            "icone": "fa-solid fa-gavel",
            "titulo": "Última licitação",
            "valor": (
                f"{ultima_licitacao.get_modalidade_display()} {ultima_licitacao.numero_processo}"
                if ultima_licitacao
                else "Sem licitação publicada"
            ),
            "subtitulo": (
                ultima_licitacao.data_abertura.strftime("%d/%m/%Y")
                if ultima_licitacao and ultima_licitacao.data_abertura
                else "Atualize o módulo de compras"
            ),
            "cor": "green",
        },
        {
            "icone": "fa-solid fa-users",
            "titulo": "Servidores municipais",
            "valor": f"{servidores_municipais:,}".replace(",", "."),
            "subtitulo": "Cadastro funcional ativo",
            "cor": "deep",
        },
    ]

    paginas_publicas = PortalPaginaPublica.objects.filter(
        municipio=municipio,
        publicado=True,
    ).order_by("ordem", "id")

    context = {
        "municipio": municipio,
        "secretarias": secretarias,
        "summary": summary,
        "links_rapidos": links_rapidos,
        "servicos_cards": servicos_cards,
        "servicos_secundarios": servicos_secundarios,
        "diarios_recentes": diarios_recentes,
        "noticias_recentes": noticias_recentes,
        "noticias_home": noticias_home,
        "noticia_principal": noticia_principal,
        "hero_image_url": hero_image_url,
        "banners_home": banners_home,
        "transparencia_cards": transparencia_cards,
        "servicos_destaque": servicos_cards[:5],
        "cta_login": _app_login_url(request),
        "cta_transparencia": reverse("core:transparencia_public"),
        "cta_servicos_online": reverse("core:portal_ouvidoria_public"),
        "top_links": [
            {"titulo": "Acessibilidade", "url": "#conteudo-principal", "icon": "fa-solid fa-universal-access"},
            {"titulo": "Ouvidoria", "url": reverse("core:portal_ouvidoria_public"), "icon": "fa-regular fa-message"},
            {"titulo": "Portal da Transparência", "url": reverse("core:transparencia_public"), "icon": "fa-solid fa-chart-column"},
            {"titulo": "Diário Oficial", "url": reverse("core:portal_diario_public"), "icon": "fa-regular fa-file-lines"},
            {"titulo": "Sistema Interno", "url": _app_login_url(request), "icon": "fa-solid fa-arrow-right-to-bracket"},
        ],
        "portal_cfg": portal_cfg,
        "menu_items_header": menu_items_header,
        "menu_items_footer": menu_items_footer,
        "paginas_publicas": paginas_publicas,
        "cor_primaria": portal_cfg.cor_primaria if portal_cfg else "#0E4A7E",
        "cor_secundaria": portal_cfg.cor_secundaria if portal_cfg else "#2F6EA9",
    }
    return render(request, "core/portal_publico_municipio.html", context)


def institucional_public(request):
    if getattr(request, "tenant_lookup_failed", False):
        return render(
            request,
            "core/tenant_not_found.html",
            {
                "slug": getattr(request, "current_municipio_slug", ""),
                "cta_home": reverse("core:institucional_public"),
                "cta_login": _app_login_url(request),
            },
            status=404,
        )

    municipio_publico = _resolve_public_municipio(request)
    if municipio_publico:
        return _render_municipio_public_home(request, municipio_publico)

    preview_mode = (request.GET.get("preview") or "").strip() == "1"
    if request.user.is_authenticated and not preview_mode:
        return redirect("core:dashboard")
    if preview_mode and request.user.is_authenticated and not can(request.user, "system.admin_django"):
        return redirect("core:dashboard")

    form = SimuladorPlanoForm(request.POST or None)
    simulacao = None

    if request.method == "POST" and form.is_valid():
        simulacao = simular_plano(
            secretarias=form.cleaned_data["numero_secretarias"],
            usuarios=form.cleaned_data["numero_usuarios"],
            alunos=form.cleaned_data["numero_alunos"],
            atendimentos=form.cleaned_data["atendimentos_estimados_ano"],
        )

    content, slides, method_steps, service_cards = _get_institutional_content()
    cta_contato = (content.get("servicos_cta_link") or "").strip()
    if not cta_contato or cta_contato == "#simulador":
        cta_contato = "#contato"
    faq_items = [
        {
            "pergunta": "O GEPUB mostra preços públicos dos planos no site?",
            "resposta": "Não. A página institucional apresenta escopo e capacidades. Valores são informados somente por contato comercial.",
        },
        {
            "pergunta": "Como funciona o primeiro acesso da prefeitura?",
            "resposta": "Após o login inicial, o responsável troca senha obrigatoriamente e segue o onboarding para ativar plano e secretarias.",
        },
        {
            "pergunta": "A plataforma atende licitação e contrato público?",
            "resposta": "Sim. O modelo SaaS considera implantação, migração, treinamento, suporte e manutenção, com regras contratuais municipais.",
        },
        {
            "pergunta": "O município pode crescer sem trocar de sistema?",
            "resposta": "Sim. O plano pode evoluir por upgrade e expansão de capacidade mantendo a mesma base integrada de operação.",
        },
    ]

    context = {
        "content": content,
        "slides": slides,
        "method_steps": method_steps,
        "service_cards": service_cards,
        "planos": _planos_para_site(),
        "form": form,
        "simulacao": simulacao,
        "faq_items": faq_items,
        "cta_login": _app_login_url(request),
        "cta_contato": cta_contato,
        "cta_docs": reverse("core:documentacao_public"),
        "cta_transparencia": reverse("core:transparencia_public"),
        "preview_mode": preview_mode,
    }
    return render(request, "core/institucional.html", context)


def sobre_public(request):
    return redirect("core:institucional_public")


def funcionalidades_public(request):
    return redirect("core:institucional_public")


def por_que_usar_public(request):
    return redirect("core:institucional_public")


def _parse_iso_date(value: str):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except Exception:
        return None


def _qs_totals(qs, date_field: str):
    agg = qs.aggregate(total=Count("id"), ultima=Max(date_field))
    return int(agg.get("total") or 0), agg.get("ultima")


def _arquivo_stats_por_categoria(q_arquivos):
    stats = {}
    rows = q_arquivos.values("categoria").annotate(total=Count("id"), ultima=Max("publicado_em"))
    for row in rows:
        stats[row["categoria"]] = {
            "total": int(row.get("total") or 0),
            "ultima": row.get("ultima"),
        }
    return stats


def _to_compare_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    return datetime.combine(value, datetime.min.time())


def _manual_totais(stats_por_categoria: dict, categorias: list[str]):
    total = 0
    ultima = None
    for categoria in categorias:
        item = stats_por_categoria.get(categoria) or {}
        total += int(item.get("total") or 0)
        atual = item.get("ultima")
        if not atual:
            continue
        if not ultima:
            ultima = atual
            continue
        atual_cmp = _to_compare_dt(atual)
        ultima_cmp = _to_compare_dt(ultima)
        if atual_cmp > ultima_cmp:
            ultima = atual
    return total, ultima


def _build_transparencia_item(
    *,
    titulo: str,
    descricao: str,
    capacidade_origem: str,
    auto_total: int = 0,
    auto_ultima=None,
    arquivo_stats: dict,
    categorias_arquivo: list[str] | None = None,
    url_publica: str = "",
):
    categorias = categorias_arquivo or []
    manual_total, manual_ultima = _manual_totais(arquivo_stats, categorias)
    total = auto_total + manual_total

    ultima = auto_ultima
    if manual_ultima:
        if not ultima:
            ultima = manual_ultima
        else:
            manual_cmp = _to_compare_dt(manual_ultima)
            ultima_cmp = _to_compare_dt(ultima)
            if manual_cmp > ultima_cmp:
                ultima = manual_ultima

    if total == 0:
        status = "vazio"
    elif total < 3:
        status = "baixo"
    else:
        status = "ativo"

    if capacidade_origem == "MISTA":
        origem = "Mista (módulo + publicações)"
        detalhe = f"{auto_total} automáticos • {manual_total} publicados"
    elif capacidade_origem == "AUTOMATICA":
        origem = "Automática (painel municipal)"
        detalhe = f"{auto_total} registros automáticos"
    else:
        origem = "Manual (publicações do portal)"
        detalhe = f"{manual_total} publicações cadastradas"

    return {
        "titulo": titulo,
        "descricao": descricao,
        "total": total,
        "status": status,
        "origem": origem,
        "detalhe": detalhe,
        "ultima_movimentacao": ultima,
        "categoria_filtro": categorias[0] if categorias else "",
        "url_publica": url_publica,
    }


def _build_transparencia_secoes(municipio: Municipio | None):
    if not municipio:
        return []

    q_arquivos = PortalTransparenciaArquivo.objects.filter(municipio=municipio, publico=True)
    arquivo_stats = _arquivo_stats_por_categoria(q_arquivos)

    diarios_total, diarios_ultima = _qs_totals(
        DiarioOficialEdicao.objects.filter(municipio=municipio, publicado=True),
        "data_publicacao",
    )
    exec_2025_total, exec_2025_ultima = _qs_totals(
        DespEmpenho.objects.filter(municipio=municipio, exercicio__ano=2025),
        "data_empenho",
    )
    exec_2024_total, exec_2024_ultima = _qs_totals(
        DespEmpenho.objects.filter(municipio=municipio, exercicio__ano=2024),
        "data_empenho",
    )
    divida_ativa_total, divida_ativa_ultima = _qs_totals(
        TributoLancamento.objects.filter(municipio=municipio).exclude(
            status__in=[TributoLancamento.Status.PAGO, TributoLancamento.Status.CANCELADO]
        ),
        "atualizado_em",
    )

    folha_total, folha_ultima = _qs_totals(
        FolhaCompetencia.objects.filter(municipio=municipio),
        "atualizado_em",
    )
    servidores_qs = RhCadastro.objects.filter(municipio=municipio)
    servidores_total, servidores_ultima = _qs_totals(servidores_qs, "atualizado_em")
    cargos_total = servidores_qs.exclude(cargo="").values("cargo").distinct().count()
    cargos_ultima = servidores_qs.exclude(cargo="").aggregate(ultima=Max("atualizado_em")).get("ultima")
    estagiarios_qs = servidores_qs.filter(Q(cargo__icontains="ESTAGI") | Q(funcao__icontains="ESTAGI"))
    estagiarios_total, estagiarios_ultima = _qs_totals(estagiarios_qs, "atualizado_em")
    terceirizados_total, terceirizados_ultima = _qs_totals(
        servidores_qs.filter(regime=RhCadastro.Regime.CLT),
        "atualizado_em",
    )
    concursos_total, concursos_ultima = _qs_totals(
        ConcursoPublico.objects.filter(municipio=municipio, publicado=True),
        "atualizado_em",
    )

    licitacoes_total, licitacoes_ultima = _qs_totals(
        ProcessoLicitatorio.objects.filter(municipio=municipio),
        "data_abertura",
    )
    contratos_qs = ContratoAdministrativo.objects.filter(municipio=municipio)
    contratos_total, contratos_ultima = _qs_totals(contratos_qs, "atualizado_em")
    aditivos_total, aditivos_ultima = _qs_totals(
        AditivoContrato.objects.filter(contrato__municipio=municipio),
        "data_ato",
    )
    fiscal_total, fiscal_ultima = _qs_totals(
        contratos_qs.exclude(fiscal_nome=""),
        "atualizado_em",
    )

    secoes = [
        {
            "titulo": "INFORMAÇÕES INSTITUCIONAIS",
            "descricao": "Normas próprias e publicações oficiais do município.",
            "itens": [
                _build_transparencia_item(
                    titulo="Atos Normativos Próprios",
                    descricao="Leis, decretos, portarias e atos institucionais.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.ATOS_NORMATIVOS],
                ),
                _build_transparencia_item(
                    titulo="Diário Oficial",
                    descricao="Edições oficiais publicadas pelo município.",
                    capacidade_origem="MISTA",
                    auto_total=diarios_total,
                    auto_ultima=diarios_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.DIARIO_OFICIAL],
                    url_publica=reverse("core:portal_diario_public"),
                ),
            ],
        },
        {
            "titulo": "EXECUÇÃO ORÇAMENTÁRIA",
            "descricao": "Execução de despesas e informações de dívida ativa.",
            "itens": [
                _build_transparencia_item(
                    titulo="Execução Orçamentária Geral 2025",
                    descricao="Movimentações de empenho/liquidação/pagamento do exercício de 2025.",
                    capacidade_origem="MISTA",
                    auto_total=exec_2025_total,
                    auto_ultima=exec_2025_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.EXEC_ORC_GERAL_2025],
                ),
                _build_transparencia_item(
                    titulo="Execução Orçamentária 2024",
                    descricao="Histórico da execução orçamentária do exercício de 2024.",
                    capacidade_origem="MISTA",
                    auto_total=exec_2024_total,
                    auto_ultima=exec_2024_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.EXEC_ORC_2024],
                ),
                _build_transparencia_item(
                    titulo="Empresas Com Dívida Ativa",
                    descricao="Contribuintes com lançamentos tributários pendentes.",
                    capacidade_origem="MISTA",
                    auto_total=divida_ativa_total,
                    auto_ultima=divida_ativa_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.EMPRESAS_DIVIDA_ATIVA],
                ),
            ],
        },
        {
            "titulo": "CONVÊNIOS, TRANSFERÊNCIAS E EMENDAS",
            "descricao": "Publicações sobre recursos recebidos, repassados e acordos firmados.",
            "itens": [
                _build_transparencia_item(
                    titulo="Emendas Parlamentares",
                    descricao="Emendas cadastradas e sua aplicação.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.EMENDAS_PARLAMENTARES],
                ),
                _build_transparencia_item(
                    titulo="Convênios E Transferências Recebidas",
                    descricao="Termos e repasses recebidos de outros entes.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.CONVENIOS_RECEBIDOS],
                ),
                _build_transparencia_item(
                    titulo="Convênios E Transferências Realizadas",
                    descricao="Transferências e convênios concedidos pelo município.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.CONVENIOS_REALIZADOS],
                ),
                _build_transparencia_item(
                    titulo="Acordos Firmados Sem Transferências De Recursos",
                    descricao="Instrumentos de cooperação sem repasse financeiro.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.ACORDOS_SEM_TRANSFERENCIA],
                ),
            ],
        },
        {
            "titulo": "RECURSOS HUMANOS",
            "descricao": "Quadro de pessoal e informações de folha e vínculos.",
            "itens": [
                _build_transparencia_item(
                    titulo="Folha De Pagamento",
                    descricao="Competências processadas no módulo de Folha.",
                    capacidade_origem="MISTA",
                    auto_total=folha_total,
                    auto_ultima=folha_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RH_FOLHA_PAGAMENTO],
                ),
                _build_transparencia_item(
                    titulo="Cargos",
                    descricao="Estrutura de cargos em uso no quadro funcional.",
                    capacidade_origem="MISTA",
                    auto_total=cargos_total,
                    auto_ultima=cargos_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RH_CARGOS],
                ),
                _build_transparencia_item(
                    titulo="Estagiários",
                    descricao="Registros de estagiários identificados no cadastro funcional.",
                    capacidade_origem="MISTA",
                    auto_total=estagiarios_total,
                    auto_ultima=estagiarios_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RH_ESTAGIARIOS],
                ),
                _build_transparencia_item(
                    titulo="Terceirizados",
                    descricao="Vínculos com regime CLT/terceirização registrados.",
                    capacidade_origem="MISTA",
                    auto_total=terceirizados_total,
                    auto_ultima=terceirizados_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RH_TERCEIRIZADOS],
                ),
                _build_transparencia_item(
                    titulo="Concursos",
                    descricao="Concursos e seletivos publicados no portal.",
                    capacidade_origem="MISTA",
                    auto_total=concursos_total,
                    auto_ultima=concursos_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RH_CONCURSOS],
                    url_publica=reverse("core:portal_concursos_public"),
                ),
                _build_transparencia_item(
                    titulo="Servidores",
                    descricao="Servidores cadastrados no módulo de RH.",
                    capacidade_origem="MISTA",
                    auto_total=servidores_total,
                    auto_ultima=servidores_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RH_SERVIDORES],
                ),
            ],
        },
        {
            "titulo": "DIÁRIAS",
            "descricao": "Pagamentos de diárias e tabela de referência vigente.",
            "itens": [
                _build_transparencia_item(
                    titulo="Diárias",
                    descricao="Relação de concessões e pagamentos de diárias.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.DIARIAS],
                ),
                _build_transparencia_item(
                    titulo="Tabelas De Valores Da Diária",
                    descricao="Tabela oficial de valores e regras de concessão.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.DIARIAS_TABELA_VALORES],
                ),
            ],
        },
        {
            "titulo": "LICITAÇÕES E CONTRATOS",
            "descricao": "Contratações públicas, aditivos, fiscalização e sanções.",
            "itens": [
                _build_transparencia_item(
                    titulo="Licitações",
                    descricao="Processos licitatórios do módulo de Compras.",
                    capacidade_origem="MISTA",
                    auto_total=licitacoes_total,
                    auto_ultima=licitacoes_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.LICITACOES],
                    url_publica=reverse("core:portal_licitacoes_public"),
                ),
                _build_transparencia_item(
                    titulo="Contratos",
                    descricao="Contratos administrativos vinculados ao município.",
                    capacidade_origem="MISTA",
                    auto_total=contratos_total,
                    auto_ultima=contratos_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.CONTRATOS],
                    url_publica=reverse("core:portal_contratos_public"),
                ),
                _build_transparencia_item(
                    titulo="Aditivos De Contratos",
                    descricao="Aditivos de prazo, valor e escopo.",
                    capacidade_origem="MISTA",
                    auto_total=aditivos_total,
                    auto_ultima=aditivos_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.ADITIVOS_CONTRATOS],
                    url_publica=reverse("core:portal_contratos_public"),
                ),
                _build_transparencia_item(
                    titulo="Licitantes E/ou Contratados Sancionados",
                    descricao="Registros de sanções administrativas aplicadas.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.LICITANTES_SANCIONADOS],
                ),
                _build_transparencia_item(
                    titulo="Fiscal De Contratos",
                    descricao="Designações de fiscais vinculadas aos contratos.",
                    capacidade_origem="MISTA",
                    auto_total=fiscal_total,
                    auto_ultima=fiscal_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.FISCAL_CONTRATOS],
                    url_publica=reverse("core:portal_contratos_public"),
                ),
                _build_transparencia_item(
                    titulo="Empresas Inidôneas E Suspensas",
                    descricao="Cadastro de empresas impedidas de contratar.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.EMPRESAS_INIDONEAS],
                ),
            ],
        },
        {
            "titulo": "OBRAS PÚBLICAS",
            "descricao": "Execução de obras, andamento e paralisações.",
            "itens": [
                _build_transparencia_item(
                    titulo="Obras Públicas",
                    descricao="Publicações de obras em execução e concluídas.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.OBRAS_PUBLICAS],
                ),
                _build_transparencia_item(
                    titulo="Obras Paralisadas",
                    descricao="Relatórios de obras interrompidas e seus motivos.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.OBRAS_PARALISADAS],
                ),
            ],
        },
        {
            "titulo": "PLANEJAMENTO E PRESTAÇÃO DE CONTAS",
            "descricao": "Instrumentos de planejamento e relatórios oficiais de controle.",
            "itens": [
                _build_transparencia_item(
                    titulo="Prestação De Contas Anos Anteriores",
                    descricao="Acervo de prestações de contas de exercícios anteriores.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.PRESTACAO_CONTAS_ANTERIORES],
                ),
                _build_transparencia_item(
                    titulo="Balanço Geral",
                    descricao="Balanço geral anual do município.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.BALANCO_GERAL],
                ),
                _build_transparencia_item(
                    titulo="Relatório De Gestão Ou Atividade",
                    descricao="Relatórios de atividades e resultados da gestão.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RELATORIO_GESTAO_ATIVIDADE],
                ),
                _build_transparencia_item(
                    titulo="Julgamento Das Contas Pelo TCE Parecer Prévio",
                    descricao="Parecer prévio emitido pelo Tribunal de Contas.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.PARECER_PREVIO_TCE],
                ),
                _build_transparencia_item(
                    titulo="Resultado De Julgamento Das Contas Legislativo",
                    descricao="Resultado do julgamento das contas pelo Legislativo.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RESULTADO_JULGAMENTO_LEGISLATIVO],
                ),
                _build_transparencia_item(
                    titulo="Relatório De Gestão Fiscal RGF",
                    descricao="Relatórios fiscais oficiais da gestão municipal.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RGF],
                ),
                _build_transparencia_item(
                    titulo="Rel. Res. De Execução Orçamentária RREO",
                    descricao="Relatórios resumidos de execução orçamentária.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.RREO],
                ),
                _build_transparencia_item(
                    titulo="Plano Estratégico Institucional PEI",
                    descricao="Planejamento estratégico institucional vigente.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.PEI],
                ),
                _build_transparencia_item(
                    titulo="Plano Plurianual PPA",
                    descricao="Plano plurianual em vigor.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.PPA],
                ),
                _build_transparencia_item(
                    titulo="Lei De Diretrizes Orçamentárias LDO",
                    descricao="Lei de diretrizes orçamentárias vigente.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.LDO],
                ),
                _build_transparencia_item(
                    titulo="Lei Orçamentária Anual LOA",
                    descricao="Lei orçamentária anual vigente.",
                    capacidade_origem="MANUAL",
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=[PortalTransparenciaArquivo.Categoria.LOA],
                ),
            ],
        },
    ]

    for secao in secoes:
        itens = secao["itens"]
        secao["total_itens"] = len(itens)
        secao["itens_com_dados"] = sum(1 for item in itens if item["total"] > 0)
        secao["total_registros"] = sum(item["total"] for item in itens)
    return secoes


def transparencia_public(request):
    if getattr(request, "tenant_lookup_failed", False):
        return render(
            request,
            "core/tenant_not_found.html",
            {
                "slug": getattr(request, "current_municipio_slug", ""),
                "cta_home": reverse("core:institucional_public"),
                "cta_login": _app_login_url(request),
            },
            status=404,
        )

    content, _, _, _ = _get_institutional_content()
    municipio_publico = _resolve_public_municipio(request)
    municipio_id_raw = (request.GET.get("municipio") or "").strip()
    modulo = (request.GET.get("modulo") or "").strip().upper()
    categoria = (request.GET.get("categoria") or "").strip().upper()
    q = (request.GET.get("q") or "").strip()
    data_inicio_raw = (request.GET.get("inicio") or "").strip()
    data_fim_raw = (request.GET.get("fim") or "").strip()

    eventos = TransparenciaEventoPublico.objects.filter(publico=True).select_related("municipio")

    municipio_id = None
    if municipio_publico:
        municipio_id = municipio_publico.id
        eventos = eventos.filter(municipio_id=municipio_id)
    elif municipio_id_raw.isdigit():
        municipio_id = int(municipio_id_raw)
        eventos = eventos.filter(municipio_id=municipio_id)

    municipio_contexto = municipio_publico
    if not municipio_contexto and municipio_id:
        municipio_contexto = Municipio.objects.filter(pk=municipio_id).first()

    modulos_validos = {code for code, _label in TransparenciaEventoPublico.Modulo.choices}
    if modulo in modulos_validos:
        eventos = eventos.filter(modulo=modulo)
    else:
        modulo = ""

    if q:
        eventos = eventos.filter(
            Q(titulo__icontains=q)
            | Q(descricao__icontains=q)
            | Q(referencia__icontains=q)
            | Q(tipo_evento__icontains=q)
            | Q(municipio__nome__icontains=q)
        )

    data_inicio = _parse_iso_date(data_inicio_raw)
    data_fim = _parse_iso_date(data_fim_raw)
    if data_inicio:
        eventos = eventos.filter(data_evento__date__gte=data_inicio)
    if data_fim:
        eventos = eventos.filter(data_evento__date__lte=data_fim)

    total_eventos = eventos.count()
    total_valor = eventos.aggregate(total=Sum("valor")).get("total") or Decimal("0.00")
    itens = eventos.order_by("-data_evento", "-id")[:250]
    arquivos_publicos = PortalTransparenciaArquivo.objects.filter(publico=True)
    if municipio_id:
        arquivos_publicos = arquivos_publicos.filter(municipio_id=municipio_id)
    categorias_validas = {codigo for codigo, _label in PortalTransparenciaArquivo.Categoria.choices}
    if categoria in categorias_validas:
        arquivos_publicos = arquivos_publicos.filter(categoria=categoria)
    else:
        categoria = ""
    if q:
        arquivos_publicos = arquivos_publicos.filter(
            Q(titulo__icontains=q) | Q(descricao__icontains=q) | Q(categoria__icontains=q)
        )
    arquivos_publicos = arquivos_publicos.select_related("municipio").order_by("categoria", "ordem", "-publicado_em", "-id")
    secoes_transparencia = _build_transparencia_secoes(municipio_contexto)
    portal_cfg = PortalMunicipalConfig.objects.filter(municipio=municipio_contexto).first() if municipio_contexto else None
    menu_items_header = (
        build_menu_items(municipio_contexto, posicao="HEADER")
        if municipio_contexto
        else [
            {"titulo": "Início", "url": reverse("core:institucional_public"), "nova_aba": False},
            {"titulo": "Transparência", "url": reverse("core:transparencia_public"), "nova_aba": False},
            {"titulo": "Documentação", "url": reverse("core:documentacao_public"), "nova_aba": False},
        ]
    )
    menu_items_footer = (
        build_menu_items(municipio_contexto, posicao="FOOTER")
        if municipio_contexto
        else []
    )

    context = {
        "title": (
            f"Transparencia Publica • {municipio_contexto.nome}"
            if municipio_contexto
            else f"Transparencia Publica • {content.get('marca_nome') or 'GEPUB'}"
        ),
        "marca_nome": municipio_contexto.nome if municipio_contexto else (content.get("marca_nome") or "GEPUB"),
        "marca_logo_url": content.get("marca_logo_url", ""),
        "eventos": itens,
        "total_eventos": total_eventos,
        "total_valor": total_valor,
        "municipios": (
            Municipio.objects.filter(pk=municipio_publico.pk)
            if municipio_publico
            else Municipio.objects.filter(ativo=True).order_by("nome")
        ),
        "modulos": TransparenciaEventoPublico.Modulo.choices,
        "filtro_municipio": municipio_id,
        "filtro_modulo": modulo,
        "filtro_categoria": categoria,
        "filtro_q": q,
        "filtro_inicio": data_inicio_raw,
        "filtro_fim": data_fim_raw,
        "lock_municipio": bool(municipio_publico),
        "categorias_arquivo": PortalTransparenciaArquivo.Categoria.choices,
        "secoes_transparencia": secoes_transparencia,
        "arquivos_publicos": arquivos_publicos[:200],
        "total_arquivos_publicos": arquivos_publicos.count(),
        "cta_home": reverse("core:institucional_public"),
        "cta_docs": reverse("core:documentacao_public"),
        "cta_login": _app_login_url(request),
        "municipio": municipio_contexto,
        "titulo_portal": (
            portal_cfg.titulo_portal
            if portal_cfg and portal_cfg.titulo_portal
            else (municipio_contexto.nome if municipio_contexto else (content.get("marca_nome") or "GEPUB"))
        ),
        "subtitulo_portal": (
            portal_cfg.subtitulo_portal
            if portal_cfg and portal_cfg.subtitulo_portal
            else "Portal Público Municipal"
        ),
        "mensagem_boas_vindas": (
            portal_cfg.mensagem_boas_vindas
            if portal_cfg and portal_cfg.mensagem_boas_vindas
            else "Consulta consolidada de eventos e arquivos públicos do município."
        ),
        "cor_primaria": portal_cfg.cor_primaria if portal_cfg else "#0E4A7E",
        "cor_secundaria": portal_cfg.cor_secundaria if portal_cfg else "#2F6EA9",
        "logo_url": (
            portal_cfg.logo.url
            if portal_cfg and portal_cfg.logo
            else content.get("marca_logo_url", "")
        ),
        "endereco": portal_cfg.endereco if portal_cfg else "",
        "telefone": portal_cfg.telefone if portal_cfg else "",
        "email": portal_cfg.email if portal_cfg else "",
        "horario_atendimento": portal_cfg.horario_atendimento if portal_cfg else "",
        "menu_items_header": menu_items_header,
        "menu_items_footer": menu_items_footer,
    }
    return render(request, "core/transparencia_public.html", context)


def documentacao_public(request):
    if getattr(request, "tenant_lookup_failed", False):
        return render(
            request,
            "core/tenant_not_found.html",
            {
                "slug": getattr(request, "current_municipio_slug", ""),
                "cta_home": reverse("core:institucional_public"),
                "cta_login": _app_login_url(request),
            },
            status=404,
        )

    municipio_publico = _resolve_public_municipio(request)
    if municipio_publico:
        return redirect("core:institucional_public")

    content, _, _, _ = _get_institutional_content()

    modulos = [
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

    funcionalidades = [
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

    integracoes = [
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

    arquitetura = [
        "Apps especializados por domínio: ORG, Accounts, Educação, Saúde, NEE e Billing.",
        "Base única por município com segregação por secretaria/unidade.",
        "Camada de permissão centralizada (RBAC) aplicada em middleware e views.",
        "Admin operacional próprio no dashboard (sem depender do admin padrão do Django).",
    ]

    fluxos = [
        "1. Contratação SaaS municipal com vigência mínima e regra de reajuste.",
        "2. Primeiro acesso com troca de senha obrigatória e onboarding inicial.",
        "3. Definição do plano municipal e ativação de secretarias por template.",
        "4. Operação diária por módulo com auditoria, indicadores e relatórios.",
        "5. Controle de consumo, upgrades e faturamento mensal por competência.",
    ]

    pilares = [
        "Segurança e LGPD: campos sensíveis protegidos, controle de acesso e trilha de auditoria.",
        "Escalabilidade municipal: base única multi-secretaria com crescimento por limites e addons.",
        "Governança pública: linguagem e estrutura aderentes ao cenário de licitação e contrato.",
        "Operação orientada a dados: indicadores, relatórios e histórico para tomada de decisão.",
    ]

    kpis = [
        {"label": "Módulos principais", "value": "7"},
        {"label": "Planos SaaS", "value": "4"},
        {"label": "Formato de cobrança", "value": "Mensal + overage"},
        {"label": "Modelo contratual", "value": "SaaS municipal"},
    ]

    context = {
        "titulo": f"Documentação {content.get('marca_nome', 'GEPUB')}",
        "subtitulo": "Visão completa de arquitetura, apps, integrações e funcionalidades operacionais",
        "marca_nome": content.get("marca_nome") or "GEPUB",
        "marca_logo_url": content.get("marca_logo_url", ""),
        "planos": _planos_para_site(),
        "funcionalidades": funcionalidades,
        "arquitetura": arquitetura,
        "modulos": modulos,
        "integracoes": integracoes,
        "fluxos": fluxos,
        "pilares": pilares,
        "kpis": kpis,
        "cta_login": _app_login_url(request),
        "cta_home": reverse("core:institucional_public"),
        "cta_transparencia": reverse("core:transparencia_public"),
        "cta_simulador": reverse("core:institucional_public") + "#simulador",
    }
    return render(request, "core/documentacao_public.html", context)
