from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Max, Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.core.rbac import can, role_scope_base

from .forms import AlunoForm
from .forms_informatica import (
    InformaticaAulaForm,
    InformaticaCursoForm,
    InformaticaGradeHorarioForm,
    InformaticaLaboratorioForm,
    InformaticaMatriculaForm,
    InformaticaMatriculaRemanejamentoForm,
    InformaticaSolicitacaoForm,
    InformaticaTurmaForm,
    alunos_scope,
    cursos_scope,
    grades_scope,
    laboratorios_scope,
    turmas_scope,
)
from .models import Aluno, Matricula
from .models_calendario import CalendarioEducacionalEvento
from .models_informatica import (
    InformaticaAlertaFrequencia,
    InformaticaAulaDiario,
    InformaticaCurso,
    InformaticaEncontroSemanal,
    InformaticaGradeHorario,
    InformaticaFrequencia,
    InformaticaLaboratorio,
    InformaticaListaEspera,
    InformaticaMatricula,
    InformaticaMatriculaMovimentacao,
    InformaticaOcorrencia,
    InformaticaSolicitacaoVaga,
    InformaticaTurma,
)
from .models_periodos import PeriodoLetivo
from .services_informatica_matricula import registrar_movimentacao_informatica


INFORMATICA_INICIO_PADRAO_MUNICIPIO_ANO = {
    ("governador nunes freire", 2026): date(2026, 3, 16),
}


def _forbidden(message: str = "403 — Você não tem permissão para acessar esta página."):
    return HttpResponseForbidden(message)


def _assert_perm(request, perm: str):
    if not can(request.user, perm):
        return _forbidden()
    return None


def _is_professor(user) -> bool:
    profile = getattr(user, "profile", None)
    return role_scope_base(getattr(profile, "role", None) if profile else None) == "PROFESSOR"


def _profile_role(user) -> str:
    profile = getattr(user, "profile", None)
    return ((getattr(profile, "role", "") or "") + "").strip().upper()


def _is_informatica_read_only(user) -> bool:
    # Secretaria de Educação acompanha o curso em modo somente leitura.
    return _profile_role(user) == "EDU_SECRETARIO"


def _is_informatica_coord(user) -> bool:
    return _profile_role(user) == "EDU_COORD"


def _can_manage_informatica(user) -> bool:
    return can(user, "educacao.manage") and not _is_informatica_read_only(user)


def _can_manage_informatica_execucao(user) -> bool:
    # Coordenação de informática atua em planejamento/estrutura e acompanhamento.
    # Execução pedagógica (aula/frequência/notas) é responsabilidade da docência.
    return _can_manage_informatica(user) and not _is_informatica_coord(user)


def _can_view_informatica_execucao(user) -> bool:
    # Coordenação não acessa telas de execução (aula/frequência/notas).
    return not _is_informatica_coord(user)


def _assert_informatica_write(request):
    if _can_manage_informatica(request.user):
        return None
    return _forbidden("403 — Perfil com acesso somente leitura ao Curso de Informática.")


def _can_manage_or_professor_informatica(user) -> bool:
    if _can_manage_informatica(user):
        return True
    if not _is_professor(user):
        return False
    return InformaticaTurma.objects.filter(
        instrutor=user,
        status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
    ).exists()


def _resolve_profile_municipio_id(user) -> int | None:
    profile = getattr(user, "profile", None)
    if profile and profile.municipio_id:
        return int(profile.municipio_id)
    if profile and profile.secretaria_id:
        secretaria_obj = getattr(profile, "secretaria", None)
        secretaria_municipio_id = getattr(secretaria_obj, "municipio_id", None)
        if secretaria_municipio_id:
            return int(secretaria_municipio_id)
        from apps.org.models import Secretaria

        secretaria_municipio_id = Secretaria.objects.filter(pk=profile.secretaria_id).values_list(
            "municipio_id", flat=True
        ).first()
        if secretaria_municipio_id:
            return int(secretaria_municipio_id)
    if profile and profile.unidade_id:
        unidade_obj = getattr(profile, "unidade", None)
        unidade_municipio_id = getattr(getattr(unidade_obj, "secretaria", None), "municipio_id", None)
        if unidade_municipio_id:
            return int(unidade_municipio_id)
        from apps.org.models import Unidade

        unidade_municipio_id = Unidade.objects.filter(pk=profile.unidade_id).values_list(
            "secretaria__municipio_id", flat=True
        ).first()
        if unidade_municipio_id:
            return int(unidade_municipio_id)
    return None


def _resolve_default_municipio_id(user) -> int | None:
    if can(user, "org.manage_municipio"):
        return _resolve_profile_municipio_id(user)

    curso = cursos_scope(user).values_list("municipio_id", flat=True).first()
    if curso:
        return int(curso)

    municipio_id = _resolve_profile_municipio_id(user)
    if municipio_id:
        return int(municipio_id)

    return None


def _resolve_escola_origem_do_aluno(aluno_id: int):
    mat = (
        Matricula.objects.filter(aluno_id=aluno_id, situacao=Matricula.Situacao.ATIVA)
        .select_related("turma", "turma__unidade")
        .order_by("-id")
        .first()
    )
    return getattr(getattr(mat, "turma", None), "unidade", None)


def _resolve_origem_indicacao_do_aluno(aluno_id: int) -> tuple[object | None, str]:
    escola = _resolve_escola_origem_do_aluno(aluno_id)
    if escola:
        origem = f"Escola de origem: {escola.nome}"
        return escola, origem[:80]
    return None, "Cadastro do aluno"


def _next_lista_espera_item(curso_id: int, turma: InformaticaTurma | None = None):
    qs = (
        InformaticaListaEspera.objects.select_related(
            "aluno",
            "escola_origem",
            "curso",
            "turma_preferida",
            "laboratorio_preferido",
        )
        .filter(curso_id=curso_id, status=InformaticaListaEspera.Status.ATIVA)
        .order_by("-prioridade", "posicao", "id")
    )
    if turma:
        qs = qs.filter(
            Q(turma_preferida__isnull=True) | Q(turma_preferida_id=turma.id),
            Q(laboratorio_preferido__isnull=True) | Q(laboratorio_preferido_id=turma.laboratorio_id),
            Q(turno_preferido=InformaticaSolicitacaoVaga.TurnoPreferido.QUALQUER) | Q(turno_preferido=turma.turno),
        )
    return qs.first()


def _renumber_lista_espera(curso_id: int):
    itens = list(
        InformaticaListaEspera.objects.filter(curso_id=curso_id, status=InformaticaListaEspera.Status.ATIVA)
        .order_by("-prioridade", "posicao", "id")
        .values_list("id", flat=True)
    )
    if not itens:
        return
    for idx, item_id in enumerate(itens, start=1):
        InformaticaListaEspera.objects.filter(pk=item_id).update(posicao=idx)


def _upsert_alerta(matricula: InformaticaMatricula, tipo: str, ativo: bool, percentual: float, faltas_consecutivas: int):
    alerta, _ = InformaticaAlertaFrequencia.objects.get_or_create(
        matricula=matricula,
        tipo=tipo,
        defaults={
            "percentual_frequencia": percentual,
            "faltas_consecutivas": faltas_consecutivas,
            "ativo": ativo,
        },
    )
    if alerta.ativo != ativo or float(alerta.percentual_frequencia or 0) != float(percentual) or int(
        alerta.faltas_consecutivas or 0
    ) != int(faltas_consecutivas):
        alerta.ativo = ativo
        alerta.percentual_frequencia = percentual
        alerta.faltas_consecutivas = faltas_consecutivas
        if not ativo and not alerta.resolvido_em:
            alerta.resolvido_em = timezone.now()
        if ativo:
            alerta.resolvido_em = None
        alerta.save(update_fields=["ativo", "percentual_frequencia", "faltas_consecutivas", "resolvido_em"])


def _recalcular_alertas_frequencia_turma(turma_id: int):
    matriculas = list(
        InformaticaMatricula.objects.filter(
            turma_id=turma_id,
            status=InformaticaMatricula.Status.MATRICULADO,
        ).select_related("aluno")
    )
    for m in matriculas:
        freq_qs = InformaticaFrequencia.objects.filter(aula__turma_id=turma_id, aluno_id=m.aluno_id).order_by(
            "aula__data_aula", "id"
        )
        total = freq_qs.count()
        presencas = freq_qs.filter(presente=True).count()
        percentual = round((presencas / total) * 100, 2) if total > 0 else 100.0

        consecutivas = 0
        max_consecutivas = 0
        for item in freq_qs:
            if item.presente:
                consecutivas = 0
            else:
                consecutivas += 1
                if consecutivas > max_consecutivas:
                    max_consecutivas = consecutivas

        _upsert_alerta(
            matricula=m,
            tipo=InformaticaAlertaFrequencia.Tipo.BAIXA_FREQUENCIA,
            ativo=percentual < 75,
            percentual=percentual,
            faltas_consecutivas=max_consecutivas,
        )
        _upsert_alerta(
            matricula=m,
            tipo=InformaticaAlertaFrequencia.Tipo.FALTAS_CONSECUTIVAS,
            ativo=max_consecutivas >= 3,
            percentual=percentual,
            faltas_consecutivas=max_consecutivas,
        )


