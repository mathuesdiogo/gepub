from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

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

from org.models import Municipio, Secretaria, Unidade
from educacao.models import Turma, Aluno, Matricula


@login_required
def dashboard(request):
    user = request.user
    p = get_profile(user)

    # ===== ADMIN =====
    if is_admin(user):
        ctx = {
            "municipios": Municipio.objects.count(),
            "secretarias": Secretaria.objects.count(),
            "unidades": Unidade.objects.count(),
            "turmas": Turma.objects.count(),
            "alunos": Aluno.objects.count(),
            "matriculas": Matricula.objects.count(),
            "ultimos_municipios": Municipio.objects.order_by("-id")[:5],
        }
        return render(request, "core/dashboard_admin.html", ctx)

    # Sem profile ou inativo
    if not p or not getattr(p, "ativo", True):
        return render(request, "core/dashboard_default.html")

    role = p.role

    # ===== PROFESSOR ===== (você já curtiu, mantém)
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
        chart1_labels = [r["secretaria__nome"] or "—" for r in graf_unidades_por_secretaria]
        chart1_values = [r["total"] for r in graf_unidades_por_secretaria]

        # ========= GRÁFICO 2: Alunos por Secretaria (Top 8) =========
        # alunos distintos via matrículas (melhor indicador)
        graf_alunos_por_secretaria = list(
            matriculas_qs.values("turma__unidade__secretaria__id", "turma__unidade__secretaria__nome")
            .annotate(total=Count("aluno_id", distinct=True))
            .order_by("-total")[:8]
        )
        chart2_labels = [r["turma__unidade__secretaria__nome"] or "—" for r in graf_alunos_por_secretaria]
        chart2_values = [r["total"] for r in graf_alunos_por_secretaria]

        municipio_id = getattr(p, "municipio_id", None)
        municipio_nome = getattr(getattr(p, "municipio", None), "nome", "—") if municipio_id else "—"

        ctx = {
            "municipio_id": municipio_id,
            "municipio_nome": municipio_nome,

            # KPIs
            "secretarias_total": secretarias_qs.count(),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),

            # listas
            "ultimas_secretarias": secretarias_qs.order_by("-id")[:6],

            # charts (JSON no template)
            "chart1_labels": chart1_labels,
            "chart1_values": chart1_values,
            "chart2_labels": chart2_labels,
            "chart2_values": chart2_values,
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
