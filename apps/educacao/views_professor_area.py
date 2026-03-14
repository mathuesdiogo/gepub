from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.rbac import can, role_scope_base, scope_filter_turmas

from .forms_professor_area import (
    InformaticaAvaliacaoForm,
    InformaticaPlanoEnsinoProfessorForm,
    MaterialAulaProfessorForm,
    PlanoEnsinoProfessorForm,
)
from .models import Matricula, Turma
from .models_diario import (
    AVALIACAO_CONCEITOS_CHOICES,
    Aula,
    Avaliacao,
    DiarioTurma,
    Frequencia,
    JustificativaFaltaPedido,
    MaterialAulaProfessor,
    Nota,
    PlanoEnsinoProfessor,
)
from .models_calendario import CalendarioEducacionalEvento
from .models_horarios import AulaHorario
from .models_informatica import (
    InformaticaAlertaFrequencia,
    InformaticaAulaDiario,
    InformaticaAvaliacao,
    InformaticaEncontroSemanal,
    InformaticaFrequencia,
    InformaticaMatricula,
    InformaticaNota,
    InformaticaPlanoEnsinoProfessor,
    InformaticaTurma,
)
from .models_periodos import FechamentoPeriodoTurma, PeriodoLetivo


def _clean_code(value: str | None) -> str:
    return (value or "").strip()


def _viewer_role_code(user) -> str:
    profile = getattr(user, "profile", None)
    return ((_clean_code(getattr(profile, "role", "")) or "") + "").upper()


def _is_edu_coord(user) -> bool:
    return _viewer_role_code(user) == "EDU_COORD"


def _can_edit_informatica_execucao(request_user, professor_user) -> bool:
    """Somente o professor dono do perfil/turma pode editar execução de informática."""
    profile = getattr(request_user, "profile", None)
    return (
        request_user.id == professor_user.id
        and role_scope_base(getattr(profile, "role", None)) == "PROFESSOR"
    )


def codigo_professor_canonico(user) -> str:
    profile = getattr(user, "profile", None)
    codigo = _clean_code(getattr(profile, "codigo_acesso", ""))
    if codigo:
        return codigo
    username = _clean_code(getattr(user, "username", ""))
    if username:
        return username
    return str(getattr(user, "id", ""))


def _resolve_professor_by_codigo(viewer, codigo: str):
    code = _clean_code(codigo)
    if not code:
        raise Http404("Professor não encontrado.")

    viewer_profile = getattr(viewer, "profile", None)
    viewer_base = role_scope_base(getattr(viewer_profile, "role", None))

    if viewer_base == "PROFESSOR":
        aliases = {
            str(getattr(viewer, "id", "")),
            (_clean_code(getattr(viewer, "username", ""))).lower(),
            (_clean_code(getattr(viewer_profile, "codigo_acesso", ""))).lower(),
        }
        if code.lower() not in aliases:
            raise Http404("Professor não encontrado.")
        return viewer

    User = get_user_model()
    qs = User.objects.select_related("profile")

    professor_user = None
    if code.isdigit():
        professor_user = qs.filter(pk=int(code)).first()

    if professor_user is None:
        professor_user = qs.filter(username__iexact=code).first()

    if professor_user is None:
        professor_user = qs.filter(profile__codigo_acesso__iexact=code).first()

    if professor_user is None:
        raise Http404("Professor não encontrado.")

    profile = getattr(professor_user, "profile", None)
    if role_scope_base(getattr(profile, "role", None)) != "PROFESSOR":
        raise Http404("Professor não encontrado.")

    if can(viewer, "educacao.manage"):
        return professor_user

    turmas_scope = scope_filter_turmas(viewer, Turma.objects.all())
    has_scope = DiarioTurma.objects.filter(professor=professor_user, turma__in=turmas_scope).exists()
    if not has_scope:
        raise Http404("Professor não encontrado.")

    return professor_user


def _professor_diarios_qs(viewer, professor_user):
    qs = DiarioTurma.objects.select_related(
        "turma",
        "turma__unidade",
        "turma__unidade__secretaria",
        "turma__unidade__secretaria__municipio",
        "professor",
    ).filter(professor=professor_user)

    if viewer != professor_user and not can(viewer, "educacao.manage"):
        turmas_scope = scope_filter_turmas(viewer, Turma.objects.all())
        qs = qs.filter(turma__in=turmas_scope)

    return qs.order_by("-ano_letivo", "turma__nome")


def _fmt_decimal(value) -> str:
    if value is None:
        return "—"
    try:
        num = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    return f"{num:.2f}".replace(".", ",")


def _nota_lancada_q(prefix: str = ""):
    return Q(**{f"{prefix}valor__isnull": False}) | ~Q(**{f"{prefix}conceito": ""})


def _status_badge(label: str, variant: str = "neutral") -> str:
    variant_map = {
        "success": "gp-badge--success",
        "warning": "gp-badge--warning",
        "danger": "gp-badge--danger",
        "primary": "gp-badge--primary",
        "neutral": "gp-badge--neutral",
    }
    cls = variant_map.get(variant, "gp-badge--neutral")
    return f'<span class="gp-badge {cls}">{label}</span>'


def _link_button(url: str, label: str, icon: str = "fa-solid fa-arrow-up-right-from-square") -> str:
    return (
        f'<a class="gp-button gp-button--outline" href="{url}">'
        f'<i class="{icon}" aria-hidden="true"></i>{label}</a>'
    )


def _actions_group(*buttons_html: str) -> str:
    joined = "".join(buttons_html)
    return f'<div class="gp-professor-inline-actions">{joined}</div>'


PLANO_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ("titulo", "Título do plano"),
    ("ementa", "Ementa"),
    ("objetivos", "Objetivos"),
    ("metodologia", "Metodologia"),
    ("criterios_avaliacao", "Critérios de avaliação"),
    ("cronograma", "Cronograma"),
    ("referencias", "Referências"),
)


def _plano_checklist(plano) -> dict:
    checks = []
    preenchidos = 0
    for field, label in PLANO_REQUIRED_FIELDS:
        value = getattr(plano, field, "") if plano is not None else ""
        filled = bool((value or "").strip())
        if filled:
            preenchidos += 1
        checks.append(
            {
                "field": field,
                "label": label,
                "filled": filled,
            }
        )
    total = len(checks)
    pendencias = [item["label"] for item in checks if not item["filled"]]
    percentual = int(round((preenchidos / total) * 100)) if total else 0
    return {
        "items": checks,
        "total": total,
        "filled": preenchidos,
        "missing": total - preenchidos,
        "missing_labels": pendencias,
        "percent": percentual,
        "can_submit": not pendencias,
    }


def _plano_status_meta(plano) -> dict:
    if plano is None:
        return {
            "key": "nao_iniciado",
            "label": "Não iniciado",
            "badge_class": "gp-badge--neutral",
            "chip_class": "is-neutral",
        }
    if plano.status == PlanoEnsinoProfessor.Status.SUBMETIDO:
        return {
            "key": "submetido",
            "label": "Aguardando aprovação",
            "badge_class": "gp-badge--primary",
            "chip_class": "is-primary",
        }
    if plano.status == PlanoEnsinoProfessor.Status.APROVADO:
        return {
            "key": "aprovado",
            "label": "Aguardando homologação",
            "badge_class": "gp-badge--primary",
            "chip_class": "is-primary",
        }
    if plano.status == PlanoEnsinoProfessor.Status.HOMOLOGADO:
        return {
            "key": "homologado",
            "label": "Homologado",
            "badge_class": "gp-badge--success",
            "chip_class": "is-success",
        }
    if plano.status == PlanoEnsinoProfessor.Status.DEVOLVIDO:
        return {
            "key": "devolvido",
            "label": "Devolvido para ajustes",
            "badge_class": "gp-badge--danger",
            "chip_class": "is-danger",
        }
    return {
        "key": "rascunho",
        "label": "Rascunho",
        "badge_class": "gp-badge--warning",
        "chip_class": "is-warning",
    }


def _plano_fluxo_status(plano) -> list[dict]:
    status = getattr(plano, "status", "")
    is_devolvido = status == PlanoEnsinoProfessor.Status.DEVOLVIDO
    step_submit_done = status in {
        PlanoEnsinoProfessor.Status.SUBMETIDO,
        PlanoEnsinoProfessor.Status.APROVADO,
        PlanoEnsinoProfessor.Status.HOMOLOGADO,
        PlanoEnsinoProfessor.Status.DEVOLVIDO,
    }
    step_approve_done = status in {
        PlanoEnsinoProfessor.Status.APROVADO,
        PlanoEnsinoProfessor.Status.HOMOLOGADO,
    }
    step_homolog_done = status == PlanoEnsinoProfessor.Status.HOMOLOGADO
    return [
        {
            "title": "Acesso e edição",
            "desc": "Preencha todos os campos pedagógicos do plano.",
            "state": "done" if plano else "active",
        },
        {
            "title": "Submissão",
            "desc": "Envie o plano para validação institucional.",
            "state": "done" if step_submit_done else ("active" if plano else "pending"),
        },
        {
            "title": "Aprovação da coordenação",
            "desc": "A coordenação valida o conteúdo pedagógico enviado.",
            "state": "done" if step_approve_done else ("active" if step_submit_done else "pending"),
        },
        {
            "title": "Homologação",
            "desc": "Conclusão institucional do plano para o período letivo.",
            "state": "done" if step_homolog_done else ("active" if step_approve_done else "pending"),
        },
        {
            "title": "Ajustes (quando necessário)",
            "desc": "Se devolvido, o professor ajusta e reenvia o plano.",
            "state": "active" if is_devolvido else "pending",
        },
    ]


def _build_diario_stats(diarios: list[DiarioTurma]):
    diario_ids = [d.id for d in diarios]
    turma_ids = [d.turma_id for d in diarios]
    if not diario_ids:
        return {
            "aulas": {},
            "avaliacoes": {},
            "ativos": {},
            "latest_aula": {},
            "latest_avaliacao": {},
            "notas_latest": {},
            "pendencias": {},
        }

    aulas_map = {
        row["diario_id"]: row["total"]
        for row in Aula.objects.filter(diario_id__in=diario_ids).values("diario_id").annotate(total=Count("id"))
    }
    avaliacoes_map = {
        row["diario_id"]: row["total"]
        for row in Avaliacao.objects.filter(diario_id__in=diario_ids).values("diario_id").annotate(total=Count("id"))
    }
    ativos_map = {
        row["turma_id"]: row["total"]
        for row in Matricula.objects.filter(
            turma_id__in=turma_ids,
            situacao=Matricula.Situacao.ATIVA,
        )
        .values("turma_id")
        .annotate(total=Count("id"))
    }

    latest_aula_map: dict[int, int] = {}
    for row in Aula.objects.filter(diario_id__in=diario_ids).order_by("diario_id", "-data", "-id").values("id", "diario_id"):
        latest_aula_map.setdefault(row["diario_id"], row["id"])

    latest_avaliacao_map: dict[int, int] = {}
    for row in Avaliacao.objects.filter(diario_id__in=diario_ids).order_by("diario_id", "-data", "-id").values("id", "diario_id"):
        latest_avaliacao_map.setdefault(row["diario_id"], row["id"])

    latest_avaliacao_ids = [v for v in latest_avaliacao_map.values() if v]
    notas_latest_map = {
        row["avaliacao_id"]: row["total"]
        for row in Nota.objects.filter(avaliacao_id__in=latest_avaliacao_ids)
        .filter(_nota_lancada_q())
        .values("avaliacao_id")
        .annotate(total=Count("id"))
    }

    pendencias_map: dict[int, int] = {}
    for d in diarios:
        avaliacao_id = latest_avaliacao_map.get(d.id)
        if not avaliacao_id:
            pendencias_map[d.id] = 0
            continue
        total_ativos = ativos_map.get(d.turma_id, 0)
        total_lancadas = notas_latest_map.get(avaliacao_id, 0)
        pendencias_map[d.id] = max(total_ativos - total_lancadas, 0)

    return {
        "aulas": aulas_map,
        "avaliacoes": avaliacoes_map,
        "ativos": ativos_map,
        "latest_aula": latest_aula_map,
        "latest_avaliacao": latest_avaliacao_map,
        "notas_latest": notas_latest_map,
        "pendencias": pendencias_map,
    }


def _professor_informatica_turmas_qs(professor_user):
    return (
        InformaticaTurma.objects.select_related(
            "curso",
            "laboratorio",
            "laboratorio__unidade",
            "grade_horario",
        )
        .filter(
            Q(instrutor=professor_user)
            | Q(instrutor__isnull=True, grade_horario__professor_principal=professor_user),
            status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
        )
        .order_by("-ano_letivo", "codigo")
        .distinct()
    )


def _build_informatica_stats(turmas: list[InformaticaTurma]):
    turma_ids = [t.id for t in turmas]
    if not turma_ids:
        return {
            "matriculados": {},
            "aulas_total": {},
            "aulas_realizadas": {},
            "latest_aula": {},
            "proxima_aula": {},
            "freq_totais": {},
            "freq_presentes": {},
        }

    matriculados_map = {
        row["turma_id"]: row["total"]
        for row in InformaticaMatricula.objects.filter(
            turma_id__in=turma_ids,
            status=InformaticaMatricula.Status.MATRICULADO,
        )
        .values("turma_id")
        .annotate(total=Count("id"))
    }

    aulas_total_map = {
        row["turma_id"]: row["total"]
        for row in InformaticaAulaDiario.objects.filter(turma_id__in=turma_ids)
        .values("turma_id")
        .annotate(total=Count("id"))
    }

    aulas_realizadas_map = {
        row["turma_id"]: row["total"]
        for row in InformaticaAulaDiario.objects.filter(
            turma_id__in=turma_ids,
            status=InformaticaAulaDiario.Status.REALIZADA,
        )
        .values("turma_id")
        .annotate(total=Count("id"))
    }

    latest_aula_map: dict[int, int] = {}
    for row in (
        InformaticaAulaDiario.objects.filter(turma_id__in=turma_ids)
        .order_by("turma_id", "-data_aula", "-id")
        .values("id", "turma_id")
    ):
        latest_aula_map.setdefault(row["turma_id"], row["id"])

    hoje = timezone.localdate()
    proxima_aula_map: dict[int, int] = {}
    for row in (
        InformaticaAulaDiario.objects.filter(turma_id__in=turma_ids, data_aula__gte=hoje)
        .order_by("turma_id", "data_aula", "id")
        .values("id", "turma_id")
    ):
        proxima_aula_map.setdefault(row["turma_id"], row["id"])

    freq_rows = list(
        InformaticaFrequencia.objects.filter(aula__turma_id__in=turma_ids)
        .values("aula__turma_id")
        .annotate(
            total=Count("id"),
            presentes=Count("id", filter=Q(presente=True)),
        )
    )
    freq_totais_map = {row["aula__turma_id"]: row["total"] for row in freq_rows}
    freq_presentes_map = {row["aula__turma_id"]: row["presentes"] for row in freq_rows}

    return {
        "matriculados": matriculados_map,
        "aulas_total": aulas_total_map,
        "aulas_realizadas": aulas_realizadas_map,
        "latest_aula": latest_aula_map,
        "proxima_aula": proxima_aula_map,
        "freq_totais": freq_totais_map,
        "freq_presentes": freq_presentes_map,
    }


