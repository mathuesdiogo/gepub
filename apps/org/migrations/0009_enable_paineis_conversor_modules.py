from django.db import migrations


def enable_new_modules(apps, schema_editor):
    MunicipioModuloAtivo = apps.get_model("org", "MunicipioModuloAtivo")
    SecretariaModuloAtivo = apps.get_model("org", "SecretariaModuloAtivo")

    module_keys = ["paineis", "conversor"]

    municipio_ids = (
        MunicipioModuloAtivo.objects.values_list("municipio_id", flat=True)
        .distinct()
    )
    for municipio_id in municipio_ids:
        for key in module_keys:
            obj, created = MunicipioModuloAtivo.objects.get_or_create(
                municipio_id=municipio_id,
                modulo=key,
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
        for key in module_keys:
            obj, created = SecretariaModuloAtivo.objects.get_or_create(
                secretaria_id=secretaria_id,
                modulo=key,
                defaults={"ativo": True},
            )
            if not created and not obj.ativo:
                obj.ativo = True
                obj.save(update_fields=["ativo", "atualizado_em"])


def noop_reverse(apps, schema_editor):
    # Sem rollback destrutivo para preservar configurações operacionais.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("org", "0008_municipio_slug_site_dominio_personalizado"),
    ]

    operations = [
        migrations.RunPython(enable_new_modules, noop_reverse),
    ]
