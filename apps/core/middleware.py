# apps/core/middleware.py
from __future__ import annotations

from django.conf import settings
from django.shortcuts import redirect
from django.urls import resolve
from django.http import HttpResponseForbidden

from apps.core.module_access import module_enabled_for_user
from apps.org.models import Municipio
from .rbac import (
    can,
    PERM_ORG,
    PERM_EDU,
    PERM_AVALIACOES,
    PERM_NEE,
    PERM_SAUDE,
    PERM_BILLING,
    PERM_FINANCEIRO,
    PERM_ACCOUNTS,
    PERM_REPORTS,
    PERM_PROCESSOS,
    PERM_COMPRAS,
    PERM_CONTRATOS,
    PERM_INTEGRACOES,
    PERM_PAINEIS,
    PERM_CONVERSOR,
    PERM_RH,
    PERM_PONTO,
    PERM_FOLHA,
    PERM_PATRIMONIO,
    PERM_ALMOXARIFADO,
    PERM_FROTA,
    PERM_OUVIDORIA,
    PERM_TRIBUTOS,
)


def _normalize_host(raw_host: str) -> str:
    host = (raw_host or "").strip().lower()
    if "," in host:
        host = host.split(",", 1)[0].strip()
    if ":" in host:
        host = host.split(":", 1)[0].strip()
    return host


def _resolve_app_host() -> str:
    explicit = (getattr(settings, "GEPUB_APP_CANONICAL_HOST", "") or "").strip().lower()
    if explicit:
        return explicit
    app_hosts = list(getattr(settings, "GEPUB_APP_HOSTS", []) or [])
    return (app_hosts[0] if app_hosts else "").strip().lower()


def _build_app_url(request, path: str) -> str:
    app_host = _resolve_app_host()
    if not app_host:
        return path
    scheme = "https" if (request.is_secure() or not settings.DEBUG) else "http"
    return f"{scheme}://{app_host}{path}"


