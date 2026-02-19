from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.core.decorators import require_perm
from apps.core.rbac import scope_filter_unidades
from apps.org.models import Unidade
from .models import ProfissionalSaude


@login_required
@require_perm("saude.view")
@require_GET
def api_profissionais_por_unidade(request):
    unidade_id = (request.GET.get("unidade") or "").strip()
    if not unidade_id.isdigit():
        return JsonResponse({"results": []})

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(tipo=Unidade.Tipo.SAUDE),
    )

    if not unidades_qs.filter(pk=int(unidade_id)).exists():
        return JsonResponse({"results": []})

    qs = (
        ProfissionalSaude.objects.filter(unidade_id=int(unidade_id), ativo=True)
        .select_related("unidade")
        .order_by("nome")[:200]
    )

    results = [{"id": p.id, "text": p.nome} for p in qs]
    return JsonResponse({"results": results})
