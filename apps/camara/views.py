from __future__ import annotations

from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponseForbidden, HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.billing.services import PlanoApp, municipio_has_plan_app
from apps.core.decorators import require_perm
from apps.core.rbac import can, is_admin
from apps.org.models import Municipio

from .forms import (
    AgendaLegislativaForm,
    AtaForm,
    CamaraConfigForm,
    CamaraOuvidoriaManifestacaoForm,
    ComissaoForm,
    ComissaoMembroForm,
    DocumentoCamaraForm,
    MesaDiretoraForm,
    NoticiaCamaraForm,
    PautaForm,
    ProposicaoAutorForm,
    ProposicaoForm,
    ProposicaoTramitacaoForm,
    SessaoDocumentoForm,
    SessaoForm,
    TransparenciaCamaraItemForm,
    TransmissaoForm,
    VereadorForm,
)
from .models import (
    AgendaLegislativa,
    Ata,
    CamaraConfig,
    CamaraOuvidoriaManifestacao,
    Comissao,
    ComissaoMembro,
    DocumentoCamara,
    MesaDiretora,
    NoticiaCamara,
    Pauta,
    Proposicao,
    ProposicaoAutor,
    ProposicaoTramitacao,
    Sessao,
    SessaoDocumento,
    TransparenciaCamaraItem,
    Transmissao,
    Vereador,
)


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    title: str
    icon: str
    model: type
    form: type
    manage_perm: str
    search_fields: tuple[str, ...]
    columns: tuple[tuple[str, str], ...]
    order_by: tuple[str, ...]
    singleton: bool = False
    enctype: bool = False


