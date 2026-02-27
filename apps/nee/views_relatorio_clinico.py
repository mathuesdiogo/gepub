from __future__ import annotations

from datetime import datetime

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse

from weasyprint import HTML

from .utils import get_scoped_aluno
from .models import LaudoNEE, RecursoNEE, AcompanhamentoNEE, AlunoNecessidade, PlanoClinicoNEE
from .models import ApoioMatricula


def aluno_relatorio_clinico_pdf(request: HttpRequest, aluno_id: int) -> HttpResponse:
    aluno = get_scoped_aluno(request.user, int(aluno_id))
    plano, _ = PlanoClinicoNEE.objects.get_or_create(aluno=aluno, defaults={"responsavel": request.user})

    necessidades = AlunoNecessidade.objects.select_related("tipo").filter(aluno=aluno).order_by("-ativo", "-criado_em")
    laudos = LaudoNEE.objects.filter(aluno=aluno).order_by("-data_emissao", "-id")
    recursos = RecursoNEE.objects.filter(aluno=aluno).order_by("nome")
    apoios = ApoioMatricula.objects.select_related("matricula", "matricula__turma", "matricula__turma__unidade").filter(matricula__aluno=aluno).order_by("-criado_em", "-id")
    acompanhamentos = AcompanhamentoNEE.objects.filter(aluno=aluno).order_by("-data", "-id")[:25]

    try:
        validation_url = request.build_absolute_uri(reverse("core:validar_documento"))
    except NoReverseMatch:
        validation_url = request.build_absolute_uri("/")

    ctx = {
        "title": f"NEE — Relatório Clínico ({aluno.nome})",
        "subtitle": "Plano clínico-pedagógico",
        "aluno": aluno,
        "plano": plano,
        "necessidades": necessidades,
        "laudos": laudos,
        "recursos": recursos,
        "apoios": apoios,
        "acompanhamentos": acompanhamentos,
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "printed_by": getattr(request.user, "get_full_name", lambda: str(request.user))() or str(request.user),
        "validation_code": f"ALUNO-{aluno.pk}",
        "validation_url": validation_url,
        "report_code": "NEE-ALUNO",
        "municipio_nome": getattr(getattr(getattr(request.user, "profile", None), "municipio", None), "nome", None),
        "municipio_uf": getattr(getattr(getattr(request.user, "profile", None), "municipio", None), "uf", None),
        "secretaria_nome": getattr(getattr(getattr(request.user, "profile", None), "secretaria", None), "nome", None),
        "logo_url": None,
        "qr_data_uri": None,
        "filtros": "",
    }

    html = render_to_string("nee/relatorios/pdf/aluno_clinico.html", ctx, request=request)
    pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="nee_relatorio_clinico_aluno_{aluno.pk}.pdf"'
    return resp
