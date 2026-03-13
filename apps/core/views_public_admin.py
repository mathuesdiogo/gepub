from __future__ import annotations

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.billing.services import PlanoApp, municipio_has_plan_app
from apps.core.decorators import require_perm
from apps.core.forms import (
    CamaraMateriaForm,
    CamaraSessaoForm,
    ConcursoEtapaForm,
    ConcursoPublicoForm,
    DiarioOficialEdicaoForm,
    PortalBannerForm,
    PortalHomeBlocoForm,
    PortalTransparenciaArquivoForm,
    PortalMenuPublicoForm,
    PortalMunicipalConfigForm,
    PortalPaginaPublicaForm,
    PortalNoticiaForm,
)
from apps.core.models import (
    CamaraMateria,
    CamaraSessao,
    ConcursoEtapa,
    ConcursoPublico,
    DiarioOficialEdicao,
    PortalBanner,
    PortalHomeBloco,
    PortalTransparenciaArquivo,
    PortalMenuPublico,
    PortalMunicipalConfig,
    PortalPaginaPublica,
    PortalNoticia,
)
from apps.core.rbac import can, is_admin, role_scope_base
from apps.org.models import Municipio


def _can_manage_publicacoes(user) -> bool:
    if is_admin(user):
        return True
    p = getattr(user, "profile", None)
    if not p or not getattr(p, "ativo", False):
        return False
    return bool(
        can(user, "org.view")
        and role_scope_base(getattr(p, "role", None)) in {"ADMIN", "MUNICIPAL", "SECRETARIA"}
    )


