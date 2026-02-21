from datetime import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import can, scope_filter_turmas

from .models import Turma
from .models_horarios import GradeHorario, AulaHorario


def _parse_hhmm(value: str):
    """
    Aceita 'HH:MM' e retorna datetime.time.
    Retorna None se inválido.
    """
    value = (value or "").strip()
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        hh = int(parts[0])
        mm = int(parts[1])
    except ValueError:
        return None
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return time(hh, mm)


def _can_edit_horario(user, turma: Turma) -> bool:
    """
    Regra do GEPUB (como você pediu):
    - professor edita
    - gestor/unidade apenas visualiza e imprime
    - admin/gestor com educacao.manage edita
    """
    if can(user, "educacao.manage"):
        return True

    # Professor: se tiver Profile.role == "PROFESSOR" e pertencer à unidade da turma
    prof = getattr(user, "profile", None)
    if prof and getattr(prof, "role", None) == "PROFESSOR":
        if hasattr(prof, "unidade_id") and prof.unidade_id == turma.unidade_id:
            return True

    return False


@login_required
@require_perm("educacao.view")
def horario_turma(request, pk: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        ),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)
    can_edit = _can_edit_horario(request.user, turma)

    export = (request.GET.get("export") or "").strip().lower()
    aulas = grade.aulas.select_related("professor").all()

    if export == "pdf":
        headers = ["Dia", "Início", "Fim", "Disciplina", "Professor", "Sala"]
        rows = []
        for a in aulas:
            rows.append([
                a.get_dia_display(),
                a.inicio.strftime("%H:%M") if getattr(a, "inicio", None) else "—",
                a.fim.strftime("%H:%M") if getattr(a, "fim", None) else "—",
                getattr(a, "disciplina", "") or "—",
                getattr(getattr(a, "professor", None), "username", "—"),
                getattr(a, "sala", "") or "—",
            ])

        filtros = f"Turma={turma.nome} | Ano={turma.ano_letivo} | Unidade={getattr(turma.unidade, 'nome', '-')}"
        return export_pdf_table(
            request,
            filename="horario_turma.pdf",
            title="Horário da Turma",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:horarios_index"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": reverse("educacao:horario_turma", args=[turma.pk]) + "?export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
    ]

    if can_edit:
        actions.append(
            {
                "label": "Gerar Padrão",
                "url": reverse("educacao:horario_gerar_padrao", args=[turma.pk]),
                "icon": "fa-solid fa-wand-magic-sparkles",
                "variant": "btn--ghost",
            }
        )
        actions.append(
            {
                "label": "Duplicar horário",
                "url": reverse("educacao:horario_duplicar_select", args=[turma.pk]),
                "icon": "fa-solid fa-copy",
                "variant": "btn--ghost",
            }
        )
        actions.append(
            {
                "label": "Limpar horário",
                "url": reverse("educacao:horario_limpar", args=[turma.pk]),
                "icon": "fa-solid fa-trash",
                "variant": "btn--ghost",
            }
        )
        actions.append(
            {
                "label": "Adicionar Aula",
                "url": reverse("educacao:horario_aula_create", args=[turma.pk]),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    headers = [
        {"label": "Dia", "width": "140px"},
        {"label": "Início", "width": "110px"},
        {"label": "Fim", "width": "110px"},
        {"label": "Disciplina"},
        {"label": "Professor", "width": "220px"},
        {"label": "Sala", "width": "140px"},
    ]

    rows = []
    for a in aulas:
        rows.append({
            "cells": [
                {"text": a.get_dia_display()},
                {"text": a.inicio.strftime("%H:%M") if getattr(a, "inicio", None) else "—"},
                {"text": a.fim.strftime("%H:%M") if getattr(a, "fim", None) else "—"},
                {"text": getattr(a, "disciplina", "") or "—"},
                {"text": getattr(getattr(a, "professor", None), "username", "—")},
                {"text": getattr(a, "sala", "") or "—"},
            ],
            "can_edit": bool(can_edit),
            "edit_url": reverse("educacao:horario_aula_update", args=[turma.pk, a.pk]) if can_edit else "",
        })

    return render(
        request,
        "educacao/horario_turma.html",
        {
            "turma": turma,
            "grade": grade,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "page_obj": None,
            "can_edit": can_edit,
        },
    )



@login_required
@require_perm("educacao.view")
def horario_aula_create(request, pk: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=pk)

    if not _can_edit_horario(request.user, turma):
        return HttpResponseForbidden("403 — Você não tem permissão para editar horários.")

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    if request.method == "POST":
        dia = (request.POST.get("dia") or "").strip()
        inicio_raw = (request.POST.get("inicio") or "").strip()
        fim_raw = (request.POST.get("fim") or "").strip()
        disciplina = (request.POST.get("disciplina") or "").strip()
        sala = (request.POST.get("sala") or "").strip()

        inicio = _parse_hhmm(inicio_raw)
        fim = _parse_hhmm(fim_raw)

        if not dia or not disciplina or not inicio or not fim:
            messages.error(request, "Preencha dia, início (HH:MM), fim (HH:MM) e disciplina.")
        elif fim <= inicio:
            messages.error(request, "O horário final deve ser maior que o inicial.")
        else:
            AulaHorario.objects.create(
                grade=grade,
                dia=dia,
                inicio=inicio,
                fim=fim,
                disciplina=disciplina,
                sala=sala,
            )
            messages.success(request, "Aula adicionada ao horário.")
            return redirect("educacao:horario_turma", pk=turma.pk)

    return render(request, "educacao/horario_aula_form.html", {
        "turma": turma,
        "mode": "create",
        "cancel_url": reverse("educacao:horario_turma", args=[turma.pk]),
        "action_url": reverse("educacao:horario_aula_create", args=[turma.pk]),
        "submit_label": "Salvar",
        "dias": AulaHorario.Dia.choices,
    })


@login_required
@require_perm("educacao.view")
def horario_aula_update(request, pk: int, aula_id: int):
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=pk)

    if not _can_edit_horario(request.user, turma):
        return HttpResponseForbidden("403 — Você não tem permissão para editar horários.")

    grade = get_object_or_404(GradeHorario, turma=turma)
    aula = get_object_or_404(AulaHorario, grade=grade, pk=aula_id)

    if request.method == "POST":
        aula.dia = (request.POST.get("dia") or aula.dia).strip()

        inicio_raw = request.POST.get("inicio")
        fim_raw = request.POST.get("fim")

        if inicio_raw is not None:
            ini = _parse_hhmm(inicio_raw)
            if not ini:
                messages.error(request, "Início inválido. Use HH:MM.")
                return redirect("educacao:horario_aula_update", pk=turma.pk, aula_id=aula.pk)
            aula.inicio = ini

        if fim_raw is not None:
            fim = _parse_hhmm(fim_raw)
            if not fim:
                messages.error(request, "Fim inválido. Use HH:MM.")
                return redirect("educacao:horario_aula_update", pk=turma.pk, aula_id=aula.pk)
            aula.fim = fim

        aula.disciplina = (request.POST.get("disciplina") or aula.disciplina).strip()
        aula.sala = (request.POST.get("sala") or aula.sala).strip()

        if aula.fim and aula.inicio and aula.fim <= aula.inicio:
            messages.error(request, "O horário final deve ser maior que o inicial.")
            return redirect("educacao:horario_aula_update", pk=turma.pk, aula_id=aula.pk)

        aula.save()
        messages.success(request, "Horário atualizado.")
        return redirect("educacao:horario_turma", pk=turma.pk)

    return render(request, "educacao/horario_aula_form.html", {
        "turma": turma,
        "mode": "update",
        "aula": aula,
        "cancel_url": reverse("educacao:horario_turma", args=[turma.pk]),
        "action_url": reverse("educacao:horario_aula_update", args=[turma.pk, aula.pk]),
        "submit_label": "Atualizar",
        "dias": AulaHorario.Dia.choices,
    })
from datetime import time

def _parse_hhmm(value: str):
    value = (value or "").strip()
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        hh = int(parts[0])
        mm = int(parts[1])
    except ValueError:
        return None
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return time(hh, mm)


@login_required
@require_perm("educacao.manage")
def horario_gerar_padrao(request, pk: int):
    """
    Gera uma grade padrão para a turma (1 clique).
    Cria aulas SEG..SEX com horários fixos e disciplina placeholder.
    NÃO duplica se já existir aula na grade (proteção).
    """
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=pk)

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    # proteção: se já existe algo, não gera em cima
    if grade.aulas.exists():
        messages.warning(request, "Essa turma já possui aulas no horário. Apague/limpe antes de gerar novamente.")
        return redirect("educacao:horario_turma", pk=turma.pk)

    # Turnos padrão (você ajusta depois)
    # Se quiser, depois a gente cria uma tela pra escolher turno e qtd aulas.
    turnos = {
        "MANHA": [("07:30","08:20"), ("08:20","09:10"), ("09:20","10:10"), ("10:10","11:00"), ("11:00","11:50")],
        "TARDE": [("13:30","14:20"), ("14:20","15:10"), ("15:20","16:10"), ("16:10","17:00"), ("17:00","17:50")],
        "NOITE": [("18:30","19:20"), ("19:20","20:10"), ("20:20","21:10"), ("21:10","22:00")],
    }

    # tenta inferir pelo turno da Turma, senão usa MANHA
    turno = getattr(turma, "turno", None) or "MANHA"
    turno = str(turno).upper()
    blocos = turnos.get(turno, turnos["MANHA"])

    # dias (usa as choices do seu model)
    # Aqui assumo que seu AulaHorario.Dia é TextChoices e dia é string
    dias = [c[0] for c in AulaHorario.Dia.choices]
    # Queremos SEG..SEX
    dias_uteis = [d for d in dias if d in {"SEG", "TER", "QUA", "QUI", "SEX"}]
    if not dias_uteis:
        # fallback se suas siglas forem diferentes
        dias_uteis = dias[:5]

    created = 0
    for dia in dias_uteis:
        for idx, (ini_s, fim_s) in enumerate(blocos, start=1):
            ini = _parse_hhmm(ini_s)
            fim = _parse_hhmm(fim_s)
            AulaHorario.objects.create(
                grade=grade,
                dia=dia,
                inicio=ini,
                fim=fim,
                disciplina=f"Aula {idx}",
                sala="",
            )
            created += 1

    messages.success(request, f"Grade padrão gerada com sucesso ({created} aulas).")
    return redirect("educacao:horario_turma", pk=turma.pk)


