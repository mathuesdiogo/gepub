from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table, export_pdf_template
from apps.core.rbac import can, is_admin, scope_filter_alunos, scope_filter_turmas, scope_filter_unidades
from apps.core.services_auditoria import registrar_auditoria
from apps.org.models import Municipio, Unidade

from .forms_beneficios import (
    BeneficioCampanhaAlunoForm,
    BeneficioCampanhaForm,
    BeneficioEditalCriterioForm,
    BeneficioEditalDocumentoForm,
    BeneficioEditalForm,
    BeneficioEditalInscricaoAnaliseForm,
    BeneficioEditalInscricaoForm,
    BeneficioEditalRecursoForm,
    BeneficioEntregaForm,
    BeneficioEntregaItemForm,
    BeneficioRecorrenciaPlanoForm,
    BeneficioTipoForm,
    BeneficioTipoItemForm,
)
from .models import Aluno, Turma
from .models_beneficios import (
    BeneficioCampanha,
    BeneficioCampanhaAluno,
    BeneficioEdital,
    BeneficioEditalCriterio,
    BeneficioEditalDocumento,
    BeneficioEditalInscricao,
    BeneficioEntrega,
    BeneficioEntregaItem,
    BeneficioRecorrenciaCiclo,
    BeneficioRecorrenciaPlano,
    BeneficioTipo,
)
from .services_beneficios import (
    confirmar_entrega,
    estornar_entrega,
    gerar_ciclos_recorrencia,
    recalcular_inscricao_por_criterios,
    registrar_inscricao_com_criterios,
)


