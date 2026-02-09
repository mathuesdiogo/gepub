# apps/core/middleware.py
from __future__ import annotations

from django.shortcuts import redirect
from django.urls import resolve
from django.http import HttpResponseForbidden

from .rbac import (
    can,
    PERM_ORG,
    PERM_EDU,
    PERM_NEE,
    PERM_ACCOUNTS,
    PERM_REPORTS,
)


class RBACMiddleware:
    """
    Bloqueio real (backend) por namespace de URL.
    - Se digitar URL na mão, não passa.
    - Continua permitindo login/logout e admin.
    """

    # namespace -> perm macro
    NS_TO_PERM = {
        "org": PERM_ORG,
        "educacao": PERM_EDU,
        "nee": PERM_NEE,
        "accounts": PERM_ACCOUNTS,
        # se você tiver um app "relatorios" separado:
        "relatorios": PERM_REPORTS,
    }

    PUBLIC_URL_NAMES = {
        "accounts:login",
        "accounts:logout",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Admin do Django sempre passa
        path = request.path or ""
        if path.startswith("/admin/"):
            return self.get_response(request)

        # Se não autenticado, deixa passar login (se existir) e bloqueia resto
        if not request.user.is_authenticated:
            # se sua URL de login for outra, ajuste aqui
            if path.startswith("/accounts/login") or path == "/accounts/login/":
                return self.get_response(request)
            return redirect("accounts:login")

        # Resolve rota
        try:
            match = resolve(path)
        except Exception:
            return self.get_response(request)

        # Permite as rotas públicas
        if match.view_name in self.PUBLIC_URL_NAMES:
            return self.get_response(request)

        ns = match.namespace or ""

        # Se não tem namespace, não bloqueia (ex.: dashboard em core)
        if not ns:
            return self.get_response(request)

        required = self.NS_TO_PERM.get(ns)
        if not required:
            return self.get_response(request)

        if not can(request.user, required):
            # 403 simples (depois fazemos uma página bonita)
            return HttpResponseForbidden("Você não tem permissão para acessar esta área.")

        return self.get_response(request)