def _resolve_municipio(request, *, require_selected: bool = False):
    if is_admin(request.user):
        municipio_id = (request.GET.get("municipio") or request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            municipio = Municipio.objects.filter(pk=int(municipio_id), ativo=True).first()
            if municipio:
                request.session["camara_municipio_id"] = municipio.pk
            return municipio

        municipio_tenant = getattr(request, "current_municipio", None)
        if municipio_tenant and getattr(municipio_tenant, "ativo", False):
            request.session["camara_municipio_id"] = municipio_tenant.pk
            return municipio_tenant

        municipio_session_id = request.session.get("camara_municipio_id")
        if municipio_session_id:
            municipio_session = Municipio.objects.filter(pk=municipio_session_id, ativo=True).first()
            if municipio_session:
                return municipio_session

        if require_selected:
            return None
        return Municipio.objects.filter(ativo=True).order_by("nome").first()

    profile = getattr(request.user, "profile", None)
    if profile and profile.municipio_id:
        return Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
    return None


def _municipios_admin(request):
    if not is_admin(request.user):
        return Municipio.objects.none()
    return Municipio.objects.filter(ativo=True).order_by("nome")


def _q_municipio(municipio: Municipio) -> str:
    return f"?municipio={municipio.pk}"


def _value_from_attr(obj, attr: str):
    current = obj
    for part in attr.split("."):
        current = getattr(current, part, "")
        if callable(current):
            current = current()
        if current is None:
            return ""
    return current


def _to_text(value):
    if value is None:
        return ""
    return str(value)


MODULE_SPECS: dict[str, ModuleSpec] = {
    "config": ModuleSpec(
        key="config",
        title="Institucional",
        icon="fa-solid fa-building-columns",
        model=CamaraConfig,
        form=CamaraConfigForm,
        manage_perm="camara.cms.manage",
        search_fields=("nome_portal", "historia", "missao"),
        columns=(("Portal", "nome_portal"), ("Status", "get_status_display"), ("Atualizado", "updated_at")),
        order_by=("municipio__nome",),
        singleton=True,
    ),
    "vereadores": ModuleSpec(
        key="vereadores",
        title="Vereadores",
        icon="fa-solid fa-users",
        model=Vereador,
        form=VereadorForm,
        manage_perm="camara.manage",
        search_fields=("nome_completo", "nome_parlamentar", "partido"),
        columns=(("Nome", "nome_completo"), ("Partido", "partido"), ("Status", "get_status_display")),
        order_by=("nome_completo", "id"),
        enctype=True,
    ),
    "mesa_diretora": ModuleSpec(
        key="mesa_diretora",
        title="Mesa Diretora",
        icon="fa-solid fa-user-tie",
        model=MesaDiretora,
        form=MesaDiretoraForm,
        manage_perm="camara.manage",
        search_fields=("vereador__nome_completo", "cargo", "legislatura"),
        columns=(("Vereador", "vereador"), ("Cargo", "get_cargo_display"), ("Legislatura", "legislatura")),
        order_by=("-periodo_inicio", "cargo", "id"),
    ),
    "comissoes": ModuleSpec(
        key="comissoes",
        title="Comissões",
        icon="fa-solid fa-people-group",
        model=Comissao,
        form=ComissaoForm,
        manage_perm="camara.manage",
        search_fields=("nome", "descricao"),
        columns=(("Nome", "nome"), ("Tipo", "get_tipo_display"), ("Presidente", "presidente"), ("Status", "get_status_display")),
        order_by=("nome", "id"),
    ),
    "comissao_membros": ModuleSpec(
        key="comissao_membros",
        title="Membros de Comissão",
        icon="fa-solid fa-user-check",
        model=ComissaoMembro,
        form=ComissaoMembroForm,
        manage_perm="camara.manage",
        search_fields=("comissao__nome", "vereador__nome_completo", "papel"),
        columns=(("Comissão", "comissao"), ("Vereador", "vereador"), ("Papel", "get_papel_display")),
        order_by=("comissao__nome", "papel", "id"),
    ),
    "sessoes": ModuleSpec(
        key="sessoes",
        title="Sessões",
        icon="fa-solid fa-gavel",
        model=Sessao,
        form=SessaoForm,
        manage_perm="camara.sessoes.manage",
        search_fields=("titulo", "numero", "local"),
        columns=(("Sessão", "titulo"), ("Tipo", "get_tipo_display"), ("Data", "data_hora"), ("Situação", "get_situacao_display")),
        order_by=("-data_hora", "-id"),
    ),
    "sessao_documentos": ModuleSpec(
        key="sessao_documentos",
        title="Documentos de Sessão",
        icon="fa-solid fa-folder-open",
        model=SessaoDocumento,
        form=SessaoDocumentoForm,
        manage_perm="camara.sessoes.manage",
        search_fields=("sessao__titulo", "titulo", "tipo"),
        columns=(("Sessão", "sessao"), ("Título", "titulo"), ("Tipo", "get_tipo_display"), ("Status", "get_status_display")),
        order_by=("-created_at", "-id"),
        enctype=True,
    ),
    "proposicoes": ModuleSpec(
        key="proposicoes",
        title="Proposições",
        icon="fa-solid fa-file-signature",
        model=Proposicao,
        form=ProposicaoForm,
        manage_perm="camara.proposicoes.manage",
        search_fields=("numero", "ementa", "situacao"),
        columns=(("Tipo", "get_tipo_display"), ("Número", "numero"), ("Ano", "ano"), ("Situação", "situacao")),
        order_by=("-ano", "-id"),
        enctype=True,
    ),
    "proposicao_autores": ModuleSpec(
        key="proposicao_autores",
        title="Autores de Proposição",
        icon="fa-solid fa-user-pen",
        model=ProposicaoAutor,
        form=ProposicaoAutorForm,
        manage_perm="camara.proposicoes.manage",
        search_fields=("proposicao__numero", "vereador__nome_completo", "nome_livre"),
        columns=(("Proposição", "proposicao"), ("Autor", "vereador"), ("Autor livre", "nome_livre"), ("Papel", "get_papel_display")),
        order_by=("proposicao", "papel", "id"),
    ),
    "proposicao_tramitacoes": ModuleSpec(
        key="proposicao_tramitacoes",
        title="Tramitações",
        icon="fa-solid fa-route",
        model=ProposicaoTramitacao,
        form=ProposicaoTramitacaoForm,
        manage_perm="camara.proposicoes.manage",
        search_fields=("proposicao__numero", "etapa", "situacao"),
        columns=(("Proposição", "proposicao"), ("Data", "data_evento"), ("Etapa", "etapa"), ("Situação", "situacao")),
        order_by=("-data_evento", "-ordem", "-id"),
    ),
    "atas": ModuleSpec(
        key="atas",
        title="Atas",
        icon="fa-solid fa-file-lines",
        model=Ata,
        form=AtaForm,
        manage_perm="camara.sessoes.manage",
        search_fields=("numero", "titulo", "resumo"),
        columns=(("Número", "numero"), ("Ano", "ano"), ("Título", "titulo"), ("Data", "data_documento")),
        order_by=("-data_documento", "-id"),
        enctype=True,
    ),
    "pautas": ModuleSpec(
        key="pautas",
        title="Pautas",
        icon="fa-solid fa-list-check",
        model=Pauta,
        form=PautaForm,
        manage_perm="camara.sessoes.manage",
        search_fields=("numero", "titulo", "descricao"),
        columns=(("Número", "numero"), ("Ano", "ano"), ("Título", "titulo"), ("Data", "data_documento")),
        order_by=("-data_documento", "-id"),
        enctype=True,
    ),
    "noticias": ModuleSpec(
        key="noticias",
        title="Notícias da Câmara",
        icon="fa-solid fa-newspaper",
        model=NoticiaCamara,
        form=NoticiaCamaraForm,
        manage_perm="camara.cms.manage",
        search_fields=("titulo", "resumo", "conteudo"),
        columns=(("Título", "titulo"), ("Categoria", "get_categoria_display"), ("Status", "get_status_display"), ("Publicação", "published_at")),
        order_by=("-published_at", "-id"),
        enctype=True,
    ),
    "agenda": ModuleSpec(
        key="agenda",
        title="Agenda Legislativa",
        icon="fa-solid fa-calendar-days",
        model=AgendaLegislativa,
        form=AgendaLegislativaForm,
        manage_perm="camara.cms.manage",
        search_fields=("titulo", "descricao", "local"),
        columns=(("Título", "titulo"), ("Tipo", "get_tipo_display"), ("Início", "inicio"), ("Local", "local")),
        order_by=("inicio", "id"),
    ),
    "transmissoes": ModuleSpec(
        key="transmissoes",
        title="Transmissões",
        icon="fa-brands fa-youtube",
        model=Transmissao,
        form=TransmissaoForm,
        manage_perm="camara.transmissoes.manage",
        search_fields=("titulo", "canal_url", "live_url"),
        columns=(("Título", "titulo"), ("Status live", "get_status_transmissao_display"), ("Início previsto", "inicio_previsto"), ("Destaque", "destaque_home")),
        order_by=("-inicio_previsto", "-id"),
    ),
    "transparencia": ModuleSpec(
        key="transparencia",
        title="Transparência da Câmara",
        icon="fa-solid fa-scale-balanced",
        model=TransparenciaCamaraItem,
        form=TransparenciaCamaraItemForm,
        manage_perm="camara.transparencia.manage",
        search_fields=("titulo", "descricao", "competencia"),
        columns=(("Título", "titulo"), ("Categoria", "get_categoria_display"), ("Formato", "get_formato_display"), ("Competência", "competencia")),
        order_by=("categoria", "-published_at", "-id"),
        enctype=True,
    ),
    "documentos": ModuleSpec(
        key="documentos",
        title="Documentos Oficiais",
        icon="fa-solid fa-folder-tree",
        model=DocumentoCamara,
        form=DocumentoCamaraForm,
        manage_perm="camara.cms.manage",
        search_fields=("titulo", "descricao", "categoria"),
        columns=(("Título", "titulo"), ("Categoria", "get_categoria_display"), ("Data", "data_documento"), ("Formato", "get_formato_display")),
        order_by=("-data_documento", "-id"),
        enctype=True,
    ),
    "ouvidoria": ModuleSpec(
        key="ouvidoria",
        title="Contato e Ouvidoria",
        icon="fa-solid fa-comments",
        model=CamaraOuvidoriaManifestacao,
        form=CamaraOuvidoriaManifestacaoForm,
        manage_perm="camara.manage",
        search_fields=("protocolo", "assunto", "solicitante_nome", "mensagem"),
        columns=(("Protocolo", "protocolo"), ("Tipo", "get_tipo_display"), ("Assunto", "assunto"), ("Atendimento", "get_status_atendimento_display")),
        order_by=("-created_at", "-id"),
    ),
}


def _spec_or_404(module_key: str) -> ModuleSpec:
    spec = MODULE_SPECS.get((module_key or "").strip().lower())
    if not spec:
        raise Http404("Módulo da Câmara inválido.")
    return spec


def _module_allowed(request: HttpRequest, spec: ModuleSpec, *, manage: bool = False) -> bool:
    perm = spec.manage_perm if manage else "camara.view"
    return can(request.user, perm)


def _apply_form_scope(form, municipio: Municipio):
    for field in form.fields.values():
        qs = getattr(field, "queryset", None)
        if qs is None:
            continue
        model = qs.model
        if hasattr(model, "municipio_id"):
            field.queryset = qs.filter(municipio=municipio).order_by("id")


def _build_rows(spec: ModuleSpec, queryset):
    rows = []
    for obj in queryset:
        values = [_to_text(_value_from_attr(obj, attr)) for _, attr in spec.columns]
        rows.append(
            {
                "values": values,
                "edit_url": reverse("camara:module_update", args=[spec.key, obj.pk]),
                "delete_url": reverse("camara:module_delete", args=[spec.key, obj.pk]),
            }
        )
    return rows


def _module_cards(municipio: Municipio):
    cards = []
    for spec in MODULE_SPECS.values():
        total = spec.model.objects.filter(municipio=municipio).count()
        cards.append(
            {
                "key": spec.key,
                "title": spec.title,
                "icon": spec.icon,
                "count": total,
                "url": reverse("camara:module_list", args=[spec.key]) + _q_municipio(municipio),
            }
        )
    return cards


def _ensure_plan_access(municipio: Municipio):
    if municipio_has_plan_app(municipio, PlanoApp.CAMARA):
        return None
    return HttpResponseForbidden("403 — Portal/App da Câmara indisponível no plano atual.")


@login_required
@require_perm("camara.view")
@require_http_methods(["GET"])
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Selecione um município para acessar a Câmara.")
        return redirect("core:dashboard")
    denied = _ensure_plan_access(municipio)
    if denied:
        return denied

    return render(
        request,
        "camara/index.html",
        {
            "title": "App Câmara Municipal",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": _module_cards(municipio),
            "actions": [
                {
                    "label": "Institucional",
                    "url": reverse("camara:module_list", args=["config"]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-building-columns",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Sessões",
                    "url": reverse("camara:module_list", args=["sessoes"]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-gavel",
                    "variant": "btn-primary",
                },
                {
                    "label": "Proposições",
                    "url": reverse("camara:module_list", args=["proposicoes"]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-file-signature",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Transparência",
                    "url": reverse("camara:module_list", args=["transparencia"]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-scale-balanced",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("camara.view")
@require_http_methods(["GET"])
def module_list(request, module_key: str):
    spec = _spec_or_404(module_key)

    if not _module_allowed(request, spec, manage=False):
        return HttpResponseForbidden("403 — Perfil sem acesso ao módulo da Câmara.")

    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("camara:index")
    denied = _ensure_plan_access(municipio)
    if denied:
        return denied

    q = (request.GET.get("q") or "").strip()
    qs = spec.model.objects.filter(municipio=municipio)
    if q and spec.search_fields:
        condition = Q()
        for field_name in spec.search_fields:
            condition |= Q(**{f"{field_name}__icontains": q})
        qs = qs.filter(condition)

    if spec.order_by:
        qs = qs.order_by(*spec.order_by)

    headers = [label for label, _ in spec.columns]
    rows = _build_rows(spec, qs[:300])

    create_url = reverse("camara:module_create", args=[spec.key]) + _q_municipio(municipio)
    if spec.singleton and qs.exists():
        create_url = reverse("camara:module_update", args=[spec.key, qs.first().pk]) + _q_municipio(municipio)

    return render(
        request,
        "camara/module_list.html",
        {
            "title": spec.title,
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "module": spec,
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "q": q,
            "headers": headers,
            "rows": rows,
            "actions": [
                {
                    "label": "Voltar ao app Câmara",
                    "url": reverse("camara:index") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Novo registro" if not spec.singleton else "Editar configuração",
                    "url": create_url,
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
            ],
        },
    )


@login_required
@require_perm("camara.view")
@require_http_methods(["GET", "POST"])
def module_create(request, module_key: str):
    spec = _spec_or_404(module_key)

    if not _module_allowed(request, spec, manage=True):
        return HttpResponseForbidden("403 — Perfil sem permissão para cadastrar neste módulo da Câmara.")

    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para cadastrar.")
        return redirect(reverse("camara:module_list", args=[spec.key]))
    denied = _ensure_plan_access(municipio)
    if denied:
        return denied

    if spec.singleton:
        existing = spec.model.objects.filter(municipio=municipio).first()
        if existing:
            return redirect(reverse("camara:module_update", args=[spec.key, existing.pk]) + _q_municipio(municipio))

    form = spec.form(request.POST or None, request.FILES or None)
    _apply_form_scope(form, municipio)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.contexto = "camara"
        obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()
        messages.success(request, f"Registro salvo em {spec.title}.")
        return redirect(reverse("camara:module_list", args=[spec.key]) + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Novo registro • {spec.title}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("camara:module_list", args=[spec.key]) + _q_municipio(municipio),
            "submit_label": "Salvar",
            "enctype": "multipart/form-data" if spec.enctype else None,
        },
    )


@login_required
@require_perm("camara.view")
@require_http_methods(["GET", "POST"])
def module_update(request, module_key: str, pk: int):
    spec = _spec_or_404(module_key)

    if not _module_allowed(request, spec, manage=True):
        return HttpResponseForbidden("403 — Perfil sem permissão para editar neste módulo da Câmara.")

    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("camara:index")
    denied = _ensure_plan_access(municipio)
    if denied:
        return denied

    obj = get_object_or_404(spec.model, pk=pk, municipio=municipio)
    form = spec.form(request.POST or None, request.FILES or None, instance=obj)
    _apply_form_scope(form, municipio)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, f"Registro atualizado em {spec.title}.")
        return redirect(reverse("camara:module_list", args=[spec.key]) + _q_municipio(municipio))

    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar • {spec.title}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("camara:module_list", args=[spec.key]) + _q_municipio(municipio),
            "submit_label": "Salvar alterações",
            "enctype": "multipart/form-data" if spec.enctype else None,
        },
    )


@login_required
@require_perm("camara.view")
@require_POST
def module_delete(request, module_key: str, pk: int):
    spec = _spec_or_404(module_key)

    if not _module_allowed(request, spec, manage=True):
        return HttpResponseForbidden("403 — Perfil sem permissão para remover neste módulo da Câmara.")

    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("camara:index")
    denied = _ensure_plan_access(municipio)
    if denied:
        return denied

    obj = get_object_or_404(spec.model, pk=pk, municipio=municipio)
    obj.delete()
    messages.success(request, f"Registro removido de {spec.title}.")
    return redirect(reverse("camara:module_list", args=[spec.key]) + _q_municipio(municipio))
