from __future__ import annotations

# =========================================================
# NEE • HUB CLÍNICO (Aluno)
# =========================================================
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils.timezone import localdate

from apps.educacao.models import Aluno, Matricula

from .models import (
    AlunoNecessidade,
    LaudoNEE,
    RecursoNEE,
    ApoioMatricula,
    AcompanhamentoNEE,
)
from .utils import get_scoped_aluno


def _calc_idade(aluno: Aluno) -> str:
    dn = getattr(aluno, "data_nascimento", None)
    if not dn:
        return "—"
    try:
        today = localdate()
        years = today.year - dn.year - ((today.month, today.day) < (dn.month, dn.day))
        return f"{years} anos"
    except Exception:
        return "—"


@login_required
def aluno_hub(request, aluno_id: int):
    """HUB CLÍNICO NEE do aluno.

    - resumo (identificação + KPIs)
    - acesso rápido aos submódulos
    """
    aluno = get_scoped_aluno(request.user, int(aluno_id))

    # Matrícula "principal" (última) para exibir Turma/Unidade quando existir
    matricula = (
        Matricula.objects.filter(aluno=aluno)
        .select_related("turma", "turma__unidade")
        .order_by("-id")
        .first()
    )
    turma = getattr(matricula, "turma", None) if matricula else None
    unidade = getattr(turma, "unidade", None) if turma else None

    hoje = localdate()

    # KPIs / contagens
    necessidades_qs = AlunoNecessidade.objects.filter(aluno=aluno)
    necessidades_total = necessidades_qs.count()
    try:
        necessidades_ativas = necessidades_qs.filter(ativo=True).count()
    except Exception:
        necessidades_ativas = necessidades_total

    laudos_qs = LaudoNEE.objects.filter(aluno=aluno)
    laudos_total = laudos_qs.count()
    laudos_vigentes = laudos_qs.filter(validade__isnull=True).count() + laudos_qs.filter(validade__gte=hoje).count()

    recursos_qs = RecursoNEE.objects.filter(aluno=aluno)
    recursos_total = recursos_qs.count()
    recursos_ativos = recursos_qs.exclude(status="INATIVO").count()

    matriculas_ids = list(Matricula.objects.filter(aluno=aluno).values_list("id", flat=True))
    apoios_qs = ApoioMatricula.objects.filter(matricula_id__in=matriculas_ids) if matriculas_ids else ApoioMatricula.objects.none()
    apoios_total = apoios_qs.count()

    acompanhamentos_qs = AcompanhamentoNEE.objects.filter(aluno=aluno)
    acompanhamentos_total = acompanhamentos_qs.count()

    ultimo_laudo = laudos_qs.order_by("-data_emissao", "-id").first()
    ultimo_acomp = acompanhamentos_qs.order_by("-data", "-id").first()

    actions = [
        {
            "label": "Voltar",
            "url": reverse("nee:buscar_aluno"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
        {
            "label": "Abrir aluno",
            "url": reverse("educacao:aluno_detail", args=[aluno.pk]),
            "icon": "fa-solid fa-user",
            "variant": "btn--ghost",
        },
    ]

    ctx = {
        "aluno": aluno,
        "matricula": matricula,
        "turma": turma,
        "unidade": unidade,
        "idade": _calc_idade(aluno),
        "actions": actions,
        "page_title": "Hub Clínico",
        "page_subtitle": "Resumo clínico-pedagógico NEE",
        "kpis": [
            {"label": "Necessidades", "value": f"{necessidades_ativas}/{necessidades_total}", "variant": "badge--info"},
            {"label": "Laudos vigentes", "value": f"{laudos_vigentes}/{laudos_total}", "variant": "badge--success"},
            {"label": "Recursos", "value": f"{recursos_ativos}/{recursos_total}", "variant": "badge--info"},
            {"label": "Apoios", "value": str(apoios_total), "variant": "badge--info"},
            {"label": "Acompanhamentos", "value": str(acompanhamentos_total), "variant": "badge--info"},
        ],
        "ultimo_laudo": ultimo_laudo,
        "ultimo_acomp": ultimo_acomp,
        "links": [
            {"title": "Necessidades", "desc": "Tipos, CID e observações do aluno.", "url": reverse("nee:aluno_necessidades", args=[aluno.pk]), "icon": "fa-solid fa-notes-medical"},
            {"title": "Laudos", "desc": "Documentos clínicos e anexos.", "url": reverse("nee:aluno_laudos", args=[aluno.pk]), "icon": "fa-solid fa-file-medical"},
            {"title": "Recursos", "desc": "Recursos/adaptações ofertados pela escola.", "url": reverse("nee:aluno_recursos", args=[aluno.pk]), "icon": "fa-solid fa-wheelchair"},
            {"title": "Apoios", "desc": "Apoios por matrícula (AEE, cuidador etc.).", "url": reverse("nee:aluno_apoios", args=[aluno.pk]), "icon": "fa-solid fa-hands-helping"},
            {"title": "Acompanhamentos", "desc": "Registros clínico-pedagógicos.", "url": reverse("nee:aluno_acompanhamentos", args=[aluno.pk]), "icon": "fa-solid fa-clipboard-list"},
            {"title": "Timeline", "desc": "Histórico unificado do aluno.", "url": reverse("nee:aluno_timeline", args=[aluno.pk]), "icon": "fa-solid fa-clock-rotate-left"},
        ],
    }
    return render(request, "nee/aluno_hub.html", ctx)
