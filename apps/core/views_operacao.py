from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core.forms_operacao import (
    OperacaoRegistroAnexoForm,
    OperacaoRegistroComentarioForm,
    OperacaoRegistroTagForm,
)
from apps.core.rbac import can
from apps.core.services_registro_operacao import (
    get_entity_spec,
    normalize_entidade,
    normalize_modulo,
    resolve_entity_instance,
    save_registro_anexo,
    save_registro_comentario,
    save_registro_tag,
    user_has_scope_for_municipio,
)


def _safe_next(request, fallback: str = "/sistema/dashboard/") -> str:
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        return next_url
    return fallback


def _resolve_target_from_request(request):
    modulo = normalize_modulo(request.POST.get("modulo") or request.GET.get("modulo"))
    entidade = normalize_entidade(request.POST.get("entidade") or request.GET.get("entidade"))
    entidade_id = (request.POST.get("entidade_id") or request.GET.get("entidade_id") or "").strip()
    if not modulo or not entidade or not entidade_id:
        raise Http404("Registro operacional inválido.")

    spec = get_entity_spec(modulo, entidade)
    if not spec:
        raise Http404("Registro operacional não suportado.")

    target = resolve_entity_instance(modulo, entidade, entidade_id)
    if target is None:
        raise Http404("Entidade não encontrada.")

    municipio = getattr(target, "municipio", None)
    if municipio is None:
        raise Http404("Entidade sem município.")

    if not user_has_scope_for_municipio(request.user, getattr(municipio, "id", None)):
        return None, None, None, None
    return spec, target, municipio, entidade_id


@login_required
@require_POST
def registro_tag_create(request):
    spec, target, municipio, entidade_id = _resolve_target_from_request(request)
    if not municipio:
        return HttpResponseForbidden("403 — Fora do seu escopo.")
    if not can(request.user, spec.manage_perm):
        return HttpResponseForbidden("403 — Sem permissão de gestão.")

    form = OperacaoRegistroTagForm(request.POST)
    if form.is_valid():
        save_registro_tag(
            municipio=municipio,
            modulo=spec.modulo,
            entidade=spec.entidade,
            entidade_id=entidade_id,
            tag=form.cleaned_data["tag"],
            user=request.user,
        )
        messages.success(request, "Tag adicionada com sucesso.")
    else:
        messages.error(request, "Não foi possível adicionar a tag.")
    return redirect(_safe_next(request))


@login_required
@require_POST
def registro_comentario_create(request):
    spec, target, municipio, entidade_id = _resolve_target_from_request(request)
    if not municipio:
        return HttpResponseForbidden("403 — Fora do seu escopo.")
    if not can(request.user, spec.manage_perm):
        return HttpResponseForbidden("403 — Sem permissão de gestão.")

    form = OperacaoRegistroComentarioForm(request.POST)
    if form.is_valid():
        save_registro_comentario(
            municipio=municipio,
            modulo=spec.modulo,
            entidade=spec.entidade,
            entidade_id=entidade_id,
            comentario=form.cleaned_data["comentario"],
            interno=form.cleaned_data["interno"],
            user=request.user,
        )
        messages.success(request, "Comentário registrado.")
    else:
        messages.error(request, "Comentário inválido.")
    return redirect(_safe_next(request))


@login_required
@require_POST
def registro_anexo_create(request):
    spec, target, municipio, entidade_id = _resolve_target_from_request(request)
    if not municipio:
        return HttpResponseForbidden("403 — Fora do seu escopo.")
    if not can(request.user, spec.manage_perm):
        return HttpResponseForbidden("403 — Sem permissão de gestão.")

    form = OperacaoRegistroAnexoForm(request.POST, request.FILES)
    if form.is_valid():
        save_registro_anexo(
            municipio=municipio,
            modulo=spec.modulo,
            entidade=spec.entidade,
            entidade_id=entidade_id,
            arquivo=form.cleaned_data["arquivo"],
            tipo=form.cleaned_data.get("tipo") or "",
            titulo=form.cleaned_data.get("titulo") or "",
            observacao=form.cleaned_data.get("observacao") or "",
            user=request.user,
        )
        messages.success(request, "Anexo enviado com sucesso.")
    else:
        messages.error(request, "Falha ao enviar anexo.")
    return redirect(_safe_next(request))