def _resolve_municipio(request, *, require_selected: bool = False):
    if is_admin(request.user):
        municipio_id = (request.GET.get("municipio") or request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            municipio = Municipio.objects.filter(pk=int(municipio_id), ativo=True).first()
            if municipio:
                request.session["publicacoes_municipio_id"] = municipio.pk
            return municipio
        municipio_tenant = getattr(request, "current_municipio", None)
        if municipio_tenant and getattr(municipio_tenant, "ativo", False):
            request.session["publicacoes_municipio_id"] = municipio_tenant.pk
            return municipio_tenant
        municipio_session_id = request.session.get("publicacoes_municipio_id")
        if municipio_session_id:
            municipio_session = Municipio.objects.filter(pk=municipio_session_id, ativo=True).first()
            if municipio_session:
                return municipio_session
        if require_selected:
            return None
        return Municipio.objects.filter(ativo=True).order_by("nome").first()

    p = getattr(request.user, "profile", None)
    if p and p.municipio_id:
        return Municipio.objects.filter(pk=p.municipio_id, ativo=True).first()
    return None


def _municipios_admin(request):
    if not is_admin(request.user):
        return Municipio.objects.none()
    return Municipio.objects.filter(ativo=True).order_by("nome")


def _q_municipio(municipio: Municipio) -> str:
    return f"?municipio={municipio.pk}"


def _redirect_hub(municipio: Municipio):
    return redirect(reverse("core:publicacoes_admin") + _q_municipio(municipio) + "&portal=todos")


def _resolve_portal_focus(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in {"prefeitura", "transparencia", "camara", "todos"}:
        return value
    return "todos"


def _portal_focus_meta(portal_focus: str) -> dict[str, str]:
    mapping = {
        "prefeitura": {
            "label": "Portal da Prefeitura",
            "scope": "conteudo",
            "desc": "Você está editando o conteúdo institucional da Prefeitura (notícias, páginas, menu, diário e concursos).",
        },
        "transparencia": {
            "label": "Portal da Transparência",
            "scope": "transparencia",
            "desc": "Você está editando publicações de transparência pública (arquivos, bases e referências oficiais).",
        },
        "camara": {
            "label": "Portal da Câmara",
            "scope": "camara",
            "desc": "Você está no contexto legislativo. O editor principal da Câmara está no App Câmara dedicado.",
        },
        "todos": {
            "label": "Hub de Portais",
            "scope": "all",
            "desc": "Você está no painel consolidado de publicações de todos os portais habilitados.",
        },
    }
    return mapping.get(portal_focus, mapping["todos"])


def _portal_public_url(request, municipio: Municipio) -> str:
    def _sanitize_domain(raw: str) -> str:
        candidate = (raw or "").strip().lower()
        candidate = candidate.replace("https://", "").replace("http://", "").strip("/")
        if re.match(r"^[a-z0-9.-]+$", candidate):
            return candidate
        return ""

    if municipio.dominio_personalizado:
        domain = _sanitize_domain(municipio.dominio_personalizado)
    else:
        root = (getattr(settings, "GEPUB_PUBLIC_ROOT_DOMAIN", "") or "").strip().lower().strip(".")
        domain = _sanitize_domain(f"{municipio.slug_site}.{root}" if root else municipio.slug_site)
    if not domain:
        return reverse("core:institucional_public")
    force_https = bool(getattr(settings, "SECURE_SSL_REDIRECT", False))
    scheme = "https" if (request.is_secure() or force_https) else "http"
    return f"{scheme}://{domain}"


def _normalize_hex(value: str, fallback: str) -> str:
    raw = (value or "").strip()
    if re.match(r"^#[0-9a-fA-F]{6}$", raw):
        return raw.upper()
    return fallback


def _build_editor_blocos(municipio: Municipio, *, max_items: int = 6) -> list[dict]:
    blocos = list(
        PortalHomeBloco.objects.filter(municipio=municipio)
        .order_by("ordem", "id")[:max_items]
    )
    items: list[dict] = []
    for idx in range(max_items):
        obj = blocos[idx] if idx < len(blocos) else None
        items.append(
            {
                "idx": idx,
                "obj": obj,
                "id": obj.id if obj else "",
                "titulo": obj.titulo if obj else "",
                "descricao": obj.descricao if obj else "",
                "link": obj.link if obj else "",
                "icone": obj.icone if obj else "fa-solid fa-circle-info",
                "ativo": obj.ativo if obj else True,
            }
        )
    return items


def _build_editor_slides(municipio: Municipio, *, max_items: int = 4) -> list[dict]:
    slides = list(
        PortalBanner.objects.filter(municipio=municipio)
        .order_by("ordem", "id")[:max_items]
    )
    items: list[dict] = []
    for idx in range(max_items):
        obj = slides[idx] if idx < len(slides) else None
        items.append(
            {
                "idx": idx,
                "obj": obj,
                "id": obj.id if obj else "",
                "titulo": obj.titulo if obj else "",
                "subtitulo": obj.subtitulo if obj else "",
                "link": obj.link if obj else "",
                "ordem": obj.ordem if obj else (idx + 1),
                "ativo": obj.ativo if obj else (idx == 0),
                "tem_imagem": bool(obj and obj.imagem),
            }
        )
    return items


def _bool_from_post(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    raw = str(value).strip().lower()
    if raw in {"1", "true", "on", "sim", "yes"}:
        return True
    if raw in {"0", "false", "off", "nao", "não", "no"}:
        return False
    return default


def _apply_theme_editor_changes(request, municipio: Municipio, *, allow_files: bool) -> None:
    cfg, _ = PortalMunicipalConfig.objects.get_or_create(
        municipio=municipio,
        defaults={"titulo_portal": f"Portal de {municipio.nome}"},
    )
    cfg.titulo_portal = (request.POST.get("titulo_portal") or cfg.titulo_portal or "").strip() or f"Portal de {municipio.nome}"
    cfg.subtitulo_portal = (request.POST.get("subtitulo_portal") or "").strip()
    cfg.mensagem_boas_vindas = (request.POST.get("mensagem_boas_vindas") or "").strip()
    cfg.endereco = (request.POST.get("endereco") or "").strip()
    cfg.telefone = (request.POST.get("telefone") or "").strip()
    cfg.email = (request.POST.get("email") or "").strip()
    cfg.horario_atendimento = (request.POST.get("horario_atendimento") or "").strip()
    cfg.cor_primaria = _normalize_hex(request.POST.get("cor_primaria") or "", cfg.cor_primaria or "#0E4A7E")
    cfg.cor_secundaria = _normalize_hex(request.POST.get("cor_secundaria") or "", cfg.cor_secundaria or "#2F6EA9")

    redes_sociais = cfg.redes_sociais if isinstance(cfg.redes_sociais, dict) else {}
    theme_builder = dict(redes_sociais.get("theme_builder") or {})
    interval_raw = (request.POST.get("slider_interval_ms") or "").strip()
    if interval_raw.isdigit():
        interval_ms = int(interval_raw)
    else:
        try:
            interval_ms = int(theme_builder.get("slider_interval_ms") or 5500)
        except (TypeError, ValueError):
            interval_ms = 5500
    interval_ms = max(1500, min(interval_ms, 20000))
    theme_builder["slider_interval_ms"] = interval_ms
    theme_builder["slider_autoplay"] = _bool_from_post(request.POST.get("slider_autoplay"), True)
    theme_builder["slider_show_arrows"] = _bool_from_post(request.POST.get("slider_show_arrows"), True)
    theme_builder["slider_show_dots"] = _bool_from_post(request.POST.get("slider_show_dots"), True)
    redes_sociais["theme_builder"] = theme_builder
    cfg.redes_sociais = redes_sociais

    if allow_files and request.FILES.get("logo"):
        cfg.logo = request.FILES["logo"]
    if allow_files and request.FILES.get("brasao"):
        cfg.brasao = request.FILES["brasao"]
    cfg.save()

    existing_slides = list(PortalBanner.objects.filter(municipio=municipio).order_by("ordem", "id")[:4])
    for idx in range(4):
        slide_id_raw = (request.POST.get(f"slide_{idx}_id") or "").strip()
        slide = (
            PortalBanner.objects.filter(pk=int(slide_id_raw), municipio=municipio).first()
            if slide_id_raw.isdigit()
            else (existing_slides[idx] if idx < len(existing_slides) else None)
        )

        legacy_prefix = idx == 0 and not request.POST.get("slide_0_titulo")
        titulo = (request.POST.get(f"slide_{idx}_titulo") or "").strip()
        subtitulo = (request.POST.get(f"slide_{idx}_subtitulo") or "").strip()
        link = (request.POST.get(f"slide_{idx}_link") or "").strip()
        ordem_raw = (request.POST.get(f"slide_{idx}_ordem") or "").strip()
        ativo = _bool_from_post(request.POST.get(f"slide_{idx}_ativo"), idx == 0)

        if legacy_prefix:
            titulo = (request.POST.get("banner_titulo") or titulo or "").strip()
            subtitulo = (request.POST.get("banner_subtitulo") or subtitulo or "").strip()
            link = (request.POST.get("banner_link") or link or "").strip()
            ordem_raw = (request.POST.get("banner_ordem") or ordem_raw or "").strip()
            ativo = _bool_from_post(request.POST.get("banner_ativo"), ativo)

        file_key = f"slide_{idx}_imagem"
        if legacy_prefix and not request.FILES.get(file_key):
            file_key = "banner_imagem"
        has_file = allow_files and bool(request.FILES.get(file_key))
        has_payload = bool(titulo or subtitulo or link or has_file)

        if not slide and not has_payload:
            continue
        if not slide:
            slide = PortalBanner(municipio=municipio)

        if titulo:
            slide.titulo = titulo
        elif not slide.titulo:
            slide.titulo = f"Destaque {idx + 1} • {municipio.nome}"
        slide.subtitulo = subtitulo
        slide.link = link
        slide.ativo = ativo
        slide.ordem = int(ordem_raw) if ordem_raw.isdigit() else (idx + 1)
        if has_file:
            slide.imagem = request.FILES[file_key]
        slide.save()

    max_items = 6
    for idx in range(max_items):
        bloco_id_raw = (request.POST.get(f"bloco_{idx}_id") or "").strip()
        bloco = (
            PortalHomeBloco.objects.filter(pk=int(bloco_id_raw), municipio=municipio).first()
            if bloco_id_raw.isdigit()
            else None
        )
        titulo = (request.POST.get(f"bloco_{idx}_titulo") or "").strip()
        descricao = (request.POST.get(f"bloco_{idx}_descricao") or "").strip()
        link = (request.POST.get(f"bloco_{idx}_link") or "").strip()
        icone = (request.POST.get(f"bloco_{idx}_icone") or "").strip() or "fa-solid fa-circle-info"
        ativo = (request.POST.get(f"bloco_{idx}_ativo") or "1").strip() == "1"

        if bloco:
            if titulo:
                bloco.titulo = titulo
            bloco.descricao = descricao
            bloco.link = link
            bloco.icone = icone
            bloco.ativo = ativo
            bloco.ordem = idx + 1
            bloco.save()
            continue

        if not titulo:
            continue
        PortalHomeBloco.objects.create(
            municipio=municipio,
            titulo=titulo,
            descricao=descricao,
            link=link,
            icone=icone,
            ordem=idx + 1,
            ativo=ativo,
        )


def _ensure_access(request):
    if not _can_manage_publicacoes(request.user):
        return HttpResponseForbidden("403 — Perfil sem acesso à central de publicações.")
    return None


def _plan_publicacoes_flags(municipio: Municipio | None) -> dict[str, bool]:
    return {
        "portal": municipio_has_plan_app(municipio, PlanoApp.PORTAL),
        "transparencia": municipio_has_plan_app(municipio, PlanoApp.TRANSPARENCIA),
        "camara": municipio_has_plan_app(municipio, PlanoApp.CAMARA),
    }


def _ensure_plan_access(
    municipio: Municipio | None,
    *,
    require_portal: bool = True,
    require_transparencia: bool = False,
    require_camara: bool = False,
):
    flags = _plan_publicacoes_flags(municipio)
    if require_portal and not flags["portal"]:
        return HttpResponseForbidden("403 — Portal da Prefeitura indisponível no plano atual.")
    if require_transparencia and not flags["transparencia"]:
        return HttpResponseForbidden("403 — Portal da Transparência indisponível no plano atual.")
    if require_camara and not flags["camara"]:
        return HttpResponseForbidden("403 — Portal da Câmara indisponível no plano atual.")
    return None


@login_required
@require_perm("org.view")
@require_http_methods(["GET"])
def publicacoes_admin(request):
    denied = _ensure_access(request)
    if denied:
        return denied

    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Selecione um município para gerenciar os portais públicos.")
        return redirect("core:dashboard")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    plan_flags = _plan_publicacoes_flags(municipio)
    portal_focus = _resolve_portal_focus(request.GET.get("portal"))
    portal_meta = _portal_focus_meta(portal_focus)

    PortalMunicipalConfig.objects.get_or_create(
        municipio=municipio,
        defaults={"titulo_portal": f"Portal de {municipio.nome}"},
    )

    noticias = PortalNoticia.objects.filter(municipio=municipio).order_by("-publicado_em", "-id")[:12]
    banners = PortalBanner.objects.filter(municipio=municipio).order_by("ordem", "-id")[:12]
    paginas = PortalPaginaPublica.objects.filter(municipio=municipio).order_by("ordem", "id")[:12]
    menus = PortalMenuPublico.objects.filter(municipio=municipio).select_related("pagina").order_by("posicao", "ordem", "id")[:20]
    blocos = PortalHomeBloco.objects.filter(municipio=municipio).order_by("ordem", "id")[:12]
    diarios = DiarioOficialEdicao.objects.filter(municipio=municipio).order_by("-data_publicacao", "-id")[:12]
    arquivos_transparencia = (
        PortalTransparenciaArquivo.objects.filter(municipio=municipio).order_by("categoria", "ordem", "-publicado_em", "-id")[:12]
        if plan_flags["transparencia"]
        else PortalTransparenciaArquivo.objects.none()
    )
    concursos = ConcursoPublico.objects.filter(municipio=municipio).prefetch_related("etapas").order_by("-criado_em", "-id")[:12]
    materias = (
        CamaraMateria.objects.filter(municipio=municipio).order_by("-data_publicacao", "-id")[:12]
        if plan_flags["camara"]
        else CamaraMateria.objects.none()
    )
    sessoes = (
        CamaraSessao.objects.filter(municipio=municipio).order_by("-data_sessao", "-id")[:12]
        if plan_flags["camara"]
        else CamaraSessao.objects.none()
    )

    return render(
        request,
        "core/publicacoes_admin.html",
        {
            "title": "Central de Publicações Públicas",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "actions": [
                {
                    "label": "Editor visual do tema",
                    "url": reverse("core:publicacoes_theme_editor") + _q_municipio(municipio),
                    "icon": "fa-solid fa-wand-magic-sparkles",
                    "variant": "btn--primary",
                },
                {
                    "label": "Configuração do portal",
                    "url": reverse("core:publicacoes_config_edit") + _q_municipio(municipio),
                    "icon": "fa-solid fa-sliders",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Ver portal público",
                    "url": _portal_public_url(request, municipio),
                    "icon": "fa-solid fa-arrow-up-right-from-square",
                    "variant": "btn--ghost",
                },
            ],
            "counts": {
                "noticias": PortalNoticia.objects.filter(municipio=municipio).count(),
                "banners": PortalBanner.objects.filter(municipio=municipio).count(),
                "paginas": PortalPaginaPublica.objects.filter(municipio=municipio).count(),
                "menus": PortalMenuPublico.objects.filter(municipio=municipio).count(),
                "blocos": PortalHomeBloco.objects.filter(municipio=municipio).count(),
                "diarios": DiarioOficialEdicao.objects.filter(municipio=municipio).count(),
                "arquivos_transparencia": (
                    PortalTransparenciaArquivo.objects.filter(municipio=municipio).count()
                    if plan_flags["transparencia"]
                    else 0
                ),
                "concursos": ConcursoPublico.objects.filter(municipio=municipio).count(),
                "materias": CamaraMateria.objects.filter(municipio=municipio).count() if plan_flags["camara"] else 0,
                "sessoes": CamaraSessao.objects.filter(municipio=municipio).count() if plan_flags["camara"] else 0,
            },
            "plan_flags": plan_flags,
            "portal_focus": portal_focus,
            "portal_focus_label": portal_meta["label"],
            "portal_focus_desc": portal_meta["desc"],
            "portal_focus_scope": portal_meta["scope"],
            "noticias": noticias,
            "banners": banners,
            "paginas": paginas,
            "menus": menus,
            "blocos": blocos,
            "diarios": diarios,
            "arquivos_transparencia": arquivos_transparencia,
            "concursos": concursos,
            "materias": materias,
            "sessoes": sessoes,
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def publicacoes_theme_editor(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município.")
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    plan_flags = _plan_publicacoes_flags(municipio)

    if request.method == "POST":
        _apply_theme_editor_changes(request, municipio, allow_files=True)
        messages.success(request, "Tema atualizado e preview recarregado.")
        return redirect(reverse("core:publicacoes_theme_editor") + _q_municipio(municipio))

    cfg, _ = PortalMunicipalConfig.objects.get_or_create(
        municipio=municipio,
        defaults={"titulo_portal": f"Portal de {municipio.nome}"},
    )
    theme_builder_raw = (cfg.redes_sociais or {}).get("theme_builder", {}) if isinstance(cfg.redes_sociais, dict) else {}
    interval_cfg_raw = theme_builder_raw.get("slider_interval_ms")
    try:
        interval_cfg = int(interval_cfg_raw)
    except (TypeError, ValueError):
        interval_cfg = 5500
    interval_cfg = max(1500, min(interval_cfg, 20000))
    theme_builder = {
        "slider_interval_ms": interval_cfg,
        "slider_autoplay": _bool_from_post(
            None if theme_builder_raw.get("slider_autoplay") is None else str(theme_builder_raw.get("slider_autoplay")),
            True,
        ),
        "slider_show_arrows": _bool_from_post(
            None if theme_builder_raw.get("slider_show_arrows") is None else str(theme_builder_raw.get("slider_show_arrows")),
            True,
        ),
        "slider_show_dots": _bool_from_post(
            None if theme_builder_raw.get("slider_show_dots") is None else str(theme_builder_raw.get("slider_show_dots")),
            True,
        ),
    }
    slides_editor = _build_editor_slides(municipio)
    blocos_editor = _build_editor_blocos(municipio)
    preview_url = reverse("core:publicacoes_theme_preview") + f"?municipio={municipio.pk}&portal_editor=1"

    return render(
        request,
        "core/publicacoes_theme_editor.html",
        {
            "title": "Editor Visual do Tema",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cfg": cfg,
            "slides_editor": slides_editor,
            "blocos_editor": blocos_editor,
            "theme_builder": theme_builder,
            "preview_url": preview_url,
            "autosave_url": reverse("core:publicacoes_theme_autosave") + _q_municipio(municipio),
            "actions": [
                {
                    "label": "Voltar para central",
                    "url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
            ],
            "modulos_links": (
                [
                    {"label": "Notícias", "url": reverse("core:noticia_create") + _q_municipio(municipio)},
                    {"label": "Diário Oficial", "url": reverse("core:diario_create") + _q_municipio(municipio)},
                    {"label": "Concursos", "url": reverse("core:concurso_create") + _q_municipio(municipio)},
                ]
                + (
                    [{"label": "Transparência", "url": reverse("core:transparencia_arquivo_create") + _q_municipio(municipio)}]
                    if plan_flags["transparencia"]
                    else []
                )
                + (
                    [{"label": "Câmara", "url": reverse("core:camara_materia_create") + _q_municipio(municipio)}]
                    if plan_flags["camara"]
                    else []
                )
            ),
            "plan_flags": plan_flags,
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def publicacoes_theme_autosave(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return JsonResponse({"ok": False, "error": "municipio_nao_encontrado"}, status=400)
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return JsonResponse({"ok": False, "error": "portal_indisponivel_no_plano"}, status=403)

    _apply_theme_editor_changes(request, municipio, allow_files=False)
    return JsonResponse({"ok": True})


@login_required
@require_perm("org.view")
@require_http_methods(["GET"])
def publicacoes_theme_preview(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para visualizar o preview.")
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied

    from apps.core.views_portal import _render_municipio_public_home

    return _render_municipio_public_home(request, municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def publicacoes_config_edit(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município.")
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied

    obj, _ = PortalMunicipalConfig.objects.get_or_create(
        municipio=municipio,
        defaults={"titulo_portal": f"Portal de {municipio.nome}"},
    )
    form = PortalMunicipalConfigForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Configuração do portal atualizada.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Configuração do Portal Municipal",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar configuração",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def noticia_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município.")
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    form = PortalNoticiaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.autor = request.user
        obj.save()
        messages.success(request, "Notícia publicada.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova notícia",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar notícia",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def noticia_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalNoticia, pk=pk, municipio=municipio)
    form = PortalNoticiaForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Notícia atualizada.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar notícia",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar notícia",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def noticia_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalNoticia, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Notícia removida.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def banner_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    form = PortalBannerForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Banner salvo.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo banner",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar banner",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def banner_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalBanner, pk=pk, municipio=municipio)
    form = PortalBannerForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Banner atualizado.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar banner",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar banner",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def banner_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalBanner, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Banner removido.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def pagina_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    form = PortalPaginaPublicaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Página pública salva.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova página pública",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar página",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def pagina_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalPaginaPublica, pk=pk, municipio=municipio)
    form = PortalPaginaPublicaForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Página pública atualizada.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar página pública",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar página",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def pagina_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalPaginaPublica, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Página pública removida.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def menu_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    form = PortalMenuPublicoForm(request.POST or None)
    form.fields["pagina"].queryset = PortalPaginaPublica.objects.filter(municipio=municipio).order_by("ordem", "titulo")
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Item de menu salvo.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo item de menu",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar item de menu",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def menu_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalMenuPublico, pk=pk, municipio=municipio)
    form = PortalMenuPublicoForm(request.POST or None, instance=obj)
    form.fields["pagina"].queryset = PortalPaginaPublica.objects.filter(municipio=municipio).order_by("ordem", "titulo")
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Item de menu atualizado.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar item de menu",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar item de menu",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def menu_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalMenuPublico, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Item de menu removido.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def home_bloco_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    form = PortalHomeBlocoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Bloco da home salvo.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo bloco da home",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar bloco",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def home_bloco_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalHomeBloco, pk=pk, municipio=municipio)
    form = PortalHomeBlocoForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bloco da home atualizado.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar bloco da home",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar bloco",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def home_bloco_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalHomeBloco, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Bloco da home removido.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def transparencia_arquivo_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_transparencia=True)
    if denied:
        return denied
    form = PortalTransparenciaArquivoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Arquivo de transparência publicado.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo arquivo de transparência",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar publicação",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def transparencia_arquivo_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_transparencia=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalTransparenciaArquivo, pk=pk, municipio=municipio)
    form = PortalTransparenciaArquivoForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Arquivo de transparência atualizado.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar arquivo de transparência",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar publicação",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def transparencia_arquivo_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_transparencia=True)
    if denied:
        return denied
    obj = get_object_or_404(PortalTransparenciaArquivo, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Arquivo de transparência removido.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def diario_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    form = DiarioOficialEdicaoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Edição do diário oficial salva.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova edição do Diário Oficial",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar edição",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def diario_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(DiarioOficialEdicao, pk=pk, municipio=municipio)
    form = DiarioOficialEdicaoForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Diário atualizado.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar diário oficial",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar edição",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def diario_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(DiarioOficialEdicao, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Edição removida.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def concurso_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    form = ConcursoPublicoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Concurso salvo.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo concurso/processo seletivo",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar concurso",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def concurso_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(ConcursoPublico, pk=pk, municipio=municipio)
    form = ConcursoPublicoForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Concurso atualizado.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar concurso",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar concurso",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def concurso_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    obj = get_object_or_404(ConcursoPublico, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Concurso removido.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def concurso_etapa_create(request, concurso_pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    concurso = get_object_or_404(ConcursoPublico, pk=concurso_pk, municipio=municipio)
    form = ConcursoEtapaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        etapa = form.save(commit=False)
        etapa.concurso = concurso
        etapa.save()
        messages.success(request, "Etapa cadastrada.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Nova etapa • {concurso.titulo}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar etapa",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def concurso_etapa_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True)
    if denied:
        return denied
    etapa = get_object_or_404(ConcursoEtapa.objects.select_related("concurso"), pk=pk, concurso__municipio=municipio)
    etapa.delete()
    messages.success(request, "Etapa removida.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def camara_materia_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_camara=True)
    if denied:
        return denied
    form = CamaraMateriaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Matéria da câmara salva.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova matéria da câmara",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar matéria",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def camara_materia_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_camara=True)
    if denied:
        return denied
    obj = get_object_or_404(CamaraMateria, pk=pk, municipio=municipio)
    form = CamaraMateriaForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Matéria atualizada.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar matéria da câmara",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar matéria",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def camara_materia_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_camara=True)
    if denied:
        return denied
    obj = get_object_or_404(CamaraMateria, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Matéria removida.")
    return _redirect_hub(municipio)


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def camara_sessao_create(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_camara=True)
    if denied:
        return denied
    form = CamaraSessaoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.save()
        messages.success(request, "Sessão cadastrada.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova sessão da câmara",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar sessão",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["GET", "POST"])
def camara_sessao_update(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_camara=True)
    if denied:
        return denied
    obj = get_object_or_404(CamaraSessao, pk=pk, municipio=municipio)
    form = CamaraSessaoForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Sessão atualizada.")
        return _redirect_hub(municipio)
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Editar sessão da câmara",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("core:publicacoes_admin") + _q_municipio(municipio),
            "submit_label": "Salvar sessão",
            "enctype": "multipart/form-data",
        },
    )


@login_required
@require_perm("org.view")
@require_http_methods(["POST"])
def camara_sessao_delete(request, pk: int):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("core:publicacoes_admin")
    denied = _ensure_plan_access(municipio, require_portal=True, require_camara=True)
    if denied:
        return denied
    obj = get_object_or_404(CamaraSessao, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Sessão removida.")
    return _redirect_hub(municipio)
