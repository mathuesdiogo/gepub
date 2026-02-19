from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table, export_csv
from apps.core.rbac import scope_filter_turmas

from .models import Turma, Matricula
from .models_diario import DiarioTurma, Avaliacao, Nota, Aula, Frequencia


@login_required
@require_perm("educacao.view")
def relatorio_geral_turma(request, pk: int):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    # Filtros simples por período (opcional)
    inicio = (request.GET.get("inicio") or "").strip()
    fim = (request.GET.get("fim") or "").strip()

    matriculas = (
        Matricula.objects.filter(turma=turma, situacao="ATIVA")
        .select_related("aluno")
        .order_by("aluno__nome")
    )

    alunos_ids = list(matriculas.values_list("aluno_id", flat=True))

    # ===== NOTAS (média ponderada global por aluno) =====
    diarios = DiarioTurma.objects.filter(turma=turma)
    avals = Avaliacao.objects.filter(diario__in=diarios).only("id", "peso")
    aval_ids = list(avals.values_list("id", flat=True))

    pesos_map = {a.id: Decimal(str(a.peso or 1)) for a in avals}

    notas = (
        Nota.objects.filter(avaliacao_id__in=aval_ids, aluno_id__in=alunos_ids)
        .values("avaliacao_id", "aluno_id", "valor")
    )

    soma_notas = {aid: Decimal("0") for aid in alunos_ids}
    soma_pesos = {aid: Decimal("0") for aid in alunos_ids}

    for n in notas:
        aluno_id = n["aluno_id"]
        aval_id = n["avaliacao_id"]
        valor = n["valor"]
        if valor is None:
            continue
        try:
            peso = pesos_map.get(aval_id, Decimal("1"))
            soma_notas[aluno_id] += Decimal(str(valor)) * peso
            soma_pesos[aluno_id] += peso
        except (InvalidOperation, ValueError):
            continue

    media_map = {}
    for aluno_id in alunos_ids:
        if soma_pesos[aluno_id] > 0:
            media_map[aluno_id] = (soma_notas[aluno_id] / soma_pesos[aluno_id]).quantize(Decimal("0.01"))
        else:
            media_map[aluno_id] = None

    # ===== FREQUÊNCIA (percentual por aluno) =====
    aulas_qs = Aula.objects.filter(diario__turma=turma)
    if inicio:
        aulas_qs = aulas_qs.filter(data__gte=inicio)
    if fim:
        aulas_qs = aulas_qs.filter(data__lte=fim)

    aulas_ids = list(aulas_qs.values_list("id", flat=True))

    freq_qs = (
        Frequencia.objects.filter(aula_id__in=aulas_ids, aluno_id__in=alunos_ids)
        .values("aluno_id", "status")
    )

    total_aulas = len(aulas_ids) or 0
    presentes_map = {aid: 0 for aid in alunos_ids}

    for f in freq_qs:
        # considera P = presente
        if f["status"] == "P":
            presentes_map[f["aluno_id"]] += 1

    freq_pct_map = {}
    for aluno_id in alunos_ids:
        if total_aulas == 0:
            freq_pct_map[aluno_id] = None
        else:
            freq_pct_map[aluno_id] = round((presentes_map[aluno_id] / total_aulas) * 100, 1)

    # ===== Tabela =====
    rows_data = []
    for m in matriculas:
        rows_data.append({
            "aluno": m.aluno,
            "media": media_map.get(m.aluno_id),
            "freq_pct": freq_pct_map.get(m.aluno_id),
        })

    export = (request.GET.get("export") or "").strip().lower()
    if export in ("pdf", "csv"):
        headers = ["Aluno", "Média", "Frequência (%)"]
        rows = []
        for r in rows_data:
            rows.append([
                r["aluno"].nome,
                str(r["media"]) if r["media"] is not None else "—",
                str(r["freq_pct"]) if r["freq_pct"] is not None else "—",
            ])

        filtros = f"Turma={turma.nome} | Ano={turma.ano_letivo} | Período={inicio or '-'} até {fim or '-'} | Total aulas={total_aulas}"
        if export == "csv":
            return export_csv("relatorio_turma.csv", headers, rows)

        return export_pdf_table(
            request,
            filename="relatorio_geral_turma.pdf",
            title="Relatório Geral — Turma",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:turma_detail", args=[turma.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Exportar CSV", "url": reverse("educacao:relatorio_geral_turma", args=[turma.pk]) + f"?export=csv&inicio={inicio or ''}&fim={fim or ''}", "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Imprimir PDF", "url": reverse("educacao:relatorio_geral_turma", args=[turma.pk]) + f"?export=pdf&inicio={inicio or ''}&fim={fim or ''}", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]

    return render(request, "educacao/relatorio_geral_turma.html", {
        "turma": turma,
        "rows_data": rows_data,
        "actions": actions,
        "inicio": inicio,
        "fim": fim,
        "total_aulas": total_aulas,
    })
