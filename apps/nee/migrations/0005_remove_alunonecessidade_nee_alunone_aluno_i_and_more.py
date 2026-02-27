# Ajustada para compatibilidade entre bases antigas e bases novas de teste.
# O arquivo original tentava remover/renomear índices que não existem no estado
# da árvore de migrations atual, quebrando `migrate` em banco limpo.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nee', '0004_alter_acompanhamentonee_options_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX IF NOT EXISTS nee_alunone_ativo_9df419_idx "
                        "ON nee_alunonecessidade (ativo);"
                    ),
                    reverse_sql="DROP INDEX IF EXISTS nee_alunone_ativo_9df419_idx;",
                ),
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX IF NOT EXISTS nee_apoioma_tipo_b51452_idx "
                        "ON nee_apoiomatricula (tipo);"
                    ),
                    reverse_sql="DROP INDEX IF EXISTS nee_apoioma_tipo_b51452_idx;",
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="alunonecessidade",
                    index=models.Index(fields=["ativo"], name="nee_alunone_ativo_9df419_idx"),
                ),
                migrations.AddIndex(
                    model_name="apoiomatricula",
                    index=models.Index(fields=["tipo"], name="nee_apoioma_tipo_b51452_idx"),
                ),
            ],
        ),
    ]