class TenantHostMiddleware:
    """
    Resolve município por host público no formato:
      <slug>.gepub.com.br
    """

    PUBLIC_PATHS = {
        "/",
        "/institucional",
        "/institucional/",
        "/paginas",
        "/paginas/",
        "/noticias",
        "/noticias/",
        "/esic-ouvidoria",
        "/esic-ouvidoria/",
        "/licitacoes",
        "/licitacoes/",
        "/contratos-publicos",
        "/contratos-publicos/",
        "/diario-oficial",
        "/diario-oficial/",
        "/concursos",
        "/concursos/",
        "/camara",
        "/camara/",
        "/saude-publica",
        "/saude-publica/",
        "/educacao-publica",
        "/educacao-publica/",
        "/documentacao",
        "/documentacao/",
        "/transparencia",
        "/transparencia/",
        "/sobre",
        "/sobre/",
        "/funcionalidades",
        "/funcionalidades/",
        "/por-que-usar",
        "/por-que-usar/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.current_municipio = None
        request.current_municipio_slug = ""
        request.is_public_tenant = False
        request.tenant_lookup_failed = False
        request.gepub_host_kind = "default"
        request.public_login_url = _build_app_url(request, "/accounts/login/")

        path = request.path or ""
        static_url = getattr(settings, "STATIC_URL", "/static/")
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        if path.startswith(static_url) or path.startswith(media_url):
            return self.get_response(request)

        host = _normalize_host(
            request.META.get("HTTP_X_FORWARDED_HOST")
            or request.META.get("HTTP_HOST")
            or ""
        )
        if not host:
            return self.get_response(request)

        app_hosts = {
            _normalize_host(h)
            for h in (getattr(settings, "GEPUB_APP_HOSTS", []) or [])
            if _normalize_host(h)
        }
        if host in app_hosts:
            request.gepub_host_kind = "app"
            return self.get_response(request)

        root_domain = (getattr(settings, "GEPUB_PUBLIC_ROOT_DOMAIN", "") or "").strip().lower().strip(".")
        if not root_domain:
            return self.get_response(request)

        if host == root_domain or host == f"www.{root_domain}":
            request.gepub_host_kind = "public_root"
            return self.get_response(request)

        suffix = f".{root_domain}"
        if host.endswith(suffix):
            slug = host[: -len(suffix)].strip().lower().strip(".")
            request.current_municipio_slug = slug

            reserved = {
                s.strip().lower()
                for s in (getattr(settings, "GEPUB_RESERVED_SUBDOMAINS", []) or [])
                if s and s.strip()
            }
            if slug and "." not in slug and slug not in reserved:
                municipio = (
                    Municipio.objects.filter(ativo=True, slug_site__iexact=slug)
                    .only("id", "nome", "uf", "slug_site", "dominio_personalizado")
                    .first()
                )
                if municipio:
                    request.current_municipio = municipio
                    request.is_public_tenant = True
                    request.gepub_host_kind = "tenant_public"
                else:
                    request.tenant_lookup_failed = True
                    request.gepub_host_kind = "tenant_not_found"

        # Área administrativa sempre no host central do app.
        if (request.is_public_tenant or request.tenant_lookup_failed) and path.startswith("/accounts/"):
            return redirect(request.public_login_url)

        return self.get_response(request)


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
        "avaliacoes": PERM_AVALIACOES,
        "nee": PERM_NEE,
        "saude": PERM_SAUDE,
        "billing": PERM_BILLING,
        "financeiro": PERM_FINANCEIRO,
        "processos": PERM_PROCESSOS,
        "compras": PERM_COMPRAS,
        "contratos": PERM_CONTRATOS,
        "integracoes": PERM_INTEGRACOES,
        "paineis": PERM_PAINEIS,
        "conversor": PERM_CONVERSOR,
        "rh": PERM_RH,
        "ponto": PERM_PONTO,
        "folha": PERM_FOLHA,
        "patrimonio": PERM_PATRIMONIO,
        "almoxarifado": PERM_ALMOXARIFADO,
        "frota": PERM_FROTA,
        "ouvidoria": PERM_OUVIDORIA,
        "tributos": PERM_TRIBUTOS,
        "accounts": PERM_ACCOUNTS,
        # se você tiver um app "relatorios" separado:
        "relatorios": PERM_REPORTS,
    }
    NS_TO_MODULE = {
        "educacao": "educacao",
        "avaliacoes": "avaliacoes",
        "nee": "nee",
        "saude": "saude",
        "financeiro": "financeiro",
        "processos": "processos",
        "compras": "compras",
        "contratos": "contratos",
        "integracoes": "integracoes",
        "paineis": "paineis",
        "conversor": "conversor",
        "rh": "rh",
        "ponto": "ponto",
        "folha": "folha",
        "patrimonio": "patrimonio",
        "almoxarifado": "almoxarifado",
        "frota": "frota",
        "ouvidoria": "ouvidoria",
        "tributos": "tributos",
    }

    PUBLIC_URL_NAMES = {
        "accounts:login",
        "accounts:logout",
        "accounts:alterar_senha",
        "accounts:meu_perfil",
        "avaliacoes:folha_validar",
    }
    PUBLIC_PATH_PREFIXES = (
        "/accounts/login",
        "/institucional/",
        "/paginas/",
        "/noticias/",
        "/esic-ouvidoria/",
        "/licitacoes/",
        "/contratos-publicos/",
        "/diario-oficial/",
        "/concursos/",
        "/camara/",
        "/saude-publica/",
        "/educacao-publica/",
        "/documentacao/",
        "/transparencia/",
        "/sobre/",
        "/funcionalidades/",
        "/por-que-usar/",
        "/avaliacoes/validar/prova/",
    )
    PUBLIC_EXACT_PATHS = {
        "/",
        "/institucional",
        "/paginas",
        "/noticias",
        "/esic-ouvidoria",
        "/licitacoes",
        "/contratos-publicos",
        "/diario-oficial",
        "/concursos",
        "/camara",
        "/saude-publica",
        "/educacao-publica",
        "/documentacao",
        "/transparencia",
        "/sobre",
        "/funcionalidades",
        "/por-que-usar",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Admin do Django sempre passa
        path = request.path or ""
        static_url = getattr(settings, "STATIC_URL", "/static/")
        media_url = getattr(settings, "MEDIA_URL", "/media/")

        # Nunca aplicar RBAC em arquivos estáticos/mídia
        if path.startswith(static_url) or path.startswith(media_url):
            return self.get_response(request)

        if path.startswith("/admin/"):
            return self.get_response(request)

        # Se não autenticado, deixa passar login (se existir) e bloqueia resto
        if not request.user.is_authenticated:
            if path in self.PUBLIC_EXACT_PATHS or any(path.startswith(prefix) for prefix in self.PUBLIC_PATH_PREFIXES):
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

        module_key = self.NS_TO_MODULE.get(ns)
        if module_key and not module_enabled_for_user(request.user, module_key):
            return HttpResponseForbidden("Este módulo não está ativo para o seu escopo.")

        return self.get_response(request)
