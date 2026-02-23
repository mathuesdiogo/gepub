
# =========================================================
# NEE • PLUS (fixed imports)
# =========================================================
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.utils.timezone import localdate

from apps.educacao.models import Matricula, Aluno
from .models import AlunoNecessidade, LaudoNEE, RecursoNEE, AcompanhamentoNEE


@login_required
def aluno_timeline(request, aluno_id: int):
    aluno = get_object_or_404(Aluno, pk=aluno_id)

    eventos = []

    for ev in AcompanhamentoNEE.objects.select_related("autor").filter(aluno=aluno).order_by("-data", "-id")[:200]:
        eventos.append({
            "data": ev.data,
            "tipo": f"NEE • {ev.get_tipo_evento_display()}",
            "titulo": (ev.descricao[:80] + "…") if len(ev.descricao) > 80 else ev.descricao,
            "descricao": ev.descricao,
            "autor": getattr(ev.autor, "get_full_name", lambda: str(ev.autor))() if ev.autor else "—",
            "url": reverse("nee:acompanhamento_detail", args=[aluno.pk, ev.pk]),
            "icon": "fa-solid fa-timeline",
        })

    for l in LaudoNEE.objects.filter(aluno=aluno).order_by("-data_emissao", "-id")[:100]:
        eventos.append({
            "data": l.data_emissao,
            "tipo": "NEE • Laudo",
            "titulo": (l.numero or "Laudo"),
            "descricao": l.texto or "—",
            "autor": l.profissional or "—",
            "url": reverse("nee:laudo_detail", args=[aluno.pk, l.pk]),
            "icon": "fa-solid fa-file-medical",
        })

    for r in RecursoNEE.objects.filter(aluno=aluno).order_by("nome")[:200]:
        eventos.append({
            "data": localdate(),
            "tipo": "NEE • Recurso",
            "titulo": r.nome,
            "descricao": r.observacao or "—",
            "autor": "—",
            "url": reverse("nee:recurso_detail", args=[aluno.pk, r.pk]),
            "icon": "fa-solid fa-screwdriver-wrench",
        })

    for n in AlunoNecessidade.objects.select_related("tipo").filter(aluno=aluno).order_by("-criado_em")[:200]:
        eventos.append({
            "data": n.criado_em.date() if getattr(n, "criado_em", None) else localdate(),
            "tipo": "NEE • Necessidade",
            "titulo": n.tipo.nome,
            "descricao": n.observacao or "—",
            "autor": "—",
            "url": reverse("nee:aluno_necessidade_detail", args=[aluno.pk, n.pk]),
            "icon": "fa-solid fa-tags",
        })

    eventos.sort(key=lambda x: (x["data"], x.get("tipo","")), reverse=True)

    actions = [
        {"label": "Voltar", "url": reverse("nee:aluno_search"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]
    return render(request, "nee/timeline_unificada.html", {"aluno": aluno, "actions": actions, "eventos": eventos})


@login_required
def relatorio_por_municipio(request):
    qs = (
        Matricula.objects
        .select_related("turma__unidade__secretaria__municipio")
        .filter(aluno__necessidades_nee__isnull=False)
        .values("turma__unidade__secretaria__municipio__nome")
        .annotate(qtd=Count("aluno", distinct=True))
        .order_by("-qtd", "turma__unidade__secretaria__municipio__nome")
    )
    rows = [{"nome": x["turma__unidade__secretaria__municipio__nome"] or "—", "qtd": x["qtd"]} for x in qs]
    actions = [{"label": "Relatórios", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    return render(request, "nee/relatorios/por_municipio.html", {"actions": actions, "rows": rows})


@login_required
def relatorio_por_unidade(request):
    qs = (
        Matricula.objects
        .select_related("turma__unidade__secretaria__municipio")
        .filter(aluno__necessidades_nee__isnull=False)
        .values("turma__unidade__secretaria__municipio__nome", "turma__unidade__nome")
        .annotate(qtd=Count("aluno", distinct=True))
        .order_by("-qtd", "turma__unidade__secretaria__municipio__nome", "turma__unidade__nome")
    )
    rows = [{
        "municipio": x["turma__unidade__secretaria__municipio__nome"] or "—",
        "unidade": x["turma__unidade__nome"] or "—",
        "qtd": x["qtd"],
    } for x in qs]
    actions = [{"label": "Relatórios", "url": reverse("nee:relatorios_index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}]
    return render(request, "nee/relatorios/por_unidade.html", {"actions": actions, "rows": rows})

@login_required
def aluno_hub(request, aluno_id: int):
    aluno = get_object_or_404(Aluno, pk=aluno_id)

    actions = [
        {"label": "Voltar para lista", "url": reverse("nee:buscar_aluno"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    return render(request, "nee/aluno_hub.html", {"aluno": aluno, "actions": actions})