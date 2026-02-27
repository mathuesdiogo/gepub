from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade

from .forms import BloqueioAgendaSaudeForm, FilaEsperaSaudeForm, GradeAgendaSaudeForm
from .models import BloqueioAgendaSaude, FilaEsperaSaude, GradeAgendaSaude, ProfissionalSaude


def _scoped_unidades(user):
    return scope_filter_unidades(user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome"))


def _scoped_profissionais(unidades_qs):
    return ProfissionalSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True), ativo=True).order_by("nome")


@login_required
@require_perm("saude.view")
def grade_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = GradeAgendaSaude.objects.select_related("unidade", "profissional", "especialidade", "sala").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if q:
        qs = qs.filter(
            Q(profissional__nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(especialidade__nome__icontains=q)
        )

    paginator = Paginator(qs.order_by("profissional__nome", "dia_semana", "inicio"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")

    headers = [
        {"label": "Profissional"},
        {"label": "Dia/Horário"},
        {"label": "Unidade"},
        {"label": "Especialidade"},
        {"label": "Ativo", "width": "90px"},
    ]
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.profissional.nome, "url": reverse("saude:grade_detail", args=[obj.pk])},
                    {"text": f"{obj.get_dia_semana_display()} {obj.inicio:%H:%M}-{obj.fim:%H:%M}"},
                    {"text": obj.unidade.nome},
                    {"text": obj.especialidade.nome if obj.especialidade_id else "—"},
                    {"text": "Sim" if obj.ativo else "Não"},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:grade_update", args=[obj.pk]) if can_manage else "",
            }
        )

    actions = []
    if can_manage:
        actions.append(
            {"label": "Nova Grade", "url": reverse("saude:grade_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"}
        )

    return render(
        request,
        "saude/grade_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:grade_list"),
            "clear_url": reverse("saude:grade_list"),
            "has_filters": False,
        },
    )


