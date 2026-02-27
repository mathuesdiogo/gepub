from .settings import *  # noqa

# A pilha de migrações do NEE tem histórico legado divergente.
# Em testes usamos sync direto do model para evitar conflito de migração.
MIGRATION_MODULES = {
    "nee": None,
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}