def _professor_nav(codigo: str):
    return [
        {
            "key": "inicio",
            "label": "Início",
            "url": reverse("educacao:professor_inicio", args=[codigo]),
            "icon": "fa-solid fa-house",
        },
        {
            "key": "diarios",
            "label": "Meus Diários",
            "url": reverse("educacao:professor_diarios", args=[codigo]),
            "icon": "fa-solid fa-book",
        },
        {
            "key": "aulas",
            "label": "Aulas e Conteúdos",
            "url": reverse("educacao:professor_aulas", args=[codigo]),
            "icon": "fa-solid fa-chalkboard",
        },
        {
            "key": "frequencias",
            "label": "Presenças e Faltas",
            "url": reverse("educacao:professor_frequencias", args=[codigo]),
            "icon": "fa-solid fa-user-check",
        },
        {
            "key": "notas",
            "label": "Notas e Avaliações",
            "url": reverse("educacao:professor_notas", args=[codigo]),
            "icon": "fa-solid fa-clipboard-check",
        },
        {
            "key": "agenda",
            "label": "Agenda de Avaliações",
            "url": reverse("educacao:professor_agenda_avaliacoes", args=[codigo]),
            "icon": "fa-solid fa-calendar-check",
        },
        {
            "key": "horarios",
            "label": "Locais e Horários",
            "url": reverse("educacao:professor_horarios", args=[codigo]),
            "icon": "fa-solid fa-clock",
        },
        {
            "key": "planos",
            "label": "Plano de Ensino",
            "url": reverse("educacao:professor_planos_ensino", args=[codigo]),
            "icon": "fa-solid fa-book-open",
        },
        {
            "key": "materiais",
            "label": "Materiais de Aula",
            "url": reverse("educacao:professor_materiais", args=[codigo]),
            "icon": "fa-solid fa-folder-open",
        },
        {
            "key": "fechamento",
            "label": "Fechamento",
            "url": reverse("educacao:professor_fechamento", args=[codigo]),
            "icon": "fa-solid fa-lock",
        },
        {
            "key": "justificativas",
            "label": "Justificativas",
            "url": reverse("educacao:professor_justificativas", args=[codigo]),
            "icon": "fa-solid fa-file-signature",
        },
    ]


def _base_context(*, request, professor_user, codigo: str, page_title: str, page_subtitle: str, nav_key: str):
    display_name = professor_user.get_full_name() or professor_user.username
    actions = [
        {
            "label": "Meu perfil",
            "url": reverse("accounts:meu_perfil"),
            "icon": "fa-solid fa-user",
            "variant": "btn--ghost",
        },
        {
            "label": "Dashboard",
            "url": reverse("core:dashboard"),
            "icon": "fa-solid fa-chart-line",
            "variant": "btn--ghost",
        },
    ]
    has_regular_access = _professor_diarios_qs(request.user, professor_user).exists()
    has_informatica_access = _professor_informatica_turmas_qs(professor_user).exists()

    return {
        "hide_module_menu": True,
        "professor_user": professor_user,
        "code_value": codigo,
        "professor_nav": _professor_nav(codigo),
        "professor_nav_active": nav_key,
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "actions": actions,
        "display_name": display_name,
        "is_own_profile": request.user.id == professor_user.id,
        "has_regular_access": has_regular_access,
        "has_informatica_access": has_informatica_access,
    }


def _resolve_professor_context(request, codigo: str):
    professor_user = _resolve_professor_by_codigo(request.user, codigo)
    diarios = list(_professor_diarios_qs(request.user, professor_user)[:160])
    codigo_canonico = codigo_professor_canonico(professor_user)
    return {
        "professor_user": professor_user,
        "diarios": diarios,
        "codigo_canonico": codigo_canonico,
    }


def _status_label_pedido(status: str):
    mapping = {
        JustificativaFaltaPedido.Status.PENDENTE: ("Pendente", "warning"),
        JustificativaFaltaPedido.Status.DEFERIDO: ("Deferida", "success"),
        JustificativaFaltaPedido.Status.INDEFERIDO: ("Indeferida", "danger"),
    }
    return mapping.get(status, (status or "—", "neutral"))


@login_required
@require_perm("educacao.view")
def professor_inicio(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    diarios = ctx["diarios"]
    codigo_canonico = ctx["codigo_canonico"]
    stats = _build_diario_stats(diarios)

    total_diarios = len(diarios)
    total_turmas = len({d.turma_id for d in diarios})
    total_aulas = sum(stats["aulas"].values())
    total_avaliacoes = sum(stats["avaliacoes"].values())
    total_pendencias = sum(stats["pendencias"].values())
    hoje = timezone.localdate()
    limite_agenda = hoje + timedelta(days=14)

    diarios_ids = [d.id for d in diarios]
    pendentes_qs = (
        JustificativaFaltaPedido.objects.select_related(
            "aluno",
            "aula",
            "aula__diario",
            "aula__diario__turma",
            "aula__componente",
        )
        .filter(aula__diario_id__in=diarios_ids, status=JustificativaFaltaPedido.Status.PENDENTE)
        .order_by("-criado_em", "-id")
    )
    pendentes = list(pendentes_qs[:8])
    total_agenda_14d = (
        Avaliacao.objects.filter(diario_id__in=diarios_ids, data__gte=hoje, data__lte=limite_agenda).count()
        if diarios_ids
        else 0
    )
    total_planos_submetidos = (
        PlanoEnsinoProfessor.objects.filter(
            professor=professor_user,
            diario_id__in=diarios_ids,
            status=PlanoEnsinoProfessor.Status.SUBMETIDO,
        ).count()
        if diarios_ids
        else 0
    )
    turma_ids = [d.turma_id for d in diarios]
    total_horarios = (
        AulaHorario.objects.filter(grade__turma_id__in=turma_ids)
        .filter(Q(professor=professor_user) | Q(professor__isnull=True))
        .count()
        if turma_ids
        else 0
    )
    total_materiais_ativos = MaterialAulaProfessor.objects.filter(professor=professor_user, ativo=True).count()
    turmas_informatica_ids = list(_professor_informatica_turmas_qs(professor_user).values_list("id", flat=True))
    total_turmas_informatica = len(turmas_informatica_ids)
    total_aulas_informatica = (
        InformaticaAulaDiario.objects.filter(turma_id__in=turmas_informatica_ids).count() if turmas_informatica_ids else 0
    )
    pendencias_aulas_informatica = (
        InformaticaAulaDiario.objects.filter(
            turma_id__in=turmas_informatica_ids,
            data_aula__lte=hoje,
            encerrada=False,
        )
        .exclude(status=InformaticaAulaDiario.Status.CANCELADA)
        .count()
        if turmas_informatica_ids
        else 0
    )

    headers = [
        {"label": "Turma"},
        {"label": "Ano", "width": "90px"},
        {"label": "Aulas", "width": "90px"},
        {"label": "Avaliações", "width": "110px"},
        {"label": "Pendências", "width": "120px"},
        {"label": "Ações", "width": "420px"},
    ]
    rows = []
    for diario in diarios[:12]:
        latest_aula_id = stats["latest_aula"].get(diario.id)
        latest_avaliacao_id = stats["latest_avaliacao"].get(diario.id)
        if latest_aula_id:
            frequencia_btn = _link_button(
                reverse("educacao:aula_frequencia", args=[diario.id, latest_aula_id]),
                "Frequência",
                "fa-solid fa-user-check",
            )
        else:
            frequencia_btn = '<span class="gp-badge gp-badge--neutral">Sem aula lançada</span>'

        if latest_avaliacao_id:
            notas_btn = _link_button(
                reverse("educacao:notas_lancar", args=[latest_avaliacao_id]),
                "Lançar notas",
                "fa-solid fa-clipboard-check",
            )
        else:
            notas_btn = _link_button(
                reverse("educacao:avaliacao_list", args=[diario.id]),
                "Criar avaliação",
                "fa-solid fa-plus",
            )

        actions_html = _actions_group(
            _link_button(reverse("educacao:diario_detail", args=[diario.id]), "Abrir diário", "fa-solid fa-book-open"),
            _link_button(reverse("educacao:aula_create", args=[diario.id]), "Nova aula", "fa-solid fa-plus"),
            frequencia_btn,
            notas_btn,
        )

        rows.append(
            {
                "cells": [
                    {"text": diario.turma.nome, "url": reverse("educacao:diario_detail", args=[diario.id])},
                    {"text": str(diario.ano_letivo)},
                    {"text": str(stats["aulas"].get(diario.id, 0))},
                    {"text": str(stats["avaliacoes"].get(diario.id, 0))},
                    {
                        "html": _status_badge(
                            str(stats["pendencias"].get(diario.id, 0)),
                            "warning" if stats["pendencias"].get(diario.id, 0) else "success",
                        )
                    },
                    {"html": actions_html},
                ]
            }
        )

    quick_links_docencia = [
        {
            "label": "Meus diários",
            "url": reverse("educacao:professor_diarios", args=[codigo_canonico]),
            "icon": "fa-solid fa-book",
        },
        {
            "label": "Lançar presença",
            "url": reverse("educacao:professor_frequencias", args=[codigo_canonico]),
            "icon": "fa-solid fa-user-check",
        },
        {
            "label": "Lançar notas",
            "url": reverse("educacao:professor_notas", args=[codigo_canonico]),
            "icon": "fa-solid fa-clipboard-check",
        },
        {
            "label": "Fechar diário",
            "url": reverse("educacao:professor_fechamento", args=[codigo_canonico]),
            "icon": "fa-solid fa-lock",
        },
        {
            "label": "Agenda de avaliações",
            "url": reverse("educacao:professor_agenda_avaliacoes", args=[codigo_canonico]),
            "icon": "fa-solid fa-calendar-check",
        },
        {
            "label": "Locais e horários",
            "url": reverse("educacao:professor_horarios", args=[codigo_canonico]),
            "icon": "fa-solid fa-clock",
        },
        {
            "label": "Plano de ensino",
            "url": reverse("educacao:professor_planos_ensino", args=[codigo_canonico]),
            "icon": "fa-solid fa-book-open",
        },
        {
            "label": "Materiais de aula",
            "url": reverse("educacao:professor_materiais", args=[codigo_canonico]),
            "icon": "fa-solid fa-folder-open",
        },
    ]

    quick_links_informatica = []
    if InformaticaTurma.objects.filter(
        instrutor=professor_user,
        status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
    ).exists():
        quick_links_informatica.extend(
            [
                {
                    "label": "Agenda de Informática",
                    "url": reverse("educacao:informatica_professor_agenda"),
                    "icon": "fa-solid fa-laptop-code",
                },
                {
                    "label": "Novo aluno (Informática)",
                    "url": reverse("educacao:informatica_aluno_create"),
                    "icon": "fa-solid fa-user-plus",
                },
                {
                    "label": "Matrícula (Informática)",
                    "url": reverse("educacao:informatica_matricula_create"),
                    "icon": "fa-solid fa-id-card",
                },
            ]
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Painel do Professor",
            page_subtitle="Lançamento de aulas, presença, notas e fechamento de diário.",
            nav_key="inicio",
        ),
        "metricas": [
            {"label": "Diários", "value": total_diarios},
            {"label": "Turmas", "value": total_turmas},
            {"label": "Aulas lançadas", "value": total_aulas},
            {"label": "Avaliações", "value": total_avaliacoes},
            {"label": "Pendências de nota", "value": total_pendencias},
            {"label": "Agenda (14 dias)", "value": total_agenda_14d},
            {"label": "Horários", "value": total_horarios},
            {"label": "Planos submetidos", "value": total_planos_submetidos},
            {"label": "Materiais ativos", "value": total_materiais_ativos},
            {"label": "Turmas de informática", "value": total_turmas_informatica},
            {"label": "Aulas de informática", "value": total_aulas_informatica},
            {"label": "Pendências informática", "value": pendencias_aulas_informatica},
        ],
        "headers_diarios": headers,
        "rows_diarios": rows,
        "pendentes": pendentes,
        "total_justificativas_pendentes": pendentes_qs.count(),
        "quick_links_docencia": quick_links_docencia,
        "quick_links_informatica": quick_links_informatica,
    }
    return render(request, "educacao/professor_area/inicio.html", context)


