from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import can, scope_filter_turmas

from .models import Turma, Matricula
from .models_diario import DiarioTurma, Aula, Frequencia
from .forms_diario import AulaForm
from django.utils import timezone

from django.db.models import Q
from django.http import JsonResponse

def _is_professor(user) -> bool:
    # Seu Profile usa role="PROFESSOR" (já vimos isso)
    return getattr(getattr(user, "profile", None), "role", "") == "PROFESSOR"


def _can_edit_diario(user, diario: DiarioTurma) -> bool:
    # Professor edita apenas o próprio diário
    return _is_professor(user) and diario.professor_id == user.id


def _can_view_diario(user, diario: DiarioTurma) -> bool:
    # Professor vê o próprio diário; gestor/unidade vê se turma está no escopo
    if _can_edit_diario(user, diario):
        return True
    turmas_scope = scope_filter_turmas(user, Turma.objects.all()).values_list("id", flat=True)
    return diario.turma_id in set(turmas_scope)


@login_required
@require_perm("educacao.view")
def meus_diarios(request):
    user = request.user
    is_prof = _is_professor(user)

    if is_prof:
        qs = DiarioTurma.objects.select_related("turma", "turma__unidade").filter(professor=user).order_by("-ano_letivo", "turma__nome")
    else:
        turmas_scope = scope_filter_turmas(user, Turma.objects.all())
        qs = DiarioTurma.objects.select_related("turma", "turma__unidade", "professor").filter(turma__in=turmas_scope).order_by("-ano_letivo", "turma__nome", "professor__username")

    actions = []
    headers = [{"label": "Turma"}, {"label": "Unidade"}, {"label": "Ano", "width": "120px"}, {"label": "Professor", "width": "220px"}]
    rows = []

    for d in qs:
        rows.append({
            "cells": [
                {"text": d.turma.nome, "url": reverse("educacao:diario_detail", args=[d.pk])},
                {"text": getattr(getattr(d.turma, "unidade", None), "nome", "—")},
                {"text": str(d.ano_letivo)},
                {"text": getattr(getattr(d, "professor", None), "username", "—")},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    return render(request, "educacao/diario_list.html", {
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "page_obj": None,
        "is_professor": is_prof,
    })


@login_required
@require_perm("educacao.view")
def diario_detail(request, pk: int):
    diario = get_object_or_404(
        DiarioTurma.objects.select_related("turma", "turma__unidade", "professor"),
        pk=pk,
    )

    if not _can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar este diário.")

    can_edit = _can_edit_diario(request.user, diario)

    export = (request.GET.get("export") or "").strip().lower()
    aulas = diario.aulas.all().order_by("-data", "-id")

    # ===== PDF impressão (gestor/unidade visualiza e imprime) =====
    if export == "pdf":
        headers = ["Data", "Conteúdo", "Observações"]
        rows = []
        for a in aulas:
            rows.append([
                a.data.strftime("%d/%m/%Y") if a.data else "—",
                (a.conteudo or "—")[:80],
                (a.observacoes or "—")[:80],
            ])

        filtros = f"Turma={diario.turma.nome} | Ano={diario.ano_letivo} | Professor={getattr(diario.professor, 'username', '-')}"
        return export_pdf_table(
            request,
            filename="diario_turma.pdf",
            title="Diário de Classe — Aulas",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:meus_diarios"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": reverse("educacao:diario_detail", args=[diario.pk]) + "?export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
        {
            "label": "Avaliações",
            "url": reverse("educacao:avaliacao_list", args=[diario.pk]),
            "icon": "fa-solid fa-clipboard-check",
            "variant": "btn--ghost",
        },
    ]

    # professor pode criar aula
    if can_edit:
        actions.append(
            {
                "label": "Nova Aula",
                "url": reverse("educacao:aula_create", args=[diario.pk]),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    headers = [
        {"label": "Data", "width": "140px"},
        {"label": "Conteúdo"},
        {"label": "Ações", "width": "220px"},
    ]

    rows = []
    for a in aulas:
        rows.append({
            "cells": [
                {"text": a.data.strftime("%d/%m/%Y") if a.data else "—", "url": ""},
                {"text": (a.conteudo or "—")[:120]},
                {"text": "Frequência", "url": reverse("educacao:aula_frequencia", args=[a.pk])},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    return render(
        request,
        "educacao/diario_detail.html",
        {
            "diario": diario,
            "can_edit": can_edit,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": None,
        },
    )


@login_required
@require_perm("educacao.view")
def aula_frequencia(request, pk: int):
    aula = get_object_or_404(
        Aula.objects.select_related(
            "diario",
            "diario__turma",
            "diario__professor",
            "diario__turma__unidade",
        ),
        pk=pk,
    )
    diario = aula.diario

    if not _can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar esta aula.")

    can_edit = _can_edit_diario(request.user, diario)
    q = (request.GET.get("q") or "").strip()

    alunos_qs = (
        Matricula.objects.filter(turma=diario.turma, situacao="ATIVA")
        .select_related("aluno")
        .order_by("aluno__nome")
    )

    if q:
        alunos_qs = alunos_qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(aluno__cpf__icontains=q)
            | Q(aluno__nis__icontains=q)
        )

    # mapa de frequências existentes
    freq_map = {f.aluno_id: f.status for f in aula.frequencias.all()}

    # POST apenas para professor dono do diário
    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("403 — Somente o professor responsável pode lançar frequência.")

        # salva apenas os alunos da lista atual (filtrada ou não)
        for m in alunos_qs:
            status = (request.POST.get(f"aluno_{m.aluno_id}") or "P").strip()
            Frequencia.objects.update_or_create(
                aula=aula,
                aluno=m.aluno,
                defaults={"status": status},
            )

        messages.success(request, "Frequência salva com sucesso.")
        return redirect(f"{reverse('educacao:aula_frequencia', args=[aula.pk])}?q={q}" if q else reverse("educacao:aula_frequencia", args=[aula.pk]))

    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Aluno", "Status"]
        rows = []
        for m in alunos_qs:
            st = freq_map.get(m.aluno_id, "P")
            label = dict(Frequencia.Status.choices).get(st, "Presente")
            rows.append([m.aluno.nome, label])

        filtros = f"Turma={diario.turma.nome} | Data={aula.data.strftime('%d/%m/%Y') if aula.data else '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="frequencia_aula.pdf",
            title="Frequência — Aula",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:diario_detail", args=[diario.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": (reverse("educacao:aula_frequencia", args=[aula.pk]) + ("?q=" + q + "&" if q else "?") + "export=pdf"),
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
    ]
    if can_edit:
        actions.append(
            {
                "label": "Salvar Frequência",
                "url": "#freq-form",
                "icon": "fa-solid fa-check",
                "variant": "btn-primary",
            }
        )

    # ✅ sem helper no template: já prepara a lista renderizável
    alunos_render = []
    for m in alunos_qs:
        alunos_render.append(
            {
                "id": m.aluno_id,
                "nome": m.aluno.nome,
                "status": freq_map.get(m.aluno_id, "P"),
            }
        )

    return render(
        request,
        "educacao/aula_frequencia.html",
        {
            "aula": aula,
            "diario": diario,
            "alunos_render": alunos_render,
            "can_edit": can_edit,
            "actions": actions,

            # filter bar + autocomplete (padrão do sistema)
            "q": q,
            "action_url": reverse("educacao:aula_frequencia", args=[aula.pk]),
            "clear_url": reverse("educacao:aula_frequencia", args=[aula.pk]),
            "has_filters": bool(q),
            "autocomplete_url": reverse("educacao:api_alunos_turma_suggest", args=[diario.turma.pk]),
            "autocomplete_href": reverse("educacao:aula_frequencia", args=[aula.pk]) + "?q={q}",
        },
    )


    
@login_required
@require_perm("educacao.view")
def aula_create(request, pk: int):
    diario = get_object_or_404(DiarioTurma.objects.select_related("turma", "professor"), pk=pk)

    if not _can_edit_diario(request.user, diario):
        return HttpResponseForbidden("403 — Somente o professor responsável pode criar aula.")

    if request.method == "POST":
        form = AulaForm(request.POST)
        if form.is_valid():
            aula = form.save(commit=False)
            aula.diario = diario
            aula.save()
            messages.success(request, "Aula criada com sucesso.")
            return redirect("educacao:diario_detail", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AulaForm()

    return render(request, "educacao/aula_form.html", {
        "form": form,
        "diario": diario,
        "mode": "create",
        "cancel_url": reverse("educacao:diario_detail", args=[diario.pk]),
        "submit_label": "Salvar",
        "action_url": reverse("educacao:aula_create", args=[diario.pk]),
    })


@login_required
@require_perm("educacao.view")
def aula_update(request, pk: int, aula_id: int):
    """
    Editar uma aula dentro de um diário.
    Mantém assinatura usada no urls.py:
      pk = DiarioTurma.id
      aula_id = Aula.id
    """

    diario = get_object_or_404(
        DiarioTurma.objects.select_related("turma", "professor"),
        pk=pk,
    )

    # Mesma regra do create: só o professor responsável edita
    if not _can_edit_diario(request.user, diario):
        return HttpResponseForbidden("403 — Somente o professor responsável pode editar esta aula.")

    aula = get_object_or_404(Aula, pk=aula_id, diario=diario)

    if request.method == "POST":
        form = AulaForm(request.POST, instance=aula)
        if form.is_valid():
            form.save()
            messages.success(request, "Aula atualizada com sucesso.")
            return redirect("educacao:diario_detail", pk=diario.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AulaForm(instance=aula)

    return render(request, "educacao/aula_form.html", {
        "form": form,
        "diario": diario,
        "aula": aula,
        "mode": "update",
        "cancel_url": reverse("educacao:diario_detail", args=[diario.pk]),
        "submit_label": "Atualizar",
        "action_url": reverse("educacao:aula_update", args=[diario.pk, aula.pk]),
    })
    
    
@login_required
@require_perm("educacao.view")
def api_alunos_turma_suggest(request, pk: int):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=pk)

    # alunos ativos na turma
    alunos_qs = (
        Matricula.objects.filter(turma=turma, situacao="ATIVA")
        .select_related("aluno")
        .filter(
            Q(aluno__nome__icontains=q)
            | Q(aluno__cpf__icontains=q)
            | Q(aluno__nis__icontains=q)
        )
        .order_by("aluno__nome")[:10]
    )

    results = []
    for m in alunos_qs:
        a = m.aluno
        results.append({
            "id": a.id,
            "text": a.nome,
            "meta": (a.cpf or a.nis or ""),
        })

    return JsonResponse({"results": results})

@login_required
@require_perm("educacao.view")
def diario_create_for_turma(request, pk: int):
    # pk = turma_id
    turma_qs = scope_filter_turmas(request.user, Turma.objects.select_related("unidade"))
    turma = get_object_or_404(turma_qs, pk=pk)

    if getattr(getattr(request.user, "profile", None), "role", "") != "PROFESSOR":
        return HttpResponseForbidden("403 — Somente professor pode criar diário.")

    diario, _created = DiarioTurma.objects.get_or_create(
        turma=turma,
        professor=request.user,
        ano_letivo=getattr(turma, "ano_letivo", None) or timezone.localdate().year,
    )
    return redirect("educacao:diario_detail", pk=diario.pk)

@login_required
@require_perm("educacao.view")
def diario_turma_entry(request, pk: int):
    # pk = turma_id
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    # Professor: cria/pega o diário dele e entra direto
    if _is_professor(request.user):
        diario, _created = DiarioTurma.objects.get_or_create(
            turma=turma,
            professor=request.user,
            ano_letivo=getattr(turma, "ano_letivo", None) or timezone.localdate().year,
        )
        return redirect("educacao:diario_detail", pk=diario.pk)

    # Gestor/Unidade/Municipal: só visualiza
    diarios = (
        DiarioTurma.objects.select_related("turma", "turma__unidade", "professor")
        .filter(turma=turma)
        .order_by("-ano_letivo", "professor__username")
    )

    # Se tiver só um diário, entra direto
    if diarios.count() == 1:
        return redirect("educacao:diario_detail", pk=diarios.first().pk)

    # Senão, lista os diários da turma para escolher
    headers = [
        {"label": "Ano", "width": "120px"},
        {"label": "Professor"},
        {"label": "Unidade"},
    ]
    rows = []
    for d in diarios:
        rows.append({
            "cells": [
                {"text": str(d.ano_letivo), "url": reverse("educacao:diario_detail", args=[d.pk])},
                {"text": getattr(getattr(d, "professor", None), "username", "—")},
                {"text": getattr(getattr(getattr(d, "turma", None), "unidade", None), "nome", "—")},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    actions = [
        {"label": "Voltar", "url": reverse("educacao:turma_detail", args=[turma.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    return render(request, "educacao/diario_turma_select.html", {
        "turma": turma,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "page_obj": None,
    })