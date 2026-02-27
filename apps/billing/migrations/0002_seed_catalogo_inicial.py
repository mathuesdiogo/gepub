from decimal import Decimal

from django.db import migrations


def seed_catalogo(apps, schema_editor):
    PlanoMunicipal = apps.get_model("billing", "PlanoMunicipal")
    AddonCatalogo = apps.get_model("billing", "AddonCatalogo")

    planos = [
        {
            "codigo": "STARTER",
            "nome": "Starter",
            "descricao": "Plano para prefeituras pequenas.",
            "preco_base_mensal": Decimal("2990.00"),
            "limite_secretarias": 4,
            "limite_usuarios": 60,
            "limite_alunos": 2000,
            "limite_atendimentos_ano": 10000,
            "feature_bi_light": False,
            "feature_bi_municipal": False,
            "feature_bi_avancado": False,
            "feature_importacao_assistida": False,
            "feature_sla_prioritario": False,
            "feature_migracao_assistida": False,
            "feature_treinamento_continuo": False,
            "valor_secretaria_extra": Decimal("250.00"),
            "valor_usuario_extra": Decimal("8.00"),
            "valor_aluno_extra": Decimal("0.60"),
            "valor_atendimento_extra": Decimal("0.0000"),
            "ativo": True,
        },
        {
            "codigo": "MUNICIPAL",
            "nome": "Municipal",
            "descricao": "Plano recomendado para prefeituras de porte médio.",
            "preco_base_mensal": Decimal("6990.00"),
            "limite_secretarias": 8,
            "limite_usuarios": 200,
            "limite_alunos": 8000,
            "limite_atendimentos_ano": 50000,
            "feature_bi_light": False,
            "feature_bi_municipal": True,
            "feature_bi_avancado": False,
            "feature_importacao_assistida": True,
            "feature_sla_prioritario": False,
            "feature_migracao_assistida": False,
            "feature_treinamento_continuo": False,
            "valor_secretaria_extra": Decimal("220.00"),
            "valor_usuario_extra": Decimal("6.00"),
            "valor_aluno_extra": Decimal("0.45"),
            "valor_atendimento_extra": Decimal("0.0000"),
            "ativo": True,
        },
        {
            "codigo": "GESTAO_TOTAL",
            "nome": "Gestão Total",
            "descricao": "Plano para prefeituras médias/grandes com BI avançado e SLA prioritário.",
            "preco_base_mensal": Decimal("14900.00"),
            "limite_secretarias": None,
            "limite_usuarios": None,
            "limite_alunos": None,
            "limite_atendimentos_ano": None,
            "feature_bi_light": False,
            "feature_bi_municipal": True,
            "feature_bi_avancado": True,
            "feature_importacao_assistida": True,
            "feature_sla_prioritario": True,
            "feature_migracao_assistida": True,
            "feature_treinamento_continuo": True,
            "valor_secretaria_extra": Decimal("0.00"),
            "valor_usuario_extra": Decimal("0.00"),
            "valor_aluno_extra": Decimal("0.00"),
            "valor_atendimento_extra": Decimal("0.0000"),
            "ativo": True,
        },
        {
            "codigo": "CONSORCIO",
            "nome": "Consórcio / Estado",
            "descricao": "Plano multi-município sob proposta comercial específica.",
            "preco_base_mensal": Decimal("0.00"),
            "limite_secretarias": None,
            "limite_usuarios": None,
            "limite_alunos": None,
            "limite_atendimentos_ano": None,
            "feature_bi_light": False,
            "feature_bi_municipal": True,
            "feature_bi_avancado": True,
            "feature_importacao_assistida": True,
            "feature_sla_prioritario": True,
            "feature_migracao_assistida": True,
            "feature_treinamento_continuo": True,
            "valor_secretaria_extra": Decimal("0.00"),
            "valor_usuario_extra": Decimal("0.00"),
            "valor_aluno_extra": Decimal("0.00"),
            "valor_atendimento_extra": Decimal("0.0000"),
            "ativo": True,
        },
    ]

    for payload in planos:
        PlanoMunicipal.objects.update_or_create(
            codigo=payload["codigo"],
            defaults=payload,
        )

    addons = [
        {
            "slug": "bi-light",
            "nome": "BI Light",
            "descricao": "Pacote de indicadores adicionais para municípios no Starter.",
            "valor_mensal": Decimal("990.00"),
            "ativo": True,
        },
        {
            "slug": "ambiente-homologacao",
            "nome": "Ambiente extra de homologação",
            "descricao": "Ambiente adicional para treinamento/homologação.",
            "valor_mensal": Decimal("1490.00"),
            "ativo": True,
        },
    ]

    for payload in addons:
        AddonCatalogo.objects.update_or_create(slug=payload["slug"], defaults=payload)


def unseed_catalogo(apps, schema_editor):
    PlanoMunicipal = apps.get_model("billing", "PlanoMunicipal")
    AddonCatalogo = apps.get_model("billing", "AddonCatalogo")

    PlanoMunicipal.objects.filter(codigo__in=["STARTER", "MUNICIPAL", "GESTAO_TOTAL", "CONSORCIO"]).delete()
    AddonCatalogo.objects.filter(slug__in=["bi-light", "ambiente-homologacao"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalogo, unseed_catalogo),
    ]
