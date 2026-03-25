from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import role_scope_base, scope_filter_alunos, scope_filter_matriculas, scope_filter_turmas

from .models import Aluno, Matricula, Turma
from .models_beneficios import BeneficioEdital, BeneficioEditalInscricao
from .models_diario import Avaliacao, DiarioTurma, Nota
from .models_periodos import PeriodoLetivo
from .services_academico import calc_historico_resumo


def _nota_lancada_q():
    return Q(valor__isnull=False) | ~Q(conceito="")


def _resolve_aluno_by_codigo(user, codigo: str):
    code = (codigo or "").strip()
    alunos_qs = scope_filter_alunos(user, Aluno.objects.all())
    if not code:
        raise Http404("Aluno não encontrado.")

    profile_self = getattr(user, "profile", None)
    # Defesa em profundidade: perfil ALUNO só pode resolver o próprio código.
    if role_scope_base(getattr(profile_self, "role", None)) == "ALUNO":
        if not getattr(profile_self, "aluno_id", None):
            raise Http404("Aluno não encontrado.")
        aliases_aluno = {
            str(profile_self.aluno_id),
            (profile_self.codigo_acesso or "").strip().lower(),
            (getattr(user, "username", "") or "").strip().lower(),
        }
        if code.lower() not in aliases_aluno:
            raise Http404("Aluno não encontrado.")
        aluno_self = alunos_qs.filter(pk=profile_self.aluno_id).first()
        if aluno_self:
            return aluno_self, profile_self
        raise Http404("Aluno não encontrado.")

    if profile_self and getattr(profile_self, "aluno_id", None):
        aliases = {
            str(profile_self.aluno_id),
            (profile_self.codigo_acesso or "").strip().lower(),
            (getattr(user, "username", "") or "").strip().lower(),
        }
        if code.lower() in aliases:
            aluno = alunos_qs.filter(pk=profile_self.aluno_id).first()
            if aluno:
                return aluno, profile_self

    if code.isdigit():
        aluno = alunos_qs.filter(pk=int(code)).first()
        if aluno:
            return aluno, None

    profile = None
    try:
        from apps.accounts.models import Profile

        profile = (
            Profile.objects.select_related("aluno", "user")
            .filter(codigo_acesso__iexact=code, aluno__isnull=False)
            .order_by("-id")
            .first()
        )
        if not profile:
            profile = (
                Profile.objects.select_related("aluno", "user")
                .filter(user__username__iexact=code, aluno__isnull=False)
                .order_by("-id")
                .first()
            )
    except Exception:
        profile = None

    if profile and profile.aluno_id:
        aluno = alunos_qs.filter(pk=profile.aluno_id).first()
        if aluno:
            return aluno, profile

    raise Http404("Aluno não encontrado.")


def _codigo_aluno_canonico(user, aluno: Aluno) -> str:
    """Resolve o código canônico usado na rota pública de dados do aluno."""
    profile_self = getattr(user, "profile", None)
    if profile_self and getattr(profile_self, "aluno_id", None) == aluno.pk:
        return (
            (getattr(profile_self, "codigo_acesso", "") or "").strip()
            or (getattr(user, "username", "") or "").strip()
            or str(aluno.pk)
        )

    try:
        from apps.accounts.models import Profile

        profile_aluno = (
            Profile.objects.select_related("user")
            .filter(aluno_id=aluno.pk)
            .order_by("-id")
            .first()
        )
    except Exception:
        profile_aluno = None

    if profile_aluno:
        codigo = (profile_aluno.codigo_acesso or "").strip()
        if codigo:
            return codigo
        username = (getattr(getattr(profile_aluno, "user", None), "username", "") or "").strip()
        if username:
            return username

    return str(aluno.pk)


