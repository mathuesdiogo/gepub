from decimal import Decimal
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q, Sum
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.billing.forms import SimuladorPlanoForm
from apps.billing.models import PlanoMunicipal
from apps.billing.services import (
    PlanoApp,
    PLANO_COMERCIAL_SPECS,
    PLANO_DOC_LINKS,
    catalogo_planos_comercial,
    get_assinatura_ativa,
    municipio_has_plan_app,
    plano_comercial_data,
    resolver_municipio_usuario,
    simular_plano,
)
from apps.compras.models import ProcessoLicitatorio
from apps.contratos.models import AditivoContrato, ContratoAdministrativo
from apps.core.module_access import module_enabled_for_user
from apps.core.middleware import _build_app_url
from apps.core.models import (
    ConcursoPublico,
    DiarioOficialEdicao,
    DocumentoEmitido,
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
from apps.core.legal_contents import (
    TERMS_OF_SERVICE_LAST_UPDATE,
    TERMS_OF_SERVICE_SECTIONS,
    PRIVACY_POLICY_LAST_UPDATE,
    PRIVACY_POLICY_SECTIONS,
    COOKIES_POLICY_LAST_UPDATE,
    COOKIES_POLICY_SECTIONS,
)
from apps.core.portal_public_utils import build_menu_items
from apps.core.portal_specs import (
    DEFAULT_INSTITUTIONAL_SERVICES,
    DEFAULT_INSTITUTIONAL_SLIDES,
    DEFAULT_INSTITUTIONAL_STEPS,
    DOCUMENTATION_ARQUITETURA,
    DOCUMENTATION_FLUXOS,
    DOCUMENTATION_FUNCIONALIDADES,
    DOCUMENTATION_INTEGRACOES,
    DOCUMENTATION_KPIS,
    DOCUMENTATION_MODULES,
    DOCUMENTATION_PILARES,
    INSTITUTIONAL_DEFAULT_CONTENT,
    TRANSPARENCIA_SECTION_SPECS,
)
from apps.core.rbac_documentation import build_operational_matrix_rows, build_site_role_sections
from apps.core.rbac import can
from apps.financeiro.models import DespEmpenho
from apps.folha.models import FolhaCompetencia
from apps.org.models import Municipio, Unidade
from apps.rh.models import RhCadastro
from apps.tributos.models import TributoLancamento


@login_required
def portal(request):
    u = request.user
    municipio = resolver_municipio_usuario(u)
    plan_camara_enabled = municipio_has_plan_app(municipio, PlanoApp.CAMARA) if municipio else False
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
            "key": "camara",
            "title": "Câmara Municipal",
            "desc": "Sessões, proposições, transparência legislativa e comunicação da Câmara.",
            "icon": "fa-solid fa-landmark-dome",
            "url": "camara:index",
            "enabled": can(u, "camara.view") and module_enabled_for_user(u, "camara") and plan_camara_enabled,
            "color": "kpi-blue",
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
        {
            "key": "comunicacao",
            "title": "Comunicação",
            "desc": "E-mail, SMS e WhatsApp oficial com templates, fila e auditoria.",
            "icon": "fa-solid fa-paper-plane",
            "url": "comunicacao:index",
            "enabled": can(u, "comunicacao.view") and module_enabled_for_user(u, "comunicacao"),
            "color": "kpi-purple",
        },
    ]

    modules = [m for m in modules if m["enabled"]]
    assinatura = get_assinatura_ativa(municipio, criar_default=False) if municipio else None
    plano_atual = plano_comercial_data(assinatura.plano if assinatura else None)

    return render(
        request,
        "core/portal.html",
        {
            "modules": modules,
            "plano_atual": plano_atual,
            "assinatura": assinatura,
        },
    )


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
    faixa_por_porte = {
        PlanoMunicipal.Codigo.STARTER: "P: R$ 1.490 | M: R$ 2.490 | G: R$ 3.490",
        PlanoMunicipal.Codigo.MUNICIPAL: "P: R$ 2.490 | M: R$ 3.990 | G: R$ 5.990",
        PlanoMunicipal.Codigo.GESTAO_TOTAL: "P: R$ 3.990 | M: R$ 6.990 | G: R$ 9.990",
        PlanoMunicipal.Codigo.CONSORCIO: "P: R$ 5.990 | M: R$ 9.990 | G: R$ 14.990",
    }

    setup_por_plano = {
        PlanoMunicipal.Codigo.STARTER: "Implantação sugerida: R$ 6.000 a R$ 12.000",
        PlanoMunicipal.Codigo.MUNICIPAL: "Implantação sugerida: R$ 10.000 a R$ 20.000",
        PlanoMunicipal.Codigo.GESTAO_TOTAL: "Implantação sugerida: R$ 18.000 a R$ 35.000",
        PlanoMunicipal.Codigo.CONSORCIO: "Implantação sugerida: R$ 25.000 a R$ 60.000",
    }

    planos = list(
        PlanoMunicipal.objects.filter(ativo=True).select_related("comercial_config").order_by("preco_base_mensal", "nome")
    )
    if not planos:
        fallback_codes = [
            PlanoMunicipal.Codigo.STARTER,
            PlanoMunicipal.Codigo.MUNICIPAL,
            PlanoMunicipal.Codigo.GESTAO_TOTAL,
            PlanoMunicipal.Codigo.CONSORCIO,
        ]
        cards: list[dict] = []
        for codigo in fallback_codes:
            spec = PLANO_COMERCIAL_SPECS.get(codigo, {})
            docs = PLANO_DOC_LINKS.get(codigo, {})
            destaque = ""
            if codigo == PlanoMunicipal.Codigo.STARTER:
                destaque = "Entrada"
            elif codigo == PlanoMunicipal.Codigo.MUNICIPAL:
                destaque = "Recomendado"
            elif codigo == PlanoMunicipal.Codigo.GESTAO_TOTAL:
                destaque = "Governança"
            elif codigo == PlanoMunicipal.Codigo.CONSORCIO:
                destaque = "Município 100% Digital"
            cards.append(
                {
                    "id": codigo,
                    "codigo": codigo,
                    "nome": spec.get("nome_comercial", codigo),
                    "descricao": spec.get("descricao_comercial", ""),
                    "preco": "Sob proposta",
                    "destaque": destaque,
                    "features": list(spec.get("beneficios", [])),
                    "special_access": list(spec.get("especiais", [])),
                    "restricoes": list(spec.get("limitacoes", [])),
                    "dependencies": list(spec.get("dependencias", [])),
                    "limits": [
                        "Apps habilitados por plano (Gestão, Portal, Transparência, Câmara)",
                        "Todas as secretarias operam nos quatro planos",
                    ],
                    "overages": [
                        f"Mensalidade por porte: {faixa_por_porte.get(codigo, 'Sob proposta')}",
                        setup_por_plano.get(codigo, "Implantação sob proposta"),
                    ],
                    "doc_links": docs,
                }
            )
        return cards

    comercial = {item["codigo"]: item for item in catalogo_planos_comercial(planos)}
    cards: list[dict] = []
    for plano in planos:
        comercial_item = comercial.get(plano.codigo, {})
        limits = [
            "Secretarias: ilimitadas",
            "Núcleo de Gestão Interna ativo em todos os planos",
            "Diferença por plano: Portal da Prefeitura, Transparência e Câmara",
        ]
        features = list(comercial_item.get("beneficios", []))
        special_access = list(comercial_item.get("especiais", []))
        restricoes = list(comercial_item.get("limitacoes", []))
        dependencies = list(comercial_item.get("dependencias", []))

        destaque = ""
        if plano.codigo == PlanoMunicipal.Codigo.MUNICIPAL:
            destaque = "Recomendado"
        elif plano.codigo == PlanoMunicipal.Codigo.STARTER:
            destaque = "Entrada"
        elif plano.codigo == PlanoMunicipal.Codigo.GESTAO_TOTAL:
            destaque = "Governança"
        elif plano.codigo == PlanoMunicipal.Codigo.CONSORCIO:
            destaque = "Município 100% Digital"

        cards.append(
            {
                "id": plano.pk,
                "codigo": plano.codigo,
                "nome": comercial_item.get("nome_comercial") or plano.nome,
                "descricao": comercial_item.get("descricao_comercial") or plano.descricao,
                "preco": _format_money(plano.preco_base_mensal),
                "destaque": destaque,
                "features": features,
                "special_access": special_access,
                "restricoes": restricoes,
                "dependencies": dependencies,
                "limits": limits,
                "overages": [
                    f"Mensalidade por porte: {faixa_por_porte.get(plano.codigo, 'Sob proposta')}",
                    setup_por_plano.get(plano.codigo, "Implantação sob proposta"),
                ],
                "doc_links": comercial_item.get("links", {}),
            }
        )
    return cards