@login_required
@require_perm("educacao.manage")
def horario_duplicar(request, pk: int):
    """
    Duplica o horário de uma turma ORIGEM -> turma DESTINO.
    Uso: /turmas/<destino>/horario/duplicar/?origem=<idTurmaOrigem>
    """
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma_destino = get_object_or_404(turma_qs, pk=pk)

    origem_id = (request.GET.get("origem") or "").strip()
    if not origem_id.isdigit():
        messages.error(request, "Informe a turma origem: ?origem=123")
        return redirect("educacao:horario_turma", pk=turma_destino.pk)

    turma_origem = get_object_or_404(turma_qs, pk=int(origem_id))

    grade_destino, _ = GradeHorario.objects.get_or_create(turma=turma_destino)
    grade_origem, _ = GradeHorario.objects.get_or_create(turma=turma_origem)

    if not grade_origem.aulas.exists():
        messages.error(request, "A turma origem não possui horário cadastrado.")
        return redirect("educacao:horario_turma", pk=turma_destino.pk)

    if grade_destino.aulas.exists():
        messages.warning(request, "A turma destino já possui aulas no horário. Apague/limpe antes de duplicar.")
        return redirect("educacao:horario_turma", pk=turma_destino.pk)

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
    return redirect("educacao:horario_turma", pk=turma_destino.pk)

