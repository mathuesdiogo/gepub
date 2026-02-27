from __future__ import annotations

from calendar import Calendar, monthrange
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.exports import export_pdf_template
from apps.core.rbac import (
    can,
    get_profile,
    is_admin,
    scope_filter_secretarias,
    scope_filter_turmas,
    scope_filter_unidades,
)
from apps.org.models import Secretaria, Unidade

from .forms_calendario import CalendarioEducacionalEventoForm
from .models import Matricula, Turma
from .models_calendario import CalendarioEducacionalEvento

MESES_PTBR = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

DIAS_SEMANA_SHORT = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]


def _evento_data_label(evento: CalendarioEducacionalEvento) -> str:
    if evento.data_fim and evento.data_fim != evento.data_inicio:
        return f"{evento.data_inicio:%d/%m/%Y} até {evento.data_fim:%d/%m/%Y}"
    return f"{evento.data_inicio:%d/%m/%Y}"


def _evento_scope_label(evento: CalendarioEducacionalEvento) -> str:
    if evento.unidade_id:
        return getattr(evento.unidade, "nome", "—") or "—"
    return getattr(evento.secretaria, "nome", "—") or "—"


def _tipo_priority(tipo: str) -> int:
    priorities = {
        CalendarioEducacionalEvento.Tipo.FERIADO: 90,
        CalendarioEducacionalEvento.Tipo.RECESSO: 80,
        CalendarioEducacionalEvento.Tipo.FACULTATIVO: 70,
        CalendarioEducacionalEvento.Tipo.PLANEJAMENTO: 60,
        CalendarioEducacionalEvento.Tipo.PEDAGOGICO: 50,
        CalendarioEducacionalEvento.Tipo.BIMESTRE_INICIO: 40,
        CalendarioEducacionalEvento.Tipo.BIMESTRE_FIM: 35,
        CalendarioEducacionalEvento.Tipo.COMEMORATIVA: 30,
        CalendarioEducacionalEvento.Tipo.LETIVO: 20,
        CalendarioEducacionalEvento.Tipo.OUTRO: 10,
    }
    return priorities.get(tipo, 1)


def _tipo_css(tipo: str) -> str:
    return (tipo or CalendarioEducacionalEvento.Tipo.OUTRO).lower()


def _legendas_calendario() -> list[dict]:
    items = [
        (CalendarioEducacionalEvento.Tipo.LETIVO, "Dia letivo"),
        (CalendarioEducacionalEvento.Tipo.FACULTATIVO, "Ponto facultativo"),
        (CalendarioEducacionalEvento.Tipo.FERIADO, "Feriado"),
        (CalendarioEducacionalEvento.Tipo.COMEMORATIVA, "Data comemorativa"),
        (CalendarioEducacionalEvento.Tipo.BIMESTRE_INICIO, "Início de bimestre"),
        (CalendarioEducacionalEvento.Tipo.BIMESTRE_FIM, "Fim de bimestre"),
        (CalendarioEducacionalEvento.Tipo.PLANEJAMENTO, "Planejamento pedagógico"),
        (CalendarioEducacionalEvento.Tipo.RECESSO, "Recesso/Férias"),
        (CalendarioEducacionalEvento.Tipo.PEDAGOGICO, "Parada pedagógica"),
        (CalendarioEducacionalEvento.Tipo.OUTRO, "Outro"),
    ]
    return [
        {
            "tipo": tipo,
            "label": label,
            "cor": CalendarioEducacionalEvento.default_color_for_tipo(tipo),
            "tipo_css": _tipo_css(tipo),
        }
        for tipo, label in items
    ]


def _eventos_por_dia_no_mes(ano: int, mes: int, eventos: list[CalendarioEducacionalEvento]) -> dict[int, list]:
    inicio_mes = date(ano, mes, 1)
    fim_mes = date(ano, mes, monthrange(ano, mes)[1])
    eventos_por_dia: dict[int, list] = {}
    for evento in eventos:
        ini = max(evento.data_inicio, inicio_mes)
        fim = min(evento.data_fim_effective, fim_mes)
        cursor = ini
        while cursor <= fim:
            eventos_por_dia.setdefault(cursor.day, []).append(evento)
            cursor += timedelta(days=1)
    return eventos_por_dia


