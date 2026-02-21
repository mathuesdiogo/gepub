from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade
from .models import ProfissionalSaude
from .models import AtendimentoSaude


@login_required
@require_perm("saude.view")
def index(request):
    # =========================
    # UNIDADES (somente tipo SAÚDE)
    # =========================
    unidades_qs = Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE)

    # aplica escopo do usuário (municipal / secretaria etc.)
    unidades_qs = scope_filter_unidades(request.user, unidades_qs)

    unidades_total = unidades_qs.count()
    unidades_ativas = unidades_qs.filter(ativo=True).count()
    unidades_inativas = unidades_qs.filter(ativo=False).count()

    # =========================
    # PROFISSIONAIS
    # =========================
    profissionais_qs = ProfissionalSaude.objects.filter(
        unidade__tipo=Unidade.Tipo.SAUDE
    ).select_related("unidade")

    # aplica escopo também baseado nas unidades visíveis
    profissionais_qs = profissionais_qs.filter(
        unidade_id__in=unidades_qs.values_list("id", flat=True)
    )

    profissionais_total = profissionais_qs.filter(ativo=True).count()
    profissionais_inativos = profissionais_qs.filter(ativo=False).count()

    # =========================
    # ATENDIMENTOS (placeholder)
        # =========================
    atendimentos_total = AtendimentoSaude.objects.filter(unidade_id__in=unidades_qs.values_list("id", flat=True)).count()

    context = {
        # Unidades
        "unidades_total": unidades_total,
        "unidades_ativas": unidades_ativas,
        "unidades_inativas": unidades_inativas,

        # Profissionais
        "profissionais_total": profissionais_total,
        "profissionais_inativos": profissionais_inativos,

        # Atendimentos
        "atendimentos_total": atendimentos_total,
    }

    return render(request, "saude/index.html", context)
