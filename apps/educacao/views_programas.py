from __future__ import annotations

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade

from .forms_programas import (
    ProgramaComplementarForm,
    ProgramaComplementarFrequenciaForm,
    ProgramaComplementarHorarioForm,
    ProgramaComplementarOfertaForm,
    ProgramaComplementarParticipacaoCreateForm,
)
from .models_programas import (
    ProgramaComplementar,
    ProgramaComplementarFrequencia,
    ProgramaComplementarOferta,
    ProgramaComplementarParticipacao,
)
from .services_programas import ProgramasComplementaresService
from .services_schedule_conflicts import ScheduleConflictService


def _unidades_scope(user):
    return scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
    )


def _programas_scope(user):
    unidades = _unidades_scope(user)
    secretaria_ids = unidades.values_list("secretaria_id", flat=True).distinct()
    unidade_ids = unidades.values_list("id", flat=True)
    return ProgramaComplementar.objects.filter(
        Q(secretaria_responsavel_id__in=secretaria_ids)
        | Q(unidade_gestora_id__in=unidade_ids)
        | Q(secretaria_responsavel__isnull=True, unidade_gestora__isnull=True)
    )


def _ofertas_scope(user):
    unidades = _unidades_scope(user)
    return ProgramaComplementarOferta.objects.select_related("programa", "unidade").filter(unidade__in=unidades)


@login_required
@require_perm("educacao.view")
def programas_dashboard(request):
    programas_qs = _programas_scope(request.user)
    ofertas_qs = _ofertas_scope(request.user)
    participacoes_qs = ProgramaComplementarParticipacao.objects.select_related(
        "programa", "oferta", "aluno", "matricula_institucional"
    ).filter(oferta__in=ofertas_qs)
    context = {
        "title": "Programas Complementares",
        "subtitle": "Gestão unificada de Informática, Ballet, Reforço e demais programas educacionais.",
        "kpis": {
            "programas_ativos": programas_qs.filter(status=ProgramaComplementar.Status.ATIVO).count(),
            "ofertas_ativas": ofertas_qs.filter(status=ProgramaComplementarOferta.Status.ATIVA).count(),
            "participacoes_ativas": participacoes_qs.filter(status=ProgramaComplementarParticipacao.Status.ATIVO).count(),
            "participacoes_concluidas": participacoes_qs.filter(
                status=ProgramaComplementarParticipacao.Status.CONCLUIDO
            ).count(),
        },
        "programas_populares": list(
            participacoes_qs.values("programa_id", "programa__nome", "programa__tipo")
            .annotate(total=Count("id"))
            .order_by("-total", "programa__nome")[:10]
        ),
        "participacoes_recentes": participacoes_qs.order_by("-id")[:12],
        "actions": [
            {
                "label": "Novo programa",
                "url": reverse("educacao:programa_complementar_create"),
                "icon": "fa-solid fa-plus",
                "variant": "gp-button--primary",
            },
            {
                "label": "Nova oferta",
                "url": reverse("educacao:programa_complementar_oferta_create"),
                "icon": "fa-solid fa-layer-group",
                "variant": "gp-button--outline",
            },
            {
                "label": "Nova participação",
                "url": reverse("educacao:programa_complementar_participacao_create"),
                "icon": "fa-solid fa-user-plus",
                "variant": "gp-button--outline",
            },
            {
                "label": "Relatórios",
                "url": reverse("educacao:programa_complementar_relatorios"),
                "icon": "fa-solid fa-chart-line",
                "variant": "gp-button--outline",
            },
        ],
    }
    return render(request, "educacao/programas/dashboard.html", context)