@login_required
@require_perm("educacao.view")
def portal_professor(request):
    from .views_professor_area import codigo_professor_canonico, professor_inicio

    user = request.user
    role_base = role_scope_base(getattr(getattr(user, "profile", None), "role", None))
    if role_base == "PROFESSOR":
        return professor_inicio(request, codigo=codigo_professor_canonico(user))

    diarios_qs = DiarioTurma.objects.select_related("turma", "turma__unidade", "professor").order_by("-ano_letivo", "turma__nome")
    turmas_qs = scope_filter_turmas(user, Turma.objects.all())
    diarios_qs = diarios_qs.filter(turma__in=turmas_qs)

    diarios = list(diarios_qs[:40])
    rows = []
    total_aulas = 0
    total_avaliacoes = 0
    total_pendencias = 0

    for d in diarios:
        aulas_count = d.aulas.count()
        avaliacoes_count = d.avaliacoes.count()
        total_aulas += aulas_count
        total_avaliacoes += avaliacoes_count

        pendencias = 0
        ultima_avaliacao = Avaliacao.objects.filter(diario=d).order_by("-data", "-id").first()
        if ultima_avaliacao:
            ativos = Matricula.objects.filter(turma=d.turma, situacao=Matricula.Situacao.ATIVA).count()
            lancadas = Nota.objects.filter(avaliacao=ultima_avaliacao).filter(_nota_lancada_q()).count()
            pendencias = max(ativos - lancadas, 0)
            total_pendencias += pendencias

        rows.append(
            {
                "cells": [
                    {"text": d.turma.nome, "url": reverse("educacao:diario_detail", args=[d.pk])},
                    {"text": getattr(getattr(d, "professor", None), "username", "—")},
                    {"text": str(d.ano_letivo)},
                    {"text": str(aulas_count)},
                    {"text": str(avaliacoes_count)},
                    {"text": str(pendencias)},
                    {"text": "Visualizar avaliações", "url": reverse("educacao:avaliacao_list", args=[d.pk])},
                ]
            }
        )

    actions = [
        {"label": "Diário de Classe", "url": reverse("educacao:meus_diarios"), "icon": "fa-solid fa-book", "variant": "gp-button--ghost"},
    ]

    return render(
        request,
        "educacao/portal_professor.html",
        {
            "actions": actions,
            "total_diarios": len(diarios),
            "total_aulas": total_aulas,
            "total_avaliacoes": total_avaliacoes,
            "total_pendencias": total_pendencias,
            "headers": [
                {"label": "Turma"},
                {"label": "Professor", "width": "180px"},
                {"label": "Ano", "width": "90px"},
                {"label": "Aulas", "width": "90px"},
                {"label": "Avaliações", "width": "110px"},
                {"label": "Pendências", "width": "110px"},
                {"label": "Ação", "width": "140px"},
            ],
            "rows": rows,
        },
    )


@login_required
@require_perm("educacao.view")
def portal_aluno(request, pk: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=pk)
    # Compatibilidade retroativa: rota antiga redireciona para a rota oficial.
    return redirect("educacao:aluno_meus_dados", codigo=_codigo_aluno_canonico(request.user, aluno))


def _timeline_etapas(edital: BeneficioEdital):
    status_ord = {
        BeneficioEdital.Status.RASCUNHO: 1,
        BeneficioEdital.Status.PUBLICADO: 2,
        BeneficioEdital.Status.INSCRICOES_ENCERRADAS: 3,
        BeneficioEdital.Status.EM_ANALISE: 4,
        BeneficioEdital.Status.RESULTADO_PRELIMINAR: 5,
        BeneficioEdital.Status.EM_RECURSOS: 6,
        BeneficioEdital.Status.RESULTADO_FINAL: 7,
        BeneficioEdital.Status.ENCERRADO: 8,
    }
    current = status_ord.get(edital.status, 1)
    etapas = [
        ("Publicado", edital.inscricao_inicio, 2),
        ("Inscrições encerradas", edital.inscricao_fim, 3),
        ("Análise", edital.analise_fim, 4),
        ("Resultado preliminar", edital.resultado_preliminar_data, 5),
        ("Prazo de recurso", edital.prazo_recurso_data, 6),
        ("Resultado final", edital.resultado_final_data, 7),
        ("Encerrado", None, 8),
    ]
    out = []
    for nome, data_ref, ord_idx in etapas:
        out.append(
            {
                "nome": nome,
                "data": data_ref,
                "concluida": current >= ord_idx,
                "atual": current == ord_idx,
            }
        )
    return out


@login_required
@require_perm("educacao.view")
def portal_aluno_edital_detail(request, pk: int, inscricao_id: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=pk)
    inscricao = get_object_or_404(
        BeneficioEditalInscricao.objects.select_related("edital", "edital__beneficio", "escola", "turma").prefetch_related("documentos", "recursos"),
        pk=inscricao_id,
        aluno=aluno,
    )
    edital = inscricao.edital
    dados_json = inscricao.dados_json or {}
    avaliacao = dados_json.get("avaliacao") or {}
    pendencias = avaliacao.get("pendencias_documentos") or []
    codigo_aluno = _codigo_aluno_canonico(request.user, aluno)
    hide_module_menu = role_scope_base(getattr(getattr(request.user, "profile", None), "role", None)) == "ALUNO"

    actions = [
        {"label": "Voltar aos meus dados", "url": reverse("educacao:aluno_meus_dados", args=[codigo_aluno]), "icon": "fa-solid fa-arrow-left", "variant": "gp-button--ghost"},
    ]
    return render(
        request,
        "educacao/portal_aluno_edital_detail.html",
        {
            "aluno": aluno,
            "inscricao": inscricao,
            "edital": edital,
            "actions": actions,
            "timeline_etapas": _timeline_etapas(edital),
            "avaliacao": avaliacao,
            "pendencias_documentos": pendencias,
            "hide_module_menu": hide_module_menu,
        },
    )