def _default_institutional_content() -> dict:
    return dict(INSTITUTIONAL_DEFAULT_CONTENT)


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
        slides = [dict(item) for item in DEFAULT_INSTITUTIONAL_SLIDES]

    if not steps:
        steps = [dict(item) for item in DEFAULT_INSTITUTIONAL_STEPS]

    if not services:
        services = [dict(item) for item in DEFAULT_INSTITUTIONAL_SERVICES]

    return content, slides, steps, services


def _resolve_public_municipio(request):
    municipio = getattr(request, "current_municipio", None)
    if municipio is not None:
        return municipio
    return None


def _municipio_public_plan_flags(municipio: Municipio) -> dict[str, bool]:
    return {
        "portal": municipio_has_plan_app(municipio, PlanoApp.PORTAL),
        "transparencia": municipio_has_plan_app(municipio, PlanoApp.TRANSPARENCIA),
        "camara": municipio_has_plan_app(municipio, PlanoApp.CAMARA),
    }


def _allowed_internal_routes_for_public(flags: dict[str, bool]) -> set[str]:
    from apps.core.models import PortalMenuPublico

    routes = {PortalMenuPublico.RotaInterna.HOME}
    if flags.get("portal"):
        routes.update(
            {
                PortalMenuPublico.RotaInterna.NOTICIAS,
                PortalMenuPublico.RotaInterna.DIARIO,
                PortalMenuPublico.RotaInterna.CONCURSOS,
                PortalMenuPublico.RotaInterna.SAUDE,
                PortalMenuPublico.RotaInterna.EDUCACAO,
            }
        )
    if flags.get("transparencia"):
        routes.update(
            {
                PortalMenuPublico.RotaInterna.LICITACOES,
                PortalMenuPublico.RotaInterna.CONTRATOS,
                PortalMenuPublico.RotaInterna.TRANSPARENCIA,
                PortalMenuPublico.RotaInterna.OUVIDORIA,
            }
        )
    if flags.get("camara"):
        routes.add(PortalMenuPublico.RotaInterna.CAMARA)
    return routes


