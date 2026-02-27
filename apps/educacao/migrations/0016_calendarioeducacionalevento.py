from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0004_alter_unidade_cnpj_alter_unidade_codigo_inep_and_more"),
        ("educacao", "0015_registrorefeicaoescolar_rotatransporteescolar_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CalendarioEducacionalEvento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ano_letivo", models.PositiveIntegerField(db_index=True)),
                ("titulo", models.CharField(max_length=160)),
                ("descricao", models.TextField(blank=True, default="")),
                (
                    "tipo",
                    models.CharField(
                        choices=[
                            ("LETIVO", "Dia letivo"),
                            ("FERIADO", "Feriado"),
                            ("COMEMORATIVA", "Data comemorativa"),
                            ("BIMESTRE_INICIO", "Início de bimestre"),
                            ("BIMESTRE_FIM", "Fim de bimestre"),
                            ("RECESSO", "Recesso/Férias"),
                            ("PEDAGOGICO", "Parada pedagógica"),
                            ("OUTRO", "Outro"),
                        ],
                        db_index=True,
                        default="OUTRO",
                        max_length=20,
                    ),
                ),
                ("data_inicio", models.DateField(db_index=True)),
                ("data_fim", models.DateField(blank=True, db_index=True, null=True)),
                ("dia_letivo", models.BooleanField(default=False)),
                ("cor_hex", models.CharField(blank=True, default="", max_length=7)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "atualizado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="eventos_calendario_educacao_atualizados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "criado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="eventos_calendario_educacao_criados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "secretaria",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="eventos_calendario_educacao",
                        to="org.secretaria",
                    ),
                ),
                (
                    "unidade",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="eventos_calendario_educacao",
                        to="org.unidade",
                    ),
                ),
            ],
            options={
                "verbose_name": "Evento do calendário educacional",
                "verbose_name_plural": "Eventos do calendário educacional",
                "ordering": ["data_inicio", "titulo", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="calendarioeducacionalevento",
            index=models.Index(fields=["ano_letivo", "data_inicio"], name="educacao_ca_ano_let_54ec07_idx"),
        ),
        migrations.AddIndex(
            model_name="calendarioeducacionalevento",
            index=models.Index(fields=["secretaria", "unidade"], name="educacao_ca_secret_69fbe2_idx"),
        ),
        migrations.AddIndex(
            model_name="calendarioeducacionalevento",
            index=models.Index(fields=["tipo", "ativo"], name="educacao_ca_tipo_9eb90c_idx"),
        ),
    ]
