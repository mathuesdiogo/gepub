from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("saude", "0003_atendimentosaude_aluno_cid"),
        ("nee", "0006_planocliniconee_objetivoplanonee_evolucaoplanonee_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="laudonee",
            name="profissional_saude",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="laudos_nee", to="saude.profissionalsaude"),
        ),
        migrations.AddField(
            model_name="planocliniconee",
            name="profissional_saude",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="planos_clinicos_nee", to="saude.profissionalsaude"),
        ),
        migrations.AddField(
            model_name="evolucaoplanonee",
            name="profissional_saude",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="evolucoes_plano_nee", to="saude.profissionalsaude"),
        ),
    ]
