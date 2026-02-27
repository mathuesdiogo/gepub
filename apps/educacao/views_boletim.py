from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_table
from apps.core.rbac import can, scope_filter_turmas, scope_filter_alunos

from .models import Aluno, AlunoCertificado, Matricula, Turma
from .models_diario import DiarioTurma, Avaliacao, Nota


def _is_professor(user) -> bool:
    return getattr(getattr(user, "profile", None), "role", "") == "PROFESSOR"


def _can_view_turma(user, turma: Turma) -> bool:
    return scope_filter_turmas(user, Turma.objects.filter(pk=turma.pk)).exists()


@login_required
@require_perm("educacao.view")
def boletim_turma(request, pk: int):
    # pk = turma_id
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    # Diários da turma (um por professor, normalmente)
    diarios = (
        DiarioTurma.objects.select_related("professor")
        .filter(turma=turma)
        .order_by("professor__username", "-ano_letivo")
    )

    # avaliações + notas agregadas por diário
    # média ponderada = sum(nota * peso) / sum(peso)  (considerando avaliações com nota)
    alunos_qs = (
        Matricula.objects.filter(turma=turma, situacao="ATIVA")
        .select_related("aluno")
        .order_by("aluno__nome")
    )

    # monta matriz aluno -> {diario_id: media}
    boletim = []
    diarios_list = list(diarios)

    # pré-carrega avaliações e notas
    avaliacao_qs = Avaliacao.objects.filter(diario_id__in=[d.id for d in diarios_list]).only("id", "diario_id", "titulo", "peso", "data")
    aval_por_diario = {}
    for a in avaliacao_qs:
        aval_por_diario.setdefault(a.diario_id, []).append(a)

    nota_qs = Nota.objects.filter(avaliacao_id__in=[a.id for a in avaliacao_qs]).values("avaliacao_id", "aluno_id", "valor")
    notas_map = {}
    for n in nota_qs:
        notas_map[(n["avaliacao_id"], n["aluno_id"])] = n["valor"]

    def calc_media(diario_id: int, aluno_id: int):
        avals = aval_por_diario.get(diario_id, [])
        soma = Decimal("0")
        soma_pesos = Decimal("0")
        for av in avals:
            valor = notas_map.get((av.id, aluno_id), None)
            if valor is None:
                continue
            try:
                peso = Decimal(str(av.peso or 1))
            except (InvalidOperation, ValueError):
                peso = Decimal("1")
            soma += Decimal(str(valor)) * peso
            soma_pesos += peso
        if soma_pesos == 0:
            return None
        return (soma / soma_pesos).quantize(Decimal("0.01"))

    for m in alunos_qs:
        item = {"aluno": m.aluno, "medias": [], "media_geral": None}

        medias_validas = []
        for d in diarios_list:
            media = calc_media(d.id, m.aluno_id)
            item["medias"].append(media)
            if media is not None:
                medias_validas.append(media)

        if medias_validas:
            item["media_geral"] = (sum(medias_validas) / Decimal(str(len(medias_validas)))).quantize(Decimal("0.01"))

        boletim.append(item)

    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Aluno"] + [f"Prof. {getattr(d.professor, 'username', '—')}" for d in diarios_list] + ["Média Geral"]
        rows = []
        for b in boletim:
            row = [b["aluno"].nome]
            for media in b["medias"]:
                row.append(str(media) if media is not None else "—")
            row.append(str(b["media_geral"]) if b["media_geral"] is not None else "—")
            rows.append(row)

        filtros = f"Turma={turma.nome} | Ano={turma.ano_letivo} | Unidade={getattr(turma.unidade, 'nome', '-')}"
        return export_pdf_table(
            request,
            filename="boletim_turma.pdf",
            title="Boletim — Turma",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:turma_detail", args=[turma.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Imprimir PDF", "url": reverse("educacao:boletim_turma", args=[turma.pk]) + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]

    return render(request, "educacao/boletim_turma.html", {
        "turma": turma,
        "diarios": diarios_list,
        "boletim": boletim,
        "actions": actions,
    })


@login_required
@require_perm("educacao.view")
def boletim_aluno(request, pk: int, aluno_id: int):
    # pk = turma_id
    turma_qs = scope_filter_turmas(request.user, Turma.objects.select_related("unidade"))
    turma = get_object_or_404(turma_qs, pk=pk)

    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=aluno_id)

    # garante que o aluno pertence à turma (escopo + integridade)
    if not Matricula.objects.filter(turma=turma, aluno=aluno).exists():
        return HttpResponseForbidden("403 — Aluno não pertence a esta turma.")
    matricula_aluno = Matricula.objects.select_related("turma", "turma__curso").filter(turma=turma, aluno=aluno).first()
    certificados = AlunoCertificado.objects.filter(aluno=aluno, ativo=True).order_by("-data_emissao", "-id")[:8]

    diarios = DiarioTurma.objects.select_related("professor").filter(turma=turma).order_by("professor__username")
    diarios_list = list(diarios)

    avaliacao_qs = Avaliacao.objects.filter(diario_id__in=[d.id for d in diarios_list]).only("id", "diario_id", "titulo", "peso", "data")
    aval_por_diario = {}
    for a in avaliacao_qs:
        aval_por_diario.setdefault(a.diario_id, []).append(a)

    nota_qs = Nota.objects.filter(avaliacao_id__in=[a.id for a in avaliacao_qs], aluno=aluno).values("avaliacao_id", "valor")
    notas_map = {n["avaliacao_id"]: n["valor"] for n in nota_qs}

    linhas = []
    for d in diarios_list:
        avals = aval_por_diario.get(d.id, [])
        soma = Decimal("0")
        soma_pesos = Decimal("0")

        aval_rows = []
        for av in avals:
            valor = notas_map.get(av.id, None)
            aval_rows.append({
                "titulo": av.titulo,
                "peso": av.peso,
                "data": av.data,
                "nota": valor,
            })
            if valor is None:
                continue
            peso = Decimal(str(av.peso or 1))
            soma += Decimal(str(valor)) * peso
            soma_pesos += peso

        media = (soma / soma_pesos).quantize(Decimal("0.01")) if soma_pesos else None
        linhas.append({
            "diario": d,
            "avaliacoes": aval_rows,
            "media": media,
        })

    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Professor", "Avaliação", "Peso", "Data", "Nota"]
        rows = []
        for bloco in linhas:
            prof = getattr(getattr(bloco["diario"], "professor", None), "username", "—")
            if not bloco["avaliacoes"]:
                rows.append([prof, "—", "—", "—", "—"])
                continue
            for av in bloco["avaliacoes"]:
                rows.append([
                    prof,
                    av["titulo"],
                    str(av["peso"]),
                    av["data"].strftime("%d/%m/%Y") if av["data"] else "—",
                    str(av["nota"]) if av["nota"] is not None else "—",
                ])

        filtros = f"Aluno={aluno.nome} | Turma={turma.nome} | Ano={turma.ano_letivo}"
        return export_pdf_table(
            request,
            filename="boletim_aluno.pdf",
            title="Boletim — Aluno",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {"label": "Voltar", "url": reverse("educacao:boletim_turma", args=[turma.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        {"label": "Imprimir PDF", "url": reverse("educacao:boletim_aluno", args=[turma.pk, aluno.pk]) + "?export=pdf", "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
    ]

    return render(request, "educacao/boletim_aluno.html", {
        "turma": turma,
        "aluno": aluno,
        "matricula_aluno": matricula_aluno,
        "certificados": certificados,
        "linhas": linhas,
        "actions": actions,
    })