@login_required
@require_perm("educacao.view")
def professor_diarios(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios_all = ctx["diarios"]
    stats = _build_diario_stats(diarios_all)

    q = _clean_code(request.GET.get("q"))
    ano_filtro = _clean_code(request.GET.get("ano"))
    diarios = diarios_all
    if q:
        ql = q.lower()
        diarios = [
            d
            for d in diarios_all
            if ql in (d.turma.nome or "").lower()
            or ql in (getattr(getattr(d.turma, "unidade", None), "nome", "").lower())
            or ql in str(getattr(d, "ano_letivo", "")).lower()
        ]
    if ano_filtro.isdigit():
        diarios = [d for d in diarios if int(getattr(d, "ano_letivo", 0)) == int(ano_filtro)]

    anos_disponiveis = sorted({str(getattr(d, "ano_letivo", "")) for d in diarios_all if getattr(d, "ano_letivo", None)}, reverse=True)

    headers = [
        {"label": "Turma"},
        {"label": "Unidade"},
        {"label": "Ano", "width": "90px"},
        {"label": "Aulas", "width": "90px"},
        {"label": "Avaliações", "width": "110px"},
        {"label": "Pendências", "width": "120px"},
        {"label": "Ações", "width": "400px"},
    ]

    rows = []
    for diario in diarios:
        latest_aula_id = stats["latest_aula"].get(diario.id)
        latest_avaliacao_id = stats["latest_avaliacao"].get(diario.id)
        buttons = [
            _link_button(reverse("educacao:diario_detail", args=[diario.id]), "Acessar diário", "fa-solid fa-book-open"),
            _link_button(reverse("educacao:aula_create", args=[diario.id]), "Nova aula", "fa-solid fa-plus"),
            _link_button(reverse("educacao:avaliacao_list", args=[diario.id]), "Avaliações", "fa-solid fa-list-check"),
        ]
        if latest_aula_id:
            buttons.append(
                _link_button(
                    reverse("educacao:aula_frequencia", args=[diario.id, latest_aula_id]),
                    "Frequência",
                    "fa-solid fa-user-check",
                )
            )
        if latest_avaliacao_id:
            buttons.append(
                _link_button(
                    reverse("educacao:notas_lancar", args=[latest_avaliacao_id]),
                    "Notas",
                    "fa-solid fa-clipboard-check",
                )
            )
        rows.append(
            {
                "cells": [
                    {"text": diario.turma.nome, "url": reverse("educacao:diario_detail", args=[diario.id])},
                    {"text": getattr(getattr(diario.turma, "unidade", None), "nome", "—")},
                    {"text": str(diario.ano_letivo)},
                    {"text": str(stats["aulas"].get(diario.id, 0))},
                    {"text": str(stats["avaliacoes"].get(diario.id, 0))},
                    {
                        "html": _status_badge(
                            str(stats["pendencias"].get(diario.id, 0)),
                            "warning" if stats["pendencias"].get(diario.id, 0) else "success",
                        )
                    },
                    {"html": _actions_group(*buttons)},
                ]
            }
        )

    turmas_informatica_all = list(_professor_informatica_turmas_qs(professor_user))
    turmas_informatica = turmas_informatica_all
    if q:
        ql = q.lower()
        turmas_informatica = [
            t
            for t in turmas_informatica_all
            if ql in (t.codigo or "").lower()
            or ql in (t.nome or "").lower()
            or ql in (t.curso.nome or "").lower()
        ]
    info_stats = _build_informatica_stats(turmas_informatica)
    headers_informatica = [
        {"label": "Turma (Informática)"},
        {"label": "Curso"},
        {"label": "Unidade"},
        {"label": "Aulas", "width": "90px"},
        {"label": "Matriculados", "width": "110px"},
        {"label": "Ações", "width": "380px"},
    ]
    rows_informatica = []
    for turma in turmas_informatica:
        url_diario = reverse("educacao:informatica_turma_detail", args=[turma.id])
        url_aulas = reverse("educacao:informatica_frequencia") + f"?turma={turma.id}"
        proxima_aula_id = info_stats["proxima_aula"].get(turma.id)
        latest_aula_id = info_stats["latest_aula"].get(turma.id)

        botoes = [
            _link_button(url_diario, "Abrir diário", "fa-solid fa-book-open"),
            _link_button(
                reverse("educacao:informatica_aula_update", args=[proxima_aula_id])
                if proxima_aula_id
                else url_aulas,
                "Lançar aula",
                "fa-solid fa-plus",
            ),
            _link_button(
                reverse("educacao:informatica_frequencia_aula", args=[latest_aula_id])
                if latest_aula_id
                else url_aulas,
                "Frequência",
                "fa-solid fa-user-check",
            ),
        ]
        rows_informatica.append(
            {
                "cells": [
                    {"text": turma.codigo, "url": url_diario},
                    {"text": turma.curso.nome},
                    {"text": getattr(getattr(turma, "laboratorio", None), "unidade", None).nome if getattr(turma, "laboratorio", None) and getattr(turma.laboratorio, "unidade", None) else "—"},
                    {"text": str(info_stats["aulas_total"].get(turma.id, 0))},
                    {"text": str(info_stats["matriculados"].get(turma.id, 0))},
                    {"html": _actions_group(*botoes)},
                ]
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Meus Diários",
            page_subtitle="Acesse os diários regulares e também as turmas do Curso de Informática.",
            nav_key="diarios",
        ),
        "q": q,
        "ano_filtro": ano_filtro,
        "anos_disponiveis": anos_disponiveis,
        "headers": headers,
        "rows": rows,
        "total_diarios": len(diarios),
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
        "total_diarios_informatica": len(rows_informatica),
    }
    return render(request, "educacao/professor_area/diarios.html", context)


@login_required
@require_perm("educacao.view")
def professor_aulas(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]

    diario_ids = [d.id for d in diarios]
    q = _clean_code(request.GET.get("q"))

    aulas_qs = Aula.objects.select_related("diario", "diario__turma", "componente", "periodo").filter(diario_id__in=diario_ids)
    if q:
        aulas_qs = aulas_qs.filter(
            Q(diario__turma__nome__icontains=q)
            | Q(conteudo__icontains=q)
            | Q(componente__nome__icontains=q)
        )
    aulas = list(aulas_qs.order_by("-data", "-id")[:120])

    aula_ids = [a.id for a in aulas]
    freq_totals = {
        row["aula_id"]: row["total"]
        for row in Frequencia.objects.filter(aula_id__in=aula_ids)
        .values("aula_id")
        .annotate(total=Count("id"))
    }

    headers = [
        {"label": "Data", "width": "110px"},
        {"label": "Turma"},
        {"label": "Componente", "width": "220px"},
        {"label": "Período", "width": "120px"},
        {"label": "Conteúdo"},
        {"label": "Registros", "width": "100px"},
        {"label": "Ações", "width": "260px"},
    ]
    rows = []
    for aula in aulas:
        rows.append(
            {
                "cells": [
                    {"text": aula.data.strftime("%d/%m/%Y") if aula.data else "—"},
                    {"text": getattr(getattr(aula.diario, "turma", None), "nome", "—")},
                    {"text": str(aula.componente) if aula.componente else "—"},
                    {"text": str(aula.periodo) if aula.periodo else "—"},
                    {"text": (aula.conteudo or "—")[:140]},
                    {"text": str(freq_totals.get(aula.id, 0))},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:aula_frequencia", args=[aula.diario_id, aula.id]),
                                "Presenças",
                                "fa-solid fa-user-check",
                            ),
                            _link_button(
                                reverse("educacao:aula_update", args=[aula.diario_id, aula.id]),
                                "Editar",
                                "fa-solid fa-pen",
                            ),
                        )
                    },
                ]
            }
        )

    diarios_links = [
        {
            "turma": d.turma.nome,
            "ano": d.ano_letivo,
            "url_nova_aula": reverse("educacao:aula_create", args=[d.id]),
            "url_diario": reverse("educacao:diario_detail", args=[d.id]),
        }
        for d in diarios[:12]
    ]

    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    info_stats = _build_informatica_stats(turmas_informatica)
    informatica_turmas_links = [
        {
            "turma": t.codigo,
            "ano": t.ano_letivo,
            "url_diario": reverse("educacao:informatica_turma_detail", args=[t.id]),
            "url_aulas": reverse("educacao:informatica_frequencia") + f"?turma={t.id}",
            "url_lancar_aula": (
                reverse("educacao:informatica_aula_update", args=[info_stats["proxima_aula"].get(t.id)])
                if info_stats["proxima_aula"].get(t.id)
                else reverse("educacao:informatica_frequencia") + f"?turma={t.id}"
            ),
        }
        for t in turmas_informatica[:12]
    ]

    hoje = timezone.localdate()
    aulas_info_qs = (
        InformaticaAulaDiario.objects.select_related("turma", "encontro")
        .filter(
            turma_id__in=[t.id for t in turmas_informatica],
            encerrada=False,
            data_aula__lte=hoje,
        )
        .exclude(status=InformaticaAulaDiario.Status.CANCELADA)
    )
    if q:
        aulas_info_qs = aulas_info_qs.filter(
            Q(turma__codigo__icontains=q)
            | Q(conteudo_ministrado__icontains=q)
            | Q(atividade_realizada__icontains=q)
        )
    aulas_info = list(aulas_info_qs.order_by("-data_aula", "-id")[:120])
    aulas_info_ids = [a.id for a in aulas_info]
    freq_info_totais = {
        row["aula_id"]: row["total"]
        for row in InformaticaFrequencia.objects.filter(aula_id__in=aulas_info_ids)
        .values("aula_id")
        .annotate(total=Count("id"))
    }
    headers_informatica = [
        {"label": "Data", "width": "110px"},
        {"label": "Turma (Informática)"},
        {"label": "Encontro", "width": "190px"},
        {"label": "Conteúdo"},
        {"label": "Registros", "width": "100px"},
        {"label": "Ações", "width": "260px"},
    ]
    rows_informatica = []
    for aula in aulas_info:
        encontro_txt = "—"
        if aula.encontro:
            encontro_txt = (
                f"{aula.encontro.get_dia_semana_display()} "
                f"{aula.encontro.hora_inicio.strftime('%H:%M')}-{aula.encontro.hora_fim.strftime('%H:%M')}"
            )
        rows_informatica.append(
            {
                "cells": [
                    {"text": aula.data_aula.strftime("%d/%m/%Y") if aula.data_aula else "—"},
                    {"text": aula.turma.codigo},
                    {"text": encontro_txt},
                    {"text": ((aula.conteudo_ministrado or aula.atividade_realizada or "—")[:140])},
                    {"text": str(freq_info_totais.get(aula.id, 0))},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:informatica_frequencia_aula", args=[aula.id]),
                                "Presenças",
                                "fa-solid fa-user-check",
                            ),
                            _link_button(
                                reverse("educacao:informatica_aula_update", args=[aula.id]),
                                "Editar",
                                "fa-solid fa-pen",
                            ),
                        )
                    },
                ]
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Aulas e Conteúdos",
            page_subtitle="Registre conteúdo por aula no regular e no Curso de Informática.",
            nav_key="aulas",
        ),
        "q": q,
        "headers": headers,
        "rows": rows,
        "diarios_links": diarios_links,
        "informatica_turmas_links": informatica_turmas_links,
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
    }
    return render(request, "educacao/professor_area/aulas.html", context)


@login_required
@require_perm("educacao.view")
def professor_frequencias(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]

    diario_ids = [d.id for d in diarios]
    q = _clean_code(request.GET.get("q"))

    aulas_qs = Aula.objects.select_related("diario", "diario__turma", "componente").filter(diario_id__in=diario_ids)
    if q:
        aulas_qs = aulas_qs.filter(
            Q(diario__turma__nome__icontains=q)
            | Q(componente__nome__icontains=q)
            | Q(conteudo__icontains=q)
        )
    aulas = list(aulas_qs.order_by("-data", "-id")[:120])

    aula_ids = [a.id for a in aulas]
    status_counts = {}
    for row in Frequencia.objects.filter(aula_id__in=aula_ids).values("aula_id", "status").annotate(total=Count("id")):
        status_counts.setdefault(row["aula_id"], {})[row["status"]] = row["total"]

    headers = [
        {"label": "Data", "width": "110px"},
        {"label": "Turma"},
        {"label": "Componente", "width": "220px"},
        {"label": "Presenças", "width": "110px"},
        {"label": "Faltas", "width": "100px"},
        {"label": "Justificadas", "width": "120px"},
        {"label": "Ações", "width": "210px"},
    ]

    rows = []
    for aula in aulas:
        counts = status_counts.get(aula.id, {})
        presentes = counts.get(Frequencia.Status.PRESENTE, 0)
        faltas = counts.get(Frequencia.Status.FALTA, 0)
        justificadas = counts.get(Frequencia.Status.JUSTIFICADA, 0)

        rows.append(
            {
                "cells": [
                    {"text": aula.data.strftime("%d/%m/%Y") if aula.data else "—"},
                    {"text": getattr(getattr(aula.diario, "turma", None), "nome", "—")},
                    {"text": str(aula.componente) if aula.componente else "—"},
                    {"text": str(presentes)},
                    {
                        "html": _status_badge(str(faltas), "warning" if faltas else "success"),
                    },
                    {"text": str(justificadas)},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:aula_frequencia", args=[aula.diario_id, aula.id]),
                                "Lançar presença",
                                "fa-solid fa-user-check",
                            ),
                        )
                    },
                ]
            }
        )

    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    aulas_info_qs = InformaticaAulaDiario.objects.select_related("turma", "encontro").filter(
        turma_id__in=[t.id for t in turmas_informatica]
    )
    if q:
        aulas_info_qs = aulas_info_qs.filter(
            Q(turma__codigo__icontains=q)
            | Q(conteudo_ministrado__icontains=q)
            | Q(atividade_realizada__icontains=q)
        )
    aulas_info = list(aulas_info_qs.order_by("-data_aula", "-id")[:120])
    aulas_info_ids = [a.id for a in aulas_info]
    info_freq_rows = list(
        InformaticaFrequencia.objects.filter(aula_id__in=aulas_info_ids)
        .values("aula_id")
        .annotate(
            total=Count("id"),
            presentes=Count("id", filter=Q(presente=True)),
        )
    )
    info_freq_map = {row["aula_id"]: row for row in info_freq_rows}
    headers_informatica = [
        {"label": "Data", "width": "110px"},
        {"label": "Turma (Informática)"},
        {"label": "Encontro", "width": "190px"},
        {"label": "Presenças", "width": "110px"},
        {"label": "Faltas", "width": "100px"},
        {"label": "Ações", "width": "210px"},
    ]
    rows_informatica = []
    for aula in aulas_info:
        stat = info_freq_map.get(aula.id, {})
        total = int(stat.get("total", 0))
        presentes = int(stat.get("presentes", 0))
        faltas = max(total - presentes, 0)
        encontro_txt = "—"
        if aula.encontro:
            encontro_txt = (
                f"{aula.encontro.get_dia_semana_display()} "
                f"{aula.encontro.hora_inicio.strftime('%H:%M')}-{aula.encontro.hora_fim.strftime('%H:%M')}"
            )
        rows_informatica.append(
            {
                "cells": [
                    {"text": aula.data_aula.strftime("%d/%m/%Y") if aula.data_aula else "—"},
                    {"text": aula.turma.codigo},
                    {"text": encontro_txt},
                    {"text": str(presentes)},
                    {"html": _status_badge(str(faltas), "warning" if faltas else "success")},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:informatica_frequencia_aula", args=[aula.id]),
                                "Lançar presença",
                                "fa-solid fa-user-check",
                            ),
                        )
                    },
                ]
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Presenças e Faltas",
            page_subtitle="Controle de frequência por aula no regular e no Curso de Informática.",
            nav_key="frequencias",
        ),
        "q": q,
        "headers": headers,
        "rows": rows,
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
    }
    return render(request, "educacao/professor_area/frequencias.html", context)


