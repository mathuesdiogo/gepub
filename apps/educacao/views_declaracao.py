from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Profile
from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_template
from apps.core.rbac import scope_filter_alunos, scope_filter_matriculas

from .models import Aluno, AlunoDocumento, CoordenacaoEnsino, Matricula

try:
    from apps.core.models import PortalMunicipalConfig
except Exception:  # pragma: no cover
    PortalMunicipalConfig = None  # type: ignore


def _date_extenso_ptbr(data):
    meses = [
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]
    return f"{data.day:02d} de {meses[data.month - 1]} de {data.year}"


def _matricula_referencia(user, aluno: Aluno) -> Matricula | None:
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
    qs = scope_filter_matriculas(user, qs)
    return qs.filter(situacao=Matricula.Situacao.ATIVA).first() or qs.first()


def _nome_usuario(user) -> str:
    return user.get_full_name().strip() or user.get_username()


def _resolver_gestor_unidade(unidade) -> tuple[str, str]:
    if unidade is None:
        return "Gestor(a) da unidade não informado", "Gestão Escolar"

    coordenacao = (
        CoordenacaoEnsino.objects.select_related("coordenador")
        .filter(unidade=unidade, ativo=True)
        .order_by("-inicio", "-id")
        .first()
    )
    if coordenacao and coordenacao.coordenador_id:
        return _nome_usuario(coordenacao.coordenador), "Coordenação de Ensino"

    user_model = get_user_model()
    perfis_unidade = (
        user_model.objects.select_related("profile")
        .filter(
            profile__ativo=True,
            profile__unidade=unidade,
            profile__role__in=[
                Profile.Role.EDU_DIRETOR,
                Profile.Role.UNIDADE,
                Profile.Role.EDU_COORD,
            ],
        )
        .order_by("first_name", "username")
    )
    gestor_unidade = perfis_unidade.first()
    if gestor_unidade and getattr(gestor_unidade, "profile", None):
        return _nome_usuario(gestor_unidade), gestor_unidade.profile.get_role_display()

    if unidade.secretaria_id:
        perfis_secretaria = (
            user_model.objects.select_related("profile")
            .filter(
                profile__ativo=True,
                profile__secretaria_id=unidade.secretaria_id,
                profile__role__in=[Profile.Role.EDU_SECRETARIO, Profile.Role.SECRETARIA],
            )
            .order_by("first_name", "username")
        )
        gestor_secretaria = perfis_secretaria.first()
        if gestor_secretaria and getattr(gestor_secretaria, "profile", None):
            return _nome_usuario(gestor_secretaria), gestor_secretaria.profile.get_role_display()

    return "Gestor(a) da unidade não informado", "Gestão Escolar"


@login_required
@require_perm("educacao.view")
def declaracao_vinculo_pdf(request, aluno_id: int):
    aluno = get_object_or_404(scope_filter_alunos(request.user, Aluno.objects.all()), pk=aluno_id)
    matricula = _matricula_referencia(request.user, aluno)
    matricula = matricula if matricula is not None else Matricula(aluno=aluno)

    turma = getattr(matricula, "turma", None)
    unidade = getattr(turma, "unidade", None)
    secretaria = getattr(unidade, "secretaria", None)
    municipio = getattr(secretaria, "municipio", None)

    gestor_nome, gestor_cargo = _resolver_gestor_unidade(unidade)

    status_ativa = bool(matricula and getattr(matricula, "situacao", None) == Matricula.Situacao.ATIVA and aluno.ativo)
    situacao_texto = "regularmente matriculado(a) e frequentando as aulas"
    if not status_ativa:
        status_display = matricula.get_situacao_display().lower() if getattr(matricula, "situacao", None) else "não informada"
        situacao_texto = f"matriculado(a) nesta unidade, com situação {status_display}"

    responsaveis = "genitores não informados"
    if aluno.nome_mae or aluno.nome_pai:
        mae = aluno.nome_mae or "mãe não informada"
        pai = aluno.nome_pai or "pai não informado"
        responsaveis = f"{mae} e {pai}"

    brasao_url = ""
    logo_municipio_url = ""
    if municipio and PortalMunicipalConfig is not None:
        cfg = PortalMunicipalConfig.objects.filter(municipio=municipio).only("logo", "brasao").first()
        if cfg:
            if cfg.brasao:
                try:
                    brasao_url = request.build_absolute_uri(cfg.brasao.url)
                except Exception:
                    brasao_url = ""
            if cfg.logo:
                try:
                    logo_municipio_url = request.build_absolute_uri(cfg.logo.url)
                except Exception:
                    logo_municipio_url = ""

    data_emissao = timezone.localdate()
    contexto = {
        "aluno": aluno,
        "matricula": matricula,
        "turma": turma,
        "unidade": unidade,
        "secretaria": secretaria,
        "municipio": municipio,
        "gestor_nome": gestor_nome,
        "gestor_cargo": gestor_cargo,
        "responsaveis": responsaveis,
        "situacao_texto": situacao_texto,
        "status_ativa": status_ativa,
        "data_emissao": data_emissao,
        "data_emissao_extenso": _date_extenso_ptbr(data_emissao),
        "brasao_url": brasao_url,
        "logo_municipio_url": logo_municipio_url,
    }

    filename = f"declaracao_vinculo_{slugify(aluno.nome) or aluno.id}.pdf"
    response = export_pdf_template(
        request,
        filename=filename,
        title="Declaração de Vínculo Escolar",
        template_name="educacao/pdf/declaracao_vinculo.html",
        subtitle="Documento oficial para fins escolares e administrativos",
        filtros=f"Aluno={aluno.nome} | Situação={matricula.get_situacao_display() if getattr(matricula, 'situacao', None) else 'Não informada'}",
        hash_payload=f"declaracao_vinculo|aluno:{aluno.id}|matricula:{getattr(matricula, 'id', '')}|data:{data_emissao.isoformat()}",
        context=contexto,
    )
    timestamp = timezone.localtime().strftime("%d/%m/%Y %H:%M")
    documento = AlunoDocumento(
        aluno=aluno,
        tipo=AlunoDocumento.Tipo.DECLARACAO,
        titulo=f"Declaração de vínculo escolar ({timestamp})",
        numero_documento=f"DECL-VINC-{aluno.id}-{timezone.localtime().strftime('%Y%m%d%H%M%S')}",
        data_emissao=data_emissao,
        enviado_por=request.user,
        observacao="Gerado automaticamente na emissão da declaração de vínculo.",
        ativo=True,
    )
    documento.arquivo.save(filename, ContentFile(response.content), save=False)
    documento.save()
    return response