@login_required
@require_perm("saude.manage")
def grade_create(request):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)
    if request.method == "POST":
        form = GradeAgendaSaudeForm(request.POST, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            if not profissionais_qs.filter(pk=obj.profissional_id).exists():
                messages.error(request, "Profissional fora do seu escopo.")
                return redirect("saude:grade_create")
            if obj.profissional.unidade_id != obj.unidade_id:
                messages.error(request, "O profissional selecionado não pertence à unidade escolhida.")
                return redirect("saude:grade_create")
            obj.save()
            messages.success(request, "Grade criada com sucesso.")
            return redirect("saude:grade_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = GradeAgendaSaudeForm(unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
    return render(
        request,
        "saude/grade_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("saude:grade_list"),
            "submit_label": "Salvar",
            "action_url": reverse("saude:grade_create"),
        },
    )


@login_required
@require_perm("saude.manage")
def grade_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)
    obj = get_object_or_404(
        GradeAgendaSaude.objects.select_related("unidade", "profissional").filter(
            unidade_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )

    if request.method == "POST":
        form = GradeAgendaSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj2 = form.save(commit=False)
            if not profissionais_qs.filter(pk=obj2.profissional_id).exists():
                messages.error(request, "Profissional fora do seu escopo.")
                return redirect("saude:grade_update", pk=obj.pk)
            if obj2.profissional.unidade_id != obj2.unidade_id:
                messages.error(request, "O profissional selecionado não pertence à unidade escolhida.")
                return redirect("saude:grade_update", pk=obj.pk)
            obj2.save()
            messages.success(request, "Grade atualizada com sucesso.")
            return redirect("saude:grade_detail", pk=obj2.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = GradeAgendaSaudeForm(instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(
        request,
        "saude/grade_form.html",
        {
            "form": form,
            "mode": "update",
            "obj": obj,
            "cancel_url": reverse("saude:grade_detail", args=[obj.pk]),
            "submit_label": "Salvar",
            "action_url": reverse("saude:grade_update", args=[obj.pk]),
        },
    )


@login_required
@require_perm("saude.view")
def grade_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(
        GradeAgendaSaude.objects.select_related("unidade", "profissional", "sala", "especialidade").filter(
            unidade_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )
    can_manage = can(request.user, "saude.manage")
    actions = [{"label": "Voltar", "url": reverse("saude:grade_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:grade_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Profissional", "value": obj.profissional.nome},
        {"label": "Unidade", "value": obj.unidade.nome},
        {"label": "Especialidade", "value": obj.especialidade.nome if obj.especialidade_id else "—"},
        {"label": "Sala", "value": obj.sala.nome if obj.sala_id else "—"},
        {"label": "Dia da Semana", "value": obj.get_dia_semana_display()},
        {"label": "Horário", "value": f"{obj.inicio:%H:%M} - {obj.fim:%H:%M}"},
        {"label": "Duração", "value": f"{obj.duracao_minutos} min"},
        {"label": "Intervalo", "value": f"{obj.intervalo_minutos} min"},
    ]
    pills = [{"label": "Ativo", "value": "Sim" if obj.ativo else "Não", "variant": "info" if obj.ativo else "warning"}]
    return render(request, "saude/grade_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def bloqueio_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = BloqueioAgendaSaude.objects.select_related("unidade", "profissional", "sala", "criado_por").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if q:
        qs = qs.filter(Q(motivo__icontains=q) | Q(unidade__nome__icontains=q) | Q(profissional__nome__icontains=q))

    paginator = Paginator(qs.order_by("-inicio", "-id"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append(
            {
                "label": "Novo Bloqueio",
                "url": reverse("saude:bloqueio_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    headers = [
        {"label": "Período"},
        {"label": "Unidade"},
        {"label": "Profissional"},
        {"label": "Motivo"},
    ]
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": f"{obj.inicio:%d/%m/%Y %H:%M} - {obj.fim:%d/%m/%Y %H:%M}", "url": reverse("saude:bloqueio_detail", args=[obj.pk])},
                    {"text": obj.unidade.nome},
                    {"text": obj.profissional.nome if obj.profissional_id else "—"},
                    {"text": obj.motivo},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:bloqueio_update", args=[obj.pk]) if can_manage else "",
            }
        )

    return render(
        request,
        "saude/bloqueio_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:bloqueio_list"),
            "clear_url": reverse("saude:bloqueio_list"),
            "has_filters": False,
        },
    )


@login_required
@require_perm("saude.manage")
def bloqueio_create(request):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)
    if request.method == "POST":
        form = BloqueioAgendaSaudeForm(request.POST, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            obj.save()
            messages.success(request, "Bloqueio criado com sucesso.")
            return redirect("saude:bloqueio_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = BloqueioAgendaSaudeForm(unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(
        request,
        "saude/bloqueio_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("saude:bloqueio_list"),
            "submit_label": "Salvar",
            "action_url": reverse("saude:bloqueio_create"),
        },
    )


@login_required
@require_perm("saude.manage")
def bloqueio_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)
    obj = get_object_or_404(
        BloqueioAgendaSaude.objects.select_related("unidade", "profissional").filter(
            unidade_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )

    if request.method == "POST":
        form = BloqueioAgendaSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            form.save()
            messages.success(request, "Bloqueio atualizado com sucesso.")
            return redirect("saude:bloqueio_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = BloqueioAgendaSaudeForm(instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)

    return render(
        request,
        "saude/bloqueio_form.html",
        {
            "form": form,
            "mode": "update",
            "obj": obj,
            "cancel_url": reverse("saude:bloqueio_detail", args=[obj.pk]),
            "submit_label": "Salvar",
            "action_url": reverse("saude:bloqueio_update", args=[obj.pk]),
        },
    )


@login_required
@require_perm("saude.view")
def bloqueio_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(
        BloqueioAgendaSaude.objects.select_related("unidade", "profissional", "sala", "criado_por").filter(
            unidade_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )
    can_manage = can(request.user, "saude.manage")
    actions = [{"label": "Voltar", "url": reverse("saude:bloqueio_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:bloqueio_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Período", "value": f"{obj.inicio:%d/%m/%Y %H:%M} - {obj.fim:%d/%m/%Y %H:%M}"},
        {"label": "Unidade", "value": obj.unidade.nome},
        {"label": "Profissional", "value": obj.profissional.nome if obj.profissional_id else "—"},
        {"label": "Sala", "value": obj.sala.nome if obj.sala_id else "—"},
        {"label": "Motivo", "value": obj.motivo},
        {"label": "Criado por", "value": obj.criado_por.get_username()},
    ]
    pills = []
    return render(request, "saude/bloqueio_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def fila_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = FilaEsperaSaude.objects.select_related("unidade", "especialidade", "aluno").filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if q:
        qs = qs.filter(Q(paciente_nome__icontains=q) | Q(paciente_contato__icontains=q) | Q(unidade__nome__icontains=q))
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs.order_by("-criado_em", "-id"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append(
            {"label": "Nova Entrada", "url": reverse("saude:fila_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"}
        )

    headers = [
        {"label": "Paciente"},
        {"label": "Unidade"},
        {"label": "Especialidade"},
        {"label": "Prioridade"},
        {"label": "Status"},
    ]
    rows = []
    for obj in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": obj.paciente_nome, "url": reverse("saude:fila_detail", args=[obj.pk])},
                    {"text": obj.unidade.nome},
                    {"text": obj.especialidade.nome if obj.especialidade_id else "—"},
                    {"text": obj.get_prioridade_display()},
                    {"text": obj.get_status_display()},
                ],
                "can_edit": bool(can_manage),
                "edit_url": reverse("saude:fila_update", args=[obj.pk]) if can_manage else "",
            }
        )

    extra_filters = """
      <div class=\"filter-bar__field\">
        <label class=\"small\">Status</label>
        <select name=\"status\">
          <option value=\"\">Todos</option>
    """
    for k, v in FilaEsperaSaude.Status.choices:
        selected = "selected" if status == k else ""
        extra_filters += f"<option value=\"{k}\" {selected}>{v}</option>"
    extra_filters += """
        </select>
      </div>
    """

    return render(
        request,
        "saude/fila_list.html",
        {
            "q": q,
            "status": status,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:fila_list"),
            "clear_url": reverse("saude:fila_list"),
            "has_filters": bool(status),
            "extra_filters": extra_filters,
        },
    )


@login_required
@require_perm("saude.manage")
def fila_create(request):
    unidades_qs = _scoped_unidades(request.user)
    if request.method == "POST":
        form = FilaEsperaSaudeForm(request.POST, unidades_qs=unidades_qs)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Entrada de fila criada com sucesso.")
            return redirect("saude:fila_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = FilaEsperaSaudeForm(unidades_qs=unidades_qs)
    return render(
        request,
        "saude/fila_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("saude:fila_list"),
            "submit_label": "Salvar",
            "action_url": reverse("saude:fila_create"),
        },
    )


@login_required
@require_perm("saude.manage")
def fila_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(
        FilaEsperaSaude.objects.select_related("unidade").filter(unidade_id__in=unidades_qs.values_list("id", flat=True)),
        pk=pk,
    )
    if request.method == "POST":
        form = FilaEsperaSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs)
        if form.is_valid():
            obj2 = form.save(commit=False)
            if obj2.status == FilaEsperaSaude.Status.CHAMADO and not obj2.chamado_em:
                from django.utils import timezone

                obj2.chamado_em = timezone.now()
            obj2.save()
            messages.success(request, "Entrada de fila atualizada com sucesso.")
            return redirect("saude:fila_detail", pk=obj2.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = FilaEsperaSaudeForm(instance=obj, unidades_qs=unidades_qs)
    return render(
        request,
        "saude/fila_form.html",
        {
            "form": form,
            "mode": "update",
            "obj": obj,
            "cancel_url": reverse("saude:fila_detail", args=[obj.pk]),
            "submit_label": "Salvar",
            "action_url": reverse("saude:fila_update", args=[obj.pk]),
        },
    )


@login_required
@require_perm("saude.view")
def fila_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(
        FilaEsperaSaude.objects.select_related("unidade", "especialidade", "aluno").filter(
            unidade_id__in=unidades_qs.values_list("id", flat=True)
        ),
        pk=pk,
    )
    can_manage = can(request.user, "saude.manage")
    actions = [{"label": "Voltar", "url": reverse("saude:fila_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can_manage:
        actions.append({"label": "Editar", "url": reverse("saude:fila_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})

    fields = [
        {"label": "Paciente", "value": obj.paciente_nome},
        {"label": "Contato", "value": obj.paciente_contato or "—"},
        {"label": "Aluno vinculado", "value": obj.aluno.nome if obj.aluno_id else "—"},
        {"label": "Unidade", "value": obj.unidade.nome},
        {"label": "Especialidade", "value": obj.especialidade.nome if obj.especialidade_id else "—"},
        {"label": "Observações", "value": obj.observacoes or "—"},
        {"label": "Criado em", "value": obj.criado_em.strftime("%d/%m/%Y %H:%M")},
    ]
    pills = [
        {"label": "Prioridade", "value": obj.get_prioridade_display(), "variant": "warning"},
        {"label": "Status", "value": obj.get_status_display(), "variant": "info"},
    ]
    return render(request, "saude/fila_detail.html", {"obj": obj, "fields": fields, "pills": pills, "actions": actions})