@login_required
@require_perm("educacao.view")
def professor_notas(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]

    diario_ids = [d.id for d in diarios]
    diarios_by_id = {d.id: d for d in diarios}

    q = _clean_code(request.GET.get("q"))
    avaliacoes_qs = Avaliacao.objects.select_related("diario", "diario__turma", "periodo").filter(diario_id__in=diario_ids)
    if q:
        avaliacoes_qs = avaliacoes_qs.filter(
            Q(titulo__icontains=q)
            | Q(diario__turma__nome__icontains=q)
            | Q(periodo__nome__icontains=q)
        )
    avaliacoes = list(avaliacoes_qs.order_by("-data", "-id")[:160])

    avaliacao_ids = [a.id for a in avaliacoes]
    notas_stats = {
        row["avaliacao_id"]: row
        for row in Nota.objects.filter(avaliacao_id__in=avaliacao_ids)
        .values("avaliacao_id")
        .annotate(
            lancadas=Count("id", filter=_nota_lancada_q()),
            media=Avg("valor"),
        )
    }

    ativos_por_turma = {
        row["turma_id"]: row["total"]
        for row in Matricula.objects.filter(
            turma_id__in=[d.turma_id for d in diarios],
            situacao=Matricula.Situacao.ATIVA,
        )
        .values("turma_id")
        .annotate(total=Count("id"))
    }

    headers = [
        {"label": "Data", "width": "110px"},
        {"label": "Turma"},
        {"label": "Instrumento", "width": "170px"},
        {"label": "Avaliação"},
        {"label": "Período", "width": "140px"},
        {"label": "Modo", "width": "95px"},
        {"label": "Lançadas", "width": "90px"},
        {"label": "Pendências", "width": "100px"},
        {"label": "Média", "width": "90px"},
        {"label": "Ações", "width": "360px"},
    ]

    rows = []
    for av in avaliacoes:
        diario = diarios_by_id.get(av.diario_id)
        total_ativos = ativos_por_turma.get(getattr(diario, "turma_id", None), 0)
        stat = notas_stats.get(av.id, {})
        total_lancadas = stat.get("lancadas", 0)
        pendencias = max(total_ativos - total_lancadas, 0)
        media = stat.get("media")
        rows.append(
            {
                "cells": [
                    {"text": av.data.strftime("%d/%m/%Y") if av.data else "—"},
                    {"text": getattr(getattr(av.diario, "turma", None), "nome", "—")},
                    {"text": f"{(av.sigla or '').upper()} • {av.get_tipo_display()}" if av.sigla else av.get_tipo_display()},
                    {"text": av.titulo},
                    {"text": str(av.periodo) if av.periodo else "—"},
                    {"text": av.get_modo_registro_display()},
                    {"text": str(total_lancadas)},
                    {
                        "html": _status_badge(str(pendencias), "warning" if pendencias else "success"),
                    },
                    {"text": _fmt_decimal(media) if media is not None else "—"},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:notas_lancar", args=[av.id]),
                                "Registrar conceitos" if av.modo_registro == "CONCEITO" else "Lançar notas",
                                "fa-solid fa-clipboard-check",
                            ),
                            _link_button(reverse("educacao:avaliacao_update", args=[av.diario_id, av.id]), "Configurar", "fa-solid fa-sliders"),
                            _link_button(reverse("educacao:avaliacao_list", args=[av.diario_id]), "Avaliações", "fa-solid fa-list-check"),
                        )
                    },
                ]
            }
        )

    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    info_stats = _build_informatica_stats(turmas_informatica)
    turmas_info_ids = [t.id for t in turmas_informatica]
    avaliacoes_info_qs = InformaticaAvaliacao.objects.filter(turma_id__in=turmas_info_ids)
    avaliacoes_info = list(avaliacoes_info_qs.order_by("turma_id", "-data", "-id"))
    modo_info_map = {a.id: a.modo_registro for a in avaliacoes_info}
    avaliacoes_totais_map = {
        row["turma_id"]: row["total"]
        for row in InformaticaAvaliacao.objects.filter(turma_id__in=turmas_info_ids)
        .values("turma_id")
        .annotate(total=Count("id"))
    }
    latest_avaliacao_map: dict[int, int] = {}
    for row in avaliacoes_info:
        latest_avaliacao_map.setdefault(row.turma_id, row.id)
    notas_info_rows = list(
        InformaticaNota.objects.filter(avaliacao_id__in=[a.id for a in avaliacoes_info])
        .filter(_nota_lancada_q())
        .values("avaliacao_id")
        .annotate(total=Count("id"), media=Avg("valor"))
    )
    notas_totais_map = {row["avaliacao_id"]: row["total"] for row in notas_info_rows}
    notas_media_map = {row["avaliacao_id"]: row["media"] for row in notas_info_rows}

    headers_informatica = [
        {"label": "Turma (Informática)"},
        {"label": "Curso"},
        {"label": "Alunos", "width": "90px"},
        {"label": "Avaliações", "width": "100px"},
        {"label": "Pendências", "width": "110px"},
        {"label": "Média atual", "width": "100px"},
        {"label": "Ações", "width": "360px"},
    ]
    rows_informatica = []
    for turma in turmas_informatica:
        latest_aula_id = info_stats["latest_aula"].get(turma.id)
        latest_avaliacao_id = latest_avaliacao_map.get(turma.id)
        total_alunos = int(info_stats["matriculados"].get(turma.id, 0))
        total_lancadas = int(notas_totais_map.get(latest_avaliacao_id, 0)) if latest_avaliacao_id else 0
        pendencias = max(total_alunos - total_lancadas, 0) if latest_avaliacao_id else 0
        media_atual = notas_media_map.get(latest_avaliacao_id) if latest_avaliacao_id else None
        rows_informatica.append(
            {
                "cells": [
                    {"text": turma.codigo, "url": reverse("educacao:informatica_turma_detail", args=[turma.id])},
                    {"text": turma.curso.nome},
                    {"text": str(total_alunos)},
                    {"text": str(avaliacoes_totais_map.get(turma.id, 0))},
                    {"html": _status_badge(str(pendencias), "warning" if pendencias else "success")},
                    {"text": _fmt_decimal(media_atual) if media_atual is not None else "—"},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:professor_informatica_avaliacoes", args=[codigo_canonico, turma.id]),
                                "Avaliações",
                                "fa-solid fa-list-check",
                            ),
                            _link_button(
                                reverse(
                                    "educacao:professor_informatica_notas_lancar",
                                    args=[codigo_canonico, latest_avaliacao_id],
                                )
                                if latest_avaliacao_id
                                else reverse("educacao:professor_informatica_avaliacoes", args=[codigo_canonico, turma.id]),
                                "Registrar conceitos"
                                if latest_avaliacao_id and modo_info_map.get(latest_avaliacao_id) == "CONCEITO"
                                else "Lançar notas",
                                "fa-solid fa-clipboard-check",
                            ),
                            _link_button(
                                reverse("educacao:informatica_frequencia_aula", args=[latest_aula_id])
                                if latest_aula_id
                                else reverse("educacao:informatica_frequencia") + f"?turma={turma.id}",
                                "Frequência",
                                "fa-solid fa-user-check",
                            ),
                        )
                    },
                ]
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Notas e Avaliações",
            page_subtitle="Lance notas no regular e acompanhe o desempenho/frequência das turmas de Informática.",
            nav_key="notas",
        ),
        "q": q,
        "headers": headers,
        "rows": rows,
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
    }
    return render(request, "educacao/professor_area/notas.html", context)


def _parse_date_param(value: str | None):
    raw = _clean_code(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


@login_required
@require_perm("educacao.view")
def professor_agenda_avaliacoes(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]

    diario_ids = [d.id for d in diarios]
    diarios_by_id = {d.id: d for d in diarios}
    q = _clean_code(request.GET.get("q"))
    data_inicio = _parse_date_param(request.GET.get("inicio"))
    data_fim = _parse_date_param(request.GET.get("fim"))
    somente_pendentes = (_clean_code(request.GET.get("pendentes")) or "").lower() in {"1", "true", "on", "sim"}

    avaliacoes_qs = Avaliacao.objects.select_related("diario", "diario__turma", "periodo").filter(diario_id__in=diario_ids)
    if q:
        avaliacoes_qs = avaliacoes_qs.filter(
            Q(titulo__icontains=q)
            | Q(diario__turma__nome__icontains=q)
            | Q(periodo__nome__icontains=q)
        )
    if data_inicio:
        avaliacoes_qs = avaliacoes_qs.filter(data__gte=data_inicio)
    if data_fim:
        avaliacoes_qs = avaliacoes_qs.filter(data__lte=data_fim)

    avaliacoes = list(avaliacoes_qs.order_by("data", "id")[:220])
    avaliacao_ids = [a.id for a in avaliacoes]
    notas_stats = {
        row["avaliacao_id"]: row["lancadas"]
        for row in Nota.objects.filter(avaliacao_id__in=avaliacao_ids)
        .filter(_nota_lancada_q())
        .values("avaliacao_id")
        .annotate(lancadas=Count("id"))
    }
    ativos_por_turma = {
        row["turma_id"]: row["total"]
        for row in Matricula.objects.filter(
            turma_id__in=[d.turma_id for d in diarios],
            situacao=Matricula.Situacao.ATIVA,
        )
        .values("turma_id")
        .annotate(total=Count("id"))
    }

    headers = [
        {"label": "Data", "width": "110px"},
        {"label": "Turma"},
        {"label": "Avaliação"},
        {"label": "Período", "width": "130px"},
        {"label": "Lançadas", "width": "90px"},
        {"label": "Pendências", "width": "110px"},
        {"label": "Ação", "width": "180px"},
    ]

    rows = []
    pendencias_total = 0
    for av in avaliacoes:
        diario = diarios_by_id.get(av.diario_id)
        total_ativos = ativos_por_turma.get(getattr(diario, "turma_id", None), 0)
        lancadas = notas_stats.get(av.id, 0)
        pendencias = max(total_ativos - lancadas, 0)
        if somente_pendentes and pendencias <= 0:
            continue
        pendencias_total += pendencias
        rows.append(
            {
                "cells": [
                    {"text": av.data.strftime("%d/%m/%Y") if av.data else "—"},
                    {"text": getattr(getattr(av.diario, "turma", None), "nome", "—")},
                    {"text": av.titulo},
                    {"text": str(av.periodo) if av.periodo else "—"},
                    {"text": f"{lancadas}/{total_ativos}"},
                    {"html": _status_badge(str(pendencias), "warning" if pendencias else "success")},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:notas_lancar", args=[av.id]),
                                "Registrar conceitos" if av.modo_registro == "CONCEITO" else "Lançar notas",
                                "fa-solid fa-clipboard-check",
                            )
                        )
                    },
                ]
            }
        )

    hoje = timezone.localdate()
    resumo = {
        "hoje": sum(1 for av in avaliacoes if av.data == hoje),
        "proximos_7_dias": sum(1 for av in avaliacoes if av.data and hoje <= av.data <= hoje + timedelta(days=7)),
        "pendencias_total": pendencias_total,
    }

    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    turmas_info_ids = [t.id for t in turmas_informatica]
    ativos_info_map = {
        row["turma_id"]: row["total"]
        for row in InformaticaMatricula.objects.filter(
            turma_id__in=turmas_info_ids,
            status=InformaticaMatricula.Status.MATRICULADO,
        )
        .values("turma_id")
        .annotate(total=Count("id"))
    }
    avaliacoes_info_qs = InformaticaAvaliacao.objects.select_related("turma").filter(
        turma_id__in=turmas_info_ids,
        ativo=True,
    )
    if q:
        avaliacoes_info_qs = avaliacoes_info_qs.filter(
            Q(titulo__icontains=q)
            | Q(turma__codigo__icontains=q)
        )
    if data_inicio:
        avaliacoes_info_qs = avaliacoes_info_qs.filter(data__gte=data_inicio)
    if data_fim:
        avaliacoes_info_qs = avaliacoes_info_qs.filter(data__lte=data_fim)
    avaliacoes_info = list(avaliacoes_info_qs.order_by("data", "id")[:220])
    notas_info_rows = list(
        InformaticaNota.objects.filter(avaliacao_id__in=[a.id for a in avaliacoes_info])
        .filter(_nota_lancada_q())
        .values("avaliacao_id")
        .annotate(total=Count("id"))
    )
    notas_info_map = {row["avaliacao_id"]: row["total"] for row in notas_info_rows}

    headers_informatica = [
        {"label": "Data", "width": "110px"},
        {"label": "Turma (Informática)"},
        {"label": "Avaliação"},
        {"label": "Lançadas", "width": "90px"},
        {"label": "Pendências", "width": "100px"},
        {"label": "Ação", "width": "180px"},
    ]
    rows_informatica = []
    pendencias_informatica = 0
    for avaliacao_info in avaliacoes_info:
        total_ativos = int(ativos_info_map.get(avaliacao_info.turma_id, 0))
        total_lancadas = int(notas_info_map.get(avaliacao_info.id, 0))
        pendencias = max(total_ativos - total_lancadas, 0)
        pendencias_informatica += pendencias
        if somente_pendentes and pendencias <= 0:
            continue

        rows_informatica.append(
            {
                "cells": [
                    {"text": avaliacao_info.data.strftime("%d/%m/%Y") if avaliacao_info.data else "—"},
                    {"text": avaliacao_info.turma.codigo},
                    {"text": avaliacao_info.titulo},
                    {"text": f"{total_lancadas}/{total_ativos}"},
                    {"html": _status_badge(str(pendencias), "warning" if pendencias else "success")},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse(
                                    "educacao:professor_informatica_notas_lancar",
                                    args=[codigo_canonico, avaliacao_info.id],
                                ),
                                "Registrar conceitos" if avaliacao_info.modo_registro == "CONCEITO" else "Lançar notas",
                                "fa-solid fa-clipboard-check",
                            )
                        )
                    },
                ]
            }
        )

    resumo_informatica = {
        "hoje": sum(1 for av in avaliacoes_info if av.data == hoje),
        "proximos_7_dias": sum(
            1 for av in avaliacoes_info if av.data and hoje <= av.data <= hoje + timedelta(days=7)
        ),
        "pendencias_total": pendencias_informatica,
    }
    secretaria_ids_info = sorted(
        {
            t.laboratorio.unidade.secretaria_id
            for t in turmas_informatica
            if getattr(getattr(t, "laboratorio", None), "unidade", None) and t.laboratorio.unidade.secretaria_id
        }
    )
    unidade_ids_info = sorted(
        {
            t.laboratorio.unidade_id
            for t in turmas_informatica
            if getattr(getattr(t, "laboratorio", None), "unidade_id", None)
        }
    )
    eventos_calendario_informatica = []
    if secretaria_ids_info:
        eventos_calendario_informatica = list(
            CalendarioEducacionalEvento.objects.filter(
                ativo=True,
                secretaria_id__in=secretaria_ids_info,
                data_fim__gte=hoje,
            )
            .filter(Q(unidade__isnull=True) | Q(unidade_id__in=unidade_ids_info))
            .order_by("data_inicio", "titulo")[:12]
        )

    aulas_calendario_informatica = list(
        InformaticaAulaDiario.objects.select_related("turma", "encontro")
        .filter(
            turma_id__in=turmas_info_ids,
            data_aula__gte=hoje,
        )
        .exclude(status=InformaticaAulaDiario.Status.CANCELADA)
        .order_by("data_aula", "encontro__hora_inicio", "id")[:12]
    )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Agenda de Avaliações",
            page_subtitle="Acompanhe agenda do regular e da informática, com pendências de notas/aulas.",
            nav_key="agenda",
        ),
        "q": q,
        "inicio": data_inicio.isoformat() if data_inicio else "",
        "fim": data_fim.isoformat() if data_fim else "",
        "somente_pendentes": somente_pendentes,
        "headers": headers,
        "rows": rows,
        "resumo": resumo,
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
        "resumo_informatica": resumo_informatica,
        "eventos_calendario_informatica": eventos_calendario_informatica,
        "aulas_calendario_informatica": aulas_calendario_informatica,
    }
    return render(request, "educacao/professor_area/agenda.html", context)


