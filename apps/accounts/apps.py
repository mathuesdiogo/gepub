from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"     # ✅ caminho real do app
    label = "accounts"         # ✅ mantém label antigo (migrações/admin)
    
    def ready(self):
        from . import signals  # noqa