def _app_login_url(request) -> str:
    # Prefer middleware-provided URL (handles tenants + dev ports consistently).
    from_mw = (getattr(request, "public_login_url", "") or "").strip()
    if from_mw:
        return from_mw
    return _build_app_url(request, reverse("accounts:login"))


def _render_municipio_public_home(request, municipio: Municipio):
    plan_flags = _municipio_public_plan_flags(municipio)
    if not plan_flags["portal"]:
        raise Http404("Portal da Prefeitura indisponível para este município.")

    allowed_internal_routes = _allowed_internal_routes_for_public(plan_flags)
    portal_cfg = PortalMunicipalConfig.objects.filter(municipio=municipio).first()

    def _to_bool(value, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        raw = str(value).strip().lower()
        if raw in {"1", "true", "on", "sim", "yes"}:
            return True
        if raw in {"0", "false", "off", "nao", "não", "no"}:
            return False
        return default

    theme_builder_raw = {}
    if portal_cfg and isinstance(portal_cfg.redes_sociais, dict):
        theme_builder_raw = dict(portal_cfg.redes_sociais.get("theme_builder") or {})
    interval_raw = theme_builder_raw.get("slider_interval_ms")
    try:
        interval_ms = int(interval_raw)
    except (TypeError, ValueError):
        interval_ms = 5500
    interval_ms = max(1500, min(interval_ms, 20000))
    theme_builder = {
        "slider_interval_ms": interval_ms,
        "slider_autoplay": _to_bool(theme_builder_raw.get("slider_autoplay"), True),
        "slider_show_arrows": _to_bool(theme_builder_raw.get("slider_show_arrows"), True),
        "slider_show_dots": _to_bool(theme_builder_raw.get("slider_show_dots"), True),
    }
    menu_items_header = build_menu_items(
        municipio,
        posicao="HEADER",
        allowed_internal_routes=allowed_internal_routes,
    )
    menu_items_footer = build_menu_items(
        municipio,
        posicao="FOOTER",
        allowed_internal_routes=allowed_internal_routes,
    )

    secretarias = (
        municipio.secretarias.filter(ativo=True)
        .only("id", "nome", "sigla")
        .order_by("nome")[:16]
    )

    summary = {
        "secretarias": municipio.secretarias.filter(ativo=True).count(),
        "unidades": Unidade.objects.filter(secretaria__municipio=municipio, ativo=True).count(),
        "eventos_publicos": (
            TransparenciaEventoPublico.objects.filter(
                municipio=municipio,
                publico=True,
            ).count()
            if plan_flags["transparencia"]
            else 0
        ),
    }

    links_rapidos_default = [
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
            "titulo": "Serviços Digitais",
            "descricao": "Acesso aos principais serviços públicos do município.",
            "url": reverse("core:portal_noticias_public"),
            "icon": "fa-solid fa-circle-nodes",
        },
    ]
    if plan_flags["transparencia"]:
        links_rapidos_default.extend(
            [
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
        )
        links_rapidos_default.insert(
            0,
            {
                "titulo": "Portal da Transparência",
                "descricao": "Consulte receitas, despesas e eventos publicados.",
                "url": reverse("core:transparencia_public"),
                "icon": "fa-solid fa-scale-balanced",
            },
        )
    if plan_flags["camara"]:
        links_rapidos_default.append(
            {
                "titulo": "Portal da Câmara",
                "descricao": "Sessões, pautas, matérias legislativas e transparência.",
                "url": reverse("core:portal_camara_public"),
                "icon": "fa-solid fa-landmark-dome",
            }
        )

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
        "cta_transparencia": reverse("core:transparencia_public") if plan_flags["transparencia"] else reverse("core:portal_noticias_public"),
        "cta_servicos_online": reverse("core:portal_ouvidoria_public") if plan_flags["transparencia"] else reverse("core:portal_noticias_public"),
        "top_links": (
            [
                {"titulo": "Acessibilidade", "url": "#conteudo-principal", "icon": "fa-solid fa-universal-access"},
            ]
            + (
                [{"titulo": "Ouvidoria", "url": reverse("core:portal_ouvidoria_public"), "icon": "fa-regular fa-message"}]
                if plan_flags["transparencia"]
                else [{"titulo": "Notícias", "url": reverse("core:portal_noticias_public"), "icon": "fa-regular fa-newspaper"}]
            )
            + (
                [{"titulo": "Portal da Transparência", "url": reverse("core:transparencia_public"), "icon": "fa-solid fa-chart-column"}]
                if plan_flags["transparencia"]
                else []
            )
            + [
                {"titulo": "Diário Oficial", "url": reverse("core:portal_diario_public"), "icon": "fa-regular fa-file-lines"},
                {"titulo": "Sistema Interno", "url": _app_login_url(request), "icon": "fa-solid fa-arrow-right-to-bracket"},
            ]
        ),
        "plan_flags": plan_flags,
        "portal_cfg": portal_cfg,
        "menu_items_header": menu_items_header,
        "menu_items_footer": menu_items_footer,
        "paginas_publicas": paginas_publicas,
        "theme_builder": theme_builder,
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
            "resposta": "Sim, com faixas de referência por porte municipal (P, M e G). O valor final considera escopo, implantação e integrações contratadas.",
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
        "footer_marca_nome": content.get("marca_nome") or "GEPUB",
        "slides": slides,
        "method_steps": method_steps,
        "service_cards": service_cards,
        "planos": _planos_para_site(),
        "form": form,
        "simulacao": simulacao,
        "faq_items": faq_items,
        "cta_home": reverse("core:institucional_public"),
        "cta_login": _app_login_url(request),
        "cta_contato": cta_contato,
        "cta_blog": reverse("core:blog_public"),
        "cta_documentacao": reverse("core:documentacao_public"),
        "cta_validacao_documentos": reverse("core:validar_documento_public"),
        "cta_privacidade": reverse("core:politica_privacidade_public"),
        "cta_cookies": reverse("core:politica_cookies_public"),
        "cta_termos": reverse("core:termos_servico_public"),
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


def _public_site_context(request, content: dict | None = None) -> dict:
    base = content or {}
    marca_nome = base.get("marca_nome") or "GEPUB"
    cta_contato = (base.get("servicos_cta_link") or "").strip()
    if not cta_contato or cta_contato == "#simulador":
        cta_contato = "#contato"
    if cta_contato.startswith("#"):
        cta_contato = f'{reverse("core:institucional_public")}{cta_contato}'
    return {
        "marca_nome": marca_nome,
        "footer_marca_nome": marca_nome,
        "marca_logo_url": base.get("marca_logo_url", ""),
        "cta_home": reverse("core:institucional_public"),
        "cta_login": _app_login_url(request),
        "cta_contato": cta_contato,
        "cta_blog": reverse("core:blog_public"),
        "cta_documentacao": reverse("core:documentacao_public"),
        "cta_validacao_documentos": reverse("core:validar_documento_public"),
        "cta_privacidade": reverse("core:politica_privacidade_public"),
        "cta_cookies": reverse("core:politica_cookies_public"),
        "cta_termos": reverse("core:termos_servico_public"),
        "cta_transparencia": reverse("core:transparencia_public"),
    }


def _render_public_site_page(request, template_name: str, extra_context: dict):
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
    context = {
        **_public_site_context(request, content),
        **extra_context,
    }
    return render(request, template_name, context)


def blog_public(request):
    blog_posts = [
        {
            "categoria": "Gestão Municipal",
            "titulo": "Como integrar secretarias e reduzir retrabalho em 90 dias",
            "resumo": "Estratégia prática para conectar operação, dados e equipes usando uma base única de gestão pública.",
            "tempo_leitura": "6 min",
            "data": "12 mar 2026",
        },
        {
            "categoria": "Educação",
            "titulo": "Diário digital e indicadores: o que muda no acompanhamento pedagógico",
            "resumo": "Veja como frequência, notas e desempenho viram decisões objetivas para coordenação e secretaria.",
            "tempo_leitura": "5 min",
            "data": "10 mar 2026",
        },
        {
            "categoria": "Saúde",
            "titulo": "Fluxo de atendimento municipal com rastreabilidade ponta a ponta",
            "resumo": "Da fila ao prontuário, uma visão estruturada para reduzir gargalos e ampliar previsibilidade da rede.",
            "tempo_leitura": "7 min",
            "data": "08 mar 2026",
        },
        {
            "categoria": "Transparência",
            "titulo": "Portal público organizado: o que publicar e como manter rotina",
            "resumo": "Guia rápido para padronizar publicações oficiais e fortalecer governança de dados públicos.",
            "tempo_leitura": "4 min",
            "data": "05 mar 2026",
        },
        {
            "categoria": "Tecnologia",
            "titulo": "Arquitetura escalável para prefeituras em crescimento",
            "resumo": "Boas práticas para suportar aumento de usuários, integrações e novos módulos sem perda de desempenho.",
            "tempo_leitura": "6 min",
            "data": "03 mar 2026",
        },
        {
            "categoria": "Operação",
            "titulo": "Implantação orientada por valor: primeiros entregáveis por secretaria",
            "resumo": "Checklist objetivo para iniciar operação com metas por área e governança de execução.",
            "tempo_leitura": "5 min",
            "data": "01 mar 2026",
        },
    ]

    return _render_public_site_page(
        request,
        "core/blog_public.html",
        {
            "page_title": "Blog GEPUB",
            "page_subtitle": "Conteúdos práticos sobre transformação digital na gestão municipal.",
            "posts": blog_posts,
        },
    )


def politica_privacidade_public(request):
    return _render_public_site_page(
        request,
        "core/legal_public.html",
        {
            "page_title": "Política de Privacidade",
            "page_subtitle": "Diretrizes institucionais sobre tratamento de dados pessoais, transparência e conformidade com a LGPD no ecossistema GEPUB.",
            "last_update": PRIVACY_POLICY_LAST_UPDATE,
            "sections": PRIVACY_POLICY_SECTIONS,
        },
    )


def politica_cookies_public(request):
    return _render_public_site_page(
        request,
        "core/legal_public.html",
        {
            "page_title": "Política de Cookies",
            "page_subtitle": "Regras de utilização de cookies e tecnologias correlatas para autenticação, segurança, desempenho e experiência de uso.",
            "last_update": COOKIES_POLICY_LAST_UPDATE,
            "sections": COOKIES_POLICY_SECTIONS,
        },
    )


def termos_servico_public(request):
    return _render_public_site_page(
        request,
        "core/legal_public.html",
        {
            "page_title": "Termos de Serviço",
            "page_subtitle": "Condições institucionais de acesso e uso da plataforma GEPUB por órgãos públicos, secretarias e usuários autorizados.",
            "last_update": TERMS_OF_SERVICE_LAST_UPDATE,
            "sections": TERMS_OF_SERVICE_SECTIONS,
        },
    )


def validar_documento_public(request, codigo=None):
    code_input = (request.GET.get("codigo") or "").strip()
    documento = None
    status = "pendente"
    search_code = code_input

    if codigo:
        documento = DocumentoEmitido.objects.select_related("gerado_por").filter(codigo=codigo).first()
        status = "valido" if documento and documento.ativo else ("revogado" if documento else "nao_encontrado")
        search_code = str(codigo)
    elif code_input:
        try:
            parsed = UUID(code_input)
            documento = DocumentoEmitido.objects.select_related("gerado_por").filter(codigo=parsed).first()
            status = "valido" if documento and documento.ativo else ("revogado" if documento else "nao_encontrado")
        except Exception:
            status = "codigo_invalido"

    content, _, _, _ = _get_institutional_content()
    context = {
        **_public_site_context(request, content),
        "page_title": "Validação de Documento",
        "page_subtitle": "Confirme autenticidade, emissor e status de documentos emitidos pelo GEPUB.",
        "code_input": search_code,
        "documento": documento,
        "status": status,
    }
    return render(request, "core/validacao_documento_public.html", context)


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

    auto_stats = {
        "diarios": (diarios_total, diarios_ultima),
        "exec_2025": (exec_2025_total, exec_2025_ultima),
        "exec_2024": (exec_2024_total, exec_2024_ultima),
        "divida_ativa": (divida_ativa_total, divida_ativa_ultima),
        "folha": (folha_total, folha_ultima),
        "servidores": (servidores_total, servidores_ultima),
        "cargos": (cargos_total, cargos_ultima),
        "estagiarios": (estagiarios_total, estagiarios_ultima),
        "terceirizados": (terceirizados_total, terceirizados_ultima),
        "concursos": (concursos_total, concursos_ultima),
        "licitacoes": (licitacoes_total, licitacoes_ultima),
        "contratos": (contratos_total, contratos_ultima),
        "aditivos": (aditivos_total, aditivos_ultima),
        "fiscal": (fiscal_total, fiscal_ultima),
    }

    secoes = []
    for secao_spec in TRANSPARENCIA_SECTION_SPECS:
        itens = []
        for item_spec in secao_spec.get("itens", []):
            auto_total, auto_ultima = auto_stats.get(item_spec.get("auto_key"), (0, None))
            categorias = [
                getattr(PortalTransparenciaArquivo.Categoria, categoria_nome)
                for categoria_nome in item_spec.get("categorias", [])
                if hasattr(PortalTransparenciaArquivo.Categoria, categoria_nome)
            ]
            itens.append(
                _build_transparencia_item(
                    titulo=item_spec.get("titulo", ""),
                    descricao=item_spec.get("descricao", ""),
                    capacidade_origem=item_spec.get("capacidade_origem", "MANUAL"),
                    auto_total=auto_total,
                    auto_ultima=auto_ultima,
                    arquivo_stats=arquivo_stats,
                    categorias_arquivo=categorias,
                    url_publica=reverse(item_spec["url_name"]) if item_spec.get("url_name") else "",
                )
            )

        secoes.append(
            {
                "titulo": secao_spec.get("titulo", ""),
                "descricao": secao_spec.get("descricao", ""),
                "itens": itens,
            }
        )

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
    if municipio_publico:
        tenant_flags = _municipio_public_plan_flags(municipio_publico)
        if not tenant_flags["transparencia"]:
            raise Http404("Portal da Transparência indisponível para este município.")
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
    if municipio_contexto:
        ctx_flags = _municipio_public_plan_flags(municipio_contexto)
        if not ctx_flags["transparencia"]:
            raise Http404("Portal da Transparência indisponível para este município.")
        allowed_internal_routes = _allowed_internal_routes_for_public(ctx_flags)
    else:
        ctx_flags = None
        allowed_internal_routes = None

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
        build_menu_items(
            municipio_contexto,
            posicao="HEADER",
            allowed_internal_routes=allowed_internal_routes,
        )
        if municipio_contexto
        else [
            {"titulo": "Início", "url": reverse("core:institucional_public"), "nova_aba": False},
            {"titulo": "Transparência", "url": reverse("core:transparencia_public"), "nova_aba": False},
            {"titulo": "Documentação", "url": reverse("core:documentacao_public"), "nova_aba": False},
            {"titulo": "Validação", "url": reverse("core:validar_documento_public"), "nova_aba": False},
        ]
    )
    menu_items_footer = (
        build_menu_items(
            municipio_contexto,
            posicao="FOOTER",
            allowed_internal_routes=allowed_internal_routes,
        )
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
        "plan_flags": ctx_flags or {"portal": True, "transparencia": True, "camara": False},
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

    modulos = [dict(item) for item in DOCUMENTATION_MODULES]
    funcionalidades = [dict(item) for item in DOCUMENTATION_FUNCIONALIDADES]
    integracoes = [dict(item) for item in DOCUMENTATION_INTEGRACOES]
    arquitetura = list(DOCUMENTATION_ARQUITETURA)
    fluxos = list(DOCUMENTATION_FLUXOS)
    pilares = list(DOCUMENTATION_PILARES)
    kpis = [dict(item) for item in DOCUMENTATION_KPIS]

    rbac_sections = build_site_role_sections()
    rbac_matrix = build_operational_matrix_rows()
    rbac_roles_count = len({row["role_code"] for row in rbac_matrix})
    rbac_modules_count = len({row["module_key"] for row in rbac_matrix})
    rbac_yes_cells = len(
        [
            row
            for row in rbac_matrix
            if row["view"] == "SIM"
            or row["create"] == "SIM"
            or row["edit"] == "SIM"
            or row["delete"] == "SIM"
            or row["approve"] == "SIM"
            or row["export"] == "SIM"
            or row["configure_module"] == "SIM"
        ]
    )

    context = {
        **_public_site_context(request, content),
        "page_title": "Documentação",
        "titulo": f"Documentação {content.get('marca_nome', 'GEPUB')}",
        "subtitulo": "Visão completa de arquitetura, apps, integrações e funcionalidades operacionais",
        "marca_nome": content.get("marca_nome") or "GEPUB",
        "marca_logo_url": content.get("marca_logo_url", ""),
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
        "rbac_principios": [
            "Mesmo dashboard por modulo; o que muda e o escopo de visibilidade e acao.",
            "Permissoes por papel com filtro por municipio, secretaria, unidade e atribuicao.",
            "Perfis de auditoria/leitura sem alteracao operacional.",
            "Logs e rastreabilidade para acoes sensiveis e acessos criticos.",
        ],
        "rbac_sections": rbac_sections,
        "rbac_kpis": [
            {"label": "Perfis catalogados", "value": str(rbac_roles_count)},
            {"label": "Modulos no mapa", "value": str(rbac_modules_count)},
            {"label": "Linhas da matriz", "value": str(len(rbac_matrix))},
            {"label": "Celulas com permissao", "value": str(rbac_yes_cells)},
        ],
        "rbac_docs_files": [
            "docs/rbac_relatorio_usuarios_gepub.md",
            "docs/rbac_matriz_operacional_gepub.json",
            "docs/rbac_matriz_operacional_gepub.csv",
            "docs/enderecos_localizacao_maps.md",
        ],
    }
    return render(request, "core/documentacao_public.html", context)