@login_required
@require_perm("educacao.view")
def professor_horarios(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]

    turma_ids = sorted({d.turma_id for d in diarios})
    turmas = {d.turma_id: d.turma for d in diarios}

    turma_id = _clean_code(request.GET.get("turma"))
    dia = (_clean_code(request.GET.get("dia")) or "").upper()
    turma_informatica_id = _clean_code(request.GET.get("turma_informatica"))
    dia_info = _clean_code(request.GET.get("dia_info"))

    horarios_qs = (
        AulaHorario.objects.select_related("grade", "grade__turma", "professor")
        .filter(grade__turma_id__in=turma_ids)
        .filter(Q(professor=professor_user) | Q(professor__isnull=True))
    )
    if turma_id.isdigit():
        horarios_qs = horarios_qs.filter(grade__turma_id=int(turma_id))
    if dia in {choice[0] for choice in AulaHorario.Dia.choices}:
        horarios_qs = horarios_qs.filter(dia=dia)

    horarios = list(horarios_qs.order_by("dia", "inicio", "grade__turma__nome")[:260])
    dia_totais = {}
    for item in horarios:
        dia_totais[item.get_dia_display()] = dia_totais.get(item.get_dia_display(), 0) + 1

    headers = [
        {"label": "Dia", "width": "120px"},
        {"label": "Horário", "width": "130px"},
        {"label": "Turma"},
        {"label": "Disciplina"},
        {"label": "Sala", "width": "120px"},
        {"label": "Ação", "width": "160px"},
    ]
    rows = []
    for item in horarios:
        rows.append(
            {
                "cells": [
                    {"text": item.get_dia_display()},
                    {"text": f"{item.inicio.strftime('%H:%M')} - {item.fim.strftime('%H:%M')}"},
                    {"text": item.grade.turma.nome},
                    {"text": item.disciplina},
                    {"text": item.sala or "—"},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:horario_turma", args=[item.grade.turma_id]),
                                "Abrir grade",
                                "fa-solid fa-table-cells-large",
                            )
                        )
                    },
                ]
            }
        )

    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    encontros_info_qs = InformaticaEncontroSemanal.objects.select_related(
        "turma",
        "turma__laboratorio",
        "turma__laboratorio__unidade",
    ).filter(
        turma_id__in=[t.id for t in turmas_informatica],
        ativo=True,
        turma__status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
    )
    if turma_informatica_id.isdigit():
        encontros_info_qs = encontros_info_qs.filter(turma_id=int(turma_informatica_id))
    if dia_info.isdigit():
        encontros_info_qs = encontros_info_qs.filter(dia_semana=int(dia_info))

    encontros_info = list(encontros_info_qs.order_by("dia_semana", "hora_inicio", "turma__codigo")[:260])
    dia_totais_informatica = {}
    rows_informatica = []
    for item in encontros_info:
        dia_label = item.get_dia_semana_display()
        dia_totais_informatica[dia_label] = dia_totais_informatica.get(dia_label, 0) + 1
        rows_informatica.append(
            {
                "cells": [
                    {"text": dia_label},
                    {"text": f"{item.hora_inicio.strftime('%H:%M')} - {item.hora_fim.strftime('%H:%M')}"},
                    {"text": item.turma.codigo},
                    {"text": item.turma.laboratorio.nome},
                    {"text": item.turma.laboratorio.unidade.nome},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:informatica_turma_detail", args=[item.turma_id]),
                                "Abrir turma",
                                "fa-solid fa-laptop-code",
                            )
                        )
                    },
                ]
            }
        )
    headers_informatica = [
        {"label": "Dia", "width": "120px"},
        {"label": "Horário", "width": "130px"},
        {"label": "Turma (Informática)"},
        {"label": "Laboratório"},
        {"label": "Unidade"},
        {"label": "Ação", "width": "170px"},
    ]

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Locais e Horários de Aula",
            page_subtitle="Consulte horários planejados no regular e também nos encontros do Curso de Informática.",
            nav_key="horarios",
        ),
        "headers": headers,
        "rows": rows,
        "dia_totais": dia_totais,
        "filtro_turma": turma_id,
        "filtro_dia": dia,
        "turmas_filtro": [turmas[t_id] for t_id in turma_ids if t_id in turmas],
        "dias_choices": AulaHorario.Dia.choices,
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
        "dia_totais_informatica": dia_totais_informatica,
        "filtro_turma_informatica": turma_informatica_id,
        "filtro_dia_informatica": dia_info,
        "turmas_informatica_filtro": turmas_informatica,
        "dias_choices_informatica": InformaticaEncontroSemanal.DiaSemana.choices,
    }
    return render(request, "educacao/professor_area/horarios.html", context)


def _resolve_professor_diario_or_404(*, diario_id: int, diarios: list[DiarioTurma]) -> DiarioTurma:
    diario = next((item for item in diarios if item.id == diario_id), None)
    if diario is None:
        raise Http404("Diário não encontrado para este professor.")
    return diario


@login_required
@require_perm("educacao.view")
def professor_planos_ensino(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]

    q = _clean_code(request.GET.get("q"))
    planos_map = {
        item.diario_id: item
        for item in PlanoEnsinoProfessor.objects.filter(
            professor=professor_user,
            diario_id__in=[d.id for d in diarios],
        )
    }

    diarios_filtrados = diarios
    if q:
        ql = q.lower()
        diarios_filtrados = [
            d
            for d in diarios
            if ql in (d.turma.nome or "").lower()
            or ql in str(d.ano_letivo)
            or ql in (getattr(getattr(d.turma, "unidade", None), "nome", "").lower())
        ]

    status_filter = (_clean_code(request.GET.get("status")) or "todos").lower()
    if status_filter not in {"todos", "editaveis", "enviados", "homologados", "devolvidos"}:
        status_filter = "todos"

    headers = [
        {"label": "Turma"},
        {"label": "Unidade"},
        {"label": "Ano", "width": "90px"},
        {"label": "Status", "width": "170px"},
        {"label": "Preenchimento", "width": "150px"},
        {"label": "Atualizado em", "width": "150px"},
        {"label": "Ações", "width": "220px"},
    ]

    cards_regular = []
    rows_regular = []
    total_enviados = 0
    total_em_edicao = 0
    total_homologados = 0
    total_devolvidos = 0
    total_nao_iniciado = 0
    total_com_pendencias = 0

    for diario in diarios_filtrados:
        plano = planos_map.get(diario.id)
        checklist = _plano_checklist(plano)
        status_meta = _plano_status_meta(plano)

        if status_meta["key"] in {"submetido", "aprovado"}:
            total_enviados += 1
        elif status_meta["key"] == "homologado":
            total_homologados += 1
        elif status_meta["key"] == "devolvido":
            total_devolvidos += 1
        else:
            total_em_edicao += 1
        if status_meta["key"] == "nao_iniciado":
            total_nao_iniciado += 1
        if checklist["missing"] > 0:
            total_com_pendencias += 1

        if status_filter == "enviados" and status_meta["key"] not in {"submetido", "aprovado"}:
            continue
        if status_filter == "editaveis" and status_meta["key"] not in {"nao_iniciado", "rascunho", "devolvido"}:
            continue
        if status_filter == "homologados" and status_meta["key"] != "homologado":
            continue
        if status_filter == "devolvidos" and status_meta["key"] != "devolvido":
            continue

        plano_url = reverse("educacao:professor_plano_ensino_editar", args=[codigo_canonico, diario.id])
        cards_regular.append(
            {
                "contexto": "Ensino regular",
                "titulo": diario.turma.nome,
                "subtitulo": f"Ano letivo {diario.ano_letivo}",
                "status_label": status_meta["label"],
                "status_badge_class": status_meta["badge_class"],
                "status_chip_class": status_meta["chip_class"],
                "status_key": status_meta["key"],
                "percent": checklist["percent"],
                "missing": checklist["missing"],
                "missing_labels": checklist["missing_labels"],
                "atualizado_em": plano.atualizado_em.strftime("%d/%m/%Y %H:%M") if plano else "Nunca preenchido",
                "submetido_em": plano.submetido_em.strftime("%d/%m/%Y %H:%M") if plano and plano.submetido_em else "",
                "url": plano_url,
            }
        )
        rows_regular.append(
            {
                "cells": [
                    {"text": diario.turma.nome, "url": plano_url},
                    {"text": getattr(getattr(diario.turma, "unidade", None), "nome", "—")},
                    {"text": str(diario.ano_letivo)},
                    {
                        "html": _status_badge(
                            status_meta["label"],
                            (
                                "success"
                                if status_meta["key"] == "homologado"
                                else "primary"
                                if status_meta["key"] in {"submetido", "aprovado"}
                                else "danger"
                                if status_meta["key"] == "devolvido"
                                else "warning"
                                if status_meta["key"] == "rascunho"
                                else "neutral"
                            ),
                        )
                    },
                    {"text": f"{checklist['percent']}% • {checklist['missing']} pendência(s)"},
                    {"text": plano.atualizado_em.strftime("%d/%m/%Y %H:%M") if plano else "Nunca"},
                    {
                        "html": _actions_group(
                            _link_button(
                                plano_url,
                                "Abrir plano",
                                "fa-solid fa-pen-to-square",
                            )
                        )
                    },
                ]
            }
        )

    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    planos_info_map = {
        item.turma_id: item
        for item in InformaticaPlanoEnsinoProfessor.objects.filter(
            professor=professor_user,
            turma_id__in=[t.id for t in turmas_informatica],
        )
    }
    turmas_info_filtradas = turmas_informatica
    if q:
        ql = q.lower()
        turmas_info_filtradas = [
            t
            for t in turmas_informatica
            if ql in (t.codigo or "").lower()
            or ql in (t.nome or "").lower()
            or ql in (getattr(getattr(t, "laboratorio", None), "nome", "").lower())
            or ql in str(t.ano_letivo or "")
        ]

    headers_informatica = [
        {"label": "Turma (Informática)"},
        {"label": "Laboratório"},
        {"label": "Ano", "width": "90px"},
        {"label": "Status", "width": "170px"},
        {"label": "Preenchimento", "width": "150px"},
        {"label": "Atualizado em", "width": "150px"},
        {"label": "Ações", "width": "220px"},
    ]

    cards_informatica = []
    rows_informatica = []
    for turma in turmas_info_filtradas:
        plano = planos_info_map.get(turma.id)
        checklist = _plano_checklist(plano)
        status_meta = _plano_status_meta(plano)

        if status_meta["key"] in {"submetido", "aprovado"}:
            total_enviados += 1
        elif status_meta["key"] == "homologado":
            total_homologados += 1
        elif status_meta["key"] == "devolvido":
            total_devolvidos += 1
        else:
            total_em_edicao += 1
        if status_meta["key"] == "nao_iniciado":
            total_nao_iniciado += 1
        if checklist["missing"] > 0:
            total_com_pendencias += 1

        if status_filter == "enviados" and status_meta["key"] not in {"submetido", "aprovado"}:
            continue
        if status_filter == "editaveis" and status_meta["key"] not in {"nao_iniciado", "rascunho", "devolvido"}:
            continue
        if status_filter == "homologados" and status_meta["key"] != "homologado":
            continue
        if status_filter == "devolvidos" and status_meta["key"] != "devolvido":
            continue

        plano_url = reverse(
            "educacao:professor_plano_ensino_informatica_editar",
            args=[codigo_canonico, turma.id],
        )
        cards_informatica.append(
            {
                "contexto": "Curso de informática",
                "titulo": turma.codigo,
                "subtitulo": f"Ano letivo {turma.ano_letivo}",
                "status_label": status_meta["label"],
                "status_badge_class": status_meta["badge_class"],
                "status_chip_class": status_meta["chip_class"],
                "status_key": status_meta["key"],
                "percent": checklist["percent"],
                "missing": checklist["missing"],
                "missing_labels": checklist["missing_labels"],
                "atualizado_em": plano.atualizado_em.strftime("%d/%m/%Y %H:%M") if plano else "Nunca preenchido",
                "submetido_em": plano.submetido_em.strftime("%d/%m/%Y %H:%M") if plano and plano.submetido_em else "",
                "url": plano_url,
            }
        )
        rows_informatica.append(
            {
                "cells": [
                    {"text": turma.codigo, "url": plano_url},
                    {"text": getattr(getattr(turma, "laboratorio", None), "nome", "—")},
                    {"text": str(turma.ano_letivo or "—")},
                    {
                        "html": _status_badge(
                            status_meta["label"],
                            (
                                "success"
                                if status_meta["key"] == "homologado"
                                else "primary"
                                if status_meta["key"] in {"submetido", "aprovado"}
                                else "danger"
                                if status_meta["key"] == "devolvido"
                                else "warning"
                                if status_meta["key"] == "rascunho"
                                else "neutral"
                            ),
                        )
                    },
                    {"text": f"{checklist['percent']}% • {checklist['missing']} pendência(s)"},
                    {"text": plano.atualizado_em.strftime("%d/%m/%Y %H:%M") if plano else "Nunca"},
                    {
                        "html": _actions_group(
                            _link_button(
                                plano_url,
                                "Abrir plano",
                                "fa-solid fa-pen-to-square",
                            )
                        )
                    },
                ]
            }
        )

    total_planos = len(diarios_filtrados) + len(turmas_info_filtradas)

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Planos de Ensino",
            page_subtitle="Preencha e submeta planos de ensino no regular e nas turmas de informática.",
            nav_key="planos",
        ),
        "q": q,
        "status_filter": status_filter,
        "headers": headers,
        "rows": rows_regular,
        "total_planos_regular": len(rows_regular),
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
        "total_planos_informatica": len(rows_informatica),
        "cards_regular": cards_regular,
        "cards_informatica": cards_informatica,
        "resumo_planos": {
            "total": total_planos,
            "enviados": total_enviados,
            "em_edicao": total_em_edicao,
            "homologados": total_homologados,
            "devolvidos": total_devolvidos,
            "nao_iniciados": total_nao_iniciado,
            "com_pendencias": total_com_pendencias,
        },
    }
    return render(request, "educacao/professor_area/planos.html", context)


@login_required
@require_perm("educacao.view")
def professor_plano_ensino_editar(request, codigo: str, diario_id: int):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]
    diario = _resolve_professor_diario_or_404(diario_id=diario_id, diarios=diarios)

    plano, _created = PlanoEnsinoProfessor.objects.get_or_create(
        diario=diario,
        professor=professor_user,
        defaults={
            "ano_letivo": diario.ano_letivo,
            "titulo": f"Plano de Ensino • {diario.turma.nome}",
        },
    )

    if request.method == "POST":
        action = (_clean_code(request.POST.get("action")) or "save").lower()
        can_cancel_submissao = plano.status == PlanoEnsinoProfessor.Status.SUBMETIDO

        if action == "cancel_submit" and can_cancel_submissao:
            plano.cancelar_submissao()
            plano.save()
            messages.info(request, "Submissão cancelada. O plano voltou para rascunho.")
            return redirect("educacao:professor_plano_ensino_editar", codigo=codigo_canonico, diario_id=diario.id)

        if not plano.pode_editar_professor:
            messages.error(
                request,
                "Este plano não pode ser editado no momento. Aguarde devolução da coordenação, se necessário.",
            )
            return redirect("educacao:professor_plano_ensino_editar", codigo=codigo_canonico, diario_id=diario.id)

        form = PlanoEnsinoProfessorForm(request.POST, instance=plano)
        if form.is_valid():
            plano = form.save(commit=False)
            plano.diario = diario
            plano.professor = professor_user
            plano.ano_letivo = diario.ano_letivo

            if action == "submit":
                checklist = _plano_checklist(plano)
                if checklist["can_submit"]:
                    plano.submeter()
                    messages.success(request, "Plano de ensino submetido com sucesso.")
                else:
                    plano.cancelar_submissao()
                    pendencias_txt = ", ".join(checklist["missing_labels"])
                    messages.error(
                        request,
                        f"Não foi possível submeter. Preencha os campos obrigatórios: {pendencias_txt}.",
                    )
                    messages.info(request, "O plano foi salvo como rascunho.")
            else:
                messages.success(request, "Plano de ensino salvo como rascunho.")

            plano.save()
            return redirect("educacao:professor_plano_ensino_editar", codigo=codigo_canonico, diario_id=diario.id)
    else:
        form = PlanoEnsinoProfessorForm(instance=plano)

    plano_editavel_professor = plano.pode_editar_professor
    can_cancel_submissao = plano.status == PlanoEnsinoProfessor.Status.SUBMETIDO
    if not plano_editavel_professor:
        for field in form.fields.values():
            field.disabled = True

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title=f"Plano de Ensino • {diario.turma.nome}",
            page_subtitle="Defina objetivos, metodologia, cronograma e critérios de avaliação.",
            nav_key="planos",
        ),
        "form": form,
        "diario": diario,
        "plano": plano,
        "status_meta": _plano_status_meta(plano),
        "status_label": plano.get_status_display(),
        "plano_editavel_professor": plano_editavel_professor,
        "can_cancel_submissao": can_cancel_submissao,
        "plano_checklist": _plano_checklist(plano),
        "plano_fluxo": _plano_fluxo_status(plano),
    }
    return render(request, "educacao/professor_area/plano_form.html", context)


