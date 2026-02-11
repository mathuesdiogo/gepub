from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone

import json

from accounts.models import Profile
from core.rbac import can, get_profile
from educacao.models import Matricula
from .forms import AlunoAvisoForm, AlunoArquivoForm
from .models import AlunoAviso, AlunoArquivo

from core.rbac import (
    get_profile,
    is_admin,
    scope_filter_municipios,
    scope_filter_secretarias,
    scope_filter_unidades,
    scope_filter_turmas,
    scope_filter_alunos,
    scope_filter_matriculas,
)

from org.models import Municipio, Secretaria, Unidade, Setor
from educacao.models import Turma, Aluno, Matricula


@login_required
def dashboard(request):
    user = request.user
    p = get_profile(user)

    # ===== ADMIN =====
    if is_admin(user) or getattr(user, "is_superuser", False):
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # KPIs gerais (sempre presentes)
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

        # ===== Usuários por perfil =====
        roles_qs = (
            Profile.objects.values("role")
            .annotate(total=Count("id"))
            .order_by("-total")
        )
        role_labels = [r["role"] or "SEM_ROLE" for r in roles_qs]
        role_values = [r["total"] for r in roles_qs]

        chart_roles = {
            "labels": json.dumps(role_labels),
            "values": json.dumps(role_values),
        }

        # ===== Estrutura por Prefeitura (Top 10) =====
        # Fazemos via agregação (evita depender de related_name reverso)
        # Unidades por município
        unidades_por_municipio = list(
            Unidade.objects.values(
                "secretaria__municipio_id",
                "secretaria__municipio__nome",
            )
            .annotate(unidades=Count("id"))
            .order_by("-unidades")[:10]
        )

        # Secretarias por município
        secretarias_por_municipio = list(
            Secretaria.objects.values("municipio_id", "municipio__nome")
            .annotate(secretarias=Count("id"))
        )
        sec_map = {r["municipio_id"]: r["secretarias"] for r in secretarias_por_municipio}

        # Lista final para tabela (nome, secretarias, unidades)
        top_municipios = []
        for r in unidades_por_municipio:
            mid = r["secretaria__municipio_id"]
            top_municipios.append(
                {
                    "id": mid,
                    "nome": r["secretaria__municipio__nome"] or "—",
                    "secretarias": sec_map.get(mid, 0),
                    "unidades": r["unidades"],
                }
            )

        # ===== Top Unidades por Turmas =====
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
            "kpis": kpis,
            "chart_roles": chart_roles,
            "chart_municipios": chart_municipios,
            "top_municipios": top_municipios,
            "top_unidades": top_unidades,
            # atalhos (se seu template usar)
            "can_nee": True,
            "can_users": True,
            # opcional: lista recente
            "ultimos_municipios": Municipio.objects.order_by("-id")[:5],
        }
        return render(request, "core/dashboard_admin.html", ctx)

    # Sem profile ou inativo
    if not p or not getattr(p, "ativo", True):
        return render(request, "core/dashboard_default.html")

    role = p.role

    # ===== PROFESSOR =====
    if role == "PROFESSOR":
        ano_atual = timezone.now().date().year
        turmas_qs = (
            scope_filter_turmas(user, Turma.objects.all())
            .select_related("unidade")
            .order_by("-ano_letivo", "nome")
        )
        alunos_total = (
            Matricula.objects
            .filter(turma__in=turmas_qs)
            .values("aluno_id")
            .distinct()
            .count()
        )
        return render(
            request,
            "core/dashboard_professor.html",
            {
                "turmas": turmas_qs.filter(ano_letivo=ano_atual)[:8],
                "turmas_total": turmas_qs.count(),
                "alunos_total": alunos_total,
                "ano_atual": ano_atual,
            },
        )

    # ===== MUNICIPAL =====
    if role == "MUNICIPAL":
        secretarias_qs = scope_filter_secretarias(user, Secretaria.objects.all()).select_related("municipio")
        unidades_qs = scope_filter_unidades(user, Unidade.objects.all()).select_related(
            "secretaria", "secretaria__municipio"
        )

        # KPIs educação
        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        matriculas_qs = scope_filter_matriculas(user, Matricula.objects.all())
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())

        # ========= GRÁFICO 1: Unidades por Secretaria (Top 8) =========
        graf_unidades_por_secretaria = list(
            unidades_qs.values("secretaria__id", "secretaria__nome")
            .annotate(total=Count("id"))
            .order_by("-total")[:8]
        )

        # ========= GRÁFICO 2: Alunos por Secretaria (Top 8) =========
        graf_alunos_por_secretaria = list(
            matriculas_qs.values("turma__unidade__secretaria__id", "turma__unidade__secretaria__nome")
            .annotate(total=Count("aluno_id", distinct=True))
            .order_by("-total")[:8]
        )

        ctx = {
            "municipio_nome": getattr(p.municipio, "nome", "—") if getattr(p, "municipio_id", None) else "—",

            # KPIs
            "secretarias_total": secretarias_qs.count(),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),

            # Listas
            "ultimas_secretarias": secretarias_qs.order_by("-id")[:5],
            "ultimos_alunos": alunos_qs.prefetch_related(
                "matriculas__turma__unidade"
            ).order_by("-id")[:5],

            # Gráficos
            "chart1_labels": [i["secretaria__nome"] for i in graf_unidades_por_secretaria],
            "chart1_values": [i["total"] for i in graf_unidades_por_secretaria],

            "chart2_labels": [i["turma__unidade__secretaria__nome"] for i in graf_alunos_por_secretaria],
            "chart2_values": [i["total"] for i in graf_alunos_por_secretaria],
        }

        return render(request, "core/dashboard_municipal.html", ctx)

    # ===== SECRETARIA =====
    if role == "SECRETARIA":
        unidades_qs = scope_filter_unidades(user, Unidade.objects.all()).select_related("secretaria")
        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())

        graf_turmas_por_unidade = list(
            turmas_qs.values("unidade__nome")
            .annotate(total=Count("id"))
            .order_by("-total")[:8]
        )

        ctx = {
            "secretaria_nome": getattr(getattr(p, "secretaria", None), "nome", "—"),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "unidades": unidades_qs.order_by("nome")[:10],
            "graf_turmas_por_unidade": graf_turmas_por_unidade,
        }
        return render(request, "core/dashboard_secretaria.html", ctx)

    # ===== UNIDADE =====
    if role == "UNIDADE":
        turmas_qs = scope_filter_turmas(user, Turma.objects.all()).select_related("unidade")
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())
        matriculas_qs = scope_filter_matriculas(user, Matricula.objects.all()).select_related("turma")

        graf_matriculas_por_turma = list(
            matriculas_qs.values("turma__nome")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )

        ctx = {
            "unidade_nome": getattr(getattr(p, "unidade", None), "nome", "—"),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),
            "turmas": turmas_qs.order_by("-ano_letivo", "nome")[:10],
            "graf_matriculas_por_turma": graf_matriculas_por_turma,
        }
        return render(request, "core/dashboard_unidade.html", ctx)

    # ===== OUTROS (ALUNO, NEE, LEITURA etc.) =====
    return render(request, "core/dashboard_default.html")


