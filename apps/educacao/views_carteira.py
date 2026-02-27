from __future__ import annotations

from datetime import date
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.core.decorators import require_perm
from apps.core.exports import _try_make_qr_data_uri, export_pdf_template
from apps.core.rbac import scope_filter_alunos

from .models import Aluno, CarteiraEstudantil, Matricula, MatriculaCurso

try:
    from apps.nee.models import AlunoNecessidade
except Exception:  # pragma: no cover
    AlunoNecessidade = None  # type: ignore

try:
    from apps.core.models import PortalMunicipalConfig
except Exception:  # pragma: no cover
    PortalMunicipalConfig = None  # type: ignore


def _validade_padrao() -> date:
    today = timezone.localdate()
    return date(today.year, 12, 31)


def _matricula_referencia(aluno: Aluno) -> Matricula | None:
    qs = (
        Matricula.objects.select_related(
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        )
        .filter(aluno=aluno)
        .order_by("-id")
    )
    return qs.filter(situacao=Matricula.Situacao.ATIVA).first() or qs.first()


def _montar_snapshot(aluno: Aluno, matricula: Matricula | None) -> dict:
    unidade = getattr(getattr(matricula, "turma", None), "unidade", None)
    secretaria = getattr(unidade, "secretaria", None)
    municipio = getattr(secretaria, "municipio", None)
    turma = getattr(matricula, "turma", None)

    cursos = list(
        MatriculaCurso.objects.select_related("curso")
        .filter(aluno=aluno)
        .order_by("-data_matricula", "-id")
        .values_list("curso__nome", "situacao")[:6]
    )
    cursos_resumo = [f"{nome} ({situacao.replace('_', ' ').title()})" for nome, situacao in cursos if nome]

    nee_resumo: list[str] = []
    if AlunoNecessidade is not None:
        nee_qs = (
            AlunoNecessidade.objects.select_related("tipo")
            .filter(aluno=aluno, ativo=True)
            .order_by("-id")
            .values_list("tipo__nome", flat=True)[:6]
        )
        nee_resumo = [str(nome) for nome in nee_qs if nome]

    return {
        "aluno_nome": aluno.nome,
        "nome_mae": aluno.nome_mae or "",
        "nome_pai": aluno.nome_pai or "",
        "cpf": aluno.cpf or "",
        "nis": aluno.nis or "",
        "data_nascimento": aluno.data_nascimento.strftime("%d/%m/%Y") if aluno.data_nascimento else "",
        "escola": getattr(unidade, "nome", "") or "",
        "secretaria": getattr(secretaria, "nome", "") or "",
        "municipio": getattr(municipio, "nome", "") or "",
        "turma": getattr(turma, "nome", "") or "",
        "ano_letivo": str(getattr(turma, "ano_letivo", "") or ""),
        "turno": turma.get_turno_display() if turma else "",
        "situacao_matricula": matricula.get_situacao_display() if matricula else "",
        "modalidade": turma.get_modalidade_display() if turma else "",
        "etapa": turma.get_etapa_display() if turma else "",
        "cursos_complementares": cursos_resumo,
        "possui_nee": bool(nee_resumo),
        "necessidades_especiais": nee_resumo,
    }


@login_required
@require_perm("educacao.manage")
def carteira_emitir_pdf(request, aluno_id: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=aluno_id)
    matricula = _matricula_referencia(aluno)
    snapshot = _montar_snapshot(aluno, matricula)

    carteira = (
        CarteiraEstudantil.objects.filter(aluno=aluno, matricula=matricula, ativa=True)
        .order_by("-emitida_em", "-id")
        .first()
    )
    if carteira is None:
        carteira = CarteiraEstudantil(
            aluno=aluno,
            matricula=matricula,
            emitida_por=request.user,
            validade=_validade_padrao(),
        )

    carteira.emitida_por = request.user
    carteira.validade = carteira.validade or _validade_padrao()
    carteira.dados_snapshot = snapshot
    carteira.save()

    validation_url = request.build_absolute_uri(
        reverse("educacao:carteira_verificar_public", args=[carteira.codigo_verificacao])
    )
    qr_validacao = _try_make_qr_data_uri(validation_url)

    foto_url = ""
    if getattr(aluno, "foto", None):
        try:
            foto_url = request.build_absolute_uri(aluno.foto.url)
        except Exception:
            foto_url = ""

    municipio = None
    if matricula and getattr(matricula, "turma", None):
        unidade = getattr(matricula.turma, "unidade", None)
        secretaria = getattr(unidade, "secretaria", None) if unidade else None
        municipio = getattr(secretaria, "municipio", None) if secretaria else None

    brasao_url = ""
    if municipio and PortalMunicipalConfig is not None:
        cfg = PortalMunicipalConfig.objects.filter(municipio=municipio).only("brasao").first()
        if cfg and cfg.brasao:
            try:
                brasao_url = request.build_absolute_uri(cfg.brasao.url)
            except Exception:
                brasao_url = ""

    cursos = snapshot.get("cursos_complementares") or []
    nee_labels = snapshot.get("necessidades_especiais") or []

    filename = f"carteira_estudantil_{slugify(aluno.nome) or aluno.id}.pdf"
    return export_pdf_template(
        request,
        filename=filename,
        title="Carteira Estudantil",
        template_name="educacao/pdf/carteira_estudantil.html",
        hash_payload=f"carteira|{carteira.codigo_verificacao}|{carteira.codigo_estudante}",
        context={
            "carteira": carteira,
            "aluno": aluno,
            "snapshot": snapshot,
            "foto_url": foto_url,
            "brasao_url": brasao_url,
            "validation_url": validation_url,
            "qr_validacao": qr_validacao,
            "cursos": cursos,
            "nee_labels": nee_labels,
            "possui_nee": bool(snapshot.get("possui_nee")),
            "data_emissao": timezone.localdate(),
        },
    )


def carteira_verificar_public(request, codigo=None):
    carteira = None
    busca = (request.GET.get("codigo") or "").strip()

    if codigo:
        carteira = (
            CarteiraEstudantil.objects.select_related("aluno", "matricula", "matricula__turma", "matricula__turma__unidade")
            .filter(codigo_verificacao=codigo)
            .first()
        )
    elif busca:
        try:
            codigo_uuid = UUID(busca)
        except Exception:
            codigo_uuid = None

        qs = CarteiraEstudantil.objects.select_related(
            "aluno",
            "matricula",
            "matricula__turma",
            "matricula__turma__unidade",
        )
        carteira = (
            qs.filter(codigo_verificacao=codigo_uuid).first()
            if codigo_uuid
            else qs.filter(codigo_estudante__iexact=busca).first()
        )

    status = "nao_localizada"
    if carteira:
        hoje = timezone.localdate()
        expirada = bool(carteira.validade and carteira.validade < hoje)
        if carteira.ativa and not expirada:
            status = "valida"
        elif expirada:
            status = "expirada"
        else:
            status = "inativa"

    return render(
        request,
        "educacao/carteira_validacao_publica.html",
        {
            "carteira": carteira,
            "status": status,
            "busca": busca,
            "title": "Verificação de Carteira Estudantil",
        },
    )
