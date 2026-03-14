import os
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val.strip())
    except Exception:
        return default


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    val = os.getenv(name)
    if val is None:
        return list(default or [])
    return [item.strip() for item in val.split(",") if item.strip()]


def _safe_samesite(value: str, default: str = "Lax") -> str:
    raw = (value or "").strip().lower()
    mapping = {
        "lax": "Lax",
        "strict": "Strict",
        "none": "None",
    }
    return mapping.get(raw, default)


def _cache_config(debug: bool) -> dict:
    backend = os.getenv("DJANGO_CACHE_BACKEND", "").strip().lower()

    if not backend:
        backend = "locmem" if debug else "redis"

    if backend == "redis":
        redis_url = os.getenv("DJANGO_REDIS_URL", "redis://127.0.0.1:6379/1")
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.redis.RedisCache",
                "LOCATION": redis_url,
            }
        }

    if backend == "memcached":
        memcached_location = os.getenv("DJANGO_MEMCACHED_LOCATION", "127.0.0.1:11211")
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
                "LOCATION": memcached_location,
            }
        }

    if backend == "locmem":
        if not debug and not _env_bool("DJANGO_ALLOW_LOCMEM_IN_PRODUCTION", default=False):
            raise ImproperlyConfigured(
                "DJANGO_CACHE_BACKEND=locmem em produção não é permitido. "
                "Use redis ou memcached (ou, se for exceção controlada, defina "
                "DJANGO_ALLOW_LOCMEM_IN_PRODUCTION=true)."
            )
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "gepub-cache",
            }
        }

    raise ImproperlyConfigured(
        "DJANGO_CACHE_BACKEND inválido. Valores aceitos: redis, memcached, locmem."
    )


BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Quick-start development settings
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Defina a variável de ambiente DJANGO_SECRET_KEY antes de iniciar o projeto."
    )
CPF_HASH_KEY = os.getenv("DJANGO_CPF_HASH_KEY", "")
CPF_ENCRYPTION_KEY = os.getenv("DJANGO_CPF_ENCRYPTION_KEY", "")
DEBUG = _env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["127.0.0.1", "localhost", "testserver", ".gepub.com.br"],
)

GEPUB_PUBLIC_ROOT_DOMAIN = (os.getenv("GEPUB_PUBLIC_ROOT_DOMAIN", "gepub.com.br") or "").strip().lower().strip(".")
GEPUB_APP_HOSTS = _env_list(
    "GEPUB_APP_HOSTS",
    default=["127.0.0.1", "localhost"],
)
GEPUB_APP_CANONICAL_HOST = (os.getenv("GEPUB_APP_CANONICAL_HOST", "") or "").strip().lower()
GEPUB_RESERVED_SUBDOMAINS = _env_list(
    "GEPUB_RESERVED_SUBDOMAINS",
    default=["app", "www", "admin", "api", "static", "media"],
)

if not DEBUG and "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Em produção, DJANGO_ALLOWED_HOSTS não pode conter '*'.")

if not DEBUG and not (CPF_HASH_KEY and CPF_ENCRYPTION_KEY):
    raise ImproperlyConfigured(
        "Defina DJANGO_CPF_HASH_KEY e DJANGO_CPF_ENCRYPTION_KEY em produção."
    )


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceiros (API / permissões / realtime)
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "guardian",
    "channels",

    # Apps do GEPUB
    "apps.core",
    "apps.accounts",
    "apps.org",
    "apps.educacao",
    "apps.avaliacoes",
    "apps.nee",
    "apps.saude",
    "apps.billing",
    "apps.financeiro",
    "apps.processos",
    "apps.compras",
    "apps.contratos",
    "apps.integracoes",
    "apps.comunicacao",
    "apps.paineis",
    "apps.conversor",
    "apps.rh",
    "apps.ponto",
    "apps.folha",
    "apps.patrimonio",
    "apps.almoxarifado",
    "apps.frota",
    "apps.ouvidoria",
    "apps.tributos",
    "apps.camara",
]






MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.middleware.TenantHostMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    "apps.core.middleware.RBACMiddleware",



    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.permissions",

            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.getenv("DJANGO_DB_ENGINE", "").strip().lower()
if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DJANGO_DB_NAME", ""),
            "USER": os.getenv("DJANGO_DB_USER", ""),
            "PASSWORD": os.getenv("DJANGO_DB_PASSWORD", ""),
            "HOST": os.getenv("DJANGO_DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DJANGO_DB_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("DJANGO_DB_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ✅ pt-br + Fortaleza
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Fortaleza"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# Autenticação (GEPUB)
# =========================
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
)

# =========================
# Cache (para limitar tentativas)
# =========================
CACHES = _cache_config(DEBUG)

# =========================
# Celery (processamento assíncrono)
# =========================
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("DJANGO_REDIS_URL", "redis://127.0.0.1:6379/1"),
)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = _env_bool("CELERY_TASK_ALWAYS_EAGER", default=DEBUG)
CELERY_TASK_EAGER_PROPAGATES = _env_bool("CELERY_TASK_EAGER_PROPAGATES", default=True)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = _env_bool(
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP",
    default=True,
)
CELERY_TASK_ROUTES = {
    "comunicacao.process_job": {"queue": "comunicacao"},
    "comunicacao.process_pending": {"queue": "comunicacao"},
}
CELERY_BEAT_SCHEDULE = {
    "comunicacao-process-pending": {
        "task": "comunicacao.process_pending",
        "schedule": _env_int("COMUNICACAO_PROCESS_INTERVAL_SECONDS", default=60),
        "args": (_env_int("COMUNICACAO_PROCESS_BATCH_SIZE", default=200),),
    }
}

# =========================
# API (DRF + JWT)
# =========================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": _env_int("DRF_PAGE_SIZE", default=25),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=_env_int("JWT_ACCESS_TOKEN_MINUTES", default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=_env_int("JWT_REFRESH_TOKEN_DAYS", default=7)
    ),
    "ROTATE_REFRESH_TOKENS": _env_bool("JWT_ROTATE_REFRESH_TOKENS", default=True),
    "BLACKLIST_AFTER_ROTATION": _env_bool(
        "JWT_BLACKLIST_AFTER_ROTATION", default=False
    ),
    "UPDATE_LAST_LOGIN": _env_bool("JWT_UPDATE_LAST_LOGIN", default=False),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.getenv("JWT_SIGNING_KEY", SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# =========================
# Realtime (Django Channels)
# =========================
CHANNEL_LAYER_IN_MEMORY = _env_bool("CHANNEL_LAYER_IN_MEMORY", default=DEBUG)
if CHANNEL_LAYER_IN_MEMORY:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
else:
    CHANNEL_REDIS_URL = os.getenv(
        "CHANNEL_REDIS_URL",
        os.getenv("DJANGO_REDIS_URL", "redis://127.0.0.1:6379/2"),
    )
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [CHANNEL_REDIS_URL]},
        }
    }

# =========================
# Busca (Meilisearch)
# =========================
MEILISEARCH_URL = os.getenv("MEILISEARCH_URL", "http://127.0.0.1:7700").strip()
MEILISEARCH_MASTER_KEY = os.getenv("MEILISEARCH_MASTER_KEY", "").strip()
MEILISEARCH_INDEX_PREFIX = os.getenv("MEILISEARCH_INDEX_PREFIX", "gepub").strip()