def _resolve_municipio(request, *, require_selected: bool = False):
    user = request.user
    if is_admin(user):
        profile = getattr(user, "profile", None)
        if profile and profile.municipio_id:
            municipio = Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
            if municipio:
                return municipio
        municipio_id = (request.GET.get("municipio") or request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            return Municipio.objects.filter(pk=int(municipio_id), ativo=True).first()
        if require_selected:
            return None
        return Municipio.objects.filter(ativo=True).order_by("nome").first()
    profile = getattr(user, "profile", None)
    if profile and profile.municipio_id:
        return Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
    return None


def _municipios_admin(request):
    if not is_admin(request.user):
        return Municipio.objects.none()
    return Municipio.objects.filter(ativo=True).order_by("nome")


def _q_municipio(municipio: Municipio) -> str:
    return f"?municipio={municipio.pk}"


def _scoped_unidades(user, municipio: Municipio):
    return scope_filter_unidades(
        user,
        Unidade.objects.filter(secretaria__municipio=municipio, ativo=True),
    )


def _scoped_alunos(user, municipio: Municipio):
    return scope_filter_alunos(
        user,
        Aluno.objects.filter(matriculas__turma__unidade__secretaria__municipio=municipio).distinct(),
    ).order_by("nome")


@login_required
@require_perm("educacao.view")
def beneficios_index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    entregas = BeneficioEntrega.objects.filter(municipio=municipio)
    campanhas = BeneficioCampanha.objects.filter(municipio=municipio)
    editais = BeneficioEdital.objects.filter(municipio=municipio)
    recorrencias = BeneficioRecorrenciaPlano.objects.filter(municipio=municipio)
    tipos = BeneficioTipo.objects.filter(municipio=municipio)

    return render(
        request,
        "educacao/beneficios/index.html",
        {
            "title": "Benefícios e Entregas",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Tipos ativos", "value": tipos.filter(status=BeneficioTipo.Status.ATIVO).count()},
                {"label": "Campanhas em execução", "value": campanhas.filter(status=BeneficioCampanha.Status.EM_EXECUCAO).count()},
                {"label": "Entregas pendentes", "value": entregas.filter(status=BeneficioEntrega.Status.PENDENTE).count()},
                {"label": "Entregas confirmadas", "value": entregas.filter(status=BeneficioEntrega.Status.ENTREGUE).count()},
                {"label": "Editais ativos", "value": editais.exclude(status=BeneficioEdital.Status.ENCERRADO).count()},
                {"label": "Recorrências ativas", "value": recorrencias.filter(status=BeneficioRecorrenciaPlano.Status.ATIVA).count()},
            ],
            "actions": [
                {
                    "label": "Tipos de Benefícios",
                    "url": reverse("educacao:beneficio_tipo_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-list-check",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Campanhas",
                    "url": reverse("educacao:beneficio_campanha_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-bullhorn",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Entregas",
                    "url": reverse("educacao:beneficio_entrega_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-box-open",
                    "variant": "btn-primary",
                },
                {
                    "label": "Editais",
                    "url": reverse("educacao:beneficio_edital_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-file-circle-check",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Recorrências",
                    "url": reverse("educacao:beneficio_recorrencia_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrows-rotate",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def beneficio_tipo_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    area = (request.GET.get("area") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = BeneficioTipo.objects.filter(municipio=municipio).select_related("secretaria")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(categoria__icontains=q))
    if area:
        qs = qs.filter(area=area)
    if status:
        qs = qs.filter(status=status)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = ["Nome", "Área", "Categoria", "Público", "Periodicidade", "Status", "Secretaria"]
        rows = [
            [
                i.nome,
                i.get_area_display(),
                i.get_categoria_display(),
                i.get_publico_alvo_display(),
                i.get_periodicidade_display(),
                i.get_status_display(),
                i.secretaria.nome if i.secretaria else "-",
            ]
            for i in qs.order_by("nome")
        ]
        if export == "csv":
            return export_csv("beneficios_tipos.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="beneficios_tipos.pdf",
            title="Tipos de benefícios",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Área={area or '-'} | Status={status or '-'}",
        )

    return render(
        request,
        "educacao/beneficios/tipo_list.html",
        {
            "title": "Tipos de Benefícios",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("nome"),
            "q": q,
            "area": area,
            "status": status,
            "area_choices": BeneficioTipo.Area.choices,
            "status_choices": BeneficioTipo.Status.choices,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Novo Tipo",
                    "url": reverse("educacao:beneficio_tipo_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&area={area}&status={status}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "btn--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&area={area}&status={status}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_tipo_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("educacao:beneficios_index")
    form = BeneficioTipoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Tipo de benefício cadastrado.")
        return redirect(reverse("educacao:beneficio_tipo_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo tipo de benefício",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("educacao:beneficio_tipo_list") + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_tipo_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(BeneficioTipo, pk=pk, municipio=municipio)
    form = BeneficioTipoForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tipo de benefício atualizado.")
        return redirect(reverse("educacao:beneficio_tipo_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar tipo • {obj.nome}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("educacao:beneficio_tipo_detail", args=[obj.pk]) + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.view")
def beneficio_tipo_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(BeneficioTipo.objects.prefetch_related("itens"), pk=pk, municipio=municipio)
    form_item = BeneficioTipoItemForm(municipio=municipio)
    return render(
        request,
        "educacao/beneficios/tipo_detail.html",
        {
            "title": f"Composição do benefício • {obj.nome}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "obj": obj,
            "items": obj.itens.order_by("ordem", "id"),
            "form_item": form_item,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:beneficio_tipo_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Editar",
                    "url": reverse("educacao:beneficio_tipo_update", args=[obj.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-pen",
                    "variant": "btn-primary",
                },
            ],
            "municipio": municipio,
        },
    )


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_tipo_item_add(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioTipo, pk=pk, municipio=municipio)
    form = BeneficioTipoItemForm(request.POST, municipio=municipio)
    if form.is_valid():
        item = form.save(commit=False)
        item.beneficio = obj
        item.save()
        messages.success(request, "Item adicionado à composição.")
    else:
        messages.error(request, f"Não foi possível adicionar item: {form.errors.as_text()}")
    return redirect(reverse("educacao:beneficio_tipo_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_tipo_item_remove(request, pk: int, item_id: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioTipo, pk=pk, municipio=municipio)
    item = get_object_or_404(obj.itens, pk=item_id)
    item.delete()
    messages.success(request, "Item removido da composição.")
    return redirect(reverse("educacao:beneficio_tipo_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.view")
def beneficio_campanha_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = BeneficioCampanha.objects.filter(municipio=municipio).select_related("beneficio", "unidade")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(beneficio__nome__icontains=q))
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "educacao/beneficios/campanha_list.html",
        {
            "title": "Campanhas de Distribuição",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "items": qs.order_by("-data_inicio", "-id"),
            "status": status,
            "q": q,
            "status_choices": BeneficioCampanha.Status.choices,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Nova campanha",
                    "url": reverse("educacao:beneficio_campanha_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_campanha_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("educacao:beneficios_index")
    form = BeneficioCampanhaForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Campanha criada.")
        return redirect(reverse("educacao:beneficio_campanha_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova campanha de distribuição",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("educacao:beneficio_campanha_list") + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_campanha_update(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioCampanha, pk=pk, municipio=municipio)
    form = BeneficioCampanhaForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Campanha atualizada.")
        return redirect(reverse("educacao:beneficio_campanha_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar campanha • {obj.nome}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("educacao:beneficio_campanha_detail", args=[obj.pk]) + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.view")
def beneficio_campanha_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioCampanha, pk=pk, municipio=municipio)
    alunos_qs = _scoped_alunos(request.user, municipio)
    turmas_qs = scope_filter_turmas(
        request.user,
        Turma.objects.filter(unidade__secretaria__municipio=municipio, ativo=True).order_by("-ano_letivo", "nome"),
    )
    form_aluno = BeneficioCampanhaAlunoForm(alunos_qs=alunos_qs, turmas_qs=turmas_qs)
    return render(
        request,
        "educacao/beneficios/campanha_detail.html",
        {
            "title": f"Campanha • {obj.nome}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "obj": obj,
            "items_alunos": obj.alunos.select_related("aluno", "turma").order_by("-id"),
            "form_aluno": form_aluno,
            "turmas_qs": turmas_qs,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:beneficio_campanha_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Editar",
                    "url": reverse("educacao:beneficio_campanha_update", args=[obj.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-pen",
                    "variant": "btn-primary",
                },
            ],
            "municipio": municipio,
        },
    )


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_campanha_aluno_add(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioCampanha, pk=pk, municipio=municipio)
    alunos_qs = _scoped_alunos(request.user, municipio)
    turmas_qs = scope_filter_turmas(
        request.user,
        Turma.objects.filter(unidade__secretaria__municipio=municipio, ativo=True),
    )
    form = BeneficioCampanhaAlunoForm(request.POST, alunos_qs=alunos_qs, turmas_qs=turmas_qs)
    if form.is_valid():
        item = form.save(commit=False)
        item.campanha = obj
        item.save()
        messages.success(request, "Aluno incluído na campanha.")
    else:
        messages.error(request, f"Falha ao incluir aluno: {form.errors.as_text()}")
    return redirect(reverse("educacao:beneficio_campanha_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_campanha_gerar_alunos_turma(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioCampanha, pk=pk, municipio=municipio)
    turma_id = (request.POST.get("turma_id") or "").strip()
    if not turma_id.isdigit():
        messages.error(request, "Selecione uma turma válida.")
        return redirect(reverse("educacao:beneficio_campanha_detail", args=[obj.pk]) + _q_municipio(municipio))
    turmas_qs = scope_filter_turmas(
        request.user,
        Turma.objects.filter(unidade__secretaria__municipio=municipio),
    )
    turma = turmas_qs.filter(pk=int(turma_id)).first()
    if not turma:
        messages.error(request, "Turma fora do escopo do usuário.")
        return redirect(reverse("educacao:beneficio_campanha_detail", args=[obj.pk]) + _q_municipio(municipio))
    alunos_ids = list(turma.matriculas.filter(situacao="ATIVA").values_list("aluno_id", flat=True))
    created = 0
    for aluno_id in alunos_ids:
        _, was_created = BeneficioCampanhaAluno.objects.get_or_create(
            campanha=obj,
            aluno_id=aluno_id,
            defaults={"turma": turma, "status": BeneficioCampanhaAluno.Status.SELECIONADO},
        )
        if was_created:
            created += 1
    messages.success(request, f"{created} alunos adicionados da turma {turma.nome}.")
    return redirect(reverse("educacao:beneficio_campanha_detail", args=[obj.pk]) + _q_municipio(municipio))


def _criar_itens_padrao_entrega(entrega: BeneficioEntrega):
    if entrega.itens.exists():
        return
    for comp in entrega.beneficio.itens.filter(ativo=True).order_by("ordem", "id"):
        BeneficioEntregaItem.objects.create(
            entrega=entrega,
            composicao_item=comp,
            item_estoque=comp.item_estoque,
            item_nome=comp.item_nome,
            quantidade_planejada=comp.quantidade,
            quantidade_entregue=comp.quantidade,
            unidade=comp.unidade,
            pendente=False,
            substituido=False,
        )


@login_required
@require_perm("educacao.view")
def beneficio_entrega_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = BeneficioEntrega.objects.filter(municipio=municipio).select_related("aluno", "beneficio", "campanha")
    if q:
        qs = qs.filter(Q(aluno__nome__icontains=q) | Q(beneficio__nome__icontains=q) | Q(local_entrega__icontains=q))
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "educacao/beneficios/entrega_list.html",
        {
            "title": "Entregas de Benefícios",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "items": qs.order_by("-data_hora", "-id"),
            "q": q,
            "status": status,
            "status_choices": BeneficioEntrega.Status.choices,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Nova entrega",
                    "url": reverse("educacao:beneficio_entrega_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_entrega_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("educacao:beneficios_index")
    alunos_qs = _scoped_alunos(request.user, municipio)
    form = BeneficioEntregaForm(request.POST or None, request.FILES or None, municipio=municipio, alunos_qs=alunos_qs)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.responsavel_entrega = request.user
        obj.save()
        _criar_itens_padrao_entrega(obj)
        messages.success(request, "Entrega cadastrada.")
        return redirect(reverse("educacao:beneficio_entrega_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova entrega de benefício",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "enctype": "multipart/form-data",
            "cancel_url": reverse("educacao:beneficio_entrega_list") + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_entrega_update(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEntrega, pk=pk, municipio=municipio)
    alunos_qs = _scoped_alunos(request.user, municipio)
    form = BeneficioEntregaForm(
        request.POST or None,
        request.FILES or None,
        instance=obj,
        municipio=municipio,
        alunos_qs=alunos_qs,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        _criar_itens_padrao_entrega(obj)
        messages.success(request, "Entrega atualizada.")
        return redirect(reverse("educacao:beneficio_entrega_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar entrega #{obj.pk}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "enctype": "multipart/form-data",
            "cancel_url": reverse("educacao:beneficio_entrega_detail", args=[obj.pk]) + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.view")
def beneficio_entrega_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(
        BeneficioEntrega.objects.select_related("aluno", "beneficio", "campanha", "responsavel_entrega"),
        pk=pk,
        municipio=municipio,
    )
    _criar_itens_padrao_entrega(obj)
    form_item = BeneficioEntregaItemForm(entrega=obj, municipio=municipio)
    return render(
        request,
        "educacao/beneficios/entrega_detail.html",
        {
            "title": f"Entrega #{obj.pk}",
            "subtitle": f"{obj.aluno.nome} • {obj.beneficio.nome}",
            "obj": obj,
            "items": obj.itens.select_related("item_estoque", "composicao_item").all(),
            "form_item": form_item,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Recibo PDF",
                    "url": reverse("educacao:beneficio_entrega_recibo_pdf", args=[obj.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Voltar",
                    "url": reverse("educacao:beneficio_entrega_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Editar",
                    "url": reverse("educacao:beneficio_entrega_update", args=[obj.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-pen",
                    "variant": "btn-primary",
                },
            ],
            "municipio": municipio,
        },
    )


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_entrega_item_add(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEntrega, pk=pk, municipio=municipio)
    form = BeneficioEntregaItemForm(request.POST, entrega=obj, municipio=municipio)
    if form.is_valid():
        item = form.save(commit=False)
        item.entrega = obj
        if not (item.item_nome or "").strip() and item.item_estoque_id:
            item.item_nome = item.item_estoque.nome
        item.save()
        messages.success(request, "Item adicionado à entrega.")
    else:
        messages.error(request, f"Falha ao adicionar item: {form.errors.as_text()}")
    return redirect(reverse("educacao:beneficio_entrega_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_entrega_item_remove(request, pk: int, item_id: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEntrega, pk=pk, municipio=municipio)
    item = get_object_or_404(obj.itens, pk=item_id)
    item.delete()
    messages.success(request, "Item removido da entrega.")
    return redirect(reverse("educacao:beneficio_entrega_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_entrega_confirmar(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEntrega, pk=pk, municipio=municipio)
    try:
        confirmar_entrega(entrega=obj, user=request.user)
        messages.success(request, "Entrega confirmada com sucesso.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect(reverse("educacao:beneficio_entrega_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_entrega_estornar(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEntrega, pk=pk, municipio=municipio)
    motivo = (request.POST.get("motivo") or "").strip()
    try:
        estornar_entrega(entrega=obj, user=request.user, motivo=motivo)
        messages.success(request, "Entrega estornada com sucesso.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect(reverse("educacao:beneficio_entrega_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.view")
def beneficio_entrega_recibo_pdf(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEntrega.objects.select_related("aluno", "beneficio", "campanha"), pk=pk, municipio=municipio)
    items = obj.itens.order_by("id")
    return export_pdf_template(
        request,
        filename=f"beneficio_recibo_{obj.pk}.pdf",
        title=f"Recibo de entrega #{obj.pk}",
        template_name="educacao/beneficios/pdf/recibo.html",
        subtitle=f"{municipio.nome}/{municipio.uf}",
        hash_payload=f"{obj.pk}|{obj.aluno_id}|{obj.beneficio_id}|{obj.status}",
        context={"entrega": obj, "items": items},
    )


@login_required
@require_perm("educacao.view")
def beneficio_edital_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = BeneficioEdital.objects.filter(municipio=municipio).select_related("beneficio")
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(numero_ano__icontains=q))
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "educacao/beneficios/edital_list.html",
        {
            "title": "Editais & Seleções",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "items": qs.order_by("-criado_em", "-id"),
            "status": status,
            "q": q,
            "status_choices": BeneficioEdital.Status.choices,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Novo edital",
                    "url": reverse("educacao:beneficio_edital_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_edital_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("educacao:beneficios_index")
    form = BeneficioEditalForm(request.POST or None, request.FILES or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        form.save_m2m()
        messages.success(request, "Edital criado.")
        return redirect(reverse("educacao:beneficio_edital_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo edital",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "enctype": "multipart/form-data",
            "cancel_url": reverse("educacao:beneficio_edital_list") + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_edital_update(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEdital, pk=pk, municipio=municipio)
    form = BeneficioEditalForm(request.POST or None, request.FILES or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Edital atualizado.")
        return redirect(reverse("educacao:beneficio_edital_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar edital • {obj.numero_ano}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "enctype": "multipart/form-data",
            "cancel_url": reverse("educacao:beneficio_edital_detail", args=[obj.pk]) + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.view")
def beneficio_edital_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(
        BeneficioEdital.objects.prefetch_related(
            "criterios",
            "documentos",
            "inscricoes",
            "inscricoes__documentos",
        ),
        pk=pk,
        municipio=municipio,
    )
    alunos_qs = _scoped_alunos(request.user, municipio)
    form_criterio = BeneficioEditalCriterioForm()
    form_documento = BeneficioEditalDocumentoForm()
    form_inscricao = BeneficioEditalInscricaoForm(
        municipio=municipio,
        alunos_qs=alunos_qs,
        edital=obj,
        initial={"edital": obj},
    )
    form_recurso = BeneficioEditalRecursoForm()
    return render(
        request,
        "educacao/beneficios/edital_detail.html",
        {
            "title": f"Edital • {obj.numero_ano}",
            "subtitle": obj.titulo,
            "obj": obj,
            "inscricoes": obj.inscricoes.select_related("aluno", "escola", "turma").prefetch_related("documentos").order_by("-id"),
            "form_criterio": form_criterio,
            "form_documento": form_documento,
            "form_inscricao": form_inscricao,
            "form_recurso": form_recurso,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:beneficio_edital_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Editar",
                    "url": reverse("educacao:beneficio_edital_update", args=[obj.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-pen",
                    "variant": "btn-primary",
                },
            ],
            "municipio": municipio,
        },
    )


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_edital_criterio_add(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEdital, pk=pk, municipio=municipio)
    form = BeneficioEditalCriterioForm(request.POST)
    if form.is_valid():
        criterio = form.save(commit=False)
        criterio.edital = obj
        criterio.save()
        messages.success(request, "Critério adicionado.")
    else:
        messages.error(request, f"Falha ao adicionar critério: {form.errors.as_text()}")
    return redirect(reverse("educacao:beneficio_edital_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_edital_documento_add(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEdital, pk=pk, municipio=municipio)
    form = BeneficioEditalDocumentoForm(request.POST)
    if form.is_valid():
        documento = form.save(commit=False)
        documento.edital = obj
        documento.save()
        messages.success(request, "Documento obrigatório adicionado.")
    else:
        messages.error(request, f"Falha ao adicionar documento: {form.errors.as_text()}")
    return redirect(reverse("educacao:beneficio_edital_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_edital_inscricao_add(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(BeneficioEdital, pk=pk, municipio=municipio)
    alunos_qs = _scoped_alunos(request.user, municipio)
    form = BeneficioEditalInscricaoForm(
        request.POST,
        request.FILES,
        municipio=municipio,
        alunos_qs=alunos_qs,
        edital=obj,
    )
    if form.is_valid():
        try:
            inscricao, resumo = registrar_inscricao_com_criterios(
                edital=obj,
                aluno=form.cleaned_data["aluno"],
                escola=form.cleaned_data.get("escola"),
                turma=form.cleaned_data.get("turma"),
                justificativa=form.cleaned_data.get("justificativa") or "",
                usar_documentos_cadastro=bool(form.cleaned_data.get("usar_documentos_cadastro")),
                respostas_criterios=form.get_respostas_criterios(),
                uploads_documentos=form.get_uploads_documentos(),
                uploads_criterios=form.get_uploads_criterios(),
                user=request.user,
            )
        except Exception as exc:
            messages.error(request, f"Falha ao processar inscrição: {exc}")
            return redirect(reverse("educacao:beneficio_edital_detail", args=[obj.pk]) + _q_municipio(municipio))

        pendencias = resumo.get("pendencias_documentos") or []
        status_txt = inscricao.get_status_display()
        if pendencias:
            messages.warning(
                request,
                f"Inscrição #{inscricao.pk} processada com pendências documentais ({len(pendencias)}). "
                f"Status: {status_txt}.",
            )
        else:
            messages.success(
                request,
                f"Inscrição #{inscricao.pk} registrada com pontuação {inscricao.pontuacao} e status {status_txt}.",
            )
    else:
        messages.error(request, f"Falha ao registrar inscrição: {form.errors.as_text()}")
    return redirect(reverse("educacao:beneficio_edital_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.view")
def beneficio_edital_inscricao_detail(request, pk: int, inscricao_id: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    edital = get_object_or_404(BeneficioEdital, pk=pk, municipio=municipio)
    inscricao = get_object_or_404(
        BeneficioEditalInscricao.objects.select_related("aluno", "escola", "turma", "criado_por", "atualizado_por").prefetch_related("documentos", "recursos"),
        pk=inscricao_id,
        edital=edital,
    )
    form_analise = BeneficioEditalInscricaoAnaliseForm(instance=inscricao)
    dados_json = inscricao.dados_json or {}

    return render(
        request,
        "educacao/beneficios/inscricao_detail.html",
        {
            "title": f"Inscrição #{inscricao.pk}",
            "subtitle": f"{inscricao.aluno.nome} • {edital.numero_ano}",
            "municipio": municipio,
            "edital": edital,
            "inscricao": inscricao,
            "dados_json": dados_json,
            "snapshot": dados_json.get("snapshot") or {},
            "avaliacao": dados_json.get("avaliacao") or {},
            "criterios": dados_json.get("criterios") or [],
            "requisitos": dados_json.get("requisitos") or [],
            "can_manage": can(request.user, "educacao.manage"),
            "form_analise": form_analise,
            "actions": [
                {
                    "label": "Voltar ao edital",
                    "url": reverse("educacao:beneficio_edital_detail", args=[edital.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_edital_inscricao_reprocessar(request, pk: int, inscricao_id: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    edital = get_object_or_404(BeneficioEdital, pk=pk, municipio=municipio)
    inscricao = get_object_or_404(BeneficioEditalInscricao, pk=inscricao_id, edital=edital)
    resumo = recalcular_inscricao_por_criterios(inscricao=inscricao, user=request.user)
    pendencias = resumo.get("pendencias_documentos") or []
    if pendencias:
        messages.warning(
            request,
            f"Inscrição reprocessada. Pontuação {resumo['pontuacao_total']} • "
            f"Status {inscricao.get_status_display()} • Pendências {len(pendencias)}.",
        )
    else:
        messages.success(
            request,
            f"Inscrição reprocessada com pontuação {resumo['pontuacao_total']} "
            f"e status {inscricao.get_status_display()}.",
        )
    return redirect(
        reverse("educacao:beneficio_edital_inscricao_detail", args=[edital.pk, inscricao.pk]) + _q_municipio(municipio)
    )


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_edital_inscricao_analisar(request, pk: int, inscricao_id: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    edital = get_object_or_404(BeneficioEdital, pk=pk, municipio=municipio)
    inscricao = get_object_or_404(BeneficioEditalInscricao, pk=inscricao_id, edital=edital)
    form = BeneficioEditalInscricaoAnaliseForm(request.POST, instance=inscricao)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.atualizado_por = request.user
        obj.save(update_fields=["status", "pontuacao", "justificativa", "atualizado_por", "atualizado_em"])
        registrar_auditoria(
            municipio=municipio,
            modulo="EDUCACAO",
            evento="BENEFICIO_EDITAL_INSCRICAO_ANALISADA",
            entidade="BeneficioEditalInscricao",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"status": obj.status, "pontuacao": str(obj.pontuacao)},
        )
        messages.success(request, "Análise da inscrição atualizada.")
    else:
        messages.error(request, f"Falha ao atualizar análise: {form.errors.as_text()}")
    return redirect(
        reverse("educacao:beneficio_edital_inscricao_detail", args=[edital.pk, inscricao.pk]) + _q_municipio(municipio)
    )


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_edital_publicar(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioEdital, pk=pk, municipio=municipio)
    if obj.status == BeneficioEdital.Status.RASCUNHO:
        obj.status = BeneficioEdital.Status.PUBLICADO
        obj.save(update_fields=["status", "atualizado_em"])
        registrar_auditoria(
            municipio=municipio,
            modulo="EDUCACAO",
            evento="BENEFICIO_EDITAL_PUBLICADO",
            entidade="BeneficioEdital",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"status": obj.status},
        )
        messages.success(request, "Edital publicado.")
    else:
        messages.warning(request, "Apenas edital em rascunho pode ser publicado.")
    return redirect(reverse("educacao:beneficio_edital_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.view")
def beneficio_recorrencia_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = BeneficioRecorrenciaPlano.objects.filter(municipio=municipio).select_related("aluno", "beneficio")
    if q:
        qs = qs.filter(Q(aluno__nome__icontains=q) | Q(beneficio__nome__icontains=q))
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "educacao/beneficios/recorrencia_list.html",
        {
            "title": "Recorrências",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "items": qs.order_by("-id"),
            "q": q,
            "status": status,
            "status_choices": BeneficioRecorrenciaPlano.Status.choices,
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Novo plano",
                    "url": reverse("educacao:beneficio_recorrencia_create") + _q_municipio(municipio),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_recorrencia_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return redirect("educacao:beneficios_index")
    alunos_qs = _scoped_alunos(request.user, municipio)
    form = BeneficioRecorrenciaPlanoForm(request.POST or None, municipio=municipio, alunos_qs=alunos_qs)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        if obj.geracao_automatica:
            gerar_ciclos_recorrencia(plano=obj)
        messages.success(request, "Plano de recorrência criado.")
        return redirect(reverse("educacao:beneficio_recorrencia_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo plano de recorrência",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("educacao:beneficio_recorrencia_list") + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.manage")
def beneficio_recorrencia_update(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioRecorrenciaPlano, pk=pk, municipio=municipio)
    alunos_qs = _scoped_alunos(request.user, municipio)
    form = BeneficioRecorrenciaPlanoForm(request.POST or None, instance=obj, municipio=municipio, alunos_qs=alunos_qs)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Plano de recorrência atualizado.")
        return redirect(reverse("educacao:beneficio_recorrencia_detail", args=[obj.pk]) + _q_municipio(municipio))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar recorrência #{obj.pk}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "form": form,
            "cancel_url": reverse("educacao:beneficio_recorrencia_detail", args=[obj.pk]) + _q_municipio(municipio),
            "submit_label": "Salvar",
        },
    )


@login_required
@require_perm("educacao.view")
def beneficio_recorrencia_detail(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(
        BeneficioRecorrenciaPlano.objects.select_related("aluno", "beneficio", "inscricao"),
        pk=pk,
        municipio=municipio,
    )
    return render(
        request,
        "educacao/beneficios/recorrencia_detail.html",
        {
            "title": f"Recorrência #{obj.pk}",
            "subtitle": f"{obj.aluno.nome} • {obj.beneficio.nome}",
            "obj": obj,
            "ciclos": obj.ciclos.order_by("numero"),
            "can_manage": can(request.user, "educacao.manage"),
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:beneficio_recorrencia_list") + _q_municipio(municipio),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Editar",
                    "url": reverse("educacao:beneficio_recorrencia_update", args=[obj.pk]) + _q_municipio(municipio),
                    "icon": "fa-solid fa-pen",
                    "variant": "btn-primary",
                },
            ],
            "municipio": municipio,
        },
    )


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_recorrencia_gerar_ciclos(request, pk: int):
    municipio = _resolve_municipio(request)
    obj = get_object_or_404(BeneficioRecorrenciaPlano, pk=pk, municipio=municipio)
    force = (request.POST.get("force") or "").strip() == "1"
    created = gerar_ciclos_recorrencia(plano=obj, force=force)
    if created:
        messages.success(request, f"{created} ciclos gerados.")
    else:
        messages.warning(request, "Nenhum ciclo gerado (já existiam ciclos para este plano).")
    return redirect(reverse("educacao:beneficio_recorrencia_detail", args=[obj.pk]) + _q_municipio(municipio))


@login_required
@require_perm("educacao.manage")
@require_POST
def beneficio_recorrencia_executar_ciclo(request, pk: int, ciclo_id: int):
    municipio = _resolve_municipio(request)
    plano = get_object_or_404(BeneficioRecorrenciaPlano, pk=pk, municipio=municipio)
    ciclo = get_object_or_404(BeneficioRecorrenciaCiclo, pk=ciclo_id, plano=plano)

    if ciclo.entrega_id:
        messages.warning(request, "Este ciclo já possui entrega vinculada.")
        return redirect(reverse("educacao:beneficio_recorrencia_detail", args=[plano.pk]) + _q_municipio(municipio))

    entrega = BeneficioEntrega.objects.create(
        municipio=municipio,
        secretaria=plano.secretaria,
        unidade=plano.unidade,
        area=plano.area,
        aluno=plano.aluno,
        beneficio=plano.beneficio,
        plano_recorrencia=plano,
        ciclo_recorrencia=ciclo,
        data_hora=timezone.now(),
        responsavel_entrega=request.user,
        status=BeneficioEntrega.Status.PENDENTE,
        observacao=f"Entrega gerada a partir da recorrência #{plano.pk}, ciclo {ciclo.numero}.",
    )
    _criar_itens_padrao_entrega(entrega)
    ciclo.status = BeneficioRecorrenciaCiclo.Status.SEPARADA
    ciclo.entrega = entrega
    ciclo.responsavel_confirmacao = request.user
    ciclo.save(update_fields=["status", "entrega", "responsavel_confirmacao", "atualizado_em"])
    messages.success(request, f"Entrega #{entrega.pk} criada para o ciclo {ciclo.numero}.")
    return redirect(reverse("educacao:beneficio_entrega_detail", args=[entrega.pk]) + _q_municipio(municipio))
