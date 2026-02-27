import os
from pathlib import Path
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
    default=["127.0.0.1", "localhost", ".gepub.com.br"],
)

GEPUB_PUBLIC_ROOT_DOMAIN = (os.getenv("GEPUB_PUBLIC_ROOT_DOMAIN", "gepub.com.br") or "").strip().lower().strip(".")
GEPUB_APP_HOSTS = _env_list(
    "GEPUB_APP_HOSTS",
    default=["app.gepub.com.br", "127.0.0.1", "localhost"],
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
]






MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# Autenticação (GEPUB)
# =========================
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

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

# =========================
# Segurança HTTP / Sessão / CSRF
# =========================
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = _env_bool("DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True)
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin").strip()
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY").strip().upper() or "DENY"

# Limites de upload para módulos utilitários.
PAINEIS_MAX_UPLOAD_MB = _env_int("PAINEIS_MAX_UPLOAD_MB", default=50)
CONVERSOR_MAX_UPLOAD_MB = _env_int("CONVERSOR_MAX_UPLOAD_MB", default=80)

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
