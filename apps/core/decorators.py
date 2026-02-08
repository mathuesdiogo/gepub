from __future__ import annotations
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from core.permissions import can

def require_perm(module: str, action: str = "view"):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not can(request.user, module, action):
                messages.error(request, "Você não tem permissão para acessar esta área.")
                return redirect("core:dashboard")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
