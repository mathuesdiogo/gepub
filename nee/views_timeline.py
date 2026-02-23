from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.shortcuts import render

from apps.core.rbac import can
from apps.educacao.models import Matricula

from .models import AcompanhamentoNEE, AlunoNecessidade, ApoioMatricula, LaudoNEE, RecursoNEE
from .utils import get_scoped_aluno


@login_required
def timeline_unificada(request, aluno_id: int):
    aluno = get_scoped_aluno(request.user, aluno_id)

    eventos = []

    # Necessidades
    for n in AlunoNecessidade.objects.select_related("tipo").filter(aluno=aluno).order_by("-criado_em")[:50]:
        eventos.append({
            "tipo": "Necessidade",
            "data": n.criado_em.strftime("%d/%m/%Y") if getattr(n, "criado_em", None) else "",
            "titulo": n.tipo.nome,
            "descricao": (n.observacao or "").strip() or (f"CID: {n.cid}" if n.cid else ""),
            "url": reverse("nee:necessidade_detail", args=[n.pk]),
        })

    # Laudos
    for l in LaudoNEE.objects.filter(aluno=aluno).order_by("-data_emissao")[:50]:
        eventos.append({
            "tipo": "Laudo",
            "data": l.data_emissao.strftime("%d/%m/%Y"),
            "titulo": l.numero or "Laudo",
            "descricao": (l.profissional or "").strip() or (l.texto[:160] if l.texto else ""),
            "url": reverse("nee:laudo_detail", args=[l.pk]),
        })

    # Recursos
    for r in RecursoNEE.objects.filter(aluno=aluno).order_by("-id")[:50]:
        eventos.append({
            "tipo": "Recurso",
            "data": r.criado_em.strftime("%d/%m/%Y") if getattr(r, "criado_em", None) else "",
            "titulo": r.nome,
            "descricao": r.get_status_display(),
            "url": reverse("nee:recurso_detail", args=[r.pk]),
        })

    # Apoios (via matrículas)
    matriculas = Matricula.objects.filter(aluno=aluno)
    apoio_qs = ApoioMatricula.objects.select_related("matricula", "matricula__turma").filter(matricula__in=matriculas).order_by("-criado_em")[:50]
    for a in apoio_qs:
        turma = getattr(a.matricula, "turma", None)
        eventos.append({
            "tipo": "Apoio",
            "data": a.criado_em.strftime("%d/%m/%Y") if getattr(a, "criado_em", None) else "",
            "titulo": a.get_tipo_display() if hasattr(a, "get_tipo_display") else a.tipo,
            "descricao": (a.observacao or a.descricao or "").strip(),
            "url": reverse("nee:apoio_detail", args=[a.pk]),
        })

    # Acompanhamentos
    for e in AcompanhamentoNEE.objects.select_related("autor").filter(aluno=aluno).order_by("-data", "-id")[:100]:
        eventos.append({
            "tipo": "Timeline",
            "data": e.data.strftime("%d/%m/%Y"),
            "titulo": e.get_tipo_evento_display(),
            "descricao": e.descricao,
            "url": reverse("nee:acompanhamento_detail", args=[e.pk]),
        })

    # Ordena por data (string dd/mm/YYYY) é ruim; usamos chave interna
    def sort_key(ev):
        # tenta converter dd/mm/YYYY
        d = ev.get("_dt")
        return d

    # anexar dt
    from datetime import datetime
    for ev in eventos:
        dt = None
        if ev.get("data"):
            for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M"):
                try:
                    dt = datetime.strptime(ev["data"], fmt)
                    break
                except Exception:
                    continue
        ev["_dt"] = dt or datetime(1970,1,1)

    eventos.sort(key=lambda x: x["_dt"], reverse=True)
    for ev in eventos:
        ev.pop("_dt", None)

    actions = [
        {"label": "Voltar", "url": reverse("nee:aluno_hub", args=[aluno.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]
    if can(request.user, "nee.manage"):
        actions.append({"label": "Novo evento", "url": reverse("nee:acompanhamento_create", args=[aluno.pk]), "icon": "fa-solid fa-plus", "variant": "btn-primary"})

    return render(request, "nee/timeline_unificada.html", {"aluno": aluno, "eventos": eventos, "actions": actions})