def _semanas_render_mes(ano: int, mes: int, eventos_por_dia: dict[int, list]) -> list[list[dict]]:
    semanas_raw = Calendar(firstweekday=6).monthdayscalendar(ano, mes)
    semanas_render = []
    for semana in semanas_raw:
        row = []
        for idx_dia, dia in enumerate(semana):
            eventos_dia = eventos_por_dia.get(dia, []) if dia else []
            dominant_tipo = None
            if eventos_dia:
                dominant_tipo = max(eventos_dia, key=lambda ev: _tipo_priority(ev.tipo)).tipo
            row.append(
                {
                    "day": dia,
                    "events": eventos_dia,
                    "is_weekend": idx_dia in (0, 6),
                    "has_holiday": any(ev.tipo == CalendarioEducacionalEvento.Tipo.FERIADO for ev in eventos_dia),
                    "dominant_tipo": dominant_tipo,
                }
            )
        semanas_render.append(row)
    return semanas_render


def _dias_letivos_no_mes(eventos_por_dia: dict[int, list]) -> int:
    return len(
        [
            day
            for day, eventos in eventos_por_dia.items()
            if any(ev.dia_letivo or ev.tipo == CalendarioEducacionalEvento.Tipo.LETIVO for ev in eventos)
        ]
    )


def _build_anotacoes(eventos: list[CalendarioEducacionalEvento]) -> list[dict]:
    out: list[dict] = []
    for evento in eventos:
        out.append(
            {
                "titulo": evento.titulo or "—",
                "tipo": evento.get_tipo_display() or "—",
                "tipo_css": _tipo_css(evento.tipo),
                "periodo": _evento_data_label(evento),
                "escopo": _evento_scope_label(evento),
                "cor_hex": evento.cor_hex or CalendarioEducacionalEvento.default_color_for_tipo(evento.tipo),
                "dia_letivo": evento.dia_letivo,
                "descricao": evento.descricao or "",
            }
        )
    return out


def _eventos_mes(eventos: list[CalendarioEducacionalEvento], ano: int, mes: int) -> list[CalendarioEducacionalEvento]:
    inicio_mes = date(ano, mes, 1)
    fim_mes = date(ano, mes, monthrange(ano, mes)[1])
    return [ev for ev in eventos if ev.data_inicio <= fim_mes and ev.data_fim_effective >= inicio_mes]


def _calendar_manage_allowed(user) -> bool:
    if is_admin(user):
        return True
    if not can(user, "educacao.manage"):
        return False
    role = (getattr(get_profile(user), "role", "") or "").upper()
    return role in {"SECRETARIA", "MUNICIPAL", "ADMIN"}


def _scope_eventos_usuario(user, qs):
    if is_admin(user):
        return qs

    p = get_profile(user)
    if not p:
        return qs.none()

    role = (p.role or "").upper()

    if role == "ALUNO" and getattr(p, "aluno_id", None):
        matriculas = Matricula.objects.select_related(
            "turma__unidade__secretaria"
        ).filter(aluno_id=p.aluno_id)
        secretarias_ids = list(
            matriculas.values_list("turma__unidade__secretaria_id", flat=True).distinct()
        )
        unidades_ids = list(
            matriculas.values_list("turma__unidade_id", flat=True).distinct()
        )
        if not secretarias_ids:
            return qs.none()
        return qs.filter(secretaria_id__in=secretarias_ids).filter(
            Q(unidade__isnull=True) | Q(unidade_id__in=unidades_ids)
        )

    if role == "PROFESSOR":
        turmas_qs = scope_filter_turmas(
            user, Turma.objects.select_related("unidade__secretaria").all()
        )
        secretarias_ids = list(turmas_qs.values_list("unidade__secretaria_id", flat=True).distinct())
        unidades_ids = list(turmas_qs.values_list("unidade_id", flat=True).distinct())
        if not secretarias_ids:
            return qs.none()
        return qs.filter(secretaria_id__in=secretarias_ids).filter(
            Q(unidade__isnull=True) | Q(unidade_id__in=unidades_ids)
        )

    secretarias_qs = scope_filter_secretarias(user, Secretaria.objects.all())
    unidades_qs = scope_filter_unidades(user, Unidade.objects.all())
    return qs.filter(secretaria__in=secretarias_qs).filter(
        Q(unidade__isnull=True) | Q(unidade__in=unidades_qs)
    )


