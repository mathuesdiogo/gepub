from __future__ import annotations

from apps.core.rbac import get_profile, is_admin


MANAGED_MODULES: set[str] = {
    "educacao",
    "avaliacoes",
    "nee",
    "saude",
    "financeiro",
    "processos",
    "compras",
    "contratos",
    "integracoes",
    "paineis",
    "conversor",
    "rh",
    "ponto",
    "folha",
    "patrimonio",
    "almoxarifado",
    "frota",
    "ouvidoria",
    "tributos",
}

MODULE_ALIASES: dict[str, set[str]] = {
    # NEE opera junto da trilha educacional em boa parte dos cenários municipais.
    "nee": {"nee", "educacao"},
}


def _resolve_secretaria_id_from_profile(profile) -> int | None:
    secretaria_id = getattr(profile, "secretaria_id", None)
    if secretaria_id:
        return int(secretaria_id)

    unidade_id = getattr(profile, "unidade_id", None)
    if not unidade_id:
        return None

    try:
        from apps.org.models import Unidade

        return Unidade.objects.filter(pk=unidade_id).values_list("secretaria_id", flat=True).first()
    except Exception:
        return None


def _load_scope_modules(user) -> tuple[set[str], bool]:
    """
    Retorna (modulos_ativos, enforce_flag).
    - enforce_flag=False: modo legado (sem configuração de módulos ativa para escopo).
    - enforce_flag=True: deve restringir ao conjunto retornado.
    """
    if hasattr(user, "_gepub_module_scope_cache"):
        return user._gepub_module_scope_cache

    modules: set[str] = set()
    enforce = False

    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        user._gepub_module_scope_cache = (modules, True)
        return user._gepub_module_scope_cache

    try:
        from apps.org.models import MunicipioModuloAtivo, SecretariaModuloAtivo
    except Exception:
        user._gepub_module_scope_cache = (modules, False)
        return user._gepub_module_scope_cache

    role = (getattr(p, "role", "") or "").upper()
    secretaria_id = _resolve_secretaria_id_from_profile(p) if role in {"SECRETARIA", "UNIDADE"} else None
    municipio_id = getattr(p, "municipio_id", None)

    # Perfis setoriais sem escopo vinculado devem ficar bloqueados
    # para evitar "vazamento" de módulos do catálogo municipal.
    if role in {"SECRETARIA", "UNIDADE"} and not secretaria_id:
        user._gepub_module_scope_cache = (set(), True)
        return user._gepub_module_scope_cache

    if secretaria_id:
        qs = SecretariaModuloAtivo.objects.filter(secretaria_id=secretaria_id, ativo=True)
        modules = {str(item).strip().lower() for item in qs.values_list("modulo", flat=True)}
        enforce = SecretariaModuloAtivo.objects.filter(secretaria_id=secretaria_id).exists()

        # Fallback: se secretaria ainda não tiver catálogo próprio, usa catálogo do município.
        if (not enforce) and municipio_id:
            muni_qs = MunicipioModuloAtivo.objects.filter(municipio_id=municipio_id, ativo=True)
            modules = {str(item).strip().lower() for item in muni_qs.values_list("modulo", flat=True)}
            enforce = MunicipioModuloAtivo.objects.filter(municipio_id=municipio_id).exists()
    elif municipio_id:
        qs = MunicipioModuloAtivo.objects.filter(municipio_id=municipio_id, ativo=True)
        modules = {str(item).strip().lower() for item in qs.values_list("modulo", flat=True)}
        enforce = MunicipioModuloAtivo.objects.filter(municipio_id=municipio_id).exists()

    user._gepub_module_scope_cache = (modules, enforce)
    return user._gepub_module_scope_cache


def module_enabled_for_user(user, module_key: str) -> bool:
    module = (module_key or "").strip().lower()
    if not module or module not in MANAGED_MODULES:
        return True

    if not user or not getattr(user, "is_authenticated", False):
        return False

    if is_admin(user):
        return True

    p = get_profile(user)
    if not p or not getattr(p, "ativo", True):
        return False

    modules, enforce = _load_scope_modules(user)
    if not enforce:
        # Compatibilidade para bases antigas sem onboarding/catalogo ativado.
        return True

    accepted_keys = MODULE_ALIASES.get(module, {module})
    return any(key in modules for key in accepted_keys)
