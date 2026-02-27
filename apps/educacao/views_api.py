from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse

from apps.educacao.models import Aluno, Turma
from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_alunos, scope_filter_turmas

@login_required
@require_perm("educacao.view")
def api_alunos_suggest(request):
    if not can(request.user, "educacao.manage"):
        return JsonResponse({"results": []})

    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    alunos_qs = scope_filter_alunos(
        request.user,
        Aluno.objects.only("id", "nome", "cpf", "nis"),
    )

    qs = alunos_qs.filter(
        Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(nis__icontains=q)
    ).order_by("nome")[:10]

    results = []
    for a in qs:
        results.append(
            {
                "id": a.id,
                "nome": a.nome,
                "cpf": a.cpf or "",
                "nis": a.nis or "",
            }
        )

    return JsonResponse({"results": results})


@login_required
@require_perm("educacao.view")
def api_turmas_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade").only("id", "nome", "ano_letivo", "unidade__nome"),
    )

    if q.isdigit():
        qs = qs.filter(ano_letivo=int(q))
    else:
        qs = qs.filter(
            Q(nome__icontains=q) | Q(unidade__nome__icontains=q)
        )

    qs = qs.order_by("-ano_letivo", "nome")[:10]

    results = []
    for t in qs:
        results.append(
            {
                "id": t.id,
                "text": f"{t.nome} ({t.ano_letivo})",
                "meta": getattr(getattr(t, "unidade", None), "nome", "") or "",
            }
        )

    return JsonResponse({"results": results})
