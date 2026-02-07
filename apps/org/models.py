from django.db import models


class Municipio(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    uf = models.CharField(max_length=2, default="MA")

    # Dados da Prefeitura
    cnpj_prefeitura = models.CharField("CNPJ da Prefeitura", max_length=18, blank=True, default="")
    razao_social_prefeitura = models.CharField("Razão Social", max_length=180, blank=True, default="")
    nome_fantasia_prefeitura = models.CharField("Nome Fantasia", max_length=180, blank=True, default="")
    endereco_prefeitura = models.TextField("Endereço", blank=True, default="")
    telefone_prefeitura = models.CharField("Telefone", max_length=40, blank=True, default="")
    email_prefeitura = models.EmailField("E-mail", blank=True, default="")
    site_prefeitura = models.URLField("Site", blank=True, default="")
    nome_prefeito = models.CharField("Prefeito(a)", max_length=160, blank=True, default="")

    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Município"
        verbose_name_plural = "Municípios"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["uf"]),
            models.Index(fields=["ativo"]),
        ]

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
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return self.nome


class Unidade(models.Model):
    class Tipo(models.TextChoices):
        ESCOLA = "ESCOLA", "Escola"
        CRECHE = "CRECHE", "Creche"
        SECRETARIA = "SECRETARIA", "Secretaria/Órgão"
        OUTRO = "OUTRO", "Outro"

    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.PROTECT,
        related_name="unidades",
    )

    nome = models.CharField(max_length=180)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.ESCOLA)

    # Identificadores (opcionais)
    codigo_inep = models.CharField("Código INEP", max_length=20, blank=True, default="")
    cnpj = models.CharField("CNPJ", max_length=18, blank=True, default="")

    # Contato / endereço (opcionais)
    email = models.EmailField("E-mail", blank=True, default="")
    telefone = models.CharField("Telefone", max_length=40, blank=True, default="")
    endereco = models.TextField("Endereço", blank=True, default="")

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
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["codigo_inep"]),
            models.Index(fields=["ativo"]),
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
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.unidade})"
