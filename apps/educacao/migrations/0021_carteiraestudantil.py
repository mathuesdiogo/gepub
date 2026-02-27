from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("educacao", "0020_aula_componente_aula_periodo_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CarteiraEstudantil",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo_verificacao", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("codigo_estudante", models.CharField(blank=True, db_index=True, default="", max_length=40)),
                ("dados_snapshot", models.JSONField(blank=True, default=dict)),
                ("emitida_em", models.DateTimeField(auto_now_add=True)),
                ("validade", models.DateField(blank=True, null=True)),
                ("ativa", models.BooleanField(default=True)),
                (
                    "aluno",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="carteiras_estudantis", to="educacao.aluno"),
                ),
                (
                    "emitida_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="carteiras_estudantis_emitidas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "matricula",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="carteiras_estudantis",
                        to="educacao.matricula",
                    ),
                ),
            ],
            options={
                "verbose_name": "Carteira estudantil",
                "verbose_name_plural": "Carteiras estudantis",
                "ordering": ["-emitida_em", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="carteiraestudantil",
            index=models.Index(fields=["aluno", "ativa"], name="educacao_ca_aluno_i_1d685e_idx"),
        ),
        migrations.AddIndex(
            model_name="carteiraestudantil",
            index=models.Index(fields=["codigo_estudante"], name="educacao_ca_codigo__5b37ad_idx"),
        ),
        migrations.AddIndex(
            model_name="carteiraestudantil",
            index=models.Index(fields=["validade"], name="educacao_ca_validad_9a4570_idx"),
        ),
    ]
