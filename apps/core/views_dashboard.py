from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import OperationalError, ProgrammingError
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone
import json

from apps.accounts.models import Profile
from apps.core.rbac import can, get_profile, is_admin

from apps.org.models import (
    Municipio,
    Secretaria,
    Unidade,
    Setor,
    OnboardingStep,
    MunicipioModuloAtivo,
    SecretariaProvisionamento,
)
from apps.educacao.models import Turma, Aluno, Matricula
from apps.educacao.models_calendario import CalendarioEducacionalEvento

from apps.core.rbac import (
    scope_filter_secretarias,
    scope_filter_unidades,
    scope_filter_turmas,
    scope_filter_alunos,
    scope_filter_matriculas,
)

from .forms import AlunoAvisoForm, AlunoArquivoForm
from .models import AlunoAviso, AlunoArquivo


def portal_manage_allowed(user) -> bool:
    return bool(
        can(user, "educacao.manage")
        or can(user, "org.manage_unidade")
        or can(user, "org.manage_secretaria")
        or can(user, "org.manage_municipio")
        or (get_profile(user) and get_profile(user).role == "PROFESSOR")
        or is_admin(user)
        or getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
    )


@login_required
def dashboard_view(request):
    user = request.user
    p = get_profile(user)

    base_ctx = {
        "page_title": "Dashboard",
        "page_subtitle": "Visão geral",
        "show_page_head": False,
    }

    if is_admin(user) or getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        kpis = {
            "municipios": Municipio.objects.count(),
            "usuarios": User.objects.count(),
            "secretarias": Secretaria.objects.count(),
            "unidades": Unidade.objects.count(),
            "setores": Setor.objects.count(),
            "turmas": Turma.objects.count(),
            "alunos": Aluno.objects.count(),
            "matriculas": Matricula.objects.count(),
        }

        roles_qs = Profile.objects.values("role").annotate(total=Count("id")).order_by("-total")
        role_labels = [r["role"] or "SEM_ROLE" for r in roles_qs]
        role_values = [r["total"] for r in roles_qs]
        chart_roles = {"labels": json.dumps(role_labels), "values": json.dumps(role_values)}

        unidades_por_municipio = list(
            Unidade.objects.values("secretaria__municipio_id", "secretaria__municipio__nome")
            .annotate(unidades=Count("id"))
            .order_by("-unidades")[:10]
        )

        secretarias_por_municipio = list(
            Secretaria.objects.values("municipio_id", "municipio__nome")
            .annotate(secretarias=Count("id"))
        )
        sec_map = {r["municipio_id"]: r["secretarias"] for r in secretarias_por_municipio}

        top_municipios = []
        for r in unidades_por_municipio:
            mid = r["secretaria__municipio_id"]
            top_municipios.append({
                "id": mid,
                "nome": r["secretaria__municipio__nome"] or "—",
                "secretarias": sec_map.get(mid, 0),
                "unidades": r["unidades"],
            })

        top_unidades_raw = list(
            Turma.objects.values("unidade_id", "unidade__nome")
            .annotate(turmas=Count("id"))
            .order_by("-turmas", "unidade__nome")[:10]
        )
        top_unidades = [{"id": r["unidade_id"], "nome": r["unidade__nome"] or "—", "turmas": r["turmas"]} for r in top_unidades_raw]

        chart_municipios = {
            "labels": json.dumps([m["nome"] for m in top_municipios]),
            "values": json.dumps([m["unidades"] for m in top_municipios]),
        }

        ctx = {
            **base_ctx,
            "page_subtitle": "Visão geral do sistema",
            "dash_template": "core/dashboards/partials/admin.html",
            "kpis": kpis,
            "chart_roles": chart_roles,
            "chart_municipios": chart_municipios,
            "top_municipios": top_municipios,
            "top_unidades": top_unidades,
            "can_nee": True,
            "can_users": True,
            "ultimos_municipios": Municipio.objects.order_by("-id")[:5],
        }
        return render(request, "core/dashboard.html", ctx)

    if not p or not getattr(p, "ativo", True):
        return render(request, "core/dashboard.html", {**base_ctx, "dash_template": "core/dashboards/partials/default.html"})

    role = (p.role or "").upper()

    if role == "MUNICIPAL":
        try:
            has_steps = OnboardingStep.objects.filter(municipio_id=p.municipio_id).exists()
            has_provision = SecretariaProvisionamento.objects.filter(municipio_id=p.municipio_id).exists()
            if not has_steps and not has_provision:
                return redirect("org:onboarding_primeiro_acesso")
        except (ProgrammingError, OperationalError):
            pass

    if role == "ALUNO":
        if not getattr(p, "aluno_id", None):
            return render(request, "core/dashboard.html", {
                **base_ctx,
                "page_subtitle": "Meu painel",
                "dash_template": "core/dashboards/partials/aluno.html",
                "sem_vinculo": True,
                "avisos": [],
                "arquivos": [],
                "eventos_calendario": [],
            })

        aluno_id = p.aluno_id

        matriculas = Matricula.objects.select_related(
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        ).filter(aluno_id=aluno_id)

        turma_ids = list(matriculas.values_list("turma_id", flat=True))
        unidade_ids = list(matriculas.values_list("turma__unidade_id", flat=True))
        secretaria_ids = list(matriculas.values_list("turma__unidade__secretaria_id", flat=True))
        municipio_ids = list(matriculas.values_list("turma__unidade__secretaria__municipio_id", flat=True))

        avisos = (
            AlunoAviso.objects.filter(ativo=True)
            .filter(
                Q(aluno_id=aluno_id)
                | Q(turma_id__in=turma_ids)
                | Q(unidade_id__in=unidade_ids)
                | Q(secretaria_id__in=secretaria_ids)
                | Q(municipio_id__in=municipio_ids)
            )
            .select_related("autor")
            .order_by("-criado_em")[:20]
        )

        arquivos = (
            AlunoArquivo.objects.filter(ativo=True)
            .filter(
                Q(aluno_id=aluno_id)
                | Q(turma_id__in=turma_ids)
                | Q(unidade_id__in=unidade_ids)
                | Q(secretaria_id__in=secretaria_ids)
                | Q(municipio_id__in=municipio_ids)
            )
            .select_related("autor")
            .order_by("-criado_em")[:20]
        )

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
                    .order_by("data_inicio", "titulo")[:8]
                )
            except (ProgrammingError, OperationalError):
                eventos_calendario = CalendarioEducacionalEvento.objects.none()

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Meu painel",
            "dash_template": "core/dashboards/partials/aluno.html",
            "sem_vinculo": False,
            "avisos": avisos,
            "arquivos": arquivos,
            "eventos_calendario": eventos_calendario,
        })

    if role == "PROFESSOR":
        ano_atual = timezone.now().date().year
        turmas_qs = scope_filter_turmas(user, Turma.objects.all()).select_related("unidade").order_by("-ano_letivo", "nome")
        alunos_total = Matricula.objects.filter(turma__in=turmas_qs).values("aluno_id").distinct().count()
        secretaria_ids = list(turmas_qs.values_list("unidade__secretaria_id", flat=True).distinct())
        unidade_ids = list(turmas_qs.values_list("unidade_id", flat=True).distinct())

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
                    .order_by("data_inicio", "titulo")[:8]
                )
            except (ProgrammingError, OperationalError):
                eventos_calendario = CalendarioEducacionalEvento.objects.none()

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Minhas turmas e alunos",
            "dash_template": "core/dashboards/partials/professor.html",
            "turmas": turmas_qs.filter(ano_letivo=ano_atual)[:8],
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_total,
            "ano_atual": ano_atual,
            "eventos_calendario": eventos_calendario,
        })

    if role == "MUNICIPAL":
        secretarias_qs = scope_filter_secretarias(user, Secretaria.objects.all()).select_related("municipio")
        unidades_qs = scope_filter_unidades(user, Unidade.objects.all()).select_related("secretaria", "secretaria__municipio")

        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        matriculas_qs = scope_filter_matriculas(user, Matricula.objects.all())
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())

        graf_unidades_por_secretaria = list(
            Unidade.objects.filter(secretaria__in=secretarias_qs)
            .values("secretaria__nome").annotate(total=Count("id")).order_by("-total")[:8]
        )
        graf_alunos_por_secretaria = list(
            Matricula.objects.filter(turma__unidade__secretaria__in=secretarias_qs)
            .values("turma__unidade__secretaria__nome")
            .annotate(total=Count("aluno", distinct=True))
            .order_by("-total")[:8]
        )

        onboarding_total_steps = 0
        onboarding_done_steps = 0
        onboarding_modules_active = 0
        try:
            onboarding_steps_qs = OnboardingStep.objects.filter(municipio_id=p.municipio_id)
            onboarding_total_steps = onboarding_steps_qs.count()
            onboarding_done_steps = onboarding_steps_qs.filter(status=OnboardingStep.Status.CONCLUIDO).count()
            onboarding_modules_active = MunicipioModuloAtivo.objects.filter(
                municipio_id=p.municipio_id,
                ativo=True,
            ).count()
        except (ProgrammingError, OperationalError):
            onboarding_total_steps = 0
            onboarding_done_steps = 0
            onboarding_modules_active = 0

        ctx = {
            **base_ctx,
            "page_subtitle": "Visão municipal",
            "dash_template": "core/dashboards/partials/municipal.html",
            "municipio_nome": getattr(p.municipio, "nome", "—") if getattr(p, "municipio_id", None) else "—",
            "secretarias_total": secretarias_qs.count(),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),
            "ultimas_secretarias": secretarias_qs.order_by("-id")[:5],
            "ultimos_alunos": alunos_qs.prefetch_related("matriculas__turma__unidade").order_by("-id")[:5],
            "chart1_labels": [i["secretaria__nome"] for i in graf_unidades_por_secretaria],
            "chart1_values": [i["total"] for i in graf_unidades_por_secretaria],
            "chart2_labels": [i["turma__unidade__secretaria__nome"] for i in graf_alunos_por_secretaria],
            "chart2_values": [i["total"] for i in graf_alunos_por_secretaria],
            "onboarding_total_steps": onboarding_total_steps,
            "onboarding_done_steps": onboarding_done_steps,
            "onboarding_modules_active": onboarding_modules_active,
            "onboarding_url": "/org/onboarding/painel/",
        }
        return render(request, "core/dashboard.html", ctx)

    if role == "SECRETARIA":
        unidades_qs = scope_filter_unidades(user, Unidade.objects.all()).select_related("secretaria")
        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())

        graf_turmas_por_unidade = list(
            turmas_qs.values("unidade__nome").annotate(total=Count("id")).order_by("-total")[:8]
        )

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Visão da secretaria",
            "dash_template": "core/dashboards/partials/secretaria.html",
            "secretaria_nome": getattr(getattr(p, "secretaria", None), "nome", "—"),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "unidades": unidades_qs.order_by("nome")[:10],
            "graf_turmas_por_unidade": graf_turmas_por_unidade,
        })

    if role == "UNIDADE":
        turmas_qs = scope_filter_turmas(user, Turma.objects.all()).select_related("unidade")
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())
        matriculas_qs = scope_filter_matriculas(user, Matricula.objects.all()).select_related("turma")

        graf_matriculas_por_turma = list(
            matriculas_qs.values("turma__nome").annotate(total=Count("id")).order_by("-total")[:10]
        )

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Visão da unidade",
            "dash_template": "core/dashboards/partials/unidade.html",
            "unidade_nome": getattr(getattr(p, "unidade", None), "nome", "—"),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),
            "turmas": turmas_qs.order_by("-ano_letivo", "nome")[:10],
            "graf_matriculas_por_turma": graf_matriculas_por_turma,
        })

    return render(request, "core/dashboard.html", {**base_ctx, "dash_template": "core/dashboards/partials/default.html"})


@login_required
def dashboard_aluno(request):
    return redirect("core:dashboard")


@login_required
def aviso_create(request):
    if not portal_manage_allowed(request.user):
        return HttpResponseForbidden("Você não tem permissão para acessar esta área.")

    form = AlunoAvisoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        aviso = form.save(commit=False)
        aviso.autor = request.user
        aviso.save()
        messages.success(request, "Aviso publicado.")
        return redirect("core:dashboard")

    return render(request, "core/aviso_form.html", {"form": form})


@login_required
def arquivo_create(request):
    if not portal_manage_allowed(request.user):
        return HttpResponseForbidden("Você não tem permissão para acessar esta área.")

    form = AlunoArquivoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        arq = form.save(commit=False)
        arq.autor = request.user
        arq.save()
        messages.success(request, "Arquivo enviado.")
        return redirect("core:dashboard")

    return render(request, "core/arquivo_form.html", {"form": form})
