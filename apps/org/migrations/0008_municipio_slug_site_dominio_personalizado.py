from django.db import migrations, models
from django.utils.text import slugify


def _backfill_slug_site(apps, schema_editor):
    Municipio = apps.get_model("org", "Municipio")
    used = set(
        s
        for s in Municipio.objects.exclude(slug_site__isnull=True)
        .exclude(slug_site__exact="")
        .values_list("slug_site", flat=True)
    )

    for municipio in Municipio.objects.order_by("id"):
        current = (municipio.slug_site or "").strip().lower()
        if current:
            if current in used:
                current = ""
            else:
                used.add(current)
                continue

        base = slugify((municipio.nome or "").strip()) or "municipio"
        candidate = base[:90]
        i = 2
        while candidate in used:
            suffix = f"-{i}"
            candidate = f"{base[: max(1, 90 - len(suffix))]}{suffix}"
            i += 1
        municipio.slug_site = candidate
        municipio.save(update_fields=["slug_site"])
        used.add(candidate)


class Migration(migrations.Migration):
    dependencies = [
        ("org", "0007_secretariacadastrobase_secretariaconfiguracao_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="municipio",
            name="dominio_personalizado",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Opcional. Ex.: prefeitura.seumunicipio.gov.br",
                max_length=190,
                verbose_name="Domínio personalizado",
            ),
        ),
        migrations.AddField(
            model_name="municipio",
            name="slug_site",
            field=models.SlugField(
                blank=True,
                help_text="Usado no domínio público: slug.gepub.com.br",
                max_length=90,
                null=True,
                unique=True,
                verbose_name="Slug do portal",
            ),
        ),
        migrations.AddIndex(
            model_name="municipio",
            index=models.Index(fields=["slug_site"], name="org_municip_slug_si_cc2bd7_idx"),
        ),
        migrations.RunPython(_backfill_slug_site, migrations.RunPython.noop),
    ]
