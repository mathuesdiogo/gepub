from django.conf import settings
from django.db import models


class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin (Sistema)"
        MUNICIPAL = "MUNICIPAL", "Gestor Municipal"
        UNIDADE = "UNIDADE", "Gestor de Unidade"
        NEE = "NEE", "Técnico NEE"
        LEITURA = "LEITURA", "Somente leitura"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.LEITURA)

    # escopo
    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="profiles",
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="profiles",
    )

    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self) -> str:
        return f"{self.user} ({self.role})"
