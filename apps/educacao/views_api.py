from __future__ import annotations

import hashlib
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone

from apps.educacao.models import Aluno, Turma
from apps.educacao.models_biblioteca import MatriculaInstitucional
from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_alunos, scope_filter_turmas

logger = logging.getLogger(__name__)


def _safe_limit(raw: str | None, default: int = 10, max_limit: int = 50) -> int:
    try:
        value = int(str(raw or default).strip())
    except Exception:
        value = default
    return max(1, min(max_limit, value))


def _safe_page(raw: str | None, default: int = 1) -> int:
    try:
        value = int(str(raw or default).strip())
    except Exception:
        value = default
    return max(1, value)


def _cache_key(prefix: str, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"educacao:{prefix}:{digest}"


def _build_paginated_response(results: list[dict], total: int, page: int, limit: int):
    has_more = (page * limit) < int(total)
    return JsonResponse(
        {
            "results": results,
            "meta": {
                "page": page,
                "limit": limit,
                "total": int(total),
                "has_more": has_more,
                "generated_at": timezone.now().isoformat(),
            },
        }
    )


@login_required
@require_perm("educacao.view")
def api_alunos_suggest(request):
    if not can(request.user, "educacao.manage"):
        return _build_paginated_response([], 0, 1, 10)

    q = (request.GET.get("q") or "").strip()
    page = _safe_page(request.GET.get("page"))
    limit = _safe_limit(request.GET.get("limit"), default=10, max_limit=50)
    if len(q) < 2:
        return _build_paginated_response([], 0, page, limit)

    key = _cache_key(
        "api_alunos_suggest",
        {"u": request.user.id, "q": q.lower(), "page": page, "limit": limit},
    )
    cached = cache.get(key)
    if cached:
        return JsonResponse(cached)

    alunos_qs = scope_filter_alunos(
        request.user,
        Aluno.objects.select_related("matricula_institucional").only(
            "id",
            "nome",
            "cpf",
            "nis",
            "matricula_institucional__numero_matricula",
        ),
    )
    matricula_student_ids = MatriculaInstitucional.objects.filter(
        numero_matricula__icontains=q
    ).values_list("aluno_id", flat=True)

    base_qs = alunos_qs.filter(
        Q(nome__icontains=q)
        | Q(cpf__icontains=q)
        | Q(nis__icontains=q)
        | Q(id__in=matricula_student_ids)
    ).order_by("nome")
    total = base_qs.count()
    start = (page - 1) * limit
    end = start + limit
    qs = base_qs[start:end]

    results = []
    for a in qs:
        numero_matricula = getattr(getattr(a, "matricula_institucional", None), "numero_matricula", "") or ""
        label = a.nome if not numero_matricula else f"{a.nome} • {numero_matricula}"
        results.append(
            {
                "id": a.id,
                "label": label,
                "text": label,
                "nome": a.nome,
                "cpf": a.cpf or "",
                "nis": a.nis or "",
                "matricula_institucional": numero_matricula,
            }
        )

    response_payload = {
        "results": results,
        "meta": {
            "page": page,
            "limit": limit,
            "total": int(total),
            "has_more": (page * limit) < int(total),
            "generated_at": timezone.now().isoformat(),
        },
    }
    cache.set(key, response_payload, timeout=90)
    logger.debug(
        "educacao.api_alunos_suggest q=%s page=%s limit=%s total=%s",
        q,
        page,
        limit,
        total,
    )
    return JsonResponse(response_payload)


@login_required
@require_perm("educacao.view")
def api_turmas_suggest(request):
    q = (request.GET.get("q") or "").strip()
    page = _safe_page(request.GET.get("page"))
    limit = _safe_limit(request.GET.get("limit"), default=10, max_limit=50)
    if len(q) < 2:
        return _build_paginated_response([], 0, page, limit)

    key = _cache_key(
        "api_turmas_suggest",
        {"u": request.user.id, "q": q.lower(), "page": page, "limit": limit},
    )
    cached = cache.get(key)
    if cached:
        return JsonResponse(cached)

    base_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "matriz_curricular").only(
            "id",
            "nome",
            "ano_letivo",
            "serie_ano",
            "unidade__nome",
            "matriz_curricular__nome",
        ),
    )

    if q.isdigit():
        base_qs = base_qs.filter(ano_letivo=int(q))
    else:
        base_qs = base_qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(matriz_curricular__nome__icontains=q)
            | Q(serie_ano__icontains=q)
        )

    base_qs = base_qs.order_by("-ano_letivo", "nome")
    total = base_qs.count()
    start = (page - 1) * limit
    end = start + limit
    qs = base_qs[start:end]

    results = []
    for t in qs:
        serie_label = t.get_serie_ano_display() if hasattr(t, "get_serie_ano_display") else ""
        matriz_nome = getattr(getattr(t, "matriz_curricular", None), "nome", "") or ""
        results.append(
            {
                "id": t.id,
                "label": f"{t.nome} ({t.ano_letivo}) • {serie_label}".strip(" •"),
                "text": f"{t.nome} ({t.ano_letivo}) • {serie_label}".strip(" •"),
                "meta": getattr(getattr(t, "unidade", None), "nome", "") or "",
                "matriz": matriz_nome,
            }
        )

    response_payload = {
        "results": results,
        "meta": {
            "page": page,
            "limit": limit,
            "total": int(total),
            "has_more": (page * limit) < int(total),
            "generated_at": timezone.now().isoformat(),
        },
    }
    cache.set(key, response_payload, timeout=90)
    logger.debug(
        "educacao.api_turmas_suggest q=%s page=%s limit=%s total=%s",
        q,
        page,
        limit,
        total,
    )
    return JsonResponse(response_payload)
