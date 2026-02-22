from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.urls import reverse
from django.shortcuts import render

from apps.core.rbac import scope_filter_alunos
from apps.educacao.models import Aluno


@login_required
def aluno_search(request):
    q = (request.GET.get("q") or "").strip()

    qs = Aluno.objects.only("id", "nome", "cpf", "nis", "ativo")
    qs = scope_filter_alunos(request.user, qs).order_by("nome")
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(nis__icontains=q)
            | Q(nome_mae__icontains=q)
        )

    alunos = list(qs[:50])

    actions = [
        {"label": "Voltar", "url": reverse("nee:index"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    rows = []
    for a in alunos:
        rows.append(
            {
                "nome": a.nome,
                "cpf": a.cpf or "—",
                "nis": a.nis or "—",
                "ativo": "Sim" if getattr(a, "ativo", True) else "Não",
                "url": reverse("educacao:aluno_detail", args=[a.pk]),
            }
        )

    return render(
        request,
        "nee/aluno_search.html",
        {
            "actions": actions,
            "q": q,
            "rows": rows,
        },
    )
