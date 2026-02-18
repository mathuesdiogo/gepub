from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.core.decorators import require_perm

@login_required
@require_perm("saude.view")
def index(request):
    return render(request, "saude/index.html", {
        "unidades_total": 0,
        "profissionais_total": 0,
        "atendimentos_total": 0,
    })
