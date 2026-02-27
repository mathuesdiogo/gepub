from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.core.services_portal_seed import ensure_portal_seed_for_municipio
from apps.org.models import Municipio


class Command(BaseCommand):
    help = "Cria seed inicial dos portais públicos para municípios existentes."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Atualiza itens padrão existentes.")
        parser.add_argument("--only-active", action="store_true", help="Processa apenas municípios ativos.")

    def handle(self, *args, **options):
        qs = Municipio.objects.order_by("nome")
        if options.get("only_active"):
            qs = qs.filter(ativo=True)

        total = 0
        created_configs = 0
        created_banners = 0
        created_noticias = 0
        created_paginas = 0
        created_menus = 0
        created_blocos = 0

        for municipio in qs.iterator():
            result = ensure_portal_seed_for_municipio(
                municipio,
                autor=None,
                force=bool(options.get("force")),
            )
            total += 1
            created_configs += int(result.config_created)
            created_banners += result.banners_created
            created_noticias += result.noticias_created
            created_paginas += result.paginas_created
            created_menus += result.menus_created
            created_blocos += result.blocos_created

        self.stdout.write(
            self.style.SUCCESS(
                "Seed de portais concluído. "
                f"Municípios: {total} | "
                f"Configurações criadas: {created_configs} | "
                f"Banners criados: {created_banners} | "
                f"Notícias criadas: {created_noticias} | "
                f"Páginas criadas: {created_paginas} | "
                f"Menus criados: {created_menus} | "
                f"Blocos home criados: {created_blocos}"
            )
        )