def _seed_frequencias_aula(aula: InformaticaAulaDiario):
    matriculados = InformaticaMatricula.objects.filter(
        turma_id=aula.turma_id,
        status=InformaticaMatricula.Status.MATRICULADO,
    ).values_list("aluno_id", flat=True)
    existentes = set(
        InformaticaFrequencia.objects.filter(aula=aula).values_list("aluno_id", flat=True)
    )
    novos = []
    for aluno_id in matriculados:
        if aluno_id in existentes:
            continue
        novos.append(
            InformaticaFrequencia(
                aula=aula,
                aluno_id=aluno_id,
                presente=True,
            )
        )
    if novos:
        InformaticaFrequencia.objects.bulk_create(novos)


def _periodo_datas_turma(turma: InformaticaTurma) -> tuple[date, date]:
    periodos = PeriodoLetivo.objects.filter(ano_letivo=turma.ano_letivo, ativo=True).order_by("inicio")
    if periodos.exists():
        inicio = periodos.first().inicio
        fim = periodos.order_by("-fim").first().fim
    else:
        hoje = timezone.localdate()
        inicio = hoje
        fim = hoje + timedelta(days=120)

    # Permite início específico da oferta de Informática sem afetar o calendário geral.
    unidade = getattr(getattr(turma, "laboratorio", None), "unidade", None)
    secretaria_id = getattr(unidade, "secretaria_id", None)
    unidade_id = getattr(unidade, "id", None)
    if secretaria_id:
        ev_inicio = (
            CalendarioEducacionalEvento.objects.filter(
                ano_letivo=turma.ano_letivo,
                secretaria_id=secretaria_id,
                ativo=True,
            )
            .filter(Q(unidade__isnull=True) | Q(unidade_id=unidade_id))
            .filter(
                Q(titulo__icontains="informática")
                | Q(titulo__icontains="informatica")
            )
            .order_by("data_inicio")
            .first()
        )
        if ev_inicio and ev_inicio.data_inicio:
            inicio = max(inicio, ev_inicio.data_inicio)

    municipio_nome = (
        getattr(getattr(getattr(turma, "curso", None), "municipio", None), "nome", "")
        or ""
    ).strip().lower()
    fallback_inicio = INFORMATICA_INICIO_PADRAO_MUNICIPIO_ANO.get((municipio_nome, int(turma.ano_letivo or 0)))
    if fallback_inicio:
        inicio = max(inicio, fallback_inicio)

    if inicio > fim:
        inicio = fim
    return inicio, fim


def _datas_bloqueadas_turma(turma: InformaticaTurma, inicio: date, fim: date) -> set[date]:
    secretaria_id = turma.laboratorio.unidade.secretaria_id
    unidade_id = turma.laboratorio.unidade_id

    eventos = CalendarioEducacionalEvento.objects.filter(
        ano_letivo=turma.ano_letivo,
        secretaria_id=secretaria_id,
        ativo=True,
        data_inicio__lte=fim,
        data_fim__gte=inicio,
    ).filter(Q(unidade__isnull=True) | Q(unidade_id=unidade_id))

    tipos_bloqueio = {
        CalendarioEducacionalEvento.Tipo.FERIADO,
        CalendarioEducacionalEvento.Tipo.RECESSO,
        CalendarioEducacionalEvento.Tipo.FACULTATIVO,
        CalendarioEducacionalEvento.Tipo.PEDAGOGICO,
        CalendarioEducacionalEvento.Tipo.PLANEJAMENTO,
    }
    bloqueios = set()
    for ev in eventos:
        if ev.tipo not in tipos_bloqueio and ev.dia_letivo:
            continue
        cursor = max(inicio, ev.data_inicio)
        end = min(fim, ev.data_fim or ev.data_inicio)
        while cursor <= end:
            bloqueios.add(cursor)
            cursor = cursor + timedelta(days=1)
    return bloqueios


def _sync_encontros_da_grade(turma: InformaticaTurma):
    if not turma.grade_horario_id:
        return

    grade = turma.grade_horario
    expected_days = list(grade.dias_semana)
    existentes = list(turma.encontros.all())
    by_day = {int(e.dia_semana): e for e in existentes}

    for day in expected_days:
        encontro = by_day.get(int(day))
        payload = {
            "turma": turma,
            "grade_horario": grade,
            "dia_semana": int(day),
            "hora_inicio": grade.hora_inicio,
            "hora_fim": grade.hora_fim,
            "minutos_aula_efetiva": grade.duracao_aula_minutos,
            "minutos_intervalo_tecnico": grade.duracao_intervalo_minutos,
            "tipo_encontro": (
                "ESPECIAL_SEXTA"
                if grade.tipo_grade == InformaticaGradeHorario.TipoGrade.ESPECIAL_SEXTA
                else "REGULAR"
            ),
            "formato_especial": bool(grade.tipo_grade == InformaticaGradeHorario.TipoGrade.ESPECIAL_SEXTA),
            "ativo": True,
        }
        if encontro:
            for key, value in payload.items():
                setattr(encontro, key, value)
        else:
            encontro = InformaticaEncontroSemanal(**payload)
        encontro.full_clean()
        encontro.save()

    for item in existentes:
        if int(item.dia_semana) not in expected_days:
            item.ativo = False
            item.save(update_fields=["ativo"])


def _sync_calendario_aulas_turma(turma: InformaticaTurma):
    if not turma.grade_horario_id:
        return
    encontros = list(turma.encontros_ativos_qs)
    if not encontros:
        return

    inicio, fim = _periodo_datas_turma(turma)
    bloqueios = _datas_bloqueadas_turma(turma, inicio, fim)
    encontros_por_dia = {int(e.dia_semana): e for e in encontros}

    cursor = inicio
    datas_validas = set()
    while cursor <= fim:
        weekday = int(cursor.weekday())
        encontro = encontros_por_dia.get(weekday)
        if encontro and cursor not in bloqueios:
            datas_validas.add(cursor)
            defaults = {
                "encontro": encontro,
                "professor_id": turma.instrutor_id,
                "status": InformaticaAulaDiario.Status.PREVISTA,
                "tipo_encontro": (
                    InformaticaAulaDiario.TipoEncontro.ESPECIAL_SEXTA
                    if turma.encontro_unico_semana
                    else InformaticaAulaDiario.TipoEncontro.REGULAR
                ),
                "duracao_total_minutos": turma.grade_horario.duracao_total_minutos,
                "pausa_interna_minutos": turma.grade_horario.pausa_interna_opcional_minutos,
                "formato_especial": bool(turma.encontro_unico_semana),
            }
            aula, created = InformaticaAulaDiario.objects.get_or_create(
                turma_id=turma.id,
                data_aula=cursor,
                defaults=defaults,
            )
            if not created and aula.status == InformaticaAulaDiario.Status.PREVISTA:
                changed = False
                for key, value in defaults.items():
                    if getattr(aula, key) != value:
                        setattr(aula, key, value)
                        changed = True
                if changed:
                    aula.save()
        cursor = cursor + timedelta(days=1)

    # Aulas previstas fora da grade atual viram canceladas para manter rastreabilidade.
    previstas = InformaticaAulaDiario.objects.filter(
        turma_id=turma.id,
        status=InformaticaAulaDiario.Status.PREVISTA,
    )
    for aula in previstas:
        if aula.data_aula not in datas_validas:
            aula.status = InformaticaAulaDiario.Status.CANCELADA
            aula.observacoes = (aula.observacoes or "") + "\nCancelada por ajuste de grade/calendário."
            aula.save(update_fields=["status", "observacoes"])


def _sync_turma_grade(turma: InformaticaTurma):
    _sync_encontros_da_grade(turma)
    _sync_calendario_aulas_turma(turma)


def _processar_solicitacao(solicitacao: InformaticaSolicitacaoVaga, user):
    turmas = InformaticaTurma.objects.filter(
        curso_id=solicitacao.curso_id,
        status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
    ).select_related("laboratorio")

    if solicitacao.laboratorio_preferido_id:
        turmas = turmas.filter(laboratorio_id=solicitacao.laboratorio_preferido_id)
    if solicitacao.turno_preferido != InformaticaSolicitacaoVaga.TurnoPreferido.QUALQUER:
        turmas = turmas.filter(turno=solicitacao.turno_preferido)

    turmas = turmas.order_by("ano_letivo", "codigo")

    turma_disponivel = None
    for turma in turmas:
        if turma.vagas_livres > 0 and turma.encontros_ativos_count == turma.quantidade_encontros_semana:
            turma_disponivel = turma
            break

    if turma_disponivel:
        matricula = InformaticaMatricula(
            aluno_id=solicitacao.aluno_id,
            escola_origem_id=solicitacao.escola_origem_id,
            curso_id=solicitacao.curso_id,
            turma=turma_disponivel,
            status=InformaticaMatricula.Status.MATRICULADO,
            origem_indicacao=solicitacao.origem_indicacao or "Escola",
            prioridade=solicitacao.prioridade,
            observacoes=f"Gerada automaticamente da solicitação #{solicitacao.id}",
            criado_por=user,
        )
        matricula.full_clean()
        matricula.save()
        solicitacao.status = InformaticaSolicitacaoVaga.Status.APROVADA
        solicitacao.save(update_fields=["status"])
        return "MATRICULADO", matricula

    ultimo = (
        InformaticaListaEspera.objects.filter(curso_id=solicitacao.curso_id, status=InformaticaListaEspera.Status.ATIVA)
        .aggregate(max_pos=Max("posicao"))
        .get("max_pos")
        or 0
    )
    InformaticaListaEspera.objects.get_or_create(
        solicitacao=solicitacao,
        defaults={
            "curso_id": solicitacao.curso_id,
            "aluno_id": solicitacao.aluno_id,
            "escola_origem_id": solicitacao.escola_origem_id,
            "turno_preferido": solicitacao.turno_preferido,
            "laboratorio_preferido_id": solicitacao.laboratorio_preferido_id,
            "prioridade": solicitacao.prioridade,
            "posicao": int(ultimo) + 1,
            "status": InformaticaListaEspera.Status.ATIVA,
        },
    )
    solicitacao.status = InformaticaSolicitacaoVaga.Status.LISTA_ESPERA
    solicitacao.save(update_fields=["status"])
    _renumber_lista_espera(solicitacao.curso_id)
    return "LISTA_ESPERA", None


