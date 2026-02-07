from django.db import models


class Municipio(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    uf = models.CharField(max_length=2, default="MA")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Município"
        verbose_name_plural = "Municípios"
        ordering = ["nome"]

    def __str__(self) -> str:
        return f"{self.nome}/{self.uf}"


class Secretaria(models.Model):
    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT,
        related_name="secretarias",
    )
    nome = models.CharField(max_length=160)
    sigla = models.CharField(max_length=30, blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Secretaria"
        verbose_name_plural = "Secretarias"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "nome"],
                name="uniq_secretaria_por_municipio",
            )
        ]

    def __str__(self) -> str:
        return self.nome


class Unidade(models.Model):
    class Tipo(models.TextChoices):
        ESCOLA = "ESCOLA", "Escola"
        CRECHE = "CRECHE", "Creche"
        SECRETARIA = "SECRETARIA", "Secretaria"
        OUTRO = "OUTRO", "Outro"

    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.PROTECT,
        related_name="unidades",
    )
    nome = models.CharField(max_length=180)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.ESCOLA)
    codigo_inep = models.CharField(max_length=20, blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["secretaria", "nome"],
                name="uniq_unidade_por_secretaria",
            )
        ]

    def __str__(self) -> str:
        return self.nome


class Setor(models.Model):
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="setores",
    )
    nome = models.CharField(max_length=120)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidade", "nome"],
                name="uniq_setor_por_unidade",
            )
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.unidade})"