def _resolve_professor_turma_informatica_or_404(*, turma_id: int, turmas: list[InformaticaTurma]) -> InformaticaTurma:
    turma = next((item for item in turmas if item.id == turma_id), None)
    if turma is None:
        raise Http404("Turma de informática não encontrada para este professor.")
    return turma


@login_required
@require_perm("educacao.view")
def professor_plano_ensino_informatica_editar(request, codigo: str, turma_id: int):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    turma = _resolve_professor_turma_informatica_or_404(
        turma_id=turma_id,
        turmas=list(_professor_informatica_turmas_qs(professor_user)),
    )

    plano, _created = InformaticaPlanoEnsinoProfessor.objects.get_or_create(
        turma=turma,
        professor=professor_user,
        defaults={
            "ano_letivo": turma.ano_letivo,
            "titulo": f"Plano de Ensino • {turma.codigo}",
        },
    )

    if request.method == "POST":
        action = (_clean_code(request.POST.get("action")) or "save").lower()
        can_cancel_submissao = plano.status == InformaticaPlanoEnsinoProfessor.Status.SUBMETIDO

        if action == "cancel_submit" and can_cancel_submissao:
            plano.cancelar_submissao()
            plano.save()
            messages.info(request, "Submissão cancelada. O plano voltou para rascunho.")
            return redirect(
                "educacao:professor_plano_ensino_informatica_editar",
                codigo=codigo_canonico,
                turma_id=turma.id,
            )

        if not plano.pode_editar_professor:
            messages.error(
                request,
                "Este plano não pode ser editado no momento. Aguarde devolução da coordenação, se necessário.",
            )
            return redirect(
                "educacao:professor_plano_ensino_informatica_editar",
                codigo=codigo_canonico,
                turma_id=turma.id,
            )

        form = InformaticaPlanoEnsinoProfessorForm(request.POST, instance=plano)
        if form.is_valid():
            plano = form.save(commit=False)
            plano.turma = turma
            plano.professor = professor_user
            plano.ano_letivo = turma.ano_letivo

            if action == "submit":
                checklist = _plano_checklist(plano)
                if checklist["can_submit"]:
                    plano.submeter()
                    messages.success(request, "Plano de ensino (informática) submetido com sucesso.")
                else:
                    plano.cancelar_submissao()
                    pendencias_txt = ", ".join(checklist["missing_labels"])
                    messages.error(
                        request,
                        f"Não foi possível submeter. Preencha os campos obrigatórios: {pendencias_txt}.",
                    )
                    messages.info(request, "O plano foi salvo como rascunho.")
            else:
                messages.success(request, "Plano de ensino (informática) salvo como rascunho.")

            plano.save()
            return redirect(
                "educacao:professor_plano_ensino_informatica_editar",
                codigo=codigo_canonico,
                turma_id=turma.id,
            )
    else:
        form = InformaticaPlanoEnsinoProfessorForm(instance=plano)

    plano_editavel_professor = plano.pode_editar_professor
    can_cancel_submissao = plano.status == InformaticaPlanoEnsinoProfessor.Status.SUBMETIDO
    if not plano_editavel_professor:
        for field in form.fields.values():
            field.disabled = True

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title=f"Plano de Ensino • {turma.codigo}",
            page_subtitle="Defina objetivos, metodologia, cronograma e critérios para a turma de informática.",
            nav_key="planos",
        ),
        "form": form,
        "plano": plano,
        "status_meta": _plano_status_meta(plano),
        "status_label": plano.get_status_display(),
        "turma_informatica": turma,
        "is_informatica": True,
        "plano_editavel_professor": plano_editavel_professor,
        "can_cancel_submissao": can_cancel_submissao,
        "plano_checklist": _plano_checklist(plano),
        "plano_fluxo": _plano_fluxo_status(plano),
    }
    return render(request, "educacao/professor_area/plano_form.html", context)


def _apply_profile_scope_regular_planos(request_user, qs):
    profile = getattr(request_user, "profile", None)
    if getattr(request_user, "is_superuser", False):
        return qs
    if getattr(profile, "unidade_id", None):
        return qs.filter(diario__turma__unidade_id=profile.unidade_id)
    if getattr(profile, "secretaria_id", None):
        return qs.filter(diario__turma__unidade__secretaria_id=profile.secretaria_id)
    if getattr(profile, "municipio_id", None):
        return qs.filter(diario__turma__unidade__secretaria__municipio_id=profile.municipio_id)
    return qs


def _apply_profile_scope_informatica_planos(request_user, qs):
    profile = getattr(request_user, "profile", None)
    if getattr(request_user, "is_superuser", False):
        return qs
    if getattr(profile, "unidade_id", None):
        return qs.filter(turma__laboratorio__unidade_id=profile.unidade_id)
    if getattr(profile, "secretaria_id", None):
        return qs.filter(turma__laboratorio__unidade__secretaria_id=profile.secretaria_id)
    if getattr(profile, "municipio_id", None):
        return qs.filter(turma__laboratorio__unidade__secretaria__municipio_id=profile.municipio_id)
    return qs


@login_required
@require_perm("educacao.manage")
def plano_ensino_fluxo_list(request):
    q = _clean_code(request.GET.get("q"))
    status_filter = (_clean_code(request.GET.get("status")) or "todos").upper()
    tipo_filter = (_clean_code(request.GET.get("tipo")) or "todos").lower()

    status_valid = {
        "TODOS",
        PlanoEnsinoProfessor.Status.SUBMETIDO,
        PlanoEnsinoProfessor.Status.APROVADO,
        PlanoEnsinoProfessor.Status.HOMOLOGADO,
        PlanoEnsinoProfessor.Status.DEVOLVIDO,
        PlanoEnsinoProfessor.Status.RASCUNHO,
    }
    if status_filter not in status_valid:
        status_filter = "TODOS"
    if tipo_filter not in {"todos", "regular", "informatica"}:
        tipo_filter = "todos"

    regular_qs = _apply_profile_scope_regular_planos(
        request.user,
        PlanoEnsinoProfessor.objects.select_related(
            "diario",
            "diario__turma",
            "diario__turma__unidade",
            "professor",
            "professor__profile",
        ),
    )
    informatica_qs = _apply_profile_scope_informatica_planos(
        request.user,
        InformaticaPlanoEnsinoProfessor.objects.select_related(
            "turma",
            "turma__laboratorio",
            "turma__laboratorio__unidade",
            "professor",
            "professor__profile",
        ),
    )

    if q:
        ql = q.lower()
        regular_qs = regular_qs.filter(
            Q(diario__turma__nome__icontains=ql)
            | Q(diario__turma__unidade__nome__icontains=ql)
            | Q(professor__username__icontains=ql)
            | Q(professor__profile__codigo_acesso__icontains=ql)
            | Q(titulo__icontains=ql)
        )
        informatica_qs = informatica_qs.filter(
            Q(turma__codigo__icontains=ql)
            | Q(turma__nome__icontains=ql)
            | Q(turma__laboratorio__nome__icontains=ql)
            | Q(turma__laboratorio__unidade__nome__icontains=ql)
            | Q(professor__username__icontains=ql)
            | Q(professor__profile__codigo_acesso__icontains=ql)
            | Q(titulo__icontains=ql)
        )

    if status_filter != "TODOS":
        regular_qs = regular_qs.filter(status=status_filter)
        informatica_qs = informatica_qs.filter(status=status_filter)

    regular_qs = regular_qs.order_by("-atualizado_em", "-id")
    informatica_qs = informatica_qs.order_by("-atualizado_em", "-id")

    resumo_regular = _apply_profile_scope_regular_planos(request.user, PlanoEnsinoProfessor.objects.all())
    resumo_info = _apply_profile_scope_informatica_planos(request.user, InformaticaPlanoEnsinoProfessor.objects.all())
    resumo = {
        "total": resumo_regular.count() + resumo_info.count(),
        "submetidos": resumo_regular.filter(status=PlanoEnsinoProfessor.Status.SUBMETIDO).count()
        + resumo_info.filter(status=InformaticaPlanoEnsinoProfessor.Status.SUBMETIDO).count(),
        "aprovados": resumo_regular.filter(status=PlanoEnsinoProfessor.Status.APROVADO).count()
        + resumo_info.filter(status=InformaticaPlanoEnsinoProfessor.Status.APROVADO).count(),
        "homologados": resumo_regular.filter(status=PlanoEnsinoProfessor.Status.HOMOLOGADO).count()
        + resumo_info.filter(status=InformaticaPlanoEnsinoProfessor.Status.HOMOLOGADO).count(),
        "devolvidos": resumo_regular.filter(status=PlanoEnsinoProfessor.Status.DEVOLVIDO).count()
        + resumo_info.filter(status=InformaticaPlanoEnsinoProfessor.Status.DEVOLVIDO).count(),
    }

    headers_regular = [
        {"label": "Turma"},
        {"label": "Professor", "width": "190px"},
        {"label": "Status", "width": "210px"},
        {"label": "Atualizado em", "width": "165px"},
        {"label": "Ação", "width": "170px"},
    ]
    rows_regular = []
    for plano in regular_qs:
        status_meta = _plano_status_meta(plano)
        professor_nome = plano.professor.get_full_name() if plano.professor_id else "—"
        if not professor_nome and plano.professor_id:
            professor_nome = plano.professor.username
        professor_codigo = (
            codigo_professor_canonico(plano.professor)
            if plano.professor_id
            else "—"
        )
        professor_html = (
            f"<strong>{professor_nome}</strong><br><small>{professor_codigo}</small>"
            if plano.professor_id
            else "—"
        )
        rows_regular.append(
            {
                "cells": [
                    {"text": f"{plano.diario.turma.nome} • {plano.ano_letivo}"},
                    {"html": professor_html},
                    {"html": _status_badge(status_meta["label"], status_meta["badge_class"].replace("gp-badge--", ""))},
                    {"text": plano.atualizado_em.strftime("%d/%m/%Y %H:%M")},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:plano_ensino_fluxo_regular_detail", args=[plano.pk]),
                                "Analisar",
                                "fa-solid fa-clipboard-check",
                            )
                        )
                    },
                ]
            }
        )

    headers_informatica = [
        {"label": "Turma (Informática)"},
        {"label": "Professor", "width": "190px"},
        {"label": "Status", "width": "210px"},
        {"label": "Atualizado em", "width": "165px"},
        {"label": "Ação", "width": "170px"},
    ]
    rows_informatica = []
    for plano in informatica_qs:
        status_meta = _plano_status_meta(plano)
        professor_nome = plano.professor.get_full_name() if plano.professor_id else "—"
        if not professor_nome and plano.professor_id:
            professor_nome = plano.professor.username
        professor_codigo = (
            codigo_professor_canonico(plano.professor)
            if plano.professor_id
            else "—"
        )
        professor_html = (
            f"<strong>{professor_nome}</strong><br><small>{professor_codigo}</small>"
            if plano.professor_id
            else "—"
        )
        rows_informatica.append(
            {
                "cells": [
                    {"text": f"{plano.turma.codigo} • {plano.ano_letivo}"},
                    {"html": professor_html},
                    {"html": _status_badge(status_meta["label"], status_meta["badge_class"].replace("gp-badge--", ""))},
                    {"text": plano.atualizado_em.strftime("%d/%m/%Y %H:%M")},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:plano_ensino_fluxo_informatica_detail", args=[plano.pk]),
                                "Analisar",
                                "fa-solid fa-clipboard-check",
                            )
                        )
                    },
                ]
            }
        )

    if tipo_filter == "regular":
        rows_informatica = []
    elif tipo_filter == "informatica":
        rows_regular = []

    actions = [
        {
            "label": "Painel Educação",
            "url": reverse("educacao:index"),
            "icon": "fa-solid fa-chart-line",
            "variant": "btn--ghost",
        }
    ]

    context = {
        "q": q,
        "status_filter": status_filter,
        "tipo_filter": tipo_filter,
        "resumo": resumo,
        "actions": actions,
        "headers_regular": headers_regular,
        "rows_regular": rows_regular,
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
    }
    return render(request, "educacao/plano_fluxo_list.html", context)


def _processar_acao_coord_plano(request, plano):
    action = (_clean_code(request.POST.get("action")) or "").lower()
    if not action:
        messages.warning(request, "Ação inválida.")
        return

    status_submetido = plano.Status.SUBMETIDO
    status_aprovado = plano.Status.APROVADO
    status_devolvido = plano.Status.DEVOLVIDO

    if action == "aprovar":
        if plano.status != status_submetido:
            messages.warning(request, "Só é possível aprovar planos que estejam submetidos.")
            return
        plano.aprovar(usuario=request.user)
        plano.save()
        messages.success(request, "Plano aprovado. Próxima etapa: homologação.")
        return

    if action == "homologar":
        if plano.status != status_aprovado:
            messages.warning(request, "Só é possível homologar planos já aprovados.")
            return
        plano.homologar(usuario=request.user)
        plano.save()
        messages.success(request, "Plano homologado com sucesso.")
        return

    if action == "devolver":
        motivo = _clean_code(request.POST.get("motivo_devolucao"))
        if plano.status not in {status_submetido, status_aprovado}:
            messages.warning(request, "Só é possível devolver planos em análise.")
            return
        if len(motivo) < 5:
            messages.error(request, "Informe um motivo de devolução com pelo menos 5 caracteres.")
            return
        plano.devolver(usuario=request.user, motivo=motivo)
        plano.save()
        messages.success(request, "Plano devolvido para ajustes do professor.")
        return

    messages.warning(request, "Ação não reconhecida.")


@login_required
@require_perm("educacao.manage")
def plano_ensino_fluxo_regular_detail(request, pk: int):
    plano = get_object_or_404(
        _apply_profile_scope_regular_planos(
            request.user,
            PlanoEnsinoProfessor.objects.select_related(
                "diario",
                "diario__turma",
                "diario__turma__unidade",
                "professor",
                "professor__profile",
                "aprovado_por",
                "homologado_por",
                "devolvido_por",
            ),
        ),
        pk=pk,
    )

    if request.method == "POST":
        _processar_acao_coord_plano(request, plano)
        return redirect("educacao:plano_ensino_fluxo_regular_detail", pk=plano.pk)

    professor_nome = plano.professor.get_full_name() if plano.professor_id else "—"
    if not professor_nome and plano.professor_id:
        professor_nome = plano.professor.username

    context = {
        "plano": plano,
        "is_informatica": False,
        "status_meta": _plano_status_meta(plano),
        "plano_checklist": _plano_checklist(plano),
        "plano_fluxo": _plano_fluxo_status(plano),
        "professor_nome": professor_nome,
        "professor_codigo": codigo_professor_canonico(plano.professor) if plano.professor_id else "—",
        "referencia_turma": plano.diario.turma.nome,
        "referencia_unidade": getattr(plano.diario.turma.unidade, "nome", "—"),
    }
    return render(request, "educacao/plano_fluxo_detail.html", context)


