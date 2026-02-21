from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import scope_filter_turmas

from .models import Turma, Matricula
from .models_periodos import PeriodoLetivo
from .models_diario import DiarioTurma, Avaliacao, Nota, Aula, Frequencia


@login_required
@require_perm("educacao.view")
def boletim_turma_periodo(request, pk: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    periodo_id = (request.GET.get("periodo") or "").strip()
    periodo = None

    periodos = PeriodoLetivo.objects.filter(ano_letivo=turma.ano_letivo, ativo=True).order_by("numero")

    if periodo_id.isdigit():
        periodo = get_object_or_404(periodos, pk=int(periodo_id))
    elif periodos.exists():
        periodo = periodos.first()

    if not periodo:
        messages.warning(request, "Cadastre pelo menos um período letivo (bimestre/trimestre) para usar o boletim por período.")
        return redirect("educacao:boletim_turma", pk=turma.pk)

    matriculas = (
        Matricula.objects.filter(turma=turma, situacao="ATIVA")
        .select_related("aluno")
        .order_by("aluno__nome")
    )
    alunos_ids = list(matriculas.values_list("aluno_id", flat=True))

    diarios = DiarioTurma.objects.select_related("professor").filter(turma=turma).order_by("professor__username")
    diarios_list = list(diarios)

    # ===== Avaliações no período =====
    avals = Avaliacao.objects.filter(
        diario_id__in=[d.id for d in diarios_list],
        data__gte=periodo.inicio,
        data__lte=periodo.fim,
    ).only("id", "diario_id", "peso")

    aval_ids = list(avals.values_list("id", flat=True))
    pesos_map = {a.id: Decimal(str(a.peso or 1)) for a in avals}

    notas = Nota.objects.filter(avaliacao_id__in=aval_ids, aluno_id__in=alunos_ids).values("avaliacao_id", "aluno_id", "valor")

    soma = {aid: Decimal("0") for aid in alunos_ids}
    soma_peso = {aid: Decimal("0") for aid in alunos_ids}

    for n in notas:
        aluno_id = n["aluno_id"]
        valor = n["valor"]
        if valor is None:
            continue
        aval_id = n["avaliacao_id"]
        try:
            peso = pesos_map.get(aval_id, Decimal("1"))
            soma[aluno_id] += Decimal(str(valor)) * peso
            soma_peso[aluno_id] += peso
        except (InvalidOperation, ValueError):
            continue

    media_map = {}
    for aluno_id in alunos_ids:
        if soma_peso[aluno_id] > 0:
            media_map[aluno_id] = (soma[aluno_id] / soma_peso[aluno_id]).quantize(Decimal("0.01"))
        else:
            media_map[aluno_id] = None

    # ===== Frequência no período =====
    aulas_ids = list(
        Aula.objects.filter(diario__turma=turma, data__gte=periodo.inicio, data__lte=periodo.fim).values_list("id", flat=True)
    )
    total_aulas = len(aulas_ids)

    presentes = {aid: 0 for aid in alunos_ids}
    freq_qs = Frequencia.objects.filter(aula_id__in=aulas_ids, aluno_id__in=alunos_ids).values("aluno_id", "status")
    for f in freq_qs:
        if f["status"] == "P":
            presentes[f["aluno_id"]] += 1

    freq_pct = {}
    for aluno_id in alunos_ids:
        if total_aulas == 0:
            freq_pct[aluno_id] = None
        else:
            freq_pct[aluno_id] = round((presentes[aluno_id] / total_aulas) * 100, 1)

    rows_data = []
    for m in matriculas:
        rows_data.append({
            "aluno": m.aluno,
            "media": media_map.get(m.aluno_id),
            "freq": freq_pct.get(m.aluno_id),
        })

    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Aluno", "Média", "Frequência (%)"]
        rows = []
        for r in rows_data:
            rows.append([
                r["aluno"].nome,
                str(r["media"]) if r["media"] is not None else "—",
                str(r["freq"]) if r["freq"] is not None else "—",
            ])

        filtros = f"Turma={turma.nome} | Ano={turma.ano_letivo} | Período={periodo} | {periodo.inicio} a {periodo.fim}"
        return export_pdf_table(
            request,
            filename="boletim_periodo.pdf",
            title="Boletim — Período",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:boletim_turma", args=[turma.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Imprimir PDF", "url": reverse("educacao:boletim_turma_periodo", args=[turma.pk]) + f"?periodo={periodo.pk}&export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]

    return render(request, "educacao/boletim_turma_periodo.html", {
        "turma": turma,
        "periodos": periodos,
        "periodo": periodo,
        "rows_data": rows_data,
        "actions": actions,
        "total_aulas": total_aulas,
    })