def _portal_manage_allowed(user) -> bool:
    return bool(
        can(user, "educacao.manage") or can(user, "org.manage_unidade") or can(user, "org.manage_secretaria")
        or can(user, "org.manage_municipio") or (get_profile(user) and get_profile(user).role == "PROFESSOR")
    )


@login_required
def dashboard_aluno(request):
    p = get_profile(request.user)
    if not p or p.role != "ALUNO":
        return redirect("core:dashboard")

    if not p.aluno_id:
        return render(request, "core/dashboard_aluno.html", {"sem_vinculo": True, "avisos": [], "arquivos": []})

    aluno_id = p.aluno_id

    matriculas = (
        Matricula.objects.select_related(
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        )
        .filter(aluno_id=aluno_id)
    )

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

    return render(
        request,
        "core/dashboard_aluno.html",
        {"sem_vinculo": False, "avisos": avisos, "arquivos": arquivos},
    )


@login_required
def aviso_create(request):
    if not _portal_manage_allowed(request.user):
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
    if not _portal_manage_allowed(request.user):
        return HttpResponseForbidden("Você não tem permissão para acessar esta área.")

    form = AlunoArquivoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        arq = form.save(commit=False)
        arq.autor = request.user
        arq.save()
        messages.success(request, "Arquivo enviado.")
        return redirect("core:dashboard")

    return render(request, "core/arquivo_form.html", {"form": form})