# =========================
# Segurança HTTP / Sessão / CSRF
# =========================
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = _env_bool("DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True)
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin").strip()
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY").strip().upper() or "DENY"
SECURE_CROSS_ORIGIN_OPENER_POLICY = os.getenv(
    "DJANGO_SECURE_CROSS_ORIGIN_OPENER_POLICY",
    "same-origin",
).strip()
SECURE_CROSS_ORIGIN_RESOURCE_POLICY = os.getenv(
    "DJANGO_SECURE_CROSS_ORIGIN_RESOURCE_POLICY",
    "same-origin",
).strip()

# Limites de upload para módulos utilitários.
PAINEIS_MAX_UPLOAD_MB = _env_int("PAINEIS_MAX_UPLOAD_MB", default=50)
CONVERSOR_MAX_UPLOAD_MB = _env_int("CONVERSOR_MAX_UPLOAD_MB", default=80)
COMUNICACAO_API_MAX_JSON_BODY_BYTES = _env_int(
    "COMUNICACAO_API_MAX_JSON_BODY_BYTES",
    default=256 * 1024,
)
COMUNICACAO_RETRY_BASE_MINUTES = _env_int("COMUNICACAO_RETRY_BASE_MINUTES", default=2)
COMUNICACAO_RETRY_MAX_MINUTES = _env_int("COMUNICACAO_RETRY_MAX_MINUTES", default=60)
COMUNICACAO_WEBHOOK_SHARED_SECRET = (os.getenv("COMUNICACAO_WEBHOOK_SHARED_SECRET", "") or "").strip()

EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
).strip()
DEFAULT_FROM_EMAIL = (os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "no-reply@gepub.local") or "no-reply@gepub.local").strip()

SECURE_HSTS_SECONDS = _env_int("DJANGO_SECURE_HSTS_SECONDS", default=(31536000 if not DEBUG else 0))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=not DEBUG,
)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=not DEBUG)

SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", default=not DEBUG)
SESSION_COOKIE_HTTPONLY = _env_bool("DJANGO_SESSION_COOKIE_HTTPONLY", default=True)
CSRF_COOKIE_HTTPONLY = _env_bool("DJANGO_CSRF_COOKIE_HTTPONLY", default=False)
SESSION_COOKIE_SAMESITE = _safe_samesite(os.getenv("DJANGO_SESSION_COOKIE_SAMESITE", "Lax"), "Lax")
CSRF_COOKIE_SAMESITE = _safe_samesite(os.getenv("DJANGO_CSRF_COOKIE_SAMESITE", "Lax"), "Lax")
SESSION_COOKIE_AGE = _env_int("DJANGO_SESSION_COOKIE_AGE", 60 * 60 * 8)
SESSION_SAVE_EVERY_REQUEST = _env_bool("DJANGO_SESSION_SAVE_EVERY_REQUEST", default=False)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = _env_bool("DJANGO_USE_X_FORWARDED_HOST", default=not DEBUG)

_csrf_trusted_origins = set(_env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[]))
_dynamic_hosts: set[str] = set(h.lstrip(".") for h in GEPUB_APP_HOSTS if h)
if GEPUB_PUBLIC_ROOT_DOMAIN:
    _dynamic_hosts.add(GEPUB_PUBLIC_ROOT_DOMAIN)
    _dynamic_hosts.add(f"*.{GEPUB_PUBLIC_ROOT_DOMAIN}")
for _host in _dynamic_hosts:
    _host = (_host or "").strip()
    if not _host:
        continue
    _csrf_trusted_origins.add(f"https://{_host}")
    if DEBUG:
        _csrf_trusted_origins.add(f"http://{_host}")
CSRF_TRUSTED_ORIGINS = sorted(_csrf_trusted_origins)

# =========================
# Segurança de upload
# =========================
DATA_UPLOAD_MAX_MEMORY_SIZE = _env_int("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = _env_int("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024)
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750
GEPUB_PROFILE_MAX_UPLOAD_BYTES = _env_int("GEPUB_PROFILE_MAX_UPLOAD_BYTES", 2 * 1024 * 1024)

# Saúde / Governança clínica
SAUDE_EDIT_WINDOW_HOURS = _env_int("DJANGO_SAUDE_EDIT_WINDOW_HOURS", default=24)
