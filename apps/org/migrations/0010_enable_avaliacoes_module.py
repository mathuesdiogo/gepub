from django.db import migrations


def enable_avaliacoes_module(apps, schema_editor):
    MunicipioModuloAtivo = apps.get_model("org", "MunicipioModuloAtivo")
    SecretariaModuloAtivo = apps.get_model("org", "SecretariaModuloAtivo")

    module_key = "avaliacoes"

    municipio_ids = (
        MunicipioModuloAtivo.objects.values_list("municipio_id", flat=True)
        .distinct()
    )
    for municipio_id in municipio_ids:
        obj, created = MunicipioModuloAtivo.objects.get_or_create(
            municipio_id=municipio_id,
            modulo=module_key,
            defaults={"ativo": True},
        )
        if not created and not obj.ativo:
            obj.ativo = True
            obj.save(update_fields=["ativo", "atualizado_em"])

    secretaria_ids = (
        SecretariaModuloAtivo.objects.values_list("secretaria_id", flat=True)
        .distinct()
    )
    for secretaria_id in secretaria_ids:
        obj, created = SecretariaModuloAtivo.objects.get_or_create(
            secretaria_id=secretaria_id,
            modulo=module_key,
            defaults={"ativo": True},
        )
        if not created and not obj.ativo:
            obj.ativo = True
            obj.save(update_fields=["ativo", "atualizado_em"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("org", "0009_enable_paineis_conversor_modules"),
    ]

    operations = [
        migrations.RunPython(enable_avaliacoes_module, noop_reverse),
    ]
