from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .design_system import GEPUB_DS_VERSION, resolve_admin_theme_context

THEME_TOKEN_PRESETS = {
    "kassya": {
        "--gp-primary": "#2670e8",
        "--gp-primary-hover": "#1a56b8",
        "--gp-secondary": "#05152e",
        "--gp-background": "#eaf1ff",
        "--gp-surface": "#ffffff",
    },
    "inclusao": {
        "--gp-primary": "#111111",
        "--gp-primary-hover": "#000000",
        "--gp-secondary": "#111111",
        "--gp-background": "#ffffff",
        "--gp-surface": "#ffffff",
    },
    "institucional": {
        "--gp-primary": "#a1431f",
        "--gp-primary-hover": "#7f3218",
        "--gp-secondary": "#2f2a27",
        "--gp-background": "#faf5ef",
        "--gp-surface": "#ffffff",
    },
}


@login_required
def design_system_docs(request):
    theme_ctx = resolve_admin_theme_context(request)
    return render(
        request,
        "core/design_system/index.html",
        {
            "docs_page": "index",
            "theme_options": ["kassya", "inclusao", "institucional"],
            "theme_tokens_preview": THEME_TOKEN_PRESETS,
            "ds_version": GEPUB_DS_VERSION,
            "theme_ctx": theme_ctx,
        },
    )


@login_required
def design_system_components(request):
    return render(
        request,
        "core/design_system/components.html",
        {
            "docs_page": "components",
            "theme_options": ["kassya", "inclusao", "institucional"],
            "ds_version": GEPUB_DS_VERSION,
        },
    )


@login_required
def design_system_themes(request):
    return render(
        request,
        "core/design_system/themes.html",
        {
            "docs_page": "themes",
            "theme_options": ["kassya", "inclusao", "institucional"],
            "theme_tokens_preview": THEME_TOKEN_PRESETS,
            "ds_version": GEPUB_DS_VERSION,
        },
    )


@login_required
def design_system_tokens_api(request):
    theme_ctx = resolve_admin_theme_context(request)
    base = dict(THEME_TOKEN_PRESETS.get(theme_ctx.theme, {}))
    merged = {**base, **theme_ctx.token_overrides}
    return JsonResponse(
        {
            "version": theme_ctx.version,
            "theme": theme_ctx.theme,
            "tokens": merged,
            "tenant_overrides": theme_ctx.token_overrides,
            "themes": THEME_TOKEN_PRESETS,
        }
    )
