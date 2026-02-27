from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.rbac import scope_filter_turmas

from .models import Turma
from .models_horarios import GradeHorario, AulaHorario
from .views_horarios_core import parse_hhmm


def horario_gerar_padrao_impl(request, turma_id: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=turma_id)

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    if grade.aulas.exists():
        messages.warning(request, "Essa turma já possui aulas no horário. Apague/limpe antes de gerar novamente.")
        return redirect("educacao:horario_turma", turma_id=turma.pk)

    turnos = {
        "MANHA": [("07:30", "08:20"), ("08:20", "09:10"), ("09:20", "10:10"), ("10:10", "11:00"), ("11:00", "11:50")],
        "TARDE": [("13:30", "14:20"), ("14:20", "15:10"), ("15:20", "16:10"), ("16:10", "17:00"), ("17:00", "17:50")],
        "NOITE": [("18:30", "19:20"), ("19:20", "20:10"), ("20:20", "21:10"), ("21:10", "22:00")],
    }

    turno = str(getattr(turma, "turno", None) or "MANHA").upper()
    blocos = turnos.get(turno, turnos["MANHA"])

    dias = [c[0] for c in AulaHorario.Dia.choices]
    dias_uteis = [d for d in dias if d in {"SEG", "TER", "QUA", "QUI", "SEX"}]
    if not dias_uteis:
        dias_uteis = dias[:5]

    created = 0
    for dia in dias_uteis:
        for idx, (ini_s, fim_s) in enumerate(blocos, start=1):
            AulaHorario.objects.create(
                grade=grade,
                dia=dia,
                inicio=parse_hhmm(ini_s),
                fim=parse_hhmm(fim_s),
                disciplina=f"Aula {idx}",
                sala="",
            )
            created += 1

    messages.success(request, f"Grade padrão gerada com sucesso ({created} aulas).")
    return redirect("educacao:horario_turma", turma_id=turma.pk)


def horario_duplicar_impl(request, turma_id: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma_destino = get_object_or_404(turma_qs, pk=turma_id)

    origem_id = (request.GET.get("origem") or "").strip()
    if not origem_id.isdigit():
        messages.error(request, "Informe a turma origem: ?origem=123")
        return redirect("educacao:horario_turma", turma_id=turma_destino.pk)

    turma_origem = get_object_or_404(turma_qs, pk=int(origem_id))

    grade_destino, _ = GradeHorario.objects.get_or_create(turma=turma_destino)
    grade_origem, _ = GradeHorario.objects.get_or_create(turma=turma_origem)

    if not grade_origem.aulas.exists():
        messages.error(request, "A turma origem não possui horário cadastrado.")
        return redirect("educacao:horario_turma", turma_id=turma_destino.pk)

    if grade_destino.aulas.exists():
        messages.warning(request, "A turma destino já possui aulas no horário. Apague/limpe antes de duplicar.")
        return redirect("educacao:horario_turma", turma_id=turma_destino.pk)

    created = 0
    for a in grade_origem.aulas.all():
        AulaHorario.objects.create(
            grade=grade_destino,
            dia=a.dia,
            inicio=a.inicio,
            fim=a.fim,
            disciplina=a.disciplina,
            sala=getattr(a, "sala", "") or "",
        )
        created += 1

    messages.success(request, f"Horário duplicado com sucesso ({created} aulas).")
    return redirect("educacao:horario_turma", turma_id=turma_destino.pk)


def horario_duplicar_select_impl(request, turma_id: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria"),
    )
    turma_destino = get_object_or_404(turma_qs, pk=turma_id)

    grade_destino, _ = GradeHorario.objects.get_or_create(turma=turma_destino)
    if grade_destino.aulas.exists():
        messages.warning(request, "A turma destino já possui aulas. Limpe o horário antes de duplicar.")
        return redirect("educacao:horario_turma", turma_id=turma_destino.pk)

    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    qs = turma_qs.exclude(pk=turma_destino.pk).order_by("-ano_letivo", "nome")

    if ano.isdigit():
        qs = qs.filter(ano_letivo=int(ano))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
        )

    qs = qs.filter(grade_horario__aulas__isnull=False).distinct()

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:horario_turma", args=[turma_destino.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
    ]

    headers = [
        {"label": "Turma"},
        {"label": "Ano", "width": "110px"},
        {"label": "Unidade"},
        {"label": "Ação", "width": "190px"},
    ]

    rows = []
    for t in page_obj:
        rows.append(
            {
                "cells": [
                    {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                    {"text": str(t.ano_letivo or "—")},
                    {"text": getattr(getattr(t, "unidade", None), "nome", "—")},
                    {
                        "text": "Duplicar desta turma",
                        "url": reverse("educacao:horario_duplicar", args=[turma_destino.pk]) + f"?origem={t.pk}",
                    },
                ],
                "can_edit": False,
                "edit_url": "",
            }
        )

    extra_filters = f"""
      <div class=\"filter-bar__field\">
        <label class=\"small\">Ano letivo</label>
        <input name=\"ano\" value=\"{ano}\" placeholder=\"Ex.: 2026\" />
      </div>
    """

    return render(
        request,
        "educacao/horario_duplicar_select.html",
        {
            "turma_destino": turma_destino,
            "q": q,
            "ano": ano,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": page_obj,
            "action_url": reverse("educacao:horario_duplicar_select", args=[turma_destino.pk]),
            "clear_url": reverse("educacao:horario_duplicar_select", args=[turma_destino.pk]),
            "has_filters": bool(ano),
            "extra_filters": extra_filters,
            "autocomplete_url": reverse("educacao:api_turmas_suggest"),
        },
    )


def horario_limpar_impl(request, turma_id: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=turma_id)

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    ok = (request.GET.get("ok") or "").strip()
    if ok != "1":
        messages.warning(request, "Confirme a ação clicando novamente. (Segurança)")
        return redirect(reverse("educacao:horario_turma", args=[turma.pk]) + "?confirmar_limpar=1")

    deleted, _ = grade.aulas.all().delete()
    messages.success(request, f"Horário limpo com sucesso. ({deleted} registros removidos)")
    return redirect("educacao:horario_turma", turma_id=turma.pk)
