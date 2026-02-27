# Consolidada em 0002_acompanhamentonee_laudonee_recursonee_and_more.
# Mantida como no-op para preservar histórico em bancos existentes e
# evitar duplicidade de criação em bancos novos/testes.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("nee", "0001_initial"),
    ]

    operations = []