@login_required
@require_perm("educacao.manage")
def plano_ensino_fluxo_informatica_detail(request, pk: int):
    plano = get_object_or_404(
        _apply_profile_scope_informatica_planos(
            request.user,
            InformaticaPlanoEnsinoProfessor.objects.select_related(
                "turma",
                "turma__laboratorio",
                "turma__laboratorio__unidade",
                "professor",
                "professor__profile",
                "aprovado_por",
                "homologado_por",
                "devolvido_por",
            ),
        ),
        pk=pk,
    )

    if request.method == "POST":
        _processar_acao_coord_plano(request, plano)
        return redirect("educacao:plano_ensino_fluxo_informatica_detail", pk=plano.pk)

    professor_nome = plano.professor.get_full_name() if plano.professor_id else "—"
    if not professor_nome and plano.professor_id:
        professor_nome = plano.professor.username

    context = {
        "plano": plano,
        "is_informatica": True,
        "status_meta": _plano_status_meta(plano),
        "plano_checklist": _plano_checklist(plano),
        "plano_fluxo": _plano_fluxo_status(plano),
        "professor_nome": professor_nome,
        "professor_codigo": codigo_professor_canonico(plano.professor) if plano.professor_id else "—",
        "referencia_turma": plano.turma.codigo,
        "referencia_unidade": getattr(plano.turma.laboratorio.unidade, "nome", "—"),
    }
    return render(request, "educacao/plano_fluxo_detail.html", context)


@login_required
@require_perm("educacao.view")
def professor_informatica_avaliacoes(request, codigo: str, turma_id: int):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    if not _can_edit_informatica_execucao(request.user, professor_user):
        raise Http404("Apenas o professor da turma pode acessar avaliações/notas de informática.")
    turma = _resolve_professor_turma_informatica_or_404(
        turma_id=turma_id,
        turmas=list(_professor_informatica_turmas_qs(professor_user)),
    )
    avaliacoes = list(InformaticaAvaliacao.objects.filter(turma=turma).order_by("-data", "-id")[:180])
    total_alunos = InformaticaMatricula.objects.filter(
        turma=turma,
        status=InformaticaMatricula.Status.MATRICULADO,
    ).count()
    notas_rows = list(
        InformaticaNota.objects.filter(avaliacao_id__in=[a.id for a in avaliacoes])
        .filter(_nota_lancada_q())
        .values("avaliacao_id")
        .annotate(total=Count("id"), media=Avg("valor"))
    )
    notas_totais_map = {row["avaliacao_id"]: row["total"] for row in notas_rows}
    notas_media_map = {row["avaliacao_id"]: row["media"] for row in notas_rows}

    headers = [
        {"label": "Instrumento", "width": "170px"},
        {"label": "Título"},
        {"label": "Data", "width": "110px"},
        {"label": "Modo", "width": "95px"},
        {"label": "Peso", "width": "90px"},
        {"label": "Lançadas", "width": "90px"},
        {"label": "Pendências", "width": "100px"},
        {"label": "Média", "width": "90px"},
        {"label": "Ações", "width": "320px"},
    ]
    can_edit_notas = True
    rows = []
    for av in avaliacoes:
        lancadas = int(notas_totais_map.get(av.id, 0))
        pendencias = max(total_alunos - lancadas, 0)
        action_cell = "—"
        if can_edit_notas:
            action_cell = _actions_group(
                _link_button(
                    reverse("educacao:professor_informatica_avaliacao_update", args=[codigo_canonico, turma.id, av.id]),
                    "Configurar",
                    "fa-solid fa-sliders",
                ),
                _link_button(
                    reverse("educacao:professor_informatica_notas_lancar", args=[codigo_canonico, av.id]),
                    "Registrar conceitos" if av.modo_registro == "CONCEITO" else "Lançar notas",
                    "fa-solid fa-clipboard-check",
                )
            )
        rows.append(
            {
                "cells": [
                    {"text": f"{(av.sigla or '').upper()} • {av.get_tipo_display()}" if av.sigla else av.get_tipo_display()},
                    {"text": av.titulo},
                    {"text": av.data.strftime("%d/%m/%Y") if av.data else "—"},
                    {"text": av.get_modo_registro_display()},
                    {"text": _fmt_decimal(av.peso)},
                    {"text": f"{lancadas}/{total_alunos}"},
                    {"html": _status_badge(str(pendencias), "warning" if pendencias else "success")},
                    {"text": _fmt_decimal(notas_media_map.get(av.id)) if notas_media_map.get(av.id) is not None else "—"},
                    {"html": action_cell},
                ]
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title=f"Avaliações • {turma.codigo}",
            page_subtitle="Crie avaliações e lance notas para a turma de informática.",
            nav_key="notas",
        ),
        "turma_informatica": turma,
        "headers": headers,
        "rows": rows,
        "nova_avaliacao_url": reverse("educacao:professor_informatica_avaliacao_create", args=[codigo_canonico, turma.id]) if can_edit_notas else "",
        "can_edit_notas": can_edit_notas,
    }
    return render(request, "educacao/professor_area/informatica_avaliacoes.html", context)


@login_required
@require_perm("educacao.view")
def professor_informatica_avaliacao_create(request, codigo: str, turma_id: int):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    if not _can_edit_informatica_execucao(request.user, professor_user):
        raise Http404("Apenas o professor da turma pode criar avaliações de informática.")
    turma = _resolve_professor_turma_informatica_or_404(
        turma_id=turma_id,
        turmas=list(_professor_informatica_turmas_qs(professor_user)),
    )

    if request.method == "POST":
        form = InformaticaAvaliacaoForm(request.POST)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.turma = turma
            avaliacao.professor = professor_user
            avaliacao.save()
            messages.success(request, "Avaliação de informática criada com sucesso.")
            return redirect("educacao:professor_informatica_avaliacoes", codigo=codigo_canonico, turma_id=turma.id)
    else:
        form = InformaticaAvaliacaoForm(
            initial={
                "tipo": "PROVA",
                "modo_registro": "NOTA",
                "peso": Decimal("1.00"),
                "nota_maxima": Decimal("10.00"),
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title=f"Editar Configuração de Avaliação • {turma.codigo}",
            page_subtitle="Defina tipo, sigla, etapa de lançamento e critérios do instrumento.",
            nav_key="notas",
        ),
        "turma_informatica": turma,
        "form": form,
        "mode": "create",
    }
    return render(request, "educacao/professor_area/informatica_notas_form.html", context)


@login_required
@require_perm("educacao.view")
def professor_informatica_avaliacao_update(request, codigo: str, turma_id: int, avaliacao_id: int):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    if not _can_edit_informatica_execucao(request.user, professor_user):
        raise Http404("Apenas o professor da turma pode editar avaliações de informática.")
    turma = _resolve_professor_turma_informatica_or_404(
        turma_id=turma_id,
        turmas=list(_professor_informatica_turmas_qs(professor_user)),
    )
    avaliacao = get_object_or_404(InformaticaAvaliacao, pk=avaliacao_id, turma=turma)

    if request.method == "POST":
        form = InformaticaAvaliacaoForm(request.POST, instance=avaliacao)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração da avaliação atualizada com sucesso.")
            return redirect("educacao:professor_informatica_avaliacoes", codigo=codigo_canonico, turma_id=turma.id)
    else:
        form = InformaticaAvaliacaoForm(instance=avaliacao)

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title=f"Editar Configuração de Avaliação • {turma.codigo}",
            page_subtitle="Atualize tipo, sigla, modo de registro e parâmetros da avaliação.",
            nav_key="notas",
        ),
        "turma_informatica": turma,
        "form": form,
        "avaliacao_informatica": avaliacao,
        "mode": "update",
    }
    return render(request, "educacao/professor_area/informatica_notas_form.html", context)


@login_required
@require_perm("educacao.view")
def professor_informatica_notas_lancar(request, codigo: str, avaliacao_id: int):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    if not _can_edit_informatica_execucao(request.user, professor_user):
        raise Http404("Apenas o professor da turma pode acessar avaliações/notas de informática.")
    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    avaliacao = get_object_or_404(
        InformaticaAvaliacao.objects.select_related("turma"),
        pk=avaliacao_id,
        turma_id__in=[t.id for t in turmas_informatica],
    )
    turma = avaliacao.turma

    matriculas = list(
        InformaticaMatricula.objects.filter(
            turma=turma,
            status=InformaticaMatricula.Status.MATRICULADO,
        )
        .select_related("aluno")
        .order_by("aluno__nome")
    )
    notas_map = {
        nota.aluno_id: nota
        for nota in InformaticaNota.objects.filter(avaliacao=avaliacao).select_related("aluno")
    }
    can_edit_notas = True
    is_modo_conceito = avaliacao.modo_registro == "CONCEITO"
    conceitos_validos = {item[0] for item in AVALIACAO_CONCEITOS_CHOICES}

    if request.method == "POST":
        with transaction.atomic():
            for m in matriculas:
                raw = (request.POST.get(f"aluno_{m.aluno_id}") or "").strip()
                valor = None
                conceito = ""
                if is_modo_conceito:
                    conceito = raw.upper()
                    if conceito not in conceitos_validos:
                        conceito = ""
                elif raw:
                    try:
                        valor = Decimal(raw.replace(",", "."))
                    except (InvalidOperation, TypeError, ValueError):
                        valor = None

                InformaticaNota.objects.update_or_create(
                    avaliacao=avaliacao,
                    aluno_id=m.aluno_id,
                    defaults={"valor": valor, "conceito": conceito},
                )
        messages.success(
            request,
            "Conceitos da informática salvos com sucesso."
            if is_modo_conceito
            else "Notas de informática salvas com sucesso.",
        )
        return redirect(
            "educacao:professor_informatica_notas_lancar",
            codigo=codigo_canonico,
            avaliacao_id=avaliacao.id,
        )

    alunos_rows = []
    for m in matriculas:
        nota = notas_map.get(m.aluno_id)
        alunos_rows.append(
            {
                "aluno_id": m.aluno_id,
                "aluno_nome": m.aluno.nome,
                "valor": "" if (not nota or nota.valor is None) else str(nota.valor).replace(".", ","),
                "conceito": "" if not nota else (nota.conceito or ""),
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title=f"Lançar notas • {turma.codigo}",
            page_subtitle=f"Avaliação: {avaliacao.titulo}",
            nav_key="notas",
        ),
        "turma_informatica": turma,
        "avaliacao_informatica": avaliacao,
        "alunos_rows": alunos_rows,
        "voltar_url": reverse("educacao:professor_informatica_avaliacoes", args=[codigo_canonico, turma.id]),
        "can_edit_notas": can_edit_notas,
        "is_modo_conceito": is_modo_conceito,
        "conceito_choices": AVALIACAO_CONCEITOS_CHOICES,
    }
    return render(request, "educacao/professor_area/informatica_notas_lancar.html", context)


@login_required
@require_perm("educacao.view")
def professor_materiais(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]
    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    turmas_informatica_ids = [t.id for t in turmas_informatica]

    diario_ids = [d.id for d in diarios]
    q = _clean_code(request.GET.get("q"))
    materiais_qs = MaterialAulaProfessor.objects.select_related(
        "diario",
        "diario__turma",
        "aula",
        "turma_informatica",
        "aula_informatica",
    ).filter(professor=professor_user)
    if diario_ids or turmas_informatica_ids:
        materiais_qs = materiais_qs.filter(
            Q(diario_id__in=diario_ids)
            | Q(turma_informatica_id__in=turmas_informatica_ids)
            | (Q(diario__isnull=True) & Q(turma_informatica__isnull=True))
        )
    if q:
        materiais_qs = materiais_qs.filter(
            Q(titulo__icontains=q)
            | Q(descricao__icontains=q)
            | Q(diario__turma__nome__icontains=q)
            | Q(turma_informatica__codigo__icontains=q)
            | Q(turma_informatica__nome__icontains=q)
        )
    materiais = list(materiais_qs.order_by("-atualizado_em", "-id")[:200])

    headers = [
        {"label": "Material"},
        {"label": "Vínculo", "width": "220px"},
        {"label": "Origem", "width": "120px"},
        {"label": "Visibilidade", "width": "120px"},
        {"label": "Atualizado em", "width": "160px"},
        {"label": "Ações", "width": "280px"},
    ]
    rows = []
    for item in materiais:
        vinculo = "Geral"
        contexto = "Geral"
        if item.diario_id:
            vinculo = item.diario.turma.nome
            contexto = "Regular"
        if item.aula_id and item.aula and item.aula.data:
            vinculo = f"{vinculo} • Aula {item.aula.data.strftime('%d/%m/%Y')}"
        if item.turma_informatica_id:
            vinculo = item.turma_informatica.codigo
            contexto = "Informática"
        if item.aula_informatica_id and item.aula_informatica and item.aula_informatica.data_aula:
            vinculo = f"{vinculo} • Aula {item.aula_informatica.data_aula.strftime('%d/%m/%Y')}"

        origem = "Arquivo" if item.arquivo else "Link"
        visibilidade_html = _status_badge("Alunos", "primary" if item.publico_alunos else "neutral")
        contexto_html = _status_badge(contexto, "primary" if contexto == "Informática" else "neutral")
        botoes = [
            _link_button(
                reverse("educacao:professor_material_editar", args=[codigo_canonico, item.id]),
                "Editar",
                "fa-solid fa-pen",
            )
        ]
        if item.arquivo:
            botoes.append(_link_button(item.arquivo.url, "Abrir arquivo", "fa-solid fa-file-arrow-down"))
        elif item.link_externo:
            botoes.append(_link_button(item.link_externo, "Abrir link", "fa-solid fa-arrow-up-right-from-square"))

        rows.append(
            {
                "cells": [
                    {"text": item.titulo},
                    {"text": vinculo},
                    {"html": f"{origem}<br>{contexto_html}"},
                    {"html": visibilidade_html},
                    {"text": item.atualizado_em.strftime("%d/%m/%Y %H:%M")},
                    {"html": _actions_group(*botoes)},
                ]
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Materiais de Aula",
            page_subtitle="Cadastre materiais para turmas regulares e de informática, com vínculo por aula quando necessário.",
            nav_key="materiais",
        ),
        "q": q,
        "headers": headers,
        "rows": rows,
        "novo_material_url": reverse("educacao:professor_material_novo", args=[codigo_canonico]),
        "total_materiais": len(materiais),
    }
    return render(request, "educacao/professor_area/materiais.html", context)


