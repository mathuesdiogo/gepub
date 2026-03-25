from .views_users_list import usuarios_list, users_autocomplete
from .views_users_crud import (
    usuario_create,
    usuario_prefeitura_onboarding_create,
    usuario_update,
    usuario_detail,
    usuario_toggle_ativo,
    usuario_toggle_bloqueio,
    usuario_reset_codigo,
    usuario_reset_senha,
)
from .views_access import (
    acessos_matriz,
    acessos_simular,
    acessos_simular_encerrar,
)

__all__ = [
    "usuarios_list",
    "users_autocomplete",
    "usuario_create",
    "usuario_prefeitura_onboarding_create",
    "usuario_update",
    "usuario_detail",
    "usuario_toggle_ativo",
    "usuario_toggle_bloqueio",
    "usuario_reset_codigo",
    "usuario_reset_senha",
    "acessos_matriz",
    "acessos_simular",
    "acessos_simular_encerrar",
]