@login_required
@require_perm("educacao.view")
def programa_complementar_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = _programas_scope(request.user).order_by("nome")
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(tipo__icontains=q)
            | Q(slug__icontains=q)
        )
    return render(
        request,
        "educacao/programas/programa_list.html",
        {
            "title": "Programas Complementares",
            "subtitle": "Catálogo institucional de programas educacionais complementares.",
            "programas": qs[:300],
            "q": q,
            "actions": [
                {
                    "label": "Novo programa",
                    "url": reverse("educacao:programa_complementar_create"),
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Painel",
                    "url": reverse("educacao:programas_dashboard"),
                    "icon": "fa-solid fa-chart-line",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def programa_complementar_create(request):
    form = ProgramaComplementarForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Programa complementar cadastrado com sucesso.")
        return redirect("educacao:programa_complementar_list")
    return render(
        request,
        "educacao/programas/form.html",
        {
            "title": "Novo Programa Complementar",
            "subtitle": "Cadastre Informática, Ballet, Reforço e demais programas na base institucional única.",
            "form": form,
            "submit_label": "Salvar programa",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:programa_complementar_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def programa_complementar_oferta_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    qs = _ofertas_scope(request.user).order_by("-ano_letivo", "programa__nome", "codigo")
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(codigo__icontains=q)
            | Q(programa__nome__icontains=q)
            | Q(unidade__nome__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "educacao/programas/oferta_list.html",
        {
            "title": "Ofertas dos Programas",
            "subtitle": "Turmas e grupos operacionais por unidade, ano letivo e capacidade.",
            "ofertas": qs[:300],
            "q": q,
            "status": status,
            "actions": [
                {
                    "label": "Nova oferta",
                    "url": reverse("educacao:programa_complementar_oferta_create"),
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Novo horário",
                    "url": reverse("educacao:programa_complementar_horario_create"),
                    "icon": "fa-solid fa-clock",
                    "variant": "gp-button--outline",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def programa_complementar_oferta_create(request):
    form = ProgramaComplementarOfertaForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Oferta cadastrada com sucesso.")
        return redirect("educacao:programa_complementar_oferta_list")
    return render(
        request,
        "educacao/programas/form.html",
        {
            "title": "Nova Oferta",
            "subtitle": "Defina turma/grupo, unidade, turno, capacidade e vigência.",
            "form": form,
            "submit_label": "Salvar oferta",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:programa_complementar_oferta_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def programa_complementar_horario_create(request):
    form = ProgramaComplementarHorarioForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Horário da oferta registrado com sucesso.")
        return redirect("educacao:programa_complementar_oferta_list")
    return render(
        request,
        "educacao/programas/form.html",
        {
            "title": "Novo Horário de Oferta",
            "subtitle": "Defina os encontros semanais da oferta para agenda e validação de conflitos.",
            "form": form,
            "submit_label": "Salvar horário",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:programa_complementar_oferta_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def programa_complementar_participacao_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    ofertas_qs = _ofertas_scope(request.user)
    qs = ProgramaComplementarParticipacao.objects.select_related(
        "aluno",
        "matricula_institucional",
        "programa",
        "oferta",
        "oferta__unidade",
    ).filter(oferta__in=ofertas_qs)
    if q:
        qs = qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(matricula_institucional__numero_matricula__icontains=q)
            | Q(programa__nome__icontains=q)
            | Q(oferta__codigo__icontains=q)
            | Q(oferta__nome__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "educacao/programas/participacao_list.html",
        {
            "title": "Participações dos Alunos",
            "subtitle": "Acompanhe vínculos dos alunos em Informática, Ballet, Reforço e demais programas.",
            "participacoes": qs.order_by("-id")[:400],
            "q": q,
            "status": status,
            "actions": [
                {
                    "label": "Nova participação",
                    "url": reverse("educacao:programa_complementar_participacao_create"),
                    "icon": "fa-solid fa-user-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Ofertas",
                    "url": reverse("educacao:programa_complementar_oferta_list"),
                    "icon": "fa-solid fa-layer-group",
                    "variant": "gp-button--outline",
                },
                {
                    "label": "Relatórios",
                    "url": reverse("educacao:programa_complementar_relatorios"),
                    "icon": "fa-solid fa-chart-line",
                    "variant": "gp-button--outline",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.manage")
def programa_complementar_participacao_create(request):
    can_override_conflict = ScheduleConflictService.can_user_override(request.user)
    form = ProgramaComplementarParticipacaoCreateForm(
        request.POST or None,
        user=request.user,
        allow_override=can_override_conflict,
    )
    if request.method == "POST" and form.is_valid():
        allow_override_conflict = (
            bool(form.cleaned_data.get("allow_override_conflict")) if can_override_conflict else False
        )
        override_justificativa = (
            (form.cleaned_data.get("override_justificativa") or "").strip() if can_override_conflict else ""
        )
        try:
            ProgramasComplementaresService.create_participation(
                aluno=form.aluno,
                oferta=form.cleaned_data["oferta"],
                usuario=request.user,
                data_ingresso=form.cleaned_data.get("data_ingresso"),
                status=form.cleaned_data["status"],
                escola_origem=form.cleaned_data.get("escola_origem"),
                allow_override_conflict=allow_override_conflict,
                override_justificativa=override_justificativa,
                observacoes=form.cleaned_data.get("observacoes") or "",
                origem_vinculo="MANUAL",
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Participação registrada com sucesso.")
            return redirect("educacao:programa_complementar_participacao_list")
    return render(
        request,
        "educacao/programas/form.html",
        {
            "title": "Nova Participação em Programa",
            "subtitle": "Vincule o aluno da rede municipal a uma oferta complementar com validação de elegibilidade e conflito.",
            "form": form,
            "submit_label": "Confirmar participação",
            "override_enabled": can_override_conflict,
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:programa_complementar_participacao_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("educacao.view")
def programa_complementar_relatorios(request):
    ofertas_scope = _ofertas_scope(request.user)
    participacoes_base = ProgramaComplementarParticipacao.objects.select_related(
        "aluno",
        "matricula_institucional",
        "programa",
        "oferta",
        "oferta__unidade",
    ).filter(oferta__in=ofertas_scope)

    programa_id_raw = (request.GET.get("programa") or "").strip()
    unidade_id_raw = (request.GET.get("unidade") or "").strip()
    ano_letivo_raw = (request.GET.get("ano_letivo") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip().upper()
    status = (request.GET.get("status") or "").strip().upper()
    limite_raw = (request.GET.get("frequencia_limite") or "75").strip().replace(",", ".")

    programa_id = int(programa_id_raw) if programa_id_raw.isdigit() else None
    unidade_id = int(unidade_id_raw) if unidade_id_raw.isdigit() else None
    ano_letivo = int(ano_letivo_raw) if ano_letivo_raw.isdigit() else None
    try:
        frequencia_limite = float(limite_raw)
    except (TypeError, ValueError):
        frequencia_limite = 75.0
    frequencia_limite = min(100.0, max(0.0, frequencia_limite))

    if programa_id:
        participacoes_base = participacoes_base.filter(programa_id=programa_id)
    if unidade_id:
        participacoes_base = participacoes_base.filter(oferta__unidade_id=unidade_id)
    if ano_letivo:
        participacoes_base = participacoes_base.filter(ano_letivo=ano_letivo)
    if tipo:
        participacoes_base = participacoes_base.filter(programa__tipo=tipo)

    participacoes_scope_sem_status = participacoes_base
    if status:
        participacoes_base = participacoes_base.filter(status=status)

    participacoes_annotated = participacoes_base.annotate(
        total_frequencias=Count("frequencias"),
        total_presencas=Count(
            "frequencias",
            filter=Q(
                frequencias__status_presenca=ProgramaComplementarFrequencia.StatusPresenca.PRESENTE,
            ),
        ),
    ).order_by("-id")

    participacoes_relatorio = list(participacoes_annotated[:500])
    frequencias = []
    baixa_frequencia = []
    for participacao in participacoes_relatorio:
        percentual = None
        if participacao.total_frequencias:
            percentual = float(participacao.total_presencas * 100.0 / participacao.total_frequencias)
            frequencias.append(percentual)
        participacao.percentual_frequencia_relatorio = percentual
        if (
            percentual is not None
            and participacao.status == ProgramaComplementarParticipacao.Status.ATIVO
            and percentual < frequencia_limite
        ):
            baixa_frequencia.append(participacao)
    baixa_frequencia.sort(
        key=lambda p: (
            p.percentual_frequencia_relatorio if p.percentual_frequencia_relatorio is not None else 999.0,
            p.aluno.nome,
        )
    )

    ofertas_filtradas = ofertas_scope
    if programa_id:
        ofertas_filtradas = ofertas_filtradas.filter(programa_id=programa_id)
    if unidade_id:
        ofertas_filtradas = ofertas_filtradas.filter(unidade_id=unidade_id)
    if ano_letivo:
        ofertas_filtradas = ofertas_filtradas.filter(ano_letivo=ano_letivo)
    if tipo:
        ofertas_filtradas = ofertas_filtradas.filter(programa__tipo=tipo)

    ocupacao_ofertas = list(
        ofertas_filtradas.annotate(
            participacoes_ativas=Count(
                "participacoes",
                filter=Q(participacoes__status=ProgramaComplementarParticipacao.Status.ATIVO),
            )
        ).order_by("-participacoes_ativas", "codigo", "id")[:120]
    )
    for oferta in ocupacao_ofertas:
        oferta.vagas_disponiveis_relatorio = max(
            0,
            int(oferta.capacidade_maxima or 0) - int(oferta.participacoes_ativas or 0),
        )

    alunos_multiplos_programas = list(
        participacoes_scope_sem_status.filter(status=ProgramaComplementarParticipacao.Status.ATIVO)
        .values("aluno_id", "aluno__nome", "matricula_institucional__numero_matricula")
        .annotate(
            total_programas=Count("programa_id", distinct=True),
            total_ofertas=Count("oferta_id", distinct=True),
        )
        .filter(total_programas__gt=1)
        .order_by("-total_programas", "aluno__nome")[:100]
    )

    if (request.GET.get("export") or "").strip().lower() == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="programas_relatorios.csv"'
        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "Aluno",
                "Matrícula",
                "Programa",
                "Tipo",
                "Oferta",
                "Unidade",
                "Ano letivo",
                "Status",
                "Data ingresso",
                "Frequência (%)",
            ]
        )
        for participacao in participacoes_relatorio:
            writer.writerow(
                [
                    participacao.aluno.nome,
                    participacao.matricula_institucional.numero_matricula,
                    participacao.programa.nome,
                    participacao.programa.get_tipo_display(),
                    f"{participacao.oferta.codigo} - {participacao.oferta.nome}",
                    getattr(participacao.oferta.unidade, "nome", ""),
                    participacao.ano_letivo,
                    participacao.get_status_display(),
                    participacao.data_ingresso.strftime("%d/%m/%Y") if participacao.data_ingresso else "",
                    (
                        f"{participacao.percentual_frequencia_relatorio:.1f}"
                        if participacao.percentual_frequencia_relatorio is not None
                        else ""
                    ),
                ]
            )
        return response

    export_query = request.GET.copy()
    export_query["export"] = "csv"
    export_url = f"{reverse('educacao:programa_complementar_relatorios')}?{export_query.urlencode()}"

    context = {
        "title": "Relatórios de Programas",
        "subtitle": "Indicadores gerenciais de participação, ocupação e frequência por programa complementar.",
        "programas": _programas_scope(request.user).order_by("nome")[:300],
        "unidades": _unidades_scope(request.user).order_by("nome")[:300],
        "anos_letivos": list(ofertas_scope.values_list("ano_letivo", flat=True).distinct().order_by("-ano_letivo")),
        "tipos_programa": ProgramaComplementar.Tipo.choices,
        "programa_id": programa_id_raw,
        "unidade_id": unidade_id_raw,
        "ano_letivo": ano_letivo_raw,
        "tipo": tipo,
        "status": status,
        "frequencia_limite": f"{frequencia_limite:.1f}",
        "kpis": {
            "total_participacoes": participacoes_base.count(),
            "participacoes_ativas": participacoes_scope_sem_status.filter(
                status=ProgramaComplementarParticipacao.Status.ATIVO
            ).count(),
            "participacoes_concluidas": participacoes_scope_sem_status.filter(
                status=ProgramaComplementarParticipacao.Status.CONCLUIDO
            ).count(),
            "ofertas_ativas": ofertas_filtradas.filter(status=ProgramaComplementarOferta.Status.ATIVA).count(),
            "frequencia_media": (sum(frequencias) / len(frequencias)) if frequencias else None,
            "alunos_multiplos_programas": len(alunos_multiplos_programas),
        },
        "baixa_frequencia": baixa_frequencia[:100],
        "alunos_multiplos_programas": alunos_multiplos_programas,
        "ocupacao_ofertas": ocupacao_ofertas[:80],
        "participacoes_relatorio": participacoes_relatorio[:120],
        "export_url": export_url,
        "actions": [
            {
                "label": "Exportar CSV",
                "url": export_url,
                "icon": "fa-solid fa-file-csv",
                "variant": "gp-button--outline",
            },
            {
                "label": "Nova participação",
                "url": reverse("educacao:programa_complementar_participacao_create"),
                "icon": "fa-solid fa-user-plus",
                "variant": "gp-button--primary",
            },
            {
                "label": "Painel",
                "url": reverse("educacao:programas_dashboard"),
                "icon": "fa-solid fa-chart-line",
                "variant": "gp-button--ghost",
            },
        ],
    }
    return render(request, "educacao/programas/relatorios.html", context)


@login_required
@require_perm("educacao.manage")
def programa_complementar_frequencia_registrar(request, pk: int):
    oferta_scope = _ofertas_scope(request.user)
    participacao = get_object_or_404(
        ProgramaComplementarParticipacao.objects.select_related("aluno", "programa", "oferta", "matricula_institucional"),
        pk=pk,
        oferta__in=oferta_scope,
    )
    form = ProgramaComplementarFrequenciaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            ProgramasComplementaresService.register_attendance(
                participacao=participacao,
                data_aula=form.cleaned_data["data_aula"],
                status_presenca=form.cleaned_data["status_presenca"],
                usuario=request.user,
                justificativa=form.cleaned_data.get("justificativa") or "",
                observacoes=form.cleaned_data.get("observacoes") or "",
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Frequência registrada com sucesso.")
            return redirect("educacao:programa_complementar_participacao_list")
    historico = participacao.frequencias.order_by("-data_aula", "-id")[:30]
    return render(
        request,
        "educacao/programas/frequencia_form.html",
        {
            "title": "Registrar Frequência",
            "subtitle": (
                f"Aluno: {participacao.aluno.nome} • "
                f"Matrícula: {participacao.matricula_institucional.numero_matricula} • "
                f"Programa: {participacao.programa.nome}"
            ),
            "participacao": participacao,
            "form": form,
            "historico": historico,
            "submit_label": "Salvar frequência",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("educacao:programa_complementar_participacao_list"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )
