from django.db import migrations


def seed_institutional_page(apps, schema_editor):
    InstitutionalPageConfig = apps.get_model("core", "InstitutionalPageConfig")
    InstitutionalSlide = apps.get_model("core", "InstitutionalSlide")
    InstitutionalMethodStep = apps.get_model("core", "InstitutionalMethodStep")
    InstitutionalServiceCard = apps.get_model("core", "InstitutionalServiceCard")

    page, created = InstitutionalPageConfig.objects.get_or_create(
        nome="Página Institucional Padrão",
        defaults={"ativo": True, "marca_nome": "GEPUB"},
    )

    if not created:
        return

    slides = [
        {
            "titulo": "Time GEPUB",
            "subtitulo": "Especialistas em operação municipal digital",
            "descricao": "Consultoria de implantação e acompanhamento contínuo.",
            "icone": "fa-solid fa-user-tie",
            "ordem": 1,
            "ativo": True,
        },
        {
            "titulo": "Onboarding por secretaria",
            "subtitulo": "Educação, Saúde, NEE e mais",
            "descricao": "Ative módulos com templates e perfis padronizados.",
            "icone": "fa-solid fa-wand-magic-sparkles",
            "ordem": 2,
            "ativo": True,
        },
        {
            "titulo": "Cobrança previsível",
            "subtitulo": "Plano base + limites + overage",
            "descricao": "Fatura mensal por competência e gestão de upgrades.",
            "icone": "fa-solid fa-file-invoice-dollar",
            "ordem": 3,
            "ativo": True,
        },
    ]
    for item in slides:
        InstitutionalSlide.objects.create(pagina=page, **item)

    steps = [
        {
            "titulo": "1. Diagnóstico municipal",
            "descricao": "Mapeamos secretarias, unidades e metas da prefeitura.",
            "icone": "fa-solid fa-map-location-dot",
            "ordem": 1,
            "ativo": True,
        },
        {
            "titulo": "2. Configuração do plano",
            "descricao": "Definimos limites, módulos e política de crescimento.",
            "icone": "fa-solid fa-sliders",
            "ordem": 2,
            "ativo": True,
        },
        {
            "titulo": "3. Onboarding assistido",
            "descricao": "Ativamos secretarias, perfis e trilhas de onboarding.",
            "icone": "fa-solid fa-rocket",
            "ordem": 3,
            "ativo": True,
        },
        {
            "titulo": "4. Gestão e expansão",
            "descricao": "Monitoramos consumo, BI e upgrades com cálculo claro.",
            "icone": "fa-solid fa-chart-pie",
            "ordem": 4,
            "ativo": True,
        },
    ]
    for item in steps:
        InstitutionalMethodStep.objects.create(pagina=page, **item)

    services = [
        {
            "titulo": "Organização",
            "descricao": "Municípios, secretarias, unidades e setores com governança.",
            "icone": "fa-solid fa-sitemap",
            "ordem": 1,
            "ativo": True,
        },
        {
            "titulo": "Educação",
            "descricao": "Matrícula, turmas, diário, indicadores e relatórios.",
            "icone": "fa-solid fa-school",
            "ordem": 2,
            "ativo": True,
        },
        {
            "titulo": "Saúde",
            "descricao": "Unidades, profissionais, agenda e atendimentos clínicos.",
            "icone": "fa-solid fa-notes-medical",
            "ordem": 3,
            "ativo": True,
        },
        {
            "titulo": "NEE",
            "descricao": "Planos de acompanhamento e relatórios institucionais.",
            "icone": "fa-solid fa-universal-access",
            "ordem": 4,
            "ativo": True,
        },
        {
            "titulo": "Planos e cobrança",
            "descricao": "Assinatura municipal, overage e fatura por competência.",
            "icone": "fa-solid fa-file-invoice-dollar",
            "ordem": 5,
            "ativo": True,
        },
        {
            "titulo": "Auditoria e LGPD",
            "descricao": "Controle de acesso, trilhas críticas e rastreabilidade.",
            "icone": "fa-solid fa-shield-halved",
            "ordem": 6,
            "ativo": True,
        },
    ]
    for item in services:
        InstitutionalServiceCard.objects.create(pagina=page, **item)


def unseed_institutional_page(apps, schema_editor):
    InstitutionalPageConfig = apps.get_model("core", "InstitutionalPageConfig")
    InstitutionalPageConfig.objects.filter(nome="Página Institucional Padrão").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_institutionalpageconfig_institutionalmethodstep_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_institutional_page, unseed_institutional_page),
    ]
