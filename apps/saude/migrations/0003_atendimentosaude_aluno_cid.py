from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("educacao", "0011_avaliacaonota_componentecurricular_notacurricular_and_more"),
        ("saude", "0002_alter_profissionalsaude_unidade_atendimentosaude"),
    ]

    operations = [
        migrations.AddField(
            model_name="atendimentosaude",
            name="aluno",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="atendimentos_saude", to="educacao.aluno"),
        ),
        migrations.AddField(
            model_name="atendimentosaude",
            name="cid",
            field=models.CharField(blank=True, default="", max_length=20, verbose_name="CID (opcional)"),
        ),
    ]
