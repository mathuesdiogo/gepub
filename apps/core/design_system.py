from __future__ import annotations

from dataclasses import dataclass


GEPUB_DS_VERSION = "GEPUB DS v2.0"
THEME_DEFAULT = "kassya"
THEME_CHOICES = {"kassya", "inclusao", "institucional"}
THEME_OPTIONS = (
    ("kassya", "Kassya"),
    ("inclusao", "Inclusão"),
    ("institucional", "Institucional"),
)

TOKEN_ALLOWLIST = {
    "--gp-primary",
    "--gp-primary-hover",
    "--gp-secondary",
    "--gp-background",
    "--gp-surface",
    "--gp-border",
    "--gp-text-primary",
    "--gp-text-secondary",
    "--gp-success",
    "--gp-warning",
    "--gp-danger",
    "--gp-info",
    "--gp-radius",
    "--gp-spacing-unit",
    "--gp-shadow-1",
    "--gp-shadow-2",
    "--gp-shadow-3",
}


@dataclass
class DesignSystemThemeContext:
    theme: str
    token_overrides: dict[str, str]
    lock_theme_for_users: bool
    allow_user_theme_override: bool
    version: str


def _normalize_theme(value: str | None) -> str:
    theme = str(value or "").strip().lower()
    return theme if theme in THEME_CHOICES else THEME_DEFAULT


def _extract_theme(value: str | None) -> str | None:
    theme = str(value or "").strip().lower()
    return theme if theme in THEME_CHOICES else None


def _sanitize_token_overrides(raw: dict | None) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        key = str(k or "").strip()
        if key not in TOKEN_ALLOWLIST:
            continue
        value = str(v or "").strip()
        if not value:
            continue
        out[key] = value
    return out


def resolve_admin_theme_context(request) -> DesignSystemThemeContext:
    user = getattr(request, "user", None)
    profile = getattr(user, "profile", None) if user and getattr(user, "is_authenticated", False) else None
    municipio = getattr(profile, "municipio", None) if profile else None

    default_theme = THEME_DEFAULT
    lock_theme_for_users = False
    allow_user_theme_override = True
    token_overrides: dict[str, str] = {}

    if municipio is not None:
        try:
            from apps.org.models import MunicipioThemeConfig

            config = MunicipioThemeConfig.objects.filter(municipio=municipio).first()
        except Exception:
            config = None

        if config:
            default_theme = _normalize_theme(config.default_theme)
            lock_theme_for_users = bool(config.lock_theme_for_users)
            allow_user_theme_override = bool(config.allow_user_theme_override)
            token_overrides = _sanitize_token_overrides(config.token_overrides)

    theme = default_theme
    if profile:
        theme = _normalize_theme(getattr(profile, "ui_theme", "") or default_theme)

    # Override explícito por URL (qualquer usuário autenticado) + persistência em sessão.
    requested_theme = _extract_theme(request.GET.get("theme"))
    if requested_theme and user and getattr(user, "is_authenticated", False):
        request.session["gepub_theme_override"] = requested_theme
        theme = requested_theme
        if profile and getattr(profile, "ui_theme", "") != requested_theme:
            try:
                profile.ui_theme = requested_theme
                profile.save(update_fields=["ui_theme"])
            except Exception:
                pass
    elif user and getattr(user, "is_authenticated", False):
        session_theme = _extract_theme(request.session.get("gepub_theme_override"))
        if session_theme:
            theme = session_theme

    return DesignSystemThemeContext(
        theme=theme,
        token_overrides=token_overrides,
        lock_theme_for_users=lock_theme_for_users,
        allow_user_theme_override=allow_user_theme_override,
        version=GEPUB_DS_VERSION,
    )


def token_overrides_to_style(token_overrides: dict[str, str]) -> str:
    if not token_overrides:
        return ""
    lines = [":root {"]
    for key, value in token_overrides.items():
        lines.append(f"  {key}: {value};")
    lines.append("}")
    return "\n".join(lines)