@login_required
@require_perm("educacao.view")
def calendario_index(request):
    today = timezone.localdate()
    ano_default = today.year
    mes_default = today.month

    try:
        ano = int(request.GET.get("ano", ano_default))
    except Exception:
        ano = ano_default

    try:
        mes = int(request.GET.get("mes", mes_default))
    except Exception:
        mes = mes_default

    if mes < 1 or mes > 12:
        mes = mes_default

    inicio_mes = date(ano, mes, 1)
    fim_mes = date(ano, mes, monthrange(ano, mes)[1])

    eventos_qs = _scope_eventos_usuario(
        request.user,
        CalendarioEducacionalEvento.objects.select_related("secretaria", "unidade")
        .filter(ativo=True, ano_letivo=ano),
    )

    eventos_mes_qs = eventos_qs.filter(
            data_inicio__lte=fim_mes,
            data_fim__gte=inicio_mes,
        )
    eventos_mes = list(eventos_mes_qs.order_by("data_inicio", "titulo", "id"))

    export_kind = (request.GET.get("export") or "").strip().lower()
    if export_kind in {"pdf_mes", "pdf_ano"}:
        legendas_pdf = _legendas_calendario()
        if export_kind == "pdf_mes":
            eventos_export = list(eventos_mes_qs.order_by("data_inicio", "titulo", "id"))
            eventos_por_dia_pdf = _eventos_por_dia_no_mes(ano, mes, eventos_export)
            semanas_pdf = _semanas_render_mes(ano, mes, eventos_por_dia_pdf)
            dias_letivos_pdf = _dias_letivos_no_mes(eventos_por_dia_pdf)
            anotacoes_pdf = _build_anotacoes(eventos_export)
            return export_pdf_template(
                request,
                filename=f"calendario_educacional_{ano}_{mes:02d}.pdf",
                title=f"Calendário Educacional • {MESES_PTBR.get(mes, mes)} {ano}",
                template_name="educacao/pdf/calendario_mes.html",
                subtitle="Eventos do mês letivo selecionado",
                filtros=f"Ano={ano} | Mês={MESES_PTBR.get(mes, mes)}",
                hash_payload=f"{ano}-{mes}-{len(eventos_export)}",
                context={
                    "ano": ano,
                    "mes": mes,
                    "mes_nome": MESES_PTBR.get(mes, str(mes)),
                    "dias_semana": DIAS_SEMANA_SHORT,
                    "semanas": semanas_pdf,
                    "legendas": legendas_pdf,
                    "anotacoes": anotacoes_pdf,
                    "dias_letivos_mes": dias_letivos_pdf,
                    "total_eventos_mes": len(eventos_export),
                },
            )

        eventos_export = list(eventos_qs.order_by("data_inicio", "titulo", "id"))
        meses_cards = []
        dias_letivos_ano = 0
        total_eventos_ano = len(eventos_export)
        for mes_i in range(1, 13):
            eventos_no_mes = _eventos_mes(eventos_export, ano, mes_i)
            eventos_por_dia_mes = _eventos_por_dia_no_mes(ano, mes_i, eventos_no_mes)
            semanas_mes = _semanas_render_mes(ano, mes_i, eventos_por_dia_mes)
            dias_letivos_mes = _dias_letivos_no_mes(eventos_por_dia_mes)
            dias_letivos_ano += dias_letivos_mes
            meses_cards.append(
                {
                    "mes": mes_i,
                    "mes_nome": MESES_PTBR.get(mes_i, str(mes_i)),
                    "semanas": semanas_mes,
                    "dias_letivos": dias_letivos_mes,
                    "eventos": len(eventos_no_mes),
                }
            )
        anotacoes_ano = _build_anotacoes(eventos_export)
        return export_pdf_template(
            request,
            filename=f"calendario_educacional_anual_{ano}.pdf",
            title=f"Calendário Educacional Anual • {ano}",
            template_name="educacao/pdf/calendario_ano.html",
            subtitle="Eventos do ano letivo completo",
            filtros=f"Ano letivo={ano}",
            hash_payload=f"{ano}-anual-{total_eventos_ano}",
            context={
                "ano": ano,
                "dias_semana": DIAS_SEMANA_SHORT,
                "meses_cards": meses_cards,
                "legendas": legendas_pdf,
                "anotacoes": anotacoes_ano,
                "dias_letivos_ano": dias_letivos_ano,
                "total_eventos_ano": total_eventos_ano,
            },
        )

    eventos_por_dia = _eventos_por_dia_no_mes(ano, mes, eventos_mes)

    ancora = today if (ano == today.year and mes == today.month) else inicio_mes

    eventos_proximos = [ev for ev in eventos_mes if ev.data_fim_effective >= ancora][:20]
    avisos_proximos_mes = []
    for ev in eventos_proximos[:10]:
        if ev.data_inicio > ancora:
            dias = (ev.data_inicio - ancora).days
            aviso = f"Começa em {dias} dia(s)"
        elif ev.data_fim_effective >= ancora:
            aviso = "Em andamento"
        else:
            aviso = "Encerrado"
        avisos_proximos_mes.append({"evento": ev, "aviso": aviso})

    can_manage_calendar = _calendar_manage_allowed(request.user)
    base_query = f"ano={ano}&mes={mes}"
    actions = [
        {
            "label": "PDF do Mês",
            "url": f"{reverse('educacao:calendario_index')}?{base_query}&export=pdf_mes",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
        {
            "label": "PDF Anual",
            "url": f"{reverse('educacao:calendario_index')}?ano={ano}&export=pdf_ano",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
    ]
    if can_manage_calendar:
        actions.insert(
            0,
            {
                "label": "Novo Evento",
                "url": reverse("educacao:calendario_evento_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            },
        )

    prev_ano, prev_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    next_ano, next_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)

    semanas_render = _semanas_render_mes(ano, mes, eventos_por_dia)

    context = {
        "actions": actions,
        "can_manage_calendar": can_manage_calendar,
        "ano": ano,
        "mes": mes,
        "mes_nome": MESES_PTBR.get(mes, str(mes)),
        "semanas": semanas_render,
        "eventos_por_dia": eventos_por_dia,
        "eventos_proximos": eventos_proximos,
        "avisos_proximos_mes": avisos_proximos_mes,
        "ano_prev": prev_ano,
        "mes_prev": prev_mes,
        "ano_next": next_ano,
        "mes_next": next_mes,
        "anos_opcoes": list(range(ano - 2, ano + 3)),
        "meses_opcoes": [(i, MESES_PTBR.get(i, str(i))) for i in range(1, 13)],
        "legendas": _legendas_calendario(),
    }
    return render(request, "educacao/calendario_index.html", context)


@login_required
@require_perm("educacao.manage")
def calendario_evento_create(request):
    if not _calendar_manage_allowed(request.user):
        return HttpResponseForbidden("403 — Apenas a secretaria de educação pode editar o calendário.")

    if request.method == "POST":
        form = CalendarioEducacionalEventoForm(request.POST, user=request.user)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.criado_por = request.user
            evento.atualizado_por = request.user
            evento.save()
            messages.success(request, "Evento do calendário criado com sucesso.")
            return redirect("educacao:calendario_index")
        messages.error(request, "Corrija os campos do formulário.")
    else:
        form = CalendarioEducacionalEventoForm(user=request.user)

    return render(
        request,
        "educacao/calendario_form.html",
        {
            "form": form,
            "mode": "create",
            "cancel_url": reverse("educacao:calendario_index"),
            "submit_label": "Salvar evento",
            "action_url": reverse("educacao:calendario_evento_create"),
        },
    )


@login_required
@require_perm("educacao.manage")
def calendario_evento_update(request, pk: int):
    if not _calendar_manage_allowed(request.user):
        return HttpResponseForbidden("403 — Apenas a secretaria de educação pode editar o calendário.")

    evento = get_object_or_404(
        _scope_eventos_usuario(request.user, CalendarioEducacionalEvento.objects.all()),
        pk=pk,
    )

    if request.method == "POST":
        form = CalendarioEducacionalEventoForm(request.POST, instance=evento, user=request.user)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.atualizado_por = request.user
            evento.save()
            messages.success(request, "Evento do calendário atualizado.")
            return redirect("educacao:calendario_index")
        messages.error(request, "Corrija os campos do formulário.")
    else:
        form = CalendarioEducacionalEventoForm(instance=evento, user=request.user)

    return render(
        request,
        "educacao/calendario_form.html",
        {
            "form": form,
            "mode": "update",
            "evento": evento,
            "cancel_url": reverse("educacao:calendario_index"),
            "submit_label": "Atualizar evento",
            "action_url": reverse("educacao:calendario_evento_update", args=[evento.pk]),
        },
    )


@login_required
@require_perm("educacao.manage")
def calendario_evento_delete(request, pk: int):
    if not _calendar_manage_allowed(request.user):
        return HttpResponseForbidden("403 — Apenas a secretaria de educação pode editar o calendário.")

    evento = get_object_or_404(
        _scope_eventos_usuario(request.user, CalendarioEducacionalEvento.objects.all()),
        pk=pk,
    )
    if request.method == "POST":
        evento.delete()
        messages.success(request, "Evento removido do calendário.")
        return redirect("educacao:calendario_index")
    return redirect("educacao:calendario_index")
