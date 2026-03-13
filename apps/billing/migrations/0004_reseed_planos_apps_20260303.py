from decimal import Decimal

from django.db import migrations


PLANOS = [
    {
        "codigo": "STARTER",
        "nome": "GEPUB Essencial",
        "descricao": "Gestão interna municipal com foco em organização operacional por secretarias.",
        "preco_base_mensal": Decimal("1490.00"),
        "limite_secretarias": None,
        "limite_usuarios": None,
        "limite_alunos": None,
        "limite_atendimentos_ano": None,
        "feature_bi_light": False,
        "feature_bi_municipal": False,
        "feature_bi_avancado": False,
        "feature_importacao_assistida": False,
        "feature_sla_prioritario": False,
        "feature_migracao_assistida": False,
        "feature_treinamento_continuo": False,
        "valor_secretaria_extra": Decimal("0.00"),
        "valor_usuario_extra": Decimal("0.00"),
        "valor_aluno_extra": Decimal("0.00"),
        "valor_atendimento_extra": Decimal("0.0000"),
        "ativo": True,
    },
    {
        "codigo": "MUNICIPAL",
        "nome": "GEPUB Gestão Integrada",
        "descricao": "Gestão interna + Portal da Prefeitura para comunicação institucional.",
        "preco_base_mensal": Decimal("2490.00"),
        "limite_secretarias": None,
        "limite_usuarios": None,
        "limite_alunos": None,
        "limite_atendimentos_ano": None,
        "feature_bi_light": False,
        "feature_bi_municipal": False,
        "feature_bi_avancado": False,
        "feature_importacao_assistida": False,
        "feature_sla_prioritario": False,
        "feature_migracao_assistida": False,
        "feature_treinamento_continuo": False,
        "valor_secretaria_extra": Decimal("0.00"),
        "valor_usuario_extra": Decimal("0.00"),
        "valor_aluno_extra": Decimal("0.00"),
        "valor_atendimento_extra": Decimal("0.0000"),
        "ativo": True,
    },
    {
        "codigo": "GESTAO_TOTAL",
        "nome": "GEPUB Transformação Digital",
        "descricao": "Gestão + Portal + Transparência para governança, LAI e rastreabilidade.",
        "preco_base_mensal": Decimal("3990.00"),
        "limite_secretarias": None,
        "limite_usuarios": None,
        "limite_alunos": None,
        "limite_atendimentos_ano": None,
        "feature_bi_light": False,
        "feature_bi_municipal": False,
        "feature_bi_avancado": False,
        "feature_importacao_assistida": False,
        "feature_sla_prioritario": False,
        "feature_migracao_assistida": False,
        "feature_treinamento_continuo": False,
        "valor_secretaria_extra": Decimal("0.00"),
        "valor_usuario_extra": Decimal("0.00"),
        "valor_aluno_extra": Decimal("0.00"),
        "valor_atendimento_extra": Decimal("0.0000"),
        "ativo": True,
    },
    {
        "codigo": "CONSORCIO",
        "nome": "GEPUB Governo Completo",
        "descricao": "Executivo + Legislativo integrados, com Portal da Câmara e transparência completa.",
        "preco_base_mensal": Decimal("5990.00"),
        "limite_secretarias": None,
        "limite_usuarios": None,
        "limite_alunos": None,
        "limite_atendimentos_ano": None,
        "feature_bi_light": False,
        "feature_bi_municipal": False,
        "feature_bi_avancado": False,
        "feature_importacao_assistida": False,
        "feature_sla_prioritario": False,
        "feature_migracao_assistida": False,
        "feature_treinamento_continuo": False,
        "valor_secretaria_extra": Decimal("0.00"),
        "valor_usuario_extra": Decimal("0.00"),
        "valor_aluno_extra": Decimal("0.00"),
        "valor_atendimento_extra": Decimal("0.0000"),
        "ativo": True,
    },
]


def forwards(apps, schema_editor):
    PlanoMunicipal = apps.get_model("billing", "PlanoMunicipal")
    PlanoComercialConfig = apps.get_model("billing", "PlanoComercialConfig")

    for payload in PLANOS:
        plano, _ = PlanoMunicipal.objects.update_or_create(
            codigo=payload["codigo"],
            defaults=payload,
        )

        defaults_comercial = {
            "nome_comercial": payload["nome"],
            "categoria": "Maturidade",
            "descricao_comercial": payload["descricao"],
        }
        PlanoComercialConfig.objects.update_or_create(plano=plano, defaults=defaults_comercial)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0003_planocomercialconfig"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
