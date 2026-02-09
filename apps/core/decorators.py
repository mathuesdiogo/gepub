# apps/core/decorators.py
from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from core.rbac import can


def require_perm(perm: str):
    """
    Decorator RBAC:
    - se não logado: redirect para login
    - se logado e sem perm: 403
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = getattr(request, "user", None)

            if not user or not user.is_authenticated:
                # usa o LOGIN_URL do Django, com fallback
                login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
                return redirect(f"{login_url}?next={request.get_full_path()}")

            if not can(user, perm):
                return HttpResponseForbidden("403 — Você não tem permissão para acessar esta página.")

            return view_func(request, *args, **kwargs)

        return _wrapped
    return decorator