@login_required
@require_perm("educacao.view")
def professor_material_novo(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]
    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    diarios_qs = DiarioTurma.objects.filter(id__in=[d.id for d in diarios]).select_related("turma").order_by("-ano_letivo", "turma__nome")
    turmas_informatica_qs = InformaticaTurma.objects.filter(id__in=[t.id for t in turmas_informatica]).order_by(
        "-ano_letivo", "codigo"
    )

    if request.method == "POST":
        form = MaterialAulaProfessorForm(
            request.POST,
            request.FILES,
            diarios_qs=diarios_qs,
            turmas_informatica_qs=turmas_informatica_qs,
        )
        if form.is_valid():
            item = form.save(commit=False)
            item.professor = professor_user
            item.save()
            messages.success(request, "Material de aula cadastrado com sucesso.")
            return redirect("educacao:professor_materiais", codigo=codigo_canonico)
    else:
        form = MaterialAulaProfessorForm(diarios_qs=diarios_qs, turmas_informatica_qs=turmas_informatica_qs)

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Novo Material de Aula",
            page_subtitle="Cadastre arquivo ou link e vincule com diário/aula regular ou turma/aula de informática.",
            nav_key="materiais",
        ),
        "form": form,
        "is_create": True,
    }
    return render(request, "educacao/professor_area/material_form.html", context)


@login_required
@require_perm("educacao.view")
def professor_material_editar(request, codigo: str, pk: int):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]
    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    diarios_qs = DiarioTurma.objects.filter(id__in=[d.id for d in diarios]).select_related("turma").order_by("-ano_letivo", "turma__nome")
    turmas_informatica_qs = InformaticaTurma.objects.filter(id__in=[t.id for t in turmas_informatica]).order_by(
        "-ano_letivo", "codigo"
    )

    material = get_object_or_404(MaterialAulaProfessor, pk=pk, professor=professor_user)
    if material.diario_id and material.diario_id not in {d.id for d in diarios}:
        raise Http404("Material não encontrado para este professor.")
    if material.turma_informatica_id and material.turma_informatica_id not in {t.id for t in turmas_informatica}:
        raise Http404("Material de informática não encontrado para este professor.")

    if request.method == "POST":
        form = MaterialAulaProfessorForm(
            request.POST,
            request.FILES,
            instance=material,
            diarios_qs=diarios_qs,
            turmas_informatica_qs=turmas_informatica_qs,
        )
        if form.is_valid():
            material = form.save(commit=False)
            material.professor = professor_user
            material.save()
            messages.success(request, "Material de aula atualizado com sucesso.")
            return redirect("educacao:professor_materiais", codigo=codigo_canonico)
    else:
        form = MaterialAulaProfessorForm(
            instance=material,
            diarios_qs=diarios_qs,
            turmas_informatica_qs=turmas_informatica_qs,
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title=f"Editar Material • {material.titulo}",
            page_subtitle="Atualize vínculo, visibilidade e conteúdo do material.",
            nav_key="materiais",
        ),
        "form": form,
        "material": material,
        "is_create": False,
    }
    return render(request, "educacao/professor_area/material_form.html", context)


@login_required
@require_perm("educacao.view")
def professor_justificativas(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]

    diarios_ids = [d.id for d in diarios]
    status_filter = (_clean_code(request.GET.get("status")) or "").upper()
    q = _clean_code(request.GET.get("q"))

    pedidos_qs = JustificativaFaltaPedido.objects.select_related(
        "aluno",
        "aula",
        "aula__diario",
        "aula__diario__turma",
        "aula__componente",
        "analisado_por",
    ).filter(aula__diario_id__in=diarios_ids)

    if status_filter in {
        JustificativaFaltaPedido.Status.PENDENTE,
        JustificativaFaltaPedido.Status.DEFERIDO,
        JustificativaFaltaPedido.Status.INDEFERIDO,
    }:
        pedidos_qs = pedidos_qs.filter(status=status_filter)

    if q:
        pedidos_qs = pedidos_qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(aula__diario__turma__nome__icontains=q)
            | Q(aula__componente__nome__icontains=q)
            | Q(motivo__icontains=q)
        )

    pedidos = list(pedidos_qs.order_by("-criado_em", "-id")[:180])

    headers = [
        {"label": "Aluno"},
        {"label": "Turma"},
        {"label": "Aula", "width": "180px"},
        {"label": "Status", "width": "120px"},
        {"label": "Solicitado em", "width": "150px"},
        {"label": "Ação", "width": "140px"},
    ]

    rows = []
    for pedido in pedidos:
        label, variant = _status_label_pedido(pedido.status)
        rows.append(
            {
                "cells": [
                    {"text": pedido.aluno.nome},
                    {"text": pedido.aula.diario.turma.nome},
                    {
                        "text": (
                            f"{pedido.aula.data.strftime('%d/%m/%Y') if pedido.aula.data else '—'}"
                            f" • {pedido.aula.componente or 'Sem componente'}"
                        )
                    },
                    {"html": _status_badge(label, variant)},
                    {"text": pedido.criado_em.strftime("%d/%m/%Y %H:%M") if pedido.criado_em else "—"},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:justificativa_falta_detail", args=[pedido.id]),
                                "Analisar",
                                "fa-solid fa-file-signature",
                            )
                        )
                    },
                ]
            }
        )

    counters = {
        "pendente": pedidos_qs.filter(status=JustificativaFaltaPedido.Status.PENDENTE).count(),
        "deferido": pedidos_qs.filter(status=JustificativaFaltaPedido.Status.DEFERIDO).count(),
        "indeferido": pedidos_qs.filter(status=JustificativaFaltaPedido.Status.INDEFERIDO).count(),
    }

    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    justificativas_info_qs = InformaticaFrequencia.objects.select_related(
        "aluno",
        "aula",
        "aula__turma",
    ).filter(
        aula__turma_id__in=[t.id for t in turmas_informatica]
    ).filter(
        Q(justificativa__gt="") | Q(presente=False)
    )
    if q:
        justificativas_info_qs = justificativas_info_qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(aula__turma__codigo__icontains=q)
            | Q(justificativa__icontains=q)
            | Q(observacao__icontains=q)
        )
    justificativas_info = list(justificativas_info_qs.order_by("-aula__data_aula", "-id")[:180])
    headers_informatica = [
        {"label": "Aluno"},
        {"label": "Turma (Informática)"},
        {"label": "Aula", "width": "160px"},
        {"label": "Presença", "width": "110px"},
        {"label": "Justificativa"},
        {"label": "Ação", "width": "150px"},
    ]
    rows_informatica = []
    for item in justificativas_info:
        presenca_html = _status_badge("Presente", "success") if item.presente else _status_badge("Falta", "warning")
        rows_informatica.append(
            {
                "cells": [
                    {"text": item.aluno.nome},
                    {"text": item.aula.turma.codigo},
                    {"text": item.aula.data_aula.strftime("%d/%m/%Y") if item.aula and item.aula.data_aula else "—"},
                    {"html": presenca_html},
                    {"text": item.justificativa or item.observacao or "Sem justificativa informada"},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:informatica_frequencia_aula", args=[item.aula_id]),
                                "Abrir aula",
                                "fa-solid fa-user-check",
                            )
                        )
                    },
                ]
            }
        )
    counters_informatica = {
        "total": len(justificativas_info),
        "faltas": sum(1 for item in justificativas_info if not item.presente),
        "com_justificativa": sum(1 for item in justificativas_info if (item.justificativa or "").strip()),
    }

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Justificativas de Falta",
            page_subtitle="Analise pedidos do regular e acompanhe justificativas lançadas nas aulas de informática.",
            nav_key="justificativas",
        ),
        "q": q,
        "status_filter": status_filter,
        "headers": headers,
        "rows": rows,
        "counters": counters,
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
        "counters_informatica": counters_informatica,
    }
    return render(request, "educacao/professor_area/justificativas.html", context)


@login_required
@require_perm("educacao.view")
def professor_fechamento(request, codigo: str):
    ctx = _resolve_professor_context(request, codigo)
    professor_user = ctx["professor_user"]
    codigo_canonico = ctx["codigo_canonico"]
    diarios = ctx["diarios"]

    # Turmas únicas, mantendo ordenação por ano e nome.
    turmas_map = {}
    for diario in diarios:
        turmas_map.setdefault(diario.turma_id, diario.turma)
    turmas = sorted(
        turmas_map.values(),
        key=lambda t: (-(t.ano_letivo or 0), t.nome or ""),
    )

    hoje = timezone.localdate()
    anos = {t.ano_letivo for t in turmas if t.ano_letivo}
    periodos_qs = PeriodoLetivo.objects.filter(ano_letivo__in=anos, ativo=True).order_by("ano_letivo", "numero")
    periodos_by_ano: dict[int, list[PeriodoLetivo]] = {}
    for p in periodos_qs:
        periodos_by_ano.setdefault(p.ano_letivo, []).append(p)

    fechamento_qs = FechamentoPeriodoTurma.objects.select_related("periodo", "fechado_por").filter(
        turma_id__in=[t.id for t in turmas]
    )
    fechamentos_map = {(f.turma_id, f.periodo_id): f for f in fechamento_qs}

    can_close = can(request.user, "educacao.manage") or request.user.id == professor_user.id

    headers = [
        {"label": "Turma"},
        {"label": "Ano", "width": "90px"},
        {"label": "Período ativo", "width": "170px"},
        {"label": "Status", "width": "170px"},
        {"label": "Resumo", "width": "220px"},
        {"label": "Ação", "width": "220px"},
    ]

    rows = []
    for turma in turmas:
        periodos = periodos_by_ano.get(turma.ano_letivo, [])
        periodo_ref = next((p for p in periodos if p.inicio <= hoje <= p.fim), None)
        if periodo_ref is None and periodos:
            periodo_ref = periodos[0]

        fechamento = None
        if periodo_ref is not None:
            fechamento = fechamentos_map.get((turma.id, periodo_ref.id))

        if fechamento:
            status_html = _status_badge("Fechado", "success")
            resumo = f"Aprovados {fechamento.aprovados} • Recuperação {fechamento.recuperacao} • Reprovados {fechamento.reprovados}"
        else:
            status_html = _status_badge("Pendente", "warning")
            resumo = "Período sem fechamento consolidado."

        if periodo_ref is not None:
            url = reverse("educacao:fechamento_turma_periodo", args=[turma.id]) + f"?periodo={periodo_ref.id}"
            if can_close:
                acao_html = _actions_group(_link_button(url, "Fechar diário", "fa-solid fa-lock"))
            else:
                acao_html = _actions_group(_link_button(url, "Visualizar", "fa-solid fa-eye"))
        else:
            acao_html = _status_badge("Sem período", "neutral")

        rows.append(
            {
                "cells": [
                    {"text": turma.nome},
                    {"text": str(turma.ano_letivo or "—")},
                    {"text": str(periodo_ref) if periodo_ref else "Não definido"},
                    {"html": status_html},
                    {"text": resumo},
                    {"html": acao_html},
                ]
            }
        )

    turmas_informatica = list(_professor_informatica_turmas_qs(professor_user))
    turmas_info_ids = [t.id for t in turmas_informatica]
    aulas_info_rows = list(
        InformaticaAulaDiario.objects.filter(turma_id__in=turmas_info_ids)
        .values("turma_id")
        .annotate(
            total=Count("id"),
            encerradas=Count("id", filter=Q(encerrada=True)),
            realizadas=Count("id", filter=Q(status=InformaticaAulaDiario.Status.REALIZADA)),
        )
    )
    aulas_info_map = {row["turma_id"]: row for row in aulas_info_rows}
    freq_info_rows = list(
        InformaticaFrequencia.objects.filter(aula__turma_id__in=turmas_info_ids)
        .values("aula__turma_id")
        .annotate(total=Count("id"), presentes=Count("id", filter=Q(presente=True)))
    )
    freq_info_map = {row["aula__turma_id"]: row for row in freq_info_rows}
    alertas_info_map = {
        row["matricula__turma_id"]: row["total"]
        for row in InformaticaAlertaFrequencia.objects.filter(
            ativo=True,
            matricula__turma_id__in=turmas_info_ids,
        )
        .values("matricula__turma_id")
        .annotate(total=Count("id"))
    }
    latest_aula_map = {}
    for row in (
        InformaticaAulaDiario.objects.filter(turma_id__in=turmas_info_ids)
        .order_by("turma_id", "-data_aula", "-id")
        .values("id", "turma_id")
    ):
        latest_aula_map.setdefault(row["turma_id"], row["id"])

    headers_informatica = [
        {"label": "Turma (Informática)"},
        {"label": "Ano", "width": "90px"},
        {"label": "Aulas", "width": "110px"},
        {"label": "Frequência", "width": "110px"},
        {"label": "Status", "width": "160px"},
        {"label": "Resumo", "width": "230px"},
        {"label": "Ação", "width": "250px"},
    ]
    rows_informatica = []
    for turma in turmas_informatica:
        aula_row = aulas_info_map.get(turma.id, {})
        aulas_total = int(aula_row.get("total", 0))
        aulas_encerradas = int(aula_row.get("encerradas", 0))
        freq_row = freq_info_map.get(turma.id, {})
        freq_total = int(freq_row.get("total", 0))
        freq_presentes = int(freq_row.get("presentes", 0))
        freq_media = round((freq_presentes / freq_total) * 100, 2) if freq_total > 0 else 0
        alertas_ativos = int(alertas_info_map.get(turma.id, 0))

        if aulas_total == 0:
            status_html = _status_badge("Sem calendário", "neutral")
            resumo = "Não há encontros/aulas gerados para a turma."
        elif aulas_encerradas >= aulas_total and alertas_ativos == 0:
            status_html = _status_badge("Pronto para encerrar", "success")
            resumo = f"Aulas fechadas: {aulas_encerradas}/{aulas_total} • Alertas: {alertas_ativos}"
        else:
            status_html = _status_badge("Em andamento", "warning")
            resumo = f"Aulas fechadas: {aulas_encerradas}/{aulas_total} • Alertas: {alertas_ativos}"

        latest_aula_id = latest_aula_map.get(turma.id)
        rows_informatica.append(
            {
                "cells": [
                    {"text": turma.codigo, "url": reverse("educacao:informatica_turma_detail", args=[turma.id])},
                    {"text": str(turma.ano_letivo)},
                    {"text": f"{aulas_encerradas}/{aulas_total}"},
                    {"text": f"{freq_media:.2f}%"},
                    {"html": status_html},
                    {"text": resumo},
                    {
                        "html": _actions_group(
                            _link_button(
                                reverse("educacao:informatica_turma_detail", args=[turma.id]),
                                "Abrir turma",
                                "fa-solid fa-laptop-code",
                            ),
                            _link_button(
                                reverse("educacao:informatica_frequencia_aula", args=[latest_aula_id])
                                if latest_aula_id
                                else reverse("educacao:informatica_frequencia") + f"?turma={turma.id}",
                                "Fechar aula",
                                "fa-solid fa-lock",
                            ),
                        )
                    },
                ]
            }
        )

    context = {
        **_base_context(
            request=request,
            professor_user=professor_user,
            codigo=codigo_canonico,
            page_title="Fechamento de Diário",
            page_subtitle="Consolide resultados do regular e acompanhe o fechamento operacional das turmas de informática.",
            nav_key="fechamento",
        ),
        "headers": headers,
        "rows": rows,
        "can_close": can_close,
        "headers_informatica": headers_informatica,
        "rows_informatica": rows_informatica,
    }
    return render(request, "educacao/professor_area/fechamento.html", context)