@login_required
@require_perm("educacao.manage")
def horario_duplicar_select(request, pk: int):
    """
    Tela para selecionar uma turma origem e duplicar o horário.
    """
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria")
    )
    turma_destino = get_object_or_404(turma_qs, pk=pk)

    # destino não pode ter aulas para duplicar
    grade_destino, _ = GradeHorario.objects.get_or_create(turma=turma_destino)
    if grade_destino.aulas.exists():
        messages.warning(request, "A turma destino já possui aulas. Limpe o horário antes de duplicar.")
        return redirect("educacao:horario_turma", pk=turma_destino.pk)

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

    # mostra apenas turmas que possuem horário cadastrado
    # (grade com pelo menos uma aula)
    qs = qs.filter(grade_horario__aulas__isnull=False).distinct()

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    actions = [
        {"label": "Voltar", "url": reverse("educacao:horario_turma", args=[turma_destino.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    headers = [
        {"label": "Turma"},
        {"label": "Ano", "width": "110px"},
        {"label": "Unidade"},
        {"label": "Ação", "width": "190px"},
    ]

    rows = []
    for t in page_obj:
        rows.append({
            "cells": [
                {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                {"text": str(t.ano_letivo or "—")},
                {"text": getattr(getattr(t, "unidade", None), "nome", "—")},
                {"text": "Duplicar desta turma", "url": reverse("educacao:horario_duplicar", args=[turma_destino.pk]) + f"?origem={t.pk}"},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    extra_filters = f"""
      <div class="filter-bar__field">
        <label class="small">Ano letivo</label>
        <input name="ano" value="{ano}" placeholder="Ex.: 2026" />
      </div>
    """

    return render(request, "educacao/horario_duplicar_select.html", {
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
    })


@login_required
@require_perm("educacao.manage")
def horario_limpar(request, pk: int):
    """
    Remove todas as aulas do horário da turma (com confirmação via GET ?ok=1).
    """
    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=pk)

    grade, _ = GradeHorario.objects.get_or_create(turma=turma)

    ok = (request.GET.get("ok") or "").strip()
    if ok != "1":
        messages.warning(request, "Confirme a ação clicando novamente. (Segurança)")
        return redirect(reverse("educacao:horario_turma", args=[turma.pk]) + "?confirmar_limpar=1")

    deleted, _ = grade.aulas.all().delete()
    messages.success(request, f"Horário limpo com sucesso. ({deleted} registros removidos)")
    return redirect("educacao:horario_turma", pk=turma.pk)