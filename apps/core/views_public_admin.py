from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

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
from apps.core.rbac import is_admin
from apps.org.models import Municipio


def _can_manage_publicacoes(user) -> bool:
    if is_admin(user):
        return True
    p = getattr(user, "profile", None)
    if not p or not getattr(p, "ativo", False):
        return False
    return (p.role or "").upper() in {"MUNICIPAL", "SECRETARIA"}


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
    return redirect(reverse("core:publicacoes_admin") + _q_municipio(municipio))


def _portal_public_url(request, municipio: Municipio) -> str:
    if municipio.dominio_personalizado:
        domain = municipio.dominio_personalizado.strip()
    else:
        root = (getattr(settings, "GEPUB_PUBLIC_ROOT_DOMAIN", "") or "").strip().lower().strip(".")
        domain = f"{municipio.slug_site}.{root}" if root else municipio.slug_site
    scheme = "https" if (request.is_secure() or not settings.DEBUG) else "http"
    return f"{scheme}://{domain}"


def _ensure_access(request):
    if not _can_manage_publicacoes(request.user):
        return HttpResponseForbidden("403 — Perfil sem acesso à central de publicações.")
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
    arquivos_transparencia = PortalTransparenciaArquivo.objects.filter(municipio=municipio).order_by("categoria", "ordem", "-publicado_em", "-id")[:12]
    concursos = ConcursoPublico.objects.filter(municipio=municipio).prefetch_related("etapas").order_by("-criado_em", "-id")[:12]
    materias = CamaraMateria.objects.filter(municipio=municipio).order_by("-data_publicacao", "-id")[:12]
    sessoes = CamaraSessao.objects.filter(municipio=municipio).order_by("-data_sessao", "-id")[:12]

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
                    "label": "Configuração do portal",
                    "url": reverse("core:publicacoes_config_edit") + _q_municipio(municipio),
                    "icon": "fa-solid fa-sliders",
                    "variant": "btn-primary",
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
                "arquivos_transparencia": PortalTransparenciaArquivo.objects.filter(municipio=municipio).count(),
                "concursos": ConcursoPublico.objects.filter(municipio=municipio).count(),
                "materias": CamaraMateria.objects.filter(municipio=municipio).count(),
                "sessoes": CamaraSessao.objects.filter(municipio=municipio).count(),
            },
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
def publicacoes_config_edit(request):
    denied = _ensure_access(request)
    if denied:
        return denied
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município.")
        return redirect("core:publicacoes_admin")

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
    obj = get_object_or_404(CamaraSessao, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, "Sessão removida.")
    return _redirect_hub(municipio)
