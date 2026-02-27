from __future__ import annotations

from django.urls import reverse

from apps.core.models import PortalMenuPublico, PortalPaginaPublica


ROTA_URL_NAME_MAP = {
    PortalMenuPublico.RotaInterna.HOME: "core:home",
    PortalMenuPublico.RotaInterna.NOTICIAS: "core:portal_noticias_public",
    PortalMenuPublico.RotaInterna.LICITACOES: "core:portal_licitacoes_public",
    PortalMenuPublico.RotaInterna.CONTRATOS: "core:portal_contratos_public",
    PortalMenuPublico.RotaInterna.TRANSPARENCIA: "core:transparencia_public",
    PortalMenuPublico.RotaInterna.OUVIDORIA: "core:portal_ouvidoria_public",
    PortalMenuPublico.RotaInterna.DIARIO: "core:portal_diario_public",
    PortalMenuPublico.RotaInterna.CONCURSOS: "core:portal_concursos_public",
    PortalMenuPublico.RotaInterna.CAMARA: "core:portal_camara_public",
    PortalMenuPublico.RotaInterna.SAUDE: "core:portal_saude_public",
    PortalMenuPublico.RotaInterna.EDUCACAO: "core:portal_educacao_public",
}


def default_nav_urls() -> dict[str, str]:
    return {k: reverse(v) for k, v in ROTA_URL_NAME_MAP.items()}


def resolve_internal_route_url(route_key: str) -> str:
    url_name = ROTA_URL_NAME_MAP.get(route_key or "")
    if not url_name:
        return "#"
    return reverse(url_name)


def _fallback_header_menu() -> list[dict]:
    return [
        {"titulo": "Início", "url": resolve_internal_route_url(PortalMenuPublico.RotaInterna.HOME), "nova_aba": False},
        {"titulo": "Notícias", "url": resolve_internal_route_url(PortalMenuPublico.RotaInterna.NOTICIAS), "nova_aba": False},
        {"titulo": "Licitações", "url": resolve_internal_route_url(PortalMenuPublico.RotaInterna.LICITACOES), "nova_aba": False},
        {"titulo": "Contratos", "url": resolve_internal_route_url(PortalMenuPublico.RotaInterna.CONTRATOS), "nova_aba": False},
        {"titulo": "Transparência", "url": resolve_internal_route_url(PortalMenuPublico.RotaInterna.TRANSPARENCIA), "nova_aba": False},
        {"titulo": "e-SIC/Ouvidoria", "url": resolve_internal_route_url(PortalMenuPublico.RotaInterna.OUVIDORIA), "nova_aba": False},
    ]


def _fallback_footer_menu(municipio) -> list[dict]:
    pages = (
        PortalPaginaPublica.objects.filter(
            municipio=municipio,
            publicado=True,
            mostrar_no_rodape=True,
        )
        .order_by("ordem", "id")
    )
    return [
        {
            "titulo": page.titulo,
            "url": reverse("core:portal_pagina_public", kwargs={"slug": page.slug}),
            "nova_aba": False,
        }
        for page in pages
    ]


def build_menu_items(municipio, *, posicao: str) -> list[dict]:
    qs = (
        PortalMenuPublico.objects.filter(
            municipio=municipio,
            posicao=posicao,
            ativo=True,
        )
        .select_related("pagina")
        .order_by("ordem", "id")
    )
    items: list[dict] = []
    for item in qs:
        if item.tipo_destino == PortalMenuPublico.TipoDestino.INTERNO:
            url = resolve_internal_route_url(item.rota_interna)
        elif item.tipo_destino == PortalMenuPublico.TipoDestino.PAGINA:
            if not item.pagina_id or not item.pagina or not item.pagina.publicado:
                continue
            url = reverse("core:portal_pagina_public", kwargs={"slug": item.pagina.slug})
        else:
            url = (item.url_externa or "").strip()
            if not url:
                continue
        items.append(
            {
                "titulo": item.titulo,
                "url": url,
                "nova_aba": bool(item.abrir_em_nova_aba),
            }
        )

    if items:
        return items
    if posicao == PortalMenuPublico.Posicao.HEADER:
        return _fallback_header_menu()
    return _fallback_footer_menu(municipio)
