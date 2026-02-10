from __future__ import annotations

import re
from django.conf import settings
from django.db import models
from django.utils import timezone


def _only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def gerar_codigo_acesso(nome: str, ano: int | None = None) -> str:
    """
    Ex.: "joao.silva-2026"
    """
    base = (nome or "").strip().lower()
    base = re.sub(r"[^a-z0-9]+", ".", base)
    base = base.strip(".") or "usuario"
    ano = ano or timezone.now().year
    return f"{base}-{ano}"


class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin (Sistema)"
        MUNICIPAL = "MUNICIPAL", "Gestor Municipal"
        SECRETARIA = "SECRETARIA", "Gestor de Secretaria"
        UNIDADE = "UNIDADE", "Gestor de Unidade"
        PROFESSOR = "PROFESSOR", "Professor"
        ALUNO = "ALUNO", "Aluno"
        NEE = "NEE", "Técnico NEE"
        LEITURA = "LEITURA", "Somente leitura"
        
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfis",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

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

    # =========================
    # Acesso (GEPUB)
    # =========================
    cpf = models.CharField(max_length=14, blank=True, default="")
    codigo_acesso = models.CharField(max_length=60, unique=True, blank=True, default="")
    must_change_password = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self) -> str:
        return f"{self.user} ({self.role})"

    def save(self, *args, **kwargs):
        # Gera código se vazio, garantindo unicidade
        if not self.codigo_acesso:
            nome_base = (self.user.get_full_name() or self.user.username or "usuario").strip()
            base = gerar_codigo_acesso(nome_base)

            codigo = base
            i = 2
            while Profile.objects.filter(codigo_acesso__iexact=codigo).exclude(pk=self.pk).exists():
                codigo = f"{base}-{i}"
                i += 1

            self.codigo_acesso = codigo

        super().save(*args, **kwargs)

    @property
    def cpf_digits(self) -> str:
        return _only_digits(self.cpf)