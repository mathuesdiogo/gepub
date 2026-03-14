from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render
from datetime import timedelta
import calendar

from apps.core.decorators import require_perm
from apps.core.rbac import (
    can,
    role_scope_base,
    scope_filter_alunos,
    scope_filter_matriculas,
    scope_filter_secretarias,
    scope_filter_turmas,
    scope_filter_unidades,
)
from apps.org.models import Secretaria, Unidade

from .models import Aluno, Matricula, MatrizCurricular, RenovacaoMatricula, Turma
from .models_calendario import CalendarioEducacionalEvento
from .models_diario import Aula, DiarioTurma, JustificativaFaltaPedido
from . import views_alunos_crud, views_turmas_crud


def _build_month_calendar_context(eventos, ref_date):
    meses_pt = [
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    ]
    semana_labels = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    month_start = ref_date.replace(day=1)
    last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
    month_end = ref_date.replace(day=last_day)

    tipo_prioridade = {
        "FERIADO": 100,
        "RECESSO": 90,
        "FACULTATIVO": 80,
        "PEDAGOGICO": 70,
        "PLANEJAMENTO": 60,
        "COMEMORATIVA": 50,
        "BIMESTRE_INICIO": 40,
        "BIMESTRE_FIM": 35,
        "LETIVO": 20,
        "OUTRO": 10,
    }
    event_type_by_day: dict[int, str] = {}
    for ev in eventos:
        ev_start = ev.data_inicio
        ev_end = ev.data_fim or ev.data_inicio
        start = max(ev_start, month_start)
        end = min(ev_end, month_end)
        cursor = start
        while cursor <= end:
            day = cursor.day
            tipo = (getattr(ev, "tipo", "") or "OUTRO").upper()
            current_tipo = event_type_by_day.get(day)
            if current_tipo is None:
                event_type_by_day[day] = tipo
            elif tipo_prioridade.get(tipo, 0) > tipo_prioridade.get(current_tipo, 0):
                event_type_by_day[day] = tipo
            cursor += timedelta(days=1)

    cal = calendar.Calendar(firstweekday=6)
    weeks = []
    for week in cal.monthdayscalendar(ref_date.year, ref_date.month):
        row = []
        for day in week:
            in_month = day > 0
            day_tipo = event_type_by_day.get(day) if in_month else None
            row.append(
                {
                    "day": day if in_month else "",
                    "is_today": in_month and day == ref_date.day,
                    "has_event": bool(in_month and day_tipo),
                    "event_type": (day_tipo or "").lower(),
                }
            )
        weeks.append(row)

    return {
        "mes_label": f"{meses_pt[ref_date.month - 1]} de {ref_date.year}",
        "semana_labels": semana_labels,
        "weeks": weeks,
    }


