from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from core.rbac import get_profile
from educacao.models import Turma, Matricula


@login_required
def dashboard(request):
    p = get_profile(request.user)

    # Dashboard específico do professor
    if p and p.role == "PROFESSOR":
        ano_atual = timezone.now().date().year

        turmas_qs = (
            Turma.objects
            .filter(professores=request.user)
            .select_related("unidade")
            .order_by("-ano_letivo", "nome")
        )

        alunos_count = (
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
                "alunos_total": alunos_count,
                "ano_atual": ano_atual,
            },
        )

    # Dashboard padrão (outros perfis)
    return render(request, "core/dashboard.html")
