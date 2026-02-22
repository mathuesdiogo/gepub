from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def alertas_index(request):
    """Painel de alertas do NEE (stub inicial).
    Evoluir para pendências e acompanhamentos (drilldown por aluno/unidade).
    """
    context = {
        "actions": [],
        "items": [],
    }
    return render(request, "nee/alertas/index.html", context)