@login_required
@require_perm("educacao.view")
def index(request):
    user = request.user
    cache_key = f"edu_dashboard_{user.id}"

    data = cache.get(cache_key)

    if data is None:
        unidades_educacao_qs = scope_filter_unidades(
            user,
            Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
        )
        turmas_educacao_qs = scope_filter_turmas(
            user,
            Turma.objects.filter(unidade__tipo=Unidade.Tipo.EDUCACAO),
        )
        matriculas_educacao_qs = scope_filter_matriculas(
            user,
            Matricula.objects.filter(turma__unidade__tipo=Unidade.Tipo.EDUCACAO),
        )
        aluno_ids_educacao = matriculas_educacao_qs.values_list("aluno_id", flat=True).distinct()

        unidades_total = unidades_educacao_qs.count()
        turmas_total = turmas_educacao_qs.count()
        alunos_total = scope_filter_alunos(user, Aluno.objects.filter(id__in=aluno_ids_educacao)).count()
        matriculas_total = matriculas_educacao_qs.count()

        matrizes_qs = MatrizCurricular.objects.select_related("unidade")
        unidades_scope = unidades_educacao_qs
        matrizes_total = matrizes_qs.filter(unidade__in=unidades_scope, ativo=True).count()

        secretarias_scope = scope_filter_secretarias(user, Secretaria.objects.all())
        hoje = timezone.localdate()
        renovacoes_qs = RenovacaoMatricula.objects.filter(secretaria__in=secretarias_scope)
        renovacoes_total = renovacoes_qs.count()
        renovacoes_agendadas = renovacoes_qs.filter(
            ativo=True,
            processado_em__isnull=True,
            data_inicio__gt=hoje,
        ).count()
        renovacoes_abertas = renovacoes_qs.filter(
            ativo=True,
            processado_em__isnull=True,
            data_inicio__lte=hoje,
            data_fim__gte=hoje,
        ).count()
        renovacoes_pendentes_processamento = renovacoes_qs.filter(
            ativo=True,
            processado_em__isnull=True,
            data_fim__lt=hoje,
        ).count()
        renovacoes_processadas = renovacoes_qs.filter(processado_em__isnull=False).count()

        data = {
            "unidades_total": unidades_total,
            "turmas_total": turmas_total,
            "alunos_total": alunos_total,
            "matriculas_total": matriculas_total,
            "matrizes_total": matrizes_total,
            "renovacoes_total": renovacoes_total,
            "renovacoes_agendadas": renovacoes_agendadas,
            "renovacoes_abertas": renovacoes_abertas,
            "renovacoes_pendentes_processamento": renovacoes_pendentes_processamento,
            "renovacoes_processadas": renovacoes_processadas,
        }

        cache.set(cache_key, data, 300)

    profile = getattr(user, "profile", None)
    role_base = role_scope_base(getattr(profile, "role", None))
    if role_base == "PROFESSOR":
        turmas_scope = scope_filter_turmas(
            user,
            Turma.objects.filter(unidade__tipo=Unidade.Tipo.EDUCACAO),
        ).select_related("unidade")
        diarios_qs = (
            DiarioTurma.objects.select_related("turma", "turma__unidade")
            .filter(professor=user, turma__in=turmas_scope)
            .order_by("-ano_letivo", "turma__nome")
        )
        diarios_ids = list(diarios_qs.values_list("id", flat=True))
        secretaria_ids = list(turmas_scope.values_list("unidade__secretaria_id", flat=True).distinct())
        unidade_ids = list(turmas_scope.values_list("unidade_id", flat=True).distinct())
        eventos_calendario = CalendarioEducacionalEvento.objects.none()
        if secretaria_ids:
            try:
                eventos_calendario = (
                    CalendarioEducacionalEvento.objects.filter(
                        ativo=True,
                        secretaria_id__in=secretaria_ids,
                        data_fim__gte=timezone.localdate(),
                    )
                    .filter(Q(unidade__isnull=True) | Q(unidade_id__in=unidade_ids))
                    .order_by("data_inicio", "titulo")
                )
            except (ProgrammingError, OperationalError):
                eventos_calendario = CalendarioEducacionalEvento.objects.none()
        eventos_lista = list(eventos_calendario[:8])
        data.update(
            {
                "professor_code": (getattr(profile, "codigo_acesso", "") or user.username),
                "diarios_total": len(diarios_ids),
                "aulas_total": Aula.objects.filter(diario_id__in=diarios_ids).count() if diarios_ids else 0,
                "pendencias_total": JustificativaFaltaPedido.objects.filter(
                    aula__diario_id__in=diarios_ids,
                    status=JustificativaFaltaPedido.Status.PENDENTE,
                ).count()
                if diarios_ids
                else 0,
                "diarios_preview": list(diarios_qs[:6]),
                "eventos_calendario": eventos_lista,
                "professor_calendario": _build_month_calendar_context(eventos_lista, timezone.localdate()),
            }
        )

    data["can_edu_manage"] = can(user, "educacao.manage")
    data["can_nee_view"] = can(user, "nee.view")

    return render(request, "educacao/index.html", data)


@login_required
@require_perm("educacao.view")
def turma_list(request):
    return views_turmas_crud.turma_list(request)


@login_required
@require_perm("educacao.view")
def turma_detail(request, pk: int):
    return views_turmas_crud.turma_detail(request, pk)


@login_required
@require_perm("educacao.manage")
def turma_create(request):
    return views_turmas_crud.turma_create(request)


@login_required
@require_perm("educacao.manage")
def turma_update(request, pk: int):
    return views_turmas_crud.turma_update(request, pk)


@login_required
@require_perm("educacao.view")
def aluno_list(request):
    return views_alunos_crud.aluno_list(request)


@login_required
@require_perm("educacao.view")
def aluno_detail(request, pk: int):
    return views_alunos_crud.aluno_detail(request, pk)


@login_required
@require_perm("educacao.manage")
def aluno_create(request):
    return views_alunos_crud.aluno_create(request)


@login_required
@require_perm("educacao.manage")
def aluno_update(request, pk: int):
    return views_alunos_crud.aluno_update(request, pk)