@login_required
def informatica_index(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    turmas_qs = turmas_scope(request.user)
    cursos_qs = cursos_scope(request.user)
    labs_qs = laboratorios_scope(request.user)
    grades_qs = grades_scope(request.user)
    matriculas_qs = InformaticaMatricula.objects.filter(turma_id__in=turmas_qs.values_list("id", flat=True))

    total_matriculados = matriculas_qs.filter(status=InformaticaMatricula.Status.MATRICULADO).count()

    freq_qs = InformaticaFrequencia.objects.filter(aula__turma_id__in=turmas_qs.values_list("id", flat=True))
    freq_total = freq_qs.count()
    freq_presentes = freq_qs.filter(presente=True).count()
    media_frequencia = round((freq_presentes / freq_total) * 100, 2) if freq_total else 0

    context = {
        "cursos_total": cursos_qs.count(),
        "laboratorios_total": labs_qs.count(),
        "grades_total": grades_qs.count(),
        "turmas_total": turmas_qs.count(),
        "turmas_sexta_total": turmas_qs.filter(encontro_unico_semana=True).count(),
        "matriculados_total": total_matriculados,
        "lista_espera_total": InformaticaListaEspera.objects.filter(
            curso_id__in=cursos_qs.values_list("id", flat=True), status=InformaticaListaEspera.Status.ATIVA
        ).count(),
        "alunos_externos_total": matriculas_qs.filter(
            status=InformaticaMatricula.Status.MATRICULADO, externo_laboratorio=True
        ).count(),
        "media_frequencia": media_frequencia,
        "proximas_turmas": turmas_qs.filter(status=InformaticaTurma.Status.ATIVA).order_by("ano_letivo", "codigo")[:6],
        "can_manage": _can_manage_informatica(request.user),
        "can_view_execucao": _can_view_informatica_execucao(request.user),
        "is_professor": _is_professor(request.user),
    }
    return render(request, "educacao/informatica/index.html", context)


@login_required
def informatica_curso_list(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    q = (request.GET.get("q") or "").strip()
    qs = cursos_scope(request.user)
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(descricao__icontains=q) | Q(ano_escolar_permitido__icontains=q))

    page_obj = Paginator(qs.order_by("nome"), 20).get_page(request.GET.get("page"))

    rows = []
    can_manage = _can_manage_informatica(request.user)
    for c in page_obj:
        actions_html = ""
        if can_manage:
            actions_html = format_html(
                '<a class="gp-button gp-button--outline" href="{}">Editar</a>',
                reverse("educacao:informatica_curso_update", args=[c.pk]),
            )
        rows.append(
            {
                "cells": [
                    {"text": c.nome},
                    {"text": c.municipio.nome},
                    {"text": c.get_modalidade_display()},
                    {"text": str(c.max_alunos_por_turma)},
                    {"text": "Sim" if c.ativo else "Não"},
                    {"html": actions_html or "—"},
                ]
            }
        )

    actions = []
    if can_manage:
        actions.append(
            {
                "label": "Novo curso",
                "url": reverse("educacao:informatica_curso_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    return render(
        request,
        "educacao/informatica/curso_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "rows": rows,
            "actions": actions,
            "headers": [
                {"label": "Curso"},
                {"label": "Município"},
                {"label": "Modalidade"},
                {"label": "Máx/Turma", "width": "120px"},
                {"label": "Ativo", "width": "90px"},
                {"label": "Ações", "width": "120px"},
            ],
        },
    )


@login_required
def informatica_curso_create(request):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    form = InformaticaCursoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        municipio_id = _resolve_default_municipio_id(request.user)
        if not municipio_id:
            messages.error(request, "Não foi possível identificar o município do seu escopo.")
        else:
            obj = form.save(commit=False)
            obj.municipio_id = municipio_id
            try:
                obj.full_clean()
                obj.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Curso de informática cadastrado com sucesso.")
                return redirect("educacao:informatica_curso_list")

    return render(
        request,
        "educacao/informatica/curso_form.html",
        {
            "form": form,
            "mode": "create",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_curso_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_curso_update(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    curso = get_object_or_404(cursos_scope(request.user), pk=pk)
    form = InformaticaCursoForm(request.POST or None, instance=curso)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio_id = curso.municipio_id
        try:
            obj.full_clean()
            obj.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Curso atualizado com sucesso.")
            return redirect("educacao:informatica_curso_list")

    return render(
        request,
        "educacao/informatica/curso_form.html",
        {
            "form": form,
            "mode": "update",
            "curso": curso,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_curso_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_laboratorio_list(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    q = (request.GET.get("q") or "").strip()
    qs = laboratorios_scope(request.user)
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(unidade__nome__icontains=q) | Q(endereco__icontains=q))

    page_obj = Paginator(qs.order_by("unidade__nome", "nome"), 20).get_page(request.GET.get("page"))
    can_manage = _can_manage_informatica(request.user)
    rows = []
    for lab in page_obj:
        actions_html = ""
        if can_manage:
            actions_html = format_html(
                '<a class="gp-button gp-button--outline" href="{}">Editar</a>',
                reverse("educacao:informatica_laboratorio_update", args=[lab.pk]),
            )
        rows.append(
            {
                "cells": [
                    {"text": lab.nome},
                    {"text": lab.unidade.nome},
                    {"text": str(lab.quantidade_computadores or 0)},
                    {"text": str(lab.capacidade_operacional)},
                    {"text": lab.get_status_display()},
                    {"html": actions_html or "—"},
                ]
            }
        )

    actions = []
    if can_manage:
        actions.append(
            {
                "label": "Novo laboratório",
                "url": reverse("educacao:informatica_laboratorio_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    return render(
        request,
        "educacao/informatica/laboratorio_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "rows": rows,
            "actions": actions,
            "headers": [
                {"label": "Laboratório"},
                {"label": "Unidade"},
                {"label": "Computadores", "width": "120px"},
                {"label": "Capacidade", "width": "120px"},
                {"label": "Status", "width": "130px"},
                {"label": "Ações", "width": "120px"},
            ],
        },
    )


@login_required
def informatica_laboratorio_create(request):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    form = InformaticaLaboratorioForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        try:
            obj.full_clean()
            obj.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Laboratório cadastrado com sucesso.")
            return redirect("educacao:informatica_laboratorio_list")

    return render(
        request,
        "educacao/informatica/laboratorio_form.html",
        {
            "form": form,
            "mode": "create",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_laboratorio_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_laboratorio_update(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    obj = get_object_or_404(laboratorios_scope(request.user), pk=pk)
    form = InformaticaLaboratorioForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        try:
            obj.full_clean()
            obj.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Laboratório atualizado com sucesso.")
            return redirect("educacao:informatica_laboratorio_list")

    return render(
        request,
        "educacao/informatica/laboratorio_form.html",
        {
            "form": form,
            "mode": "update",
            "laboratorio": obj,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_laboratorio_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_grade_list(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    turno = (request.GET.get("turno") or "").strip()
    dia = (request.GET.get("dia") or "").strip()
    laboratorio_id = (request.GET.get("laboratorio") or "").strip()
    periodo = (request.GET.get("periodo") or "").strip()
    professor_id = (request.GET.get("professor") or "").strip()

    qs = grades_scope(request.user).select_related("laboratorio", "professor_principal")

    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(codigo__icontains=q) | Q(descricao__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if turno:
        qs = qs.filter(turno=turno)
    if dia.isdigit():
        dia_int = int(dia)
        qs = qs.filter(Q(dia_semana_1=dia_int) | Q(dia_semana_2=dia_int))
    if laboratorio_id.isdigit():
        qs = qs.filter(laboratorio_id=int(laboratorio_id))
    if professor_id.isdigit():
        qs = qs.filter(professor_principal_id=int(professor_id))
    if periodo:
        qs = qs.filter(periodo_letivo__icontains=periodo)

    page_obj = Paginator(qs.order_by("-ano_letivo", "laboratorio__nome", "hora_inicio", "codigo"), 20).get_page(
        request.GET.get("page")
    )
    can_manage = _can_manage_informatica(request.user)

    rows = []
    for g in page_obj:
        turma_ativa = g.turmas.filter(status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA]).first()
        dias_txt = g.get_dia_semana_1_display()
        if g.dia_semana_2 is not None:
            dias_txt = f"{dias_txt} e {g.get_dia_semana_2_display()}"
        if g.tipo_grade == InformaticaGradeHorario.TipoGrade.ESPECIAL_SEXTA:
            dias_txt = f"{dias_txt} (encontro único)"

        actions = []
        if can_manage:
            actions.append(
                format_html(
                    '<a class="gp-button gp-button--outline" href="{}">Editar</a>',
                    reverse("educacao:informatica_grade_update", args=[g.pk]),
                )
            )
            actions.append(
                format_html(
                    '<a class="gp-button gp-button--ghost" href="{}">Duplicar</a>',
                    reverse("educacao:informatica_grade_duplicate", args=[g.pk]),
                )
            )
            actions.append(
                format_html(
                    '<a class="gp-button gp-button--ghost" href="{}">{}</a>',
                    reverse("educacao:informatica_grade_toggle", args=[g.pk]),
                    "Inativar" if g.status == InformaticaGradeHorario.Status.ATIVA else "Ativar",
                )
            )

        rows.append(
            {
                "cells": [
                    {"html": format_html("<strong>{}</strong><br><small>{}</small>", g.codigo, g.nome)},
                    {"text": g.laboratorio.nome},
                    {"text": dias_txt},
                    {"text": f"{g.hora_inicio:%H:%M}-{g.hora_fim:%H:%M}"},
                    {"text": g.get_tipo_grade_display()},
                    {"text": g.professor_principal.get_full_name() or g.professor_principal.username if g.professor_principal else "—"},
                    {"text": turma_ativa.codigo if turma_ativa else "Livre"},
                    {"text": f"{g.capacidade_maxima}"},
                    {"text": g.get_status_display()},
                    {"html": format_html(" ").join(actions) if actions else "—"},
                ]
            }
        )

    return render(
        request,
        "educacao/informatica/grade_list.html",
        {
            "q": q,
            "status": status,
            "turno": turno,
            "dia": dia,
            "laboratorio_id": laboratorio_id,
            "periodo": periodo,
            "professor_id": professor_id,
            "status_choices": InformaticaGradeHorario.Status.choices,
            "turno_choices": InformaticaGradeHorario.Turno.choices,
            "dia_choices": InformaticaGradeHorario.DiaSemana.choices,
            "laboratorios": laboratorios_scope(request.user).order_by("nome"),
            "professores": InformaticaGradeHorario.objects.filter(
                pk__in=qs.values_list("pk", flat=True)
            ).values_list("professor_principal_id", "professor_principal__first_name", "professor_principal__last_name", "professor_principal__username"),
            "page_obj": page_obj,
            "rows": rows,
            "actions": [
                {
                    "label": "Nova grade",
                    "url": reverse("educacao:informatica_grade_create"),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ]
            if can_manage
            else [],
            "headers": [
                {"label": "Grade"},
                {"label": "Laboratório"},
                {"label": "Dias"},
                {"label": "Horário", "width": "120px"},
                {"label": "Tipo", "width": "170px"},
                {"label": "Professor"},
                {"label": "Turma vinculada"},
                {"label": "Vagas", "width": "70px"},
                {"label": "Status", "width": "100px"},
                {"label": "Ações", "width": "260px"},
            ],
        },
    )


@login_required
def informatica_grade_create(request):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    form = InformaticaGradeHorarioForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        try:
            obj.full_clean()
            obj.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Grade de horário cadastrada com sucesso.")
            return redirect("educacao:informatica_grade_list")

    return render(
        request,
        "educacao/informatica/grade_form.html",
        {
            "form": form,
            "mode": "create",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_grade_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_grade_update(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    obj = get_object_or_404(grades_scope(request.user), pk=pk)
    form = InformaticaGradeHorarioForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        try:
            with transaction.atomic():
                obj.full_clean()
                obj.save()
                for turma in obj.turmas.filter(status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA]):
                    turma.save()
                    _sync_turma_grade(turma)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Grade de horário atualizada com sucesso.")
            return redirect("educacao:informatica_grade_list")

    return render(
        request,
        "educacao/informatica/grade_form.html",
        {
            "form": form,
            "mode": "update",
            "grade": obj,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_grade_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_grade_duplicate(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    origem = get_object_or_404(grades_scope(request.user), pk=pk)
    clone = InformaticaGradeHorario.objects.get(pk=origem.pk)
    clone.pk = None
    clone.codigo = f"{origem.codigo}-COPIA"
    clone.nome = f"{origem.nome} (cópia)"
    clone.status = InformaticaGradeHorario.Status.INATIVA
    clone.ativo = True
    try:
        clone.full_clean()
        clone.save()
    except ValidationError:
        messages.error(request, "Não foi possível duplicar a grade. Ajuste o código e tente novamente.")
    else:
        messages.success(request, "Grade duplicada com sucesso.")
    return redirect("educacao:informatica_grade_list")


@login_required
def informatica_grade_toggle(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    obj = get_object_or_404(grades_scope(request.user), pk=pk)
    obj.status = (
        InformaticaGradeHorario.Status.INATIVA
        if obj.status == InformaticaGradeHorario.Status.ATIVA
        else InformaticaGradeHorario.Status.ATIVA
    )
    obj.save(update_fields=["status"])
    messages.success(request, f"Grade {'ativada' if obj.status == InformaticaGradeHorario.Status.ATIVA else 'inativada'} com sucesso.")
    return redirect("educacao:informatica_grade_list")


@login_required
def informatica_turma_list(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    qs = turmas_scope(request.user)

    if q:
        qs = qs.filter(
            Q(codigo__icontains=q)
            | Q(nome__icontains=q)
            | Q(curso__nome__icontains=q)
            | Q(laboratorio__nome__icontains=q)
            | Q(grade_horario__codigo__icontains=q)
            | Q(grade_horario__nome__icontains=q)
            | Q(instrutor__first_name__icontains=q)
            | Q(instrutor__last_name__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)

    total_turmas = qs.count()
    total_turmas_ativas = qs.filter(status=InformaticaTurma.Status.ATIVA).count()
    total_turmas_planejadas = qs.filter(status=InformaticaTurma.Status.PLANEJADA).count()
    vagas_totais = int(qs.aggregate(total=Sum("max_vagas")).get("total") or 0)
    matriculados_ativos = InformaticaMatricula.objects.filter(
        turma_id__in=qs.values_list("id", flat=True),
        status=InformaticaMatricula.Status.MATRICULADO,
    ).count()
    vagas_disponiveis = max(vagas_totais - matriculados_ativos, 0)

    page_obj = Paginator(qs.order_by("-ano_letivo", "codigo"), 20).get_page(request.GET.get("page"))
    can_manage = _can_manage_informatica(request.user)

    rows = []
    for turma in page_obj:
        encontros = ", ".join(
            [
                f"{e.get_dia_semana_display()} {e.hora_inicio.strftime('%H:%M')}"
                for e in turma.encontros_ativos_qs
            ]
        )
        ocupadas = turma.vagas_ocupadas
        tipo_turma = "Especial de sexta" if turma.encontro_unico_semana else "Padrão semanal"
        rows.append(
            {
                "cells": [
                    {
                        "html": format_html(
                            '<a href="{}"><strong>{}</strong></a><br><small>{}</small>',
                            reverse("educacao:informatica_turma_detail", args=[turma.pk]),
                            turma.codigo,
                            turma.curso.nome,
                        )
                    },
                    {"text": turma.laboratorio.nome},
                    {"text": turma.grade_horario.codigo if turma.grade_horario else "—"},
                    {"text": encontros or "—"},
                    {"text": tipo_turma},
                    {"text": turma.instrutor.get_full_name() or turma.instrutor.username if turma.instrutor else "—"},
                    {"text": f"{ocupadas}/{turma.max_vagas}"},
                    {"text": turma.get_status_display()},
                    {
                        "html": format_html(
                            '<a class="gp-button gp-button--outline" href="{}">Abrir</a>{}',
                            reverse("educacao:informatica_turma_detail", args=[turma.pk]),
                            format_html(
                                ' <a class="gp-button gp-button--ghost" href="{}">Editar</a>',
                                reverse("educacao:informatica_turma_update", args=[turma.pk]),
                            )
                            if can_manage
                            else "",
                        )
                    },
                ]
            }
        )

    actions = []
    if can_manage:
        actions.append(
            {
                "label": "Nova turma",
                "url": reverse("educacao:informatica_turma_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    return render(
        request,
        "educacao/informatica/turma_list.html",
        {
            "q": q,
            "status": status,
            "status_choices": InformaticaTurma.Status.choices,
            "page_obj": page_obj,
            "rows": rows,
            "actions": actions,
            "total_turmas": total_turmas,
            "total_turmas_ativas": total_turmas_ativas,
            "total_turmas_planejadas": total_turmas_planejadas,
            "vagas_disponiveis": vagas_disponiveis,
            "headers": [
                {"label": "Turma"},
                {"label": "Laboratório"},
                {"label": "Grade"},
                {"label": "Encontros"},
                {"label": "Modalidade"},
                {"label": "Instrutor"},
                {"label": "Vagas", "width": "100px"},
                {"label": "Status", "width": "130px"},
                {"label": "Ações", "width": "180px"},
            ],
        },
    )


@login_required
def informatica_turma_create(request):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    form = InformaticaTurmaForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        turma = form.save(commit=False)
        try:
            with transaction.atomic():
                turma.full_clean()
                turma.save()
                _sync_turma_grade(turma)

        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Turma cadastrada e vinculada à grade de horários.")
            return redirect("educacao:informatica_turma_detail", pk=turma.pk)

    return render(
        request,
        "educacao/informatica/turma_form.html",
        {
            "form": form,
            "mode": "create",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_turma_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_turma_update(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    turma = get_object_or_404(turmas_scope(request.user), pk=pk)
    form = InformaticaTurmaForm(request.POST or None, instance=turma, user=request.user)

    if request.method == "POST" and form.is_valid():
        turma = form.save(commit=False)
        try:
            with transaction.atomic():
                turma.full_clean()
                turma.save()
                _sync_turma_grade(turma)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Turma atualizada com sucesso.")
            return redirect("educacao:informatica_turma_detail", pk=turma.pk)

    return render(
        request,
        "educacao/informatica/turma_form.html",
        {
            "form": form,
            "mode": "update",
            "turma": turma,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_turma_detail", args=[turma.pk]),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_turma_detail(request, pk: int):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    turma = get_object_or_404(
        turmas_scope(request.user)
        .select_related(
            "curso",
            "curso__municipio",
            "grade_horario",
            "laboratorio",
            "laboratorio__unidade",
            "instrutor",
        )
        .prefetch_related("encontros"),
        pk=pk,
    )
    matriculas = (
        turma.matriculas.select_related("aluno", "escola_origem")
        .order_by("-status", "aluno__nome")
    )
    aulas = turma.aulas.order_by("-data_aula", "-id")[:10]
    lista_espera = (
        InformaticaListaEspera.objects.filter(curso_id=turma.curso_id, status=InformaticaListaEspera.Status.ATIVA)
        .select_related("aluno", "escola_origem")
        .order_by("posicao", "id")[:10]
    )

    return render(
        request,
        "educacao/informatica/turma_detail.html",
        {
            "turma": turma,
            "matriculas": matriculas,
            "aulas": aulas,
            "lista_espera": lista_espera,
            "can_manage": _can_manage_informatica(request.user),
            "can_matricular": _can_manage_or_professor_informatica(request.user),
            "can_view_execucao": _can_view_informatica_execucao(request.user),
        },
    )


@login_required
def informatica_solicitacao_list(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = InformaticaSolicitacaoVaga.objects.select_related(
        "aluno",
        "escola_origem",
        "curso",
        "curso__municipio",
        "laboratorio_preferido",
    ).filter(curso_id__in=cursos_scope(request.user).values_list("id", flat=True))

    if q:
        qs = qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(escola_origem__nome__icontains=q)
            | Q(curso__nome__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)

    page_obj = Paginator(qs.order_by("status", "-prioridade", "data_solicitacao", "id"), 20).get_page(
        request.GET.get("page")
    )

    can_manage = _can_manage_informatica(request.user)
    rows = []
    for item in page_obj:
        actions = [
            format_html(
                '<a class="gp-button gp-button--outline" href="{}">Matrícula</a>',
                reverse("educacao:informatica_matricula_create") + f"?solicitacao={item.id}",
            )
        ] if can_manage else []

        if can_manage and item.status in {
            InformaticaSolicitacaoVaga.Status.PENDENTE,
            InformaticaSolicitacaoVaga.Status.LISTA_ESPERA,
        }:
            actions.append(
                format_html(
                    '<a class="gp-button gp-button--ghost" href="{}">Lista de espera</a>',
                    reverse("educacao:informatica_solicitacao_lista", args=[item.pk]),
                )
            )

        rows.append(
            {
                "cells": [
                    {"text": item.aluno.nome},
                    {"text": item.escola_origem.nome},
                    {"text": item.curso.nome},
                    {"text": item.get_turno_preferido_display()},
                    {"text": item.data_solicitacao.strftime("%d/%m/%Y")},
                    {"text": item.get_status_display()},
                    {"html": format_html(" ").join(actions) if actions else "—"},
                ]
            }
        )

    return render(
        request,
        "educacao/informatica/solicitacao_list.html",
        {
            "q": q,
            "status": status,
            "status_choices": InformaticaSolicitacaoVaga.Status.choices,
            "rows": rows,
            "page_obj": page_obj,
            "actions": [
                {
                    "label": "Nova solicitação",
                    "url": reverse("educacao:informatica_solicitacao_create"),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ]
            if can_manage
            else [],
            "headers": [
                {"label": "Aluno"},
                {"label": "Escola origem"},
                {"label": "Curso"},
                {"label": "Turno"},
                {"label": "Data", "width": "110px"},
                {"label": "Status", "width": "130px"},
                {"label": "Ações", "width": "220px"},
            ],
        },
    )


@login_required
def informatica_solicitacao_create(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm
    if not _can_manage_or_professor_informatica(request.user):
        return _forbidden("403 — Perfil com acesso somente leitura ao Curso de Informática.")

    form = InformaticaSolicitacaoForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        solicitacao = form.save(commit=False)
        solicitacao.criado_por = request.user

        if not solicitacao.escola_origem_id and solicitacao.aluno_id:
            escola = _resolve_escola_origem_do_aluno(solicitacao.aluno_id)
            if escola:
                solicitacao.escola_origem = escola

        try:
            with transaction.atomic():
                solicitacao.full_clean()
                solicitacao.save()
                resultado, matricula = _processar_solicitacao(solicitacao, request.user)

        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if resultado == "MATRICULADO":
                messages.success(
                    request,
                    f"Solicitação aprovada e aluno matriculado automaticamente na turma {matricula.turma.codigo}.",
                )
            else:
                messages.warning(
                    request,
                    "Turmas sem vaga compatível. Solicitação enviada para lista de espera.",
                )
            return redirect("educacao:informatica_solicitacao_list")

    return render(
        request,
        "educacao/informatica/solicitacao_form.html",
        {
            "form": form,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_solicitacao_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_solicitacao_lista(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    solic = get_object_or_404(
        InformaticaSolicitacaoVaga.objects.select_related("curso", "aluno", "escola_origem"),
        pk=pk,
        curso_id__in=cursos_scope(request.user).values_list("id", flat=True),
    )

    ultimo = (
        InformaticaListaEspera.objects.filter(curso_id=solic.curso_id, status=InformaticaListaEspera.Status.ATIVA)
        .aggregate(max_pos=Max("posicao"))
        .get("max_pos")
        or 0
    )
    InformaticaListaEspera.objects.get_or_create(
        solicitacao=solic,
        defaults={
            "curso_id": solic.curso_id,
            "aluno_id": solic.aluno_id,
            "escola_origem_id": solic.escola_origem_id,
            "turno_preferido": solic.turno_preferido,
            "laboratorio_preferido_id": solic.laboratorio_preferido_id,
            "prioridade": solic.prioridade,
            "posicao": int(ultimo) + 1,
            "status": InformaticaListaEspera.Status.ATIVA,
        },
    )
    solic.status = InformaticaSolicitacaoVaga.Status.LISTA_ESPERA
    solic.save(update_fields=["status"])
    _renumber_lista_espera(solic.curso_id)

    messages.success(request, "Solicitação movida para lista de espera.")
    return redirect("educacao:informatica_solicitacao_list")


@login_required
def informatica_matricula_list(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()

    qs = InformaticaMatricula.objects.select_related(
        "aluno",
        "escola_origem",
        "curso",
        "turma",
        "turma__laboratorio",
    ).filter(turma_id__in=turmas_scope(request.user).values_list("id", flat=True))

    if q:
        qs = qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(turma__codigo__icontains=q)
            | Q(curso__nome__icontains=q)
            | Q(escola_origem__nome__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)

    page_obj = Paginator(qs.order_by("-data_matricula", "-id"), 20).get_page(request.GET.get("page"))
    can_manage = _can_manage_informatica(request.user)
    can_create_matricula = _can_manage_or_professor_informatica(request.user)

    rows = []
    for item in page_obj:
        action_buttons = []
        if can_manage and item.status in {
            InformaticaMatricula.Status.MATRICULADO,
            InformaticaMatricula.Status.APROVADA,
            InformaticaMatricula.Status.PENDENTE,
        }:
            action_buttons.append(
                format_html(
                    '<a class="gp-button gp-button--outline" href="{}">Remanejar</a>',
                    reverse("educacao:informatica_matricula_remanejar", args=[item.pk]),
                )
            )
            action_buttons.append(
                format_html(
                    '<a class="gp-button gp-button--ghost" href="{}">Cancelar</a>',
                    reverse("educacao:informatica_matricula_cancelar", args=[item.pk]),
                )
            )

        rows.append(
            {
                "cells": [
                    {"text": item.aluno.nome},
                    {"text": item.escola_origem.nome},
                    {"text": item.curso.nome},
                    {"text": item.turma.codigo},
                    {"text": "Externo" if item.externo_laboratorio else "Interno"},
                    {"text": item.get_status_display()},
                    {"html": format_html(" ").join(action_buttons) if action_buttons else "—"},
                ]
            }
        )

    actions = []
    if can_create_matricula:
        actions.append(
            {
                "label": "Nova matrícula",
                "url": reverse("educacao:informatica_matricula_create"),
                "icon": "fa-solid fa-user-plus",
                "variant": "btn-primary",
            }
        )

    return render(
        request,
        "educacao/informatica/matricula_list.html",
        {
            "q": q,
            "status": status,
            "status_choices": InformaticaMatricula.Status.choices,
            "rows": rows,
            "page_obj": page_obj,
            "actions": actions,
            "headers": [
                {"label": "Aluno"},
                {"label": "Escola origem"},
                {"label": "Curso"},
                {"label": "Turma"},
                {"label": "Origem", "width": "100px"},
                {"label": "Status", "width": "130px"},
                {"label": "Ações", "width": "260px"},
            ],
        },
    )


@login_required
def informatica_matricula_create(request):
    if not _can_manage_or_professor_informatica(request.user):
        return _forbidden()

    initial = {}
    solicitacao_id = request.GET.get("solicitacao")
    lista_id = request.GET.get("lista")
    turma_id = request.GET.get("turma")
    aluno_id = request.GET.get("aluno")

    solicitacao = None
    lista_item = None

    if solicitacao_id and str(solicitacao_id).isdigit():
        solicitacao = get_object_or_404(
            InformaticaSolicitacaoVaga.objects.select_related("curso", "aluno", "escola_origem"),
            pk=int(solicitacao_id),
            curso_id__in=cursos_scope(request.user).values_list("id", flat=True),
        )
        initial.update(
            {
                "aluno": solicitacao.aluno_id,
                "escola_origem": solicitacao.escola_origem_id,
                "origem_indicacao": solicitacao.origem_indicacao,
                "prioridade": solicitacao.prioridade,
            }
        )

    if lista_id and str(lista_id).isdigit():
        lista_item = get_object_or_404(
            InformaticaListaEspera.objects.select_related("curso", "aluno", "escola_origem", "turma_preferida"),
            pk=int(lista_id),
            curso_id__in=cursos_scope(request.user).values_list("id", flat=True),
        )
        initial.update(
            {
                "aluno": lista_item.aluno_id,
                "escola_origem": lista_item.escola_origem_id,
                "prioridade": lista_item.prioridade,
                "turma": lista_item.turma_preferida_id,
            }
        )

    if turma_id and str(turma_id).isdigit():
        initial["turma"] = int(turma_id)

    if aluno_id and str(aluno_id).isdigit():
        initial["aluno"] = int(aluno_id)

    if initial.get("aluno") and not initial.get("escola_origem"):
        escola_auto, origem_auto = _resolve_origem_indicacao_do_aluno(int(initial["aluno"]))
        if escola_auto:
            initial["escola_origem"] = escola_auto.id
        if not initial.get("origem_indicacao"):
            initial["origem_indicacao"] = origem_auto

    form = InformaticaMatriculaForm(request.POST or None, user=request.user, initial=initial)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.criado_por = request.user
        if obj.turma_id and not obj.curso_id:
            obj.curso_id = obj.turma.curso_id

        if obj.aluno_id:
            escola_auto, origem_auto = _resolve_origem_indicacao_do_aluno(obj.aluno_id)
            if not obj.escola_origem_id and escola_auto:
                obj.escola_origem = escola_auto
            if not (obj.origem_indicacao or "").strip():
                obj.origem_indicacao = origem_auto

        try:
            obj.full_clean()
            obj.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            motivo_criacao = "Matrícula criada pela tela do módulo de informática."
            if solicitacao:
                motivo_criacao = f"Matrícula criada a partir da solicitação #{solicitacao.id}."
            elif lista_item:
                motivo_criacao = f"Matrícula criada por convocação da lista de espera #{lista_item.id}."

            registrar_movimentacao_informatica(
                matricula=obj,
                tipo=InformaticaMatriculaMovimentacao.Tipo.CRIACAO,
                usuario=request.user,
                turma_destino=obj.turma,
                status_novo=obj.status,
                motivo=motivo_criacao,
            )
            if solicitacao:
                solicitacao.status = InformaticaSolicitacaoVaga.Status.APROVADA
                solicitacao.save(update_fields=["status"])
            if lista_item:
                lista_item.status = InformaticaListaEspera.Status.ENCERRADA
                lista_item.save(update_fields=["status"])
                _renumber_lista_espera(lista_item.curso_id)
            messages.success(request, "Matrícula registrada com sucesso.")
            return redirect("educacao:informatica_matricula_list")

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:informatica_matricula_list"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]
    if _can_manage_or_professor_informatica(request.user):
        novo_aluno_url = reverse("educacao:informatica_aluno_create")
        if initial.get("turma"):
            novo_aluno_url += f"?turma={int(initial['turma'])}"
        actions.append(
            {
                "label": "Novo aluno",
                "url": novo_aluno_url,
                "icon": "fa-solid fa-user-plus",
                "variant": "btn--outline",
            }
        )

    return render(
        request,
        "educacao/informatica/matricula_form.html",
        {
            "form": form,
            "actions": actions,
        },
    )


@login_required
def informatica_aluno_create(request):
    if not _can_manage_or_professor_informatica(request.user):
        return _forbidden()

    turma_id = request.GET.get("turma")
    turma_qs = turmas_scope(request.user)
    turma_obj = None
    if str(turma_id or "").isdigit():
        turma_obj = turma_qs.filter(pk=int(turma_id)).first()

    form = AlunoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        aluno = form.save()

        recentes = request.session.get("informatica_alunos_recentes", [])
        recentes = [int(x) for x in recentes if str(x).isdigit()]
        if aluno.id not in recentes:
            recentes.append(aluno.id)
        request.session["informatica_alunos_recentes"] = recentes[-30:]

        target = reverse("educacao:informatica_matricula_create") + f"?aluno={aluno.id}"
        if turma_obj:
            target += f"&turma={turma_obj.id}"
        messages.success(request, "Aluno cadastrado. Continue com a matrícula no Curso de Informática.")
        return redirect(target)

    back_url = reverse("educacao:informatica_professor_agenda") if _is_professor(request.user) else reverse(
        "educacao:informatica_matricula_list"
    )
    return render(
        request,
        "educacao/informatica/aluno_form.html",
        {
            "form": form,
            "turma": turma_obj,
            "actions": [
                {
                    "label": "Voltar",
                    "url": back_url,
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_matricula_remanejar(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    mat = get_object_or_404(
        InformaticaMatricula.objects.select_related("curso", "turma", "aluno", "escola_origem"),
        pk=pk,
        turma_id__in=turmas_scope(request.user).values_list("id", flat=True),
    )

    if mat.status not in {
        InformaticaMatricula.Status.MATRICULADO,
        InformaticaMatricula.Status.APROVADA,
        InformaticaMatricula.Status.PENDENTE,
    }:
        messages.warning(request, "Esta matrícula não está apta para remanejamento.")
        return redirect("educacao:informatica_matricula_list")

    form = InformaticaMatriculaRemanejamentoForm(
        request.POST or None,
        user=request.user,
        matricula=mat,
    )

    if request.method == "POST" and form.is_valid():
        turma_origem = mat.turma
        turma_destino = form.cleaned_data["turma_destino"]
        motivo = (form.cleaned_data.get("motivo") or "").strip()
        status_anterior = mat.status

        try:
            with transaction.atomic():
                mat.turma = turma_destino
                mat.curso_id = turma_destino.curso_id
                if motivo:
                    linha = f"[Remanejamento {timezone.localdate():%d/%m/%Y}] {motivo}"
                    mat.observacoes = f"{(mat.observacoes or '').strip()}\n{linha}".strip()
                mat.full_clean()
                mat.save()

                registrar_movimentacao_informatica(
                    matricula=mat,
                    tipo=InformaticaMatriculaMovimentacao.Tipo.REMANEJAMENTO,
                    usuario=request.user,
                    turma_origem=turma_origem,
                    turma_destino=turma_destino,
                    status_anterior=status_anterior,
                    status_novo=mat.status,
                    motivo=motivo or "Remanejamento manual na matrícula de informática.",
                )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request,
                f"Remanejamento realizado com sucesso: {turma_origem.codigo} → {turma_destino.codigo}.",
            )
            return redirect("educacao:informatica_matricula_list")

    movimentacoes = list(
        mat.movimentacoes.select_related("usuario", "turma_origem", "turma_destino").order_by("-criado_em", "-id")[:10]
    )

    return render(
        request,
        "educacao/informatica/matricula_remanejamento_form.html",
        {
            "matricula": mat,
            "form": form,
            "movimentacoes": movimentacoes,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_matricula_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_api_aluno_origem(request, aluno_id: int):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm
    if not _can_manage_or_professor_informatica(request.user):
        return _forbidden()

    allowed = _can_manage_informatica(request.user) or alunos_scope(request.user).filter(pk=aluno_id).exists()
    recentes = {int(x) for x in request.session.get("informatica_alunos_recentes", []) if str(x).isdigit()}
    if not allowed and int(aluno_id) not in recentes:
        return _forbidden("403 — Aluno fora do seu escopo de acesso.")

    aluno = get_object_or_404(Aluno.objects.filter(ativo=True), pk=aluno_id)
    escola_auto, origem_auto = _resolve_origem_indicacao_do_aluno(aluno.id)

    return JsonResponse(
        {
            "aluno_id": aluno.id,
            "aluno_nome": aluno.nome,
            "escola_origem_id": escola_auto.id if escola_auto else None,
            "escola_origem_nome": escola_auto.nome if escola_auto else "",
            "origem_indicacao": origem_auto,
        }
    )


@login_required
def informatica_matricula_cancelar(request, pk: int):
    no_perm = _assert_informatica_write(request)
    if no_perm:
        return no_perm

    mat = get_object_or_404(
        InformaticaMatricula.objects.select_related("curso", "turma", "aluno"),
        pk=pk,
        turma_id__in=turmas_scope(request.user).values_list("id", flat=True),
    )

    if mat.status not in {
        InformaticaMatricula.Status.MATRICULADO,
        InformaticaMatricula.Status.APROVADA,
        InformaticaMatricula.Status.PENDENTE,
    }:
        messages.warning(request, "Esta matrícula já não está ativa.")
        return redirect("educacao:informatica_matricula_list")

    status_anterior = mat.status
    turma_origem = mat.turma
    mat.status = InformaticaMatricula.Status.CANCELADO
    mat.save(update_fields=["status", "atualizado_em"])
    registrar_movimentacao_informatica(
        matricula=mat,
        tipo=InformaticaMatriculaMovimentacao.Tipo.CANCELAMENTO,
        usuario=request.user,
        turma_origem=turma_origem,
        turma_destino=turma_origem,
        status_anterior=status_anterior,
        status_novo=mat.status,
        motivo="Cancelamento manual da matrícula de informática.",
    )

    proximo = _next_lista_espera_item(mat.curso_id, turma=mat.turma)
    if proximo:
        url = reverse("educacao:informatica_matricula_create") + f"?lista={proximo.id}"
        messages.warning(
            request,
            format_html(
                "Vaga liberada. Próximo sugerido na fila: <strong>{}</strong> ({}). <a href='{}'>Efetuar matrícula</a>",
                proximo.aluno.nome,
                proximo.escola_origem.nome,
                url,
            ),
        )
    else:
        messages.success(request, "Matrícula cancelada. Vaga liberada na turma.")

    return redirect("educacao:informatica_matricula_list")


@login_required
def informatica_lista_espera(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    curso_id = request.GET.get("curso")
    qs = InformaticaListaEspera.objects.select_related(
        "curso",
        "aluno",
        "escola_origem",
        "turma_preferida",
        "laboratorio_preferido",
    ).filter(curso_id__in=cursos_scope(request.user).values_list("id", flat=True))

    if str(curso_id or "").isdigit():
        qs = qs.filter(curso_id=int(curso_id))

    qs = qs.order_by("curso__nome", "status", "posicao", "id")

    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))

    rows = []
    can_matricular = _can_manage_or_professor_informatica(request.user)
    for item in page_obj:
        action_html = (
            format_html(
                '<a class="gp-button gp-button--outline" href="{}">Convocar</a>',
                reverse("educacao:informatica_matricula_create") + f"?lista={item.id}",
            )
            if can_matricular
            else "—"
        )
        rows.append(
            {
                "cells": [
                    {"text": item.curso.nome},
                    {"text": str(item.posicao)},
                    {"text": item.aluno.nome},
                    {"text": item.escola_origem.nome},
                    {"text": item.turma_preferida.codigo if item.turma_preferida else "—"},
                    {"text": item.get_status_display()},
                    {"html": action_html},
                ]
            }
        )

    return render(
        request,
        "educacao/informatica/lista_espera_list.html",
        {
            "page_obj": page_obj,
            "rows": rows,
            "cursos": cursos_scope(request.user).order_by("nome"),
            "curso_id": curso_id,
            "headers": [
                {"label": "Curso"},
                {"label": "Posição", "width": "80px"},
                {"label": "Aluno"},
                {"label": "Escola origem"},
                {"label": "Turma pref."},
                {"label": "Status", "width": "120px"},
                {"label": "Ações", "width": "120px"},
            ],
        },
    )


@login_required
def informatica_aula_list(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm
    if _is_informatica_coord(request.user):
        return _forbidden("403 — Coordenação de informática não acessa a rotina de execução de aulas/frequência.")

    turma_id = request.GET.get("turma")
    qs = InformaticaAulaDiario.objects.select_related("turma", "encontro", "professor").filter(
        turma_id__in=turmas_scope(request.user).values_list("id", flat=True)
    )
    if _is_professor(request.user) and not _can_manage_informatica(request.user):
        qs = qs.filter(turma__instrutor=request.user)
    if str(turma_id or "").isdigit():
        qs = qs.filter(turma_id=int(turma_id))

    total_aulas = qs.count()
    total_aulas_realizadas = qs.filter(status=InformaticaAulaDiario.Status.REALIZADA).count()
    total_aulas_encerradas = qs.filter(encerrada=True).count()
    total_aulas_abertas = max(total_aulas - total_aulas_encerradas, 0)

    if _is_professor(request.user):
        qs = qs.order_by("data_aula", "id")
    else:
        qs = qs.order_by("-data_aula", "-id")

    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))

    rows = []
    can_execute = _can_manage_informatica_execucao(request.user)
    for item in page_obj:
        actions = [
            format_html(
                '<a class="gp-button gp-button--outline" href="{}">Frequência</a>',
                reverse("educacao:informatica_frequencia_aula", args=[item.pk]),
            )
        ]
        if can_execute or _is_professor(request.user):
            actions.append(
                format_html(
                    '<a class="gp-button gp-button--ghost" href="{}">Editar</a>',
                    reverse("educacao:informatica_aula_update", args=[item.pk]),
                )
            )

        rows.append(
            {
                "cells": [
                    {"text": item.data_aula.strftime("%d/%m/%Y")},
                    {"text": item.turma.codigo},
                    {"text": item.encontro.get_dia_semana_display() if item.encontro else "—"},
                    {"text": (item.professor.get_full_name() or item.professor.username) if item.professor else "—"},
                    {"text": item.get_status_display()},
                    {"text": "Sim" if item.encerrada else "Não"},
                    {"html": format_html(" ").join(actions)},
                ]
            }
        )

    return render(
        request,
        "educacao/informatica/aula_list.html",
        {
            "page_obj": page_obj,
            "rows": rows,
            "turmas": turmas_scope(request.user).order_by("codigo"),
            "turma_id": turma_id,
            "total_aulas": total_aulas,
            "total_aulas_realizadas": total_aulas_realizadas,
            "total_aulas_encerradas": total_aulas_encerradas,
            "total_aulas_abertas": total_aulas_abertas,
            "actions": [
                {
                    "label": "Nova aula",
                    "url": reverse("educacao:informatica_aula_create"),
                    "icon": "fa-solid fa-plus",
                    "variant": "btn-primary",
                }
            ]
            if can_execute
            else [],
            "headers": [
                {"label": "Data", "width": "110px"},
                {"label": "Turma"},
                {"label": "Encontro"},
                {"label": "Professor"},
                {"label": "Status", "width": "130px"},
                {"label": "Encerrada", "width": "100px"},
                {"label": "Ações", "width": "200px"},
            ],
        },
    )


@login_required
def informatica_aula_create(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    if _is_professor(request.user) and not _can_manage_informatica(request.user):
        messages.warning(request, "As aulas do professor são geradas automaticamente pela grade da turma.")
        return redirect("educacao:informatica_frequencia")
    if not _can_manage_informatica_execucao(request.user):
        return _forbidden("403 — A coordenação acompanha, mas o lançamento de aulas é função do professor.")

    form = InformaticaAulaForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.professor_id:
            obj.professor = request.user
        try:
            obj.full_clean()
            obj.save()
            _seed_frequencias_aula(obj)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Aula registrada com sucesso.")
            return redirect("educacao:informatica_frequencia_aula", pk=obj.pk)

    return render(
        request,
        "educacao/informatica/aula_form.html",
        {
            "form": form,
            "mode": "create",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_frequencia"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_aula_update(request, pk: int):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    aula = get_object_or_404(
        InformaticaAulaDiario.objects.select_related("turma", "professor"),
        pk=pk,
        turma_id__in=turmas_scope(request.user).values_list("id", flat=True),
    )

    if _is_professor(request.user) and not _can_manage_informatica(request.user):
        if aula.professor_id and aula.professor_id != request.user.id:
            return _forbidden("403 — Você só pode editar aulas registradas por você.")
    elif not _can_manage_informatica_execucao(request.user):
        return _forbidden("403 — A coordenação acompanha, mas a edição de aulas é função do professor.")

    form = InformaticaAulaForm(request.POST or None, request.FILES or None, instance=aula, user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not obj.professor_id:
            obj.professor = request.user
        try:
            obj.full_clean()
            obj.save()
            _seed_frequencias_aula(obj)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Aula atualizada com sucesso.")
            return redirect("educacao:informatica_frequencia_aula", pk=obj.pk)

    return render(
        request,
        "educacao/informatica/aula_form.html",
        {
            "form": form,
            "mode": "update",
            "aula": aula,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:informatica_frequencia"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
            ],
        },
    )


@login_required
def informatica_frequencia_aula(request, pk: int):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm
    if _is_informatica_coord(request.user):
        return _forbidden("403 — Coordenação de informática não acessa a rotina de execução de frequência.")

    aula = get_object_or_404(
        InformaticaAulaDiario.objects.select_related("turma", "turma__curso", "professor"),
        pk=pk,
        turma_id__in=turmas_scope(request.user).values_list("id", flat=True),
    )

    if _is_professor(request.user) and not _can_manage_informatica(request.user):
        if aula.turma.instrutor_id and aula.turma.instrutor_id != request.user.id:
            return _forbidden("403 — Você só pode lançar frequência das suas turmas de informática.")
    elif request.method == "POST" and not _can_manage_informatica_execucao(request.user):
        return _forbidden("403 — A coordenação acompanha, mas o lançamento de frequência é função do professor.")

    matriculas = list(
        InformaticaMatricula.objects.filter(
            turma_id=aula.turma_id,
            status=InformaticaMatricula.Status.MATRICULADO,
        )
        .select_related("aluno", "escola_origem")
        .order_by("aluno__nome")
    )
    _seed_frequencias_aula(aula)

    freq_map = {
        f.aluno_id: f
        for f in InformaticaFrequencia.objects.filter(aula=aula).select_related("aluno")
    }

    if request.method == "POST":
        try:
            with transaction.atomic():
                for m in matriculas:
                    presente = bool(request.POST.get(f"presente_{m.aluno_id}"))
                    justificativa = (request.POST.get(f"justificativa_{m.aluno_id}") or "").strip()
                    observacao = (request.POST.get(f"observacao_{m.aluno_id}") or "").strip()

                    obj = freq_map.get(m.aluno_id)
                    if obj is None:
                        obj = InformaticaFrequencia(aula=aula, aluno_id=m.aluno_id)

                    obj.presente = presente
                    obj.justificativa = justificativa
                    obj.observacao = observacao
                    obj.full_clean()
                    obj.save()

                aula.encerrada = bool(request.POST.get("encerrar_aula"))
                if aula.encerrada:
                    aula.status = InformaticaAulaDiario.Status.REALIZADA
                aula.save(update_fields=["encerrada", "status"])

            _recalcular_alertas_frequencia_turma(aula.turma_id)
            messages.success(request, "Frequência registrada com sucesso.")
            return redirect("educacao:informatica_frequencia_aula", pk=aula.pk)

        except ValidationError as exc:
            messages.error(request, f"Erro ao salvar frequência: {exc}")

    alunos_rows = []
    faltas_consecutivas_map = defaultdict(int)
    for m in matriculas:
        freq = freq_map.get(m.aluno_id)
        alunos_rows.append(
            {
                "matricula": m,
                "freq": freq,
            }
        )

    return render(
        request,
        "educacao/informatica/frequencia_form.html",
        {
            "aula": aula,
            "alunos_rows": alunos_rows,
            "faltas_consecutivas_map": faltas_consecutivas_map,
            "can_edit_execucao": _is_professor(request.user) or _can_manage_informatica_execucao(request.user),
        },
    )


@login_required
def informatica_agenda(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    laboratorios = laboratorios_scope(request.user).order_by("unidade__nome", "nome")
    lab_id = request.GET.get("laboratorio")
    q = (request.GET.get("q") or "").strip()
    dia = (request.GET.get("dia") or "").strip()

    if str(lab_id or "").isdigit():
        laboratorio = get_object_or_404(laboratorios, pk=int(lab_id))
    else:
        laboratorio = laboratorios.first()

    hoje = timezone.localdate()
    semana_inicio = hoje - timedelta(days=hoje.weekday())
    dias_semana = [semana_inicio + timedelta(days=i) for i in range(6)]

    encontros_qs = InformaticaEncontroSemanal.objects.none()
    if laboratorio:
        encontros_qs = (
            InformaticaEncontroSemanal.objects.select_related("turma", "turma__curso", "turma__instrutor")
            .filter(
                turma__laboratorio_id=laboratorio.id,
                ativo=True,
                turma__status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
            )
        )
        if q:
            encontros_qs = encontros_qs.filter(
                Q(turma__codigo__icontains=q)
                | Q(turma__nome__icontains=q)
                | Q(turma__curso__nome__icontains=q)
                | Q(turma__instrutor__first_name__icontains=q)
                | Q(turma__instrutor__last_name__icontains=q)
            )
        if dia.isdigit():
            encontros_qs = encontros_qs.filter(dia_semana=int(dia))
        encontros_qs = encontros_qs.order_by("dia_semana", "hora_inicio", "turma__codigo")

    total_encontros_semana = encontros_qs.count()
    dias_ocupados = encontros_qs.values("dia_semana").distinct().count()
    total_turmas_semana = encontros_qs.values("turma_id").distinct().count()

    dia_data_map = {int(d.weekday()): d for d in dias_semana}
    page_obj = Paginator(encontros_qs, 30).get_page(request.GET.get("page"))
    rows = []
    for e in page_obj:
        data_ref = dia_data_map.get(int(e.dia_semana))
        instrutor = "—"
        if e.turma.instrutor:
            instrutor = e.turma.instrutor.get_full_name() or e.turma.instrutor.username
        rows.append(
            {
                "cells": [
                    {"text": e.get_dia_semana_display()},
                    {"text": data_ref.strftime("%d/%m/%Y") if data_ref else "—"},
                    {"text": f"{e.hora_inicio.strftime('%H:%M')} - {e.hora_fim.strftime('%H:%M')}"},
                    {"text": e.turma.codigo},
                    {"text": e.turma.curso.nome},
                    {"text": instrutor},
                    {
                        "html": format_html(
                            '<a class="gp-button gp-button--outline" href="{}">Abrir turma</a>',
                            reverse("educacao:informatica_turma_detail", args=[e.turma_id]),
                        )
                    },
                ]
            }
        )

    return render(
        request,
        "educacao/informatica/agenda.html",
        {
            "laboratorios": laboratorios,
            "laboratorio": laboratorio,
            "semana_inicio": semana_inicio,
            "semana_fim": dias_semana[-1] if dias_semana else semana_inicio,
            "total_encontros_semana": total_encontros_semana,
            "dias_ocupados": dias_ocupados,
            "total_turmas_semana": total_turmas_semana,
            "q": q,
            "dia": dia,
            "dias_choices": InformaticaEncontroSemanal.DiaSemana.choices,
            "page_obj": page_obj,
            "rows": rows,
            "headers": [
                {"label": "Dia", "width": "140px"},
                {"label": "Data ref.", "width": "110px"},
                {"label": "Horário", "width": "130px"},
                {"label": "Turma", "width": "150px"},
                {"label": "Curso"},
                {"label": "Instrutor"},
                {"label": "Ação", "width": "150px"},
            ],
        },
    )


@login_required
def informatica_professor_agenda(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm
    if _is_informatica_coord(request.user):
        return _forbidden("403 — Coordenação de informática não acessa a agenda operacional do professor.")

    turmas_qs = turmas_scope(request.user)
    if _is_professor(request.user) and not _can_manage_informatica(request.user):
        turmas_qs = turmas_qs.filter(instrutor=request.user)

    hoje = timezone.localdate()
    aulas_base = InformaticaAulaDiario.objects.select_related("turma", "encontro", "professor").filter(
        turma_id__in=turmas_qs.values_list("id", flat=True)
    )
    aulas_hoje = aulas_base.filter(data_aula=hoje).order_by("encontro__hora_inicio", "id")
    proximas = aulas_base.filter(data_aula__gte=hoje).order_by("data_aula", "encontro__hora_inicio", "id")[:40]
    historico = aulas_base.filter(data_aula__lt=hoje).order_by("-data_aula", "-id")[:20]

    actions = []
    if _can_manage_or_professor_informatica(request.user):
        actions.append(
            {
                "label": "Novo aluno",
                "url": reverse("educacao:informatica_aluno_create"),
                "icon": "fa-solid fa-user-plus",
                "variant": "btn--outline",
            }
        )
        actions.append(
            {
                "label": "Nova matrícula",
                "url": reverse("educacao:informatica_matricula_create"),
                "icon": "fa-solid fa-id-card",
                "variant": "btn-primary",
            }
        )

    return render(
        request,
        "educacao/informatica/professor_agenda.html",
        {
            "aulas_hoje": aulas_hoje,
            "proximas_aulas": proximas,
            "historico_aulas": historico,
            "hoje": hoje,
            "actions": actions,
        },
    )


@login_required
def informatica_relatorios(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    turmas_ids = turmas_scope(request.user).values_list("id", flat=True)

    matriculas = InformaticaMatricula.objects.filter(turma_id__in=turmas_ids)
    matriculados = matriculas.filter(status=InformaticaMatricula.Status.MATRICULADO)

    por_escola = list(
        matriculados.values(nome=F("escola_origem__nome"))
        .annotate(total=Count("id"))
        .order_by("-total", "nome")
    )
    por_laboratorio = list(
        matriculados.values(nome=F("turma__laboratorio__nome"))
        .annotate(total=Count("id"))
        .order_by("-total", "nome")
    )
    por_turma = list(
        matriculados.values(
            codigo=F("turma__codigo"),
            curso_nome=F("curso__nome"),
            laboratorio=F("turma__laboratorio__nome"),
        )
        .annotate(total=Count("id"))
        .order_by("-total", "codigo")
    )
    por_tipo_grade = list(
        matriculados.values(tipo=F("turma__grade_horario__tipo_grade"))
        .annotate(total=Count("id"))
        .order_by("-total", "tipo")
    )

    alertas = InformaticaAlertaFrequencia.objects.select_related(
        "matricula",
        "matricula__aluno",
        "matricula__turma",
    ).filter(
        ativo=True,
        matricula__turma_id__in=turmas_ids,
    )

    lista_espera = InformaticaListaEspera.objects.filter(
        status=InformaticaListaEspera.Status.ATIVA,
        curso_id__in=cursos_scope(request.user).values_list("id", flat=True),
    )

    context = {
        "total_matriculados": matriculados.count(),
        "total_externos": matriculados.filter(externo_laboratorio=True).count(),
        "total_lista_espera": lista_espera.count(),
        "total_turmas_sexta": turmas_scope(request.user).filter(encontro_unico_semana=True).count(),
        "por_escola": por_escola,
        "por_laboratorio": por_laboratorio,
        "por_turma": por_turma,
        "por_tipo_grade": por_tipo_grade,
        "alertas": alertas.order_by("matricula__turma__codigo", "matricula__aluno__nome")[:200],
    }
    return render(request, "educacao/informatica/relatorios.html", context)


@login_required
def informatica_ocorrencia_list(request):
    no_perm = _assert_perm(request, "educacao.view")
    if no_perm:
        return no_perm

    qs = InformaticaOcorrencia.objects.select_related("turma", "aluno").filter(
        turma_id__in=turmas_scope(request.user).values_list("id", flat=True)
    )
    page_obj = Paginator(qs.order_by("-criado_em", "-id"), 20).get_page(request.GET.get("page"))

    return render(
        request,
        "educacao/informatica/ocorrencia_list.html",
        {
            "page_obj": page_obj,
        },
    )