@login_required
@require_perm("educacao.view")
def aluno_meus_dados(request, codigo: str):
    aluno, profile_link = _resolve_aluno_by_codigo(request.user, codigo)
    code_value = (codigo or "").strip()
    max_matriculas_resumo = 8
    max_observacoes_resumo = 4

    matriculas = list(
        scope_filter_matriculas(
            request.user,
            Matricula.objects.select_related("turma", "turma__unidade", "turma__curso", "turma__matriz_curricular")
            .filter(aluno=aluno)
            .order_by("-turma__ano_letivo", "-id"),
        )
    )

    rows_matriculas = []
    medias_validas: list[Decimal] = []
    total_matriculas = len(matriculas)
    for idx, matricula in enumerate(matriculas):
        periodos = PeriodoLetivo.objects.filter(ano_letivo=matricula.turma.ano_letivo, ativo=True).order_by("numero")
        media_final, freq_final, _resultado = calc_historico_resumo(
            turma=matricula.turma,
            periodos=periodos,
            aluno_id=aluno.id,
        )
        if media_final is not None:
            try:
                medias_validas.append(Decimal(str(media_final)))
            except Exception:
                pass

        rows_matriculas.append(
            {
                "periodo": max(total_matriculas - idx, 1),
                "ano_periodo": str(matricula.turma.ano_letivo),
                "turma": matricula.turma.nome,
                "situacao": matricula.get_situacao_display(),
                "media": media_final,
                "frequencia": freq_final,
            }
        )

    ira = None
    if medias_validas:
        ira = (sum(medias_validas) / Decimal(len(medias_validas))).quantize(Decimal("0.01"))

    observacoes = [m.observacao.strip() for m in matriculas if (m.observacao or "").strip()]
    # Remove duplicidades mantendo ordem de aparição.
    observacoes = list(dict.fromkeys(observacoes))
    rows_matriculas_resumo = rows_matriculas[:max_matriculas_resumo]
    observacoes_resumo = observacoes[:max_observacoes_resumo]

    curso_ref = None
    matriz_ref = None
    if matriculas:
        curso_ref = getattr(matriculas[0].turma, "curso", None)
        matriz_ref = getattr(matriculas[0].turma, "matriz_curricular", None)

    from .models import AlunoCertificado, AlunoDocumento

    docs_count = AlunoDocumento.objects.filter(aluno=aluno, ativo=True).count()
    cert_count = AlunoCertificado.objects.filter(aluno=aluno, ativo=True).count()

    ingresso = "—"
    if matriculas:
        ingresso = f"{min(m.turma.ano_letivo for m in matriculas)}/1"

    situacao_sistemica = "Sem vínculo"
    matricula_ativa = next((m for m in matriculas if m.situacao == Matricula.Situacao.ATIVA), None)
    if matricula_ativa:
        situacao_sistemica = f"{matricula_ativa.get_situacao_display()} no GEPUB"
    elif matriculas:
        situacao_sistemica = matriculas[0].get_situacao_display()

    aluno_username = ""
    aluno_email = ""
    if profile_link and getattr(profile_link, "user", None):
        aluno_username = profile_link.user.username or ""
        aluno_email = profile_link.user.email or ""
    else:
        aluno_email = aluno.email or ""

    actions = [
        {"label": "Meu perfil", "url": reverse("accounts:meu_perfil"), "icon": "fa-solid fa-user", "variant": "gp-button--ghost"},
        {"label": "Histórico completo", "url": reverse("educacao:historico_aluno", args=[aluno.pk]), "icon": "fa-solid fa-scroll", "variant": "gp-button--ghost"},
    ]

    return render(
        request,
        "educacao/aluno_meus_dados.html",
        {
            "aluno": aluno,
            "actions": actions,
            "code_value": code_value,
            "aluno_username": aluno_username,
            "aluno_email": aluno_email,
            "rows_matriculas": rows_matriculas,
            "rows_matriculas_resumo": rows_matriculas_resumo,
            "matriculas_total": len(rows_matriculas),
            "matriculas_extra_count": max(0, len(rows_matriculas) - len(rows_matriculas_resumo)),
            "observacoes": observacoes,
            "observacoes_resumo": observacoes_resumo,
            "observacoes_total": len(observacoes),
            "observacoes_extra_count": max(0, len(observacoes) - len(observacoes_resumo)),
            "ingresso": ingresso,
            "ira": ira,
            "docs_count": docs_count,
            "cert_count": cert_count,
            "curso_ref": curso_ref,
            "matriz_ref": matriz_ref,
            "situacao_sistemica": situacao_sistemica,
            "hide_module_menu": True,
        },
    )
