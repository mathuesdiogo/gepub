from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_unidades
from apps.org.models import Unidade

from .forms import (
    CheckInSaudeForm,
    CidSaudeForm,
    DispensacaoSaudeForm,
    ExameColetaSaudeForm,
    InternacaoRegistroSaudeForm,
    InternacaoSaudeForm,
    MedicamentoUsoContinuoSaudeForm,
    PacienteSaudeForm,
    ProgramaSaudeForm,
)
from .models import (
    CheckInSaude,
    CidSaude,
    DispensacaoSaude,
    ExameColetaSaude,
    InternacaoSaude,
    MedicamentoUsoContinuoSaude,
    PacienteSaude,
    ProfissionalSaude,
    ProgramaSaude,
)


def _scoped_unidades(user):
    return scope_filter_unidades(user, Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE).order_by("nome"))


def _scoped_profissionais(unidades_qs):
    return ProfissionalSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True), ativo=True).order_by("nome")


@login_required
@require_perm("saude.view")
def cid_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = CidSaude.objects.all()
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descricao__icontains=q))
    page_obj = Paginator(qs.order_by("codigo"), 15).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Novo CID", "url": reverse("saude:cid_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
    headers = [{"label": "Código"}, {"label": "Descrição"}, {"label": "Ativo", "width": "90px"}]
    rows = [
        {
            "cells": [
                {"text": obj.codigo, "url": reverse("saude:cid_detail", args=[obj.pk])},
                {"text": obj.descricao},
                {"text": "Sim" if obj.ativo else "Não"},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:cid_update", args=[obj.pk]) if can_manage else "",
        }
        for obj in page_obj
    ]
    return render(
        request,
        "saude/generic_list.html",
        {
            "title": "CID",
            "subtitle": "Tabela clínica de classificação diagnóstica",
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("saude:cid_list"),
            "clear_url": reverse("saude:cid_list"),
            "has_filters": bool(q),
            "empty_title": "Nenhum CID encontrado",
            "empty_text": "Cadastre o primeiro CID.",
        },
    )


@login_required
@require_perm("saude.manage")
def cid_create(request):
    if request.method == "POST":
        form = CidSaudeForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "CID cadastrado com sucesso.")
            return redirect("saude:cid_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = CidSaudeForm()
    return render(request, "saude/generic_form.html", {"title": "Novo CID", "subtitle": "Cadastro clínico", "form": form, "cancel_url": reverse("saude:cid_list"), "submit_label": "Salvar", "action_url": reverse("saude:cid_create")})


@login_required
@require_perm("saude.manage")
def cid_update(request, pk: int):
    obj = get_object_or_404(CidSaude, pk=pk)
    if request.method == "POST":
        form = CidSaudeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "CID atualizado com sucesso.")
            return redirect("saude:cid_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = CidSaudeForm(instance=obj)
    return render(request, "saude/generic_form.html", {"title": "Editar CID", "subtitle": obj.codigo, "form": form, "cancel_url": reverse("saude:cid_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:cid_update", args=[obj.pk])})


@login_required
@require_perm("saude.view")
def cid_detail(request, pk: int):
    obj = get_object_or_404(CidSaude, pk=pk)
    actions = [{"label": "Voltar", "url": reverse("saude:cid_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:cid_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [{"label": "Código", "value": obj.codigo}, {"label": "Descrição", "value": obj.descricao}]
    pills = [{"label": "Ativo", "value": "Sim" if obj.ativo else "Não", "variant": "info"}]
    return render(request, "saude/generic_detail.html", {"title": f"CID {obj.codigo}", "subtitle": obj.descricao, "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def programa_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = ProgramaSaude.objects.all()
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(tipo__icontains=q))
    page_obj = Paginator(qs.order_by("nome"), 15).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Novo Programa/Convênio", "url": reverse("saude:programa_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
    headers = [{"label": "Nome"}, {"label": "Tipo"}, {"label": "Ativo", "width": "90px"}]
    rows = [
        {
            "cells": [
                {"text": obj.nome, "url": reverse("saude:programa_detail", args=[obj.pk])},
                {"text": obj.get_tipo_display()},
                {"text": "Sim" if obj.ativo else "Não"},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:programa_update", args=[obj.pk]) if can_manage else "",
        }
        for obj in page_obj
    ]
    return render(request, "saude/generic_list.html", {"title": "Programas e Convênios", "subtitle": "Cadastros administrativos de cobertura e programas", "q": q, "page_obj": page_obj, "actions": actions, "headers": headers, "rows": rows, "action_url": reverse("saude:programa_list"), "clear_url": reverse("saude:programa_list"), "has_filters": bool(q), "empty_title": "Nenhum programa encontrado", "empty_text": "Cadastre o primeiro programa ou convênio."})


@login_required
@require_perm("saude.manage")
def programa_create(request):
    if request.method == "POST":
        form = ProgramaSaudeForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Programa/convênio cadastrado.")
            return redirect("saude:programa_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ProgramaSaudeForm()
    return render(request, "saude/generic_form.html", {"title": "Novo Programa/Convênio", "subtitle": "Cadastro administrativo", "form": form, "cancel_url": reverse("saude:programa_list"), "submit_label": "Salvar", "action_url": reverse("saude:programa_create")})


@login_required
@require_perm("saude.manage")
def programa_update(request, pk: int):
    obj = get_object_or_404(ProgramaSaude, pk=pk)
    if request.method == "POST":
        form = ProgramaSaudeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Programa/convênio atualizado.")
            return redirect("saude:programa_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ProgramaSaudeForm(instance=obj)
    return render(request, "saude/generic_form.html", {"title": "Editar Programa/Convênio", "subtitle": obj.nome, "form": form, "cancel_url": reverse("saude:programa_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:programa_update", args=[obj.pk])})


@login_required
@require_perm("saude.view")
def programa_detail(request, pk: int):
    obj = get_object_or_404(ProgramaSaude, pk=pk)
    actions = [{"label": "Voltar", "url": reverse("saude:programa_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:programa_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [{"label": "Nome", "value": obj.nome}, {"label": "Tipo", "value": obj.get_tipo_display()}]
    pills = [{"label": "Ativo", "value": "Sim" if obj.ativo else "Não", "variant": "info"}]
    return render(request, "saude/generic_detail.html", {"title": obj.nome, "subtitle": "Programa/Convênio", "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def paciente_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = PacienteSaude.objects.select_related("unidade_referencia", "programa").filter(
        unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)
    )
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(cartao_sus__icontains=q))
    page_obj = Paginator(qs.order_by("nome"), 15).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Novo Paciente", "url": reverse("saude:paciente_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
    headers = [{"label": "Paciente"}, {"label": "Unidade"}, {"label": "Programa"}, {"label": "CPF"}, {"label": "Ativo", "width": "90px"}]
    rows = [
        {
            "cells": [
                {"text": obj.nome, "url": reverse("saude:paciente_detail", args=[obj.pk])},
                {"text": obj.unidade_referencia.nome},
                {"text": obj.programa.nome if obj.programa_id else "—"},
                {"text": obj.cpf or "—"},
                {"text": "Sim" if obj.ativo else "Não"},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:paciente_update", args=[obj.pk]) if can_manage else "",
        }
        for obj in page_obj
    ]
    return render(request, "saude/generic_list.html", {"title": "Pacientes", "subtitle": "Cadastro base clínico com identificação e vínculos", "q": q, "page_obj": page_obj, "actions": actions, "headers": headers, "rows": rows, "action_url": reverse("saude:paciente_list"), "clear_url": reverse("saude:paciente_list"), "has_filters": bool(q), "empty_title": "Nenhum paciente encontrado", "empty_text": "Cadastre o primeiro paciente."})


@login_required
@require_perm("saude.manage")
def paciente_create(request):
    unidades_qs = _scoped_unidades(request.user)
    if request.method == "POST":
        form = PacienteSaudeForm(request.POST, unidades_qs=unidades_qs)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Paciente cadastrado com sucesso.")
            return redirect("saude:paciente_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = PacienteSaudeForm(unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Novo Paciente", "subtitle": "Cadastro clínico", "form": form, "cancel_url": reverse("saude:paciente_list"), "submit_label": "Salvar", "action_url": reverse("saude:paciente_create")})


@login_required
@require_perm("saude.manage")
def paciente_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(PacienteSaude.objects.filter(unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    if request.method == "POST":
        form = PacienteSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs)
        if form.is_valid():
            form.save()
            messages.success(request, "Paciente atualizado.")
            return redirect("saude:paciente_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = PacienteSaudeForm(instance=obj, unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Editar Paciente", "subtitle": obj.nome, "form": form, "cancel_url": reverse("saude:paciente_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:paciente_update", args=[obj.pk])})


@login_required
@require_perm("saude.view")
def paciente_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(PacienteSaude.objects.select_related("unidade_referencia", "programa").filter(unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    actions = [{"label": "Voltar", "url": reverse("saude:paciente_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:paciente_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [
        {"label": "Unidade", "value": obj.unidade_referencia.nome},
        {"label": "Programa/Convênio", "value": obj.programa.nome if obj.programa_id else "—"},
        {"label": "Data de nascimento", "value": obj.data_nascimento.strftime("%d/%m/%Y") if obj.data_nascimento else "—"},
        {"label": "Sexo", "value": obj.get_sexo_display()},
        {"label": "Cartão SUS", "value": obj.cartao_sus or "—"},
        {"label": "CPF", "value": obj.cpf or "—"},
        {"label": "Telefone", "value": obj.telefone or "—"},
        {"label": "E-mail", "value": obj.email or "—"},
        {"label": "Endereço", "value": obj.endereco or "—"},
        {"label": "Responsável", "value": obj.responsavel_nome or "—"},
        {"label": "Telefone do responsável", "value": obj.responsavel_telefone or "—"},
        {"label": "Vulnerabilidades", "value": obj.vulnerabilidades or "—"},
    ]
    pills = [{"label": "Paciente", "value": obj.nome, "variant": "info"}, {"label": "Ativo", "value": "Sim" if obj.ativo else "Não", "variant": "info"}]
    return render(request, "saude/generic_detail.html", {"title": obj.nome, "subtitle": "Detalhes do paciente", "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def checkin_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = CheckInSaude.objects.select_related("unidade", "paciente", "agendamento", "atendimento").filter(unidade_id__in=unidades_qs.values_list("id", flat=True))
    if q:
        qs = qs.filter(Q(paciente_nome__icontains=q) | Q(motivo_visita__icontains=q))
    if status:
        qs = qs.filter(status=status)
    page_obj = Paginator(qs.order_by("-chegada_em", "-id"), 15).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Novo Check-in", "url": reverse("saude:checkin_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
    headers = [{"label": "Paciente"}, {"label": "Chegada"}, {"label": "Unidade"}, {"label": "Status"}, {"label": "Risco"}]
    rows = [
        {
            "cells": [
                {"text": obj.paciente_nome, "url": reverse("saude:checkin_detail", args=[obj.pk])},
                {"text": obj.chegada_em.strftime("%d/%m/%Y %H:%M")},
                {"text": obj.unidade.nome},
                {"text": obj.get_status_display()},
                {"text": obj.classificacao_risco or "—"},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:checkin_update", args=[obj.pk]) if can_manage else "",
        }
        for obj in page_obj
    ]
    extra_filters = """
      <div class=\"filter-bar__field\">
        <label class=\"small\">Status</label>
        <select name=\"status\">
          <option value=\"\">Todos</option>
    """
    for k, v in CheckInSaude.Status.choices:
        selected = "selected" if status == k else ""
        extra_filters += f"<option value=\"{k}\" {selected}>{v}</option>"
    extra_filters += """
        </select>
      </div>
    """
    return render(request, "saude/generic_list.html", {"title": "Check-in e Acolhimento", "subtitle": "Recepção clínica, queixa e classificação de risco", "q": q, "page_obj": page_obj, "actions": actions, "headers": headers, "rows": rows, "action_url": reverse("saude:checkin_list"), "clear_url": reverse("saude:checkin_list"), "has_filters": bool(status or q), "extra_filters": extra_filters, "empty_title": "Nenhum check-in encontrado", "empty_text": "Registre o primeiro check-in."})


@login_required
@require_perm("saude.manage")
def checkin_create(request):
    unidades_qs = _scoped_unidades(request.user)
    if request.method == "POST":
        form = CheckInSaudeForm(request.POST, unidades_qs=unidades_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            if obj.paciente_id and not obj.paciente_nome:
                obj.paciente_nome = obj.paciente.nome
            obj.save()
            messages.success(request, "Check-in registrado com sucesso.")
            return redirect("saude:checkin_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = CheckInSaudeForm(unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Novo Check-in", "subtitle": "Recepção e acolhimento", "form": form, "cancel_url": reverse("saude:checkin_list"), "submit_label": "Salvar", "action_url": reverse("saude:checkin_create")})


@login_required
@require_perm("saude.manage")
def checkin_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(CheckInSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    if request.method == "POST":
        form = CheckInSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs)
        if form.is_valid():
            obj2 = form.save(commit=False)
            if obj2.paciente_id and not obj2.paciente_nome:
                obj2.paciente_nome = obj2.paciente.nome
            obj2.save()
            messages.success(request, "Check-in atualizado.")
            return redirect("saude:checkin_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = CheckInSaudeForm(instance=obj, unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Editar Check-in", "subtitle": obj.paciente_nome, "form": form, "cancel_url": reverse("saude:checkin_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:checkin_update", args=[obj.pk])})


@login_required
@require_perm("saude.view")
def checkin_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(CheckInSaude.objects.select_related("unidade", "paciente", "agendamento", "atendimento", "criado_por").filter(unidade_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    actions = [{"label": "Voltar", "url": reverse("saude:checkin_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:checkin_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [
        {"label": "Unidade", "value": obj.unidade.nome},
        {"label": "Paciente cadastro", "value": obj.paciente.nome if obj.paciente_id else "—"},
        {"label": "Agendamento", "value": f"#{obj.agendamento_id}" if obj.agendamento_id else "—"},
        {"label": "Atendimento", "value": f"#{obj.atendimento_id}" if obj.atendimento_id else "—"},
        {"label": "Motivo", "value": obj.motivo_visita or "—"},
        {"label": "Queixa principal", "value": obj.queixa_principal or "—"},
        {"label": "Classificação de risco", "value": obj.classificacao_risco or "—"},
        {"label": "Sinais vitais", "value": f"PA {obj.pa_sistolica or '—'}/{obj.pa_diastolica or '—'} | FC {obj.frequencia_cardiaca or '—'} | Temp {obj.temperatura or '—'} | SpO2 {obj.saturacao_o2 or '—'}"},
        {"label": "Registrado por", "value": obj.criado_por.get_username()},
    ]
    pills = [{"label": "Paciente", "value": obj.paciente_nome, "variant": "info"}, {"label": "Status", "value": obj.get_status_display(), "variant": "warning"}]
    return render(request, "saude/generic_detail.html", {"title": obj.paciente_nome, "subtitle": f"Check-in em {obj.chegada_em:%d/%m/%Y %H:%M}", "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def medicamento_uso_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = MedicamentoUsoContinuoSaude.objects.select_related("paciente").filter(paciente__unidade_referencia_id__in=unidades_qs.values_list("id", flat=True))
    if q:
        qs = qs.filter(Q(medicamento__icontains=q) | Q(paciente__nome__icontains=q))
    page_obj = Paginator(qs.order_by("paciente__nome", "medicamento"), 15).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Novo Medicamento em Uso", "url": reverse("saude:medicamento_uso_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
    headers = [{"label": "Paciente"}, {"label": "Medicamento"}, {"label": "Posologia"}, {"label": "Ativo"}]
    rows = [
        {
            "cells": [
                {"text": obj.paciente.nome, "url": reverse("saude:medicamento_uso_detail", args=[obj.pk])},
                {"text": obj.medicamento},
                {"text": f"{obj.dose or '—'} / {obj.frequencia or '—'}"},
                {"text": "Sim" if obj.ativo else "Não"},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:medicamento_uso_update", args=[obj.pk]) if can_manage else "",
        }
        for obj in page_obj
    ]
    return render(request, "saude/generic_list.html", {"title": "Medicamentos em Uso Contínuo", "subtitle": "Controle longitudinal de medicação ativa por paciente", "q": q, "page_obj": page_obj, "actions": actions, "headers": headers, "rows": rows, "action_url": reverse("saude:medicamento_uso_list"), "clear_url": reverse("saude:medicamento_uso_list"), "has_filters": bool(q), "empty_title": "Nenhum medicamento em uso registrado", "empty_text": "Cadastre o primeiro medicamento contínuo."})


@login_required
@require_perm("saude.manage")
def medicamento_uso_create(request):
    unidades_qs = _scoped_unidades(request.user)
    if request.method == "POST":
        form = MedicamentoUsoContinuoSaudeForm(request.POST, unidades_qs=unidades_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            obj.save()
            messages.success(request, "Medicamento em uso registrado.")
            return redirect("saude:medicamento_uso_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = MedicamentoUsoContinuoSaudeForm(unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Novo Medicamento em Uso", "subtitle": "Registro de medicação contínua", "form": form, "cancel_url": reverse("saude:medicamento_uso_list"), "submit_label": "Salvar", "action_url": reverse("saude:medicamento_uso_create")})


@login_required
@require_perm("saude.manage")
def medicamento_uso_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(MedicamentoUsoContinuoSaude.objects.filter(paciente__unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    if request.method == "POST":
        form = MedicamentoUsoContinuoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs)
        if form.is_valid():
            form.save()
            messages.success(request, "Medicamento em uso atualizado.")
            return redirect("saude:medicamento_uso_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = MedicamentoUsoContinuoSaudeForm(instance=obj, unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Editar Medicamento em Uso", "subtitle": obj.medicamento, "form": form, "cancel_url": reverse("saude:medicamento_uso_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:medicamento_uso_update", args=[obj.pk])})


@login_required
@require_perm("saude.view")
def medicamento_uso_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(MedicamentoUsoContinuoSaude.objects.select_related("paciente", "criado_por").filter(paciente__unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    actions = [{"label": "Voltar", "url": reverse("saude:medicamento_uso_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:medicamento_uso_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [{"label": "Paciente", "value": obj.paciente.nome}, {"label": "Medicamento", "value": obj.medicamento}, {"label": "Dose", "value": obj.dose or "—"}, {"label": "Via", "value": obj.via or "—"}, {"label": "Frequência", "value": obj.frequencia or "—"}, {"label": "Início", "value": obj.inicio.strftime("%d/%m/%Y") if obj.inicio else "—"}, {"label": "Fim", "value": obj.fim.strftime("%d/%m/%Y") if obj.fim else "—"}, {"label": "Observações", "value": obj.observacoes or "—"}, {"label": "Registrado por", "value": obj.criado_por.get_username()}]
    pills = [{"label": "Ativo", "value": "Sim" if obj.ativo else "Não", "variant": "info"}]
    return render(request, "saude/generic_detail.html", {"title": obj.medicamento, "subtitle": obj.paciente.nome, "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def dispensacao_list(request):
    q = (request.GET.get("q") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = DispensacaoSaude.objects.select_related("unidade", "paciente").filter(unidade_id__in=unidades_qs.values_list("id", flat=True))
    if q:
        qs = qs.filter(Q(medicamento__icontains=q) | Q(paciente__nome__icontains=q) | Q(lote__icontains=q))
    page_obj = Paginator(qs.order_by("-dispensado_em", "-id"), 15).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Nova Dispensação", "url": reverse("saude:dispensacao_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
    headers = [{"label": "Paciente"}, {"label": "Medicamento"}, {"label": "Quantidade"}, {"label": "Unidade"}, {"label": "Data"}]
    rows = [
        {
            "cells": [
                {"text": obj.paciente.nome, "url": reverse("saude:dispensacao_detail", args=[obj.pk])},
                {"text": obj.medicamento},
                {"text": f"{obj.quantidade} {obj.unidade_medida}"},
                {"text": obj.unidade.nome},
                {"text": obj.dispensado_em.strftime("%d/%m/%Y %H:%M")},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:dispensacao_update", args=[obj.pk]) if can_manage else "",
        }
        for obj in page_obj
    ]
    return render(request, "saude/generic_list.html", {"title": "Dispensação", "subtitle": "Dispensa farmacêutica vinculada ao atendimento/paciente", "q": q, "page_obj": page_obj, "actions": actions, "headers": headers, "rows": rows, "action_url": reverse("saude:dispensacao_list"), "clear_url": reverse("saude:dispensacao_list"), "has_filters": bool(q), "empty_title": "Nenhuma dispensação encontrada", "empty_text": "Registre a primeira dispensação."})


@login_required
@require_perm("saude.manage")
def dispensacao_create(request):
    unidades_qs = _scoped_unidades(request.user)
    if request.method == "POST":
        form = DispensacaoSaudeForm(request.POST, unidades_qs=unidades_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.dispensado_por = request.user
            obj.save()
            messages.success(request, "Dispensação registrada com sucesso.")
            return redirect("saude:dispensacao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = DispensacaoSaudeForm(unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Nova Dispensação", "subtitle": "Saída de medicamento", "form": form, "cancel_url": reverse("saude:dispensacao_list"), "submit_label": "Salvar", "action_url": reverse("saude:dispensacao_create")})


@login_required
@require_perm("saude.manage")
def dispensacao_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(DispensacaoSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    if request.method == "POST":
        form = DispensacaoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs)
        if form.is_valid():
            form.save()
            messages.success(request, "Dispensação atualizada.")
            return redirect("saude:dispensacao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = DispensacaoSaudeForm(instance=obj, unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Editar Dispensação", "subtitle": obj.medicamento, "form": form, "cancel_url": reverse("saude:dispensacao_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:dispensacao_update", args=[obj.pk])})


@login_required
@require_perm("saude.view")
def dispensacao_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(DispensacaoSaude.objects.select_related("unidade", "paciente", "dispensado_por").filter(unidade_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    actions = [{"label": "Voltar", "url": reverse("saude:dispensacao_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:dispensacao_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [{"label": "Paciente", "value": obj.paciente.nome}, {"label": "Medicamento", "value": obj.medicamento}, {"label": "Quantidade", "value": f"{obj.quantidade} {obj.unidade_medida}"}, {"label": "Lote", "value": obj.lote or "—"}, {"label": "Validade", "value": obj.validade.strftime("%d/%m/%Y") if obj.validade else "—"}, {"label": "Unidade", "value": obj.unidade.nome}, {"label": "Orientações", "value": obj.orientacoes or "—"}, {"label": "Dispensado por", "value": obj.dispensado_por.get_username()}]
    pills = [{"label": "Data", "value": obj.dispensado_em.strftime("%d/%m/%Y %H:%M"), "variant": "info"}]
    return render(request, "saude/generic_detail.html", {"title": obj.medicamento, "subtitle": "Dispensação", "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def exame_coleta_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = ExameColetaSaude.objects.select_related("pedido", "pedido__atendimento").filter(
        pedido__atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)
    )
    if q:
        qs = qs.filter(Q(pedido__nome_exame__icontains=q) | Q(pedido__atendimento__paciente_nome__icontains=q))
    if status:
        qs = qs.filter(status=status)
    page_obj = Paginator(qs.order_by("-atualizado_em", "-id"), 15).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Novo Fluxo de Exame", "url": reverse("saude:exame_coleta_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
    headers = [{"label": "Paciente"}, {"label": "Exame"}, {"label": "Status"}, {"label": "Coleta"}, {"label": "Atualização"}]
    rows = [
        {
            "cells": [
                {"text": obj.pedido.atendimento.paciente_nome, "url": reverse("saude:exame_coleta_detail", args=[obj.pk])},
                {"text": obj.pedido.nome_exame},
                {"text": obj.get_status_display()},
                {"text": obj.data_coleta.strftime("%d/%m/%Y %H:%M") if obj.data_coleta else "—"},
                {"text": obj.atualizado_em.strftime("%d/%m/%Y %H:%M")},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:exame_coleta_update", args=[obj.pk]) if can_manage else "",
        }
        for obj in page_obj
    ]
    extra_filters = """
      <div class=\"filter-bar__field\">
        <label class=\"small\">Status</label>
        <select name=\"status\">
          <option value=\"\">Todos</option>
    """
    for k, v in ExameColetaSaude.Status.choices:
        selected = "selected" if status == k else ""
        extra_filters += f"<option value=\"{k}\" {selected}>{v}</option>"
    extra_filters += """
        </select>
      </div>
    """
    return render(request, "saude/generic_list.html", {"title": "Coleta e Encaminhamento de Exames", "subtitle": "Fluxo operacional do exame solicitado até o resultado", "q": q, "page_obj": page_obj, "actions": actions, "headers": headers, "rows": rows, "action_url": reverse("saude:exame_coleta_list"), "clear_url": reverse("saude:exame_coleta_list"), "has_filters": bool(q or status), "extra_filters": extra_filters, "empty_title": "Nenhum fluxo de exame encontrado", "empty_text": "Cadastre o primeiro fluxo de exame."})


@login_required
@require_perm("saude.manage")
def exame_coleta_create(request):
    unidades_qs = _scoped_unidades(request.user)
    if request.method == "POST":
        form = ExameColetaSaudeForm(request.POST, unidades_qs=unidades_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.atualizado_por = request.user
            obj.save()
            messages.success(request, "Fluxo de exame registrado.")
            return redirect("saude:exame_coleta_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ExameColetaSaudeForm(unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Novo Fluxo de Exame", "subtitle": "Coleta/encaminhamento", "form": form, "cancel_url": reverse("saude:exame_coleta_list"), "submit_label": "Salvar", "action_url": reverse("saude:exame_coleta_create")})


@login_required
@require_perm("saude.manage")
def exame_coleta_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(ExameColetaSaude.objects.filter(pedido__atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    if request.method == "POST":
        form = ExameColetaSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs)
        if form.is_valid():
            obj2 = form.save(commit=False)
            obj2.atualizado_por = request.user
            obj2.save()
            messages.success(request, "Fluxo de exame atualizado.")
            return redirect("saude:exame_coleta_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = ExameColetaSaudeForm(instance=obj, unidades_qs=unidades_qs)
    return render(request, "saude/generic_form.html", {"title": "Editar Fluxo de Exame", "subtitle": obj.pedido.nome_exame, "form": form, "cancel_url": reverse("saude:exame_coleta_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:exame_coleta_update", args=[obj.pk])})


@login_required
@require_perm("saude.view")
def exame_coleta_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(ExameColetaSaude.objects.select_related("pedido", "pedido__atendimento", "atualizado_por").filter(pedido__atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    actions = [{"label": "Voltar", "url": reverse("saude:exame_coleta_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:exame_coleta_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [{"label": "Paciente", "value": obj.pedido.atendimento.paciente_nome}, {"label": "Exame", "value": obj.pedido.nome_exame}, {"label": "Local de coleta", "value": obj.local_coleta or "—"}, {"label": "Encaminhado para", "value": obj.encaminhado_para or "—"}, {"label": "Observações", "value": obj.observacoes or "—"}, {"label": "Atualizado por", "value": obj.atualizado_por.get_username()}]
    pills = [{"label": "Status", "value": obj.get_status_display(), "variant": "info"}, {"label": "Data da coleta", "value": obj.data_coleta.strftime("%d/%m/%Y %H:%M") if obj.data_coleta else "—", "variant": "warning"}]
    return render(request, "saude/generic_detail.html", {"title": obj.pedido.nome_exame, "subtitle": "Fluxo de exame", "fields": fields, "pills": pills, "actions": actions})


@login_required
@require_perm("saude.view")
def internacao_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    unidades_qs = _scoped_unidades(request.user)
    qs = InternacaoSaude.objects.select_related("unidade", "paciente", "profissional_responsavel").filter(unidade_id__in=unidades_qs.values_list("id", flat=True))
    if q:
        qs = qs.filter(Q(paciente__nome__icontains=q) | Q(leito__icontains=q) | Q(motivo__icontains=q))
    if status:
        qs = qs.filter(status=status)
    page_obj = Paginator(qs.order_by("-data_admissao", "-id"), 15).get_page(request.GET.get("page"))
    can_manage = can(request.user, "saude.manage")
    actions = []
    if can_manage:
        actions.append({"label": "Nova Internação/Observação", "url": reverse("saude:internacao_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"})
    headers = [{"label": "Paciente"}, {"label": "Tipo"}, {"label": "Leito"}, {"label": "Unidade"}, {"label": "Status"}]
    rows = [
        {
            "cells": [
                {"text": obj.paciente.nome, "url": reverse("saude:internacao_detail", args=[obj.pk])},
                {"text": obj.get_tipo_display()},
                {"text": obj.leito or "—"},
                {"text": obj.unidade.nome},
                {"text": obj.get_status_display()},
            ],
            "can_edit": bool(can_manage),
            "edit_url": reverse("saude:internacao_update", args=[obj.pk]) if can_manage else "",
        }
        for obj in page_obj
    ]
    extra_filters = """
      <div class=\"filter-bar__field\">
        <label class=\"small\">Status</label>
        <select name=\"status\">
          <option value=\"\">Todos</option>
    """
    for k, v in InternacaoSaude.Status.choices:
        selected = "selected" if status == k else ""
        extra_filters += f"<option value=\"{k}\" {selected}>{v}</option>"
    extra_filters += """
        </select>
      </div>
    """
    return render(request, "saude/generic_list.html", {"title": "Internação e Observação", "subtitle": "Admissão, leito, evolução e alta", "q": q, "page_obj": page_obj, "actions": actions, "headers": headers, "rows": rows, "action_url": reverse("saude:internacao_list"), "clear_url": reverse("saude:internacao_list"), "has_filters": bool(q or status), "extra_filters": extra_filters, "empty_title": "Nenhum registro de internação/observação", "empty_text": "Cadastre a primeira admissão."})


@login_required
@require_perm("saude.manage")
def internacao_create(request):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)
    if request.method == "POST":
        form = InternacaoSaudeForm(request.POST, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.criado_por = request.user
            obj.save()
            messages.success(request, "Internação/observação registrada.")
            return redirect("saude:internacao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = InternacaoSaudeForm(unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
    return render(request, "saude/generic_form.html", {"title": "Nova Internação/Observação", "subtitle": "Admissão clínica", "form": form, "cancel_url": reverse("saude:internacao_list"), "submit_label": "Salvar", "action_url": reverse("saude:internacao_create")})


@login_required
@require_perm("saude.manage")
def internacao_update(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    profissionais_qs = _scoped_profissionais(unidades_qs)
    obj = get_object_or_404(InternacaoSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)
    if request.method == "POST":
        form = InternacaoSaudeForm(request.POST, instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
        if form.is_valid():
            form.save()
            messages.success(request, "Internação/observação atualizada.")
            return redirect("saude:internacao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = InternacaoSaudeForm(instance=obj, unidades_qs=unidades_qs, profissionais_qs=profissionais_qs)
    return render(request, "saude/generic_form.html", {"title": "Editar Internação/Observação", "subtitle": obj.paciente.nome, "form": form, "cancel_url": reverse("saude:internacao_detail", args=[obj.pk]), "submit_label": "Salvar", "action_url": reverse("saude:internacao_update", args=[obj.pk])})


@login_required
@require_perm("saude.view")
def internacao_detail(request, pk: int):
    unidades_qs = _scoped_unidades(request.user)
    obj = get_object_or_404(InternacaoSaude.objects.select_related("unidade", "paciente", "profissional_responsavel", "criado_por").prefetch_related("registros__criado_por").filter(unidade_id__in=unidades_qs.values_list("id", flat=True)), pk=pk)

    if request.method == "POST" and can(request.user, "saude.manage"):
        reg_form = InternacaoRegistroSaudeForm(request.POST)
        if reg_form.is_valid():
            reg = reg_form.save(commit=False)
            reg.internacao = obj
            reg.criado_por = request.user
            reg.save()
            messages.success(request, "Registro de internação incluído.")
            return redirect("saude:internacao_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do registro da internação.")

    reg_form = InternacaoRegistroSaudeForm()
    actions = [{"label": "Voltar", "url": reverse("saude:internacao_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    if can(request.user, "saude.manage"):
        actions.append({"label": "Editar", "url": reverse("saude:internacao_update", args=[obj.pk]), "icon": "fa-solid fa-pen", "variant": "btn-primary"})
    fields = [{"label": "Paciente", "value": obj.paciente.nome}, {"label": "Unidade", "value": obj.unidade.nome}, {"label": "Profissional responsável", "value": obj.profissional_responsavel.nome if obj.profissional_responsavel_id else "—"}, {"label": "Leito", "value": obj.leito or "—"}, {"label": "Motivo", "value": obj.motivo}, {"label": "Resumo de alta", "value": obj.resumo_alta or "—"}, {"label": "Criado por", "value": obj.criado_por.get_username()}]
    pills = [{"label": "Tipo", "value": obj.get_tipo_display(), "variant": "info"}, {"label": "Status", "value": obj.get_status_display(), "variant": "warning"}, {"label": "Admissão", "value": obj.data_admissao.strftime("%d/%m/%Y %H:%M"), "variant": "info"}]
    registros = [
        {
            "tipo": r.get_tipo_display(),
            "texto": r.texto,
            "autor": r.criado_por.get_username(),
            "quando": r.criado_em.strftime("%d/%m/%Y %H:%M"),
        }
        for r in obj.registros.all()
    ]
    return render(request, "saude/internacao_detail.html", {"title": obj.paciente.nome, "subtitle": "Detalhes da internação/observação", "fields": fields, "pills": pills, "actions": actions, "registros": registros, "reg_form": reg_form, "can_manage": can(request.user, "saude.manage")})
