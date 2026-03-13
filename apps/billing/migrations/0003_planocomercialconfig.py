from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_seed_catalogo_inicial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanoComercialConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome_comercial", models.CharField(blank=True, default="", max_length=120)),
                ("categoria", models.CharField(blank=True, default="", max_length=60)),
                ("descricao_comercial", models.TextField(blank=True, default="")),
                ("beneficios", models.JSONField(blank=True, default=list)),
                ("especiais", models.JSONField(blank=True, default=list)),
                ("limitacoes", models.JSONField(blank=True, default=list)),
                ("dependencias", models.JSONField(blank=True, default=list)),
                ("link_documento_contratacao", models.CharField(blank=True, default="", max_length=240)),
                ("link_documento_servicos", models.CharField(blank=True, default="", max_length=240)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "plano",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comercial_config",
                        to="billing.planomunicipal",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuração comercial do plano",
                "verbose_name_plural": "Configurações comerciais dos planos",
                "ordering": ["plano__preco_base_mensal", "plano__nome"],
            },
        ),
    ]
