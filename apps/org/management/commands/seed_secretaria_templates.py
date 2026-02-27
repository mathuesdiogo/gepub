from django.core.management.base import BaseCommand

from apps.org.services.provisioning import seed_secretaria_templates


class Command(BaseCommand):
    help = "Cria/atualiza o catálogo completo de templates de secretarias para onboarding municipal."

    def handle(self, *args, **options):
        templates = seed_secretaria_templates()
        self.stdout.write(
            self.style.SUCCESS(
                f"Templates processados com sucesso: {', '.join(t.slug for t in templates)}"
            )
        )
