from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_operacaoregistroanexo_operacaoregistrocomentario_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentoemitido',
            name='assinatura_emitente',
            field=models.CharField(blank=True, default='', max_length=180),
        ),
        migrations.AddField(
            model_name='documentoemitido',
            name='assinatura_cargo',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]
