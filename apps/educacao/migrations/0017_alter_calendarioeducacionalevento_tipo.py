from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("educacao", "0016_calendarioeducacionalevento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="calendarioeducacionalevento",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("LETIVO", "Dia letivo"),
                    ("FACULTATIVO", "Ponto facultativo"),
                    ("FERIADO", "Feriado"),
                    ("COMEMORATIVA", "Data comemorativa"),
                    ("BIMESTRE_INICIO", "Início de bimestre"),
                    ("BIMESTRE_FIM", "Fim de bimestre"),
                    ("PLANEJAMENTO", "Planejamento pedagógico"),
                    ("RECESSO", "Recesso/Férias"),
                    ("PEDAGOGICO", "Parada pedagógica"),
                    ("OUTRO", "Outro"),
                ],
                db_index=True,
                default="OUTRO",
                max_length=20,
            ),
        ),
    ]
