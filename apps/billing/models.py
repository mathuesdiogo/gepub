from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class PlanoMunicipal(models.Model):
    class Codigo(models.TextChoices):
        STARTER = "STARTER", "Starter"
        MUNICIPAL = "MUNICIPAL", "Municipal"
        GESTAO_TOTAL = "GESTAO_TOTAL", "Gestão Total"
        CONSORCIO = "CONSORCIO", "Consórcio/Estado"

    codigo = models.CharField(max_length=30, choices=Codigo.choices, unique=True)
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True, default="")
    preco_base_mensal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    limite_secretarias = models.PositiveIntegerField(null=True, blank=True)
    limite_usuarios = models.PositiveIntegerField(null=True, blank=True)
    limite_alunos = models.PositiveIntegerField(null=True, blank=True)
    limite_atendimentos_ano = models.PositiveIntegerField(null=True, blank=True)

    feature_bi_light = models.BooleanField(default=False)
    feature_bi_municipal = models.BooleanField(default=False)
    feature_bi_avancado = models.BooleanField(default=False)
    feature_importacao_assistida = models.BooleanField(default=False)
    feature_sla_prioritario = models.BooleanField(default=False)
    feature_migracao_assistida = models.BooleanField(default=False)
    feature_treinamento_continuo = models.BooleanField(default=False)

    valor_secretaria_extra = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    valor_usuario_extra = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    valor_aluno_extra = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    valor_atendimento_extra = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"))

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plano municipal"
        verbose_name_plural = "Planos municipais"
        ordering = ["preco_base_mensal", "nome"]

    def __str__(self) -> str:
        return f"{self.nome} (R$ {self.preco_base_mensal})"


class AddonCatalogo(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True, default="")
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Addon"
        verbose_name_plural = "Addons"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class AssinaturaMunicipio(models.Model):
    class Status(models.TextChoices):
        TRIAL = "TRIAL", "Trial"
        ATIVO = "ATIVO", "Ativo"
        SUSPENSO = "SUSPENSO", "Suspenso"
        CANCELADO = "CANCELADO", "Cancelado"

    class IndiceReajuste(models.TextChoices):
        INPC = "INPC", "INPC"
        IPCA = "IPCA", "IPCA"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="assinaturas")
    plano = models.ForeignKey(PlanoMunicipal, on_delete=models.PROTECT, related_name="assinaturas")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO)

    inicio_vigencia = models.DateField(default=timezone.localdate)
    fim_vigencia = models.DateField(null=True, blank=True)
    contrato_meses = models.PositiveIntegerField(default=12)

    preco_base_congelado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    indice_reajuste = models.CharField(
        max_length=10,
        choices=IndiceReajuste.choices,
        default=IndiceReajuste.INPC,
    )
    desconto_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Assinatura municipal"
        verbose_name_plural = "Assinaturas municipais"
        ordering = ["-inicio_vigencia", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["inicio_vigencia"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.plano.nome} • {self.status}"

    def valor_desconto_mensal(self) -> Decimal:
        if self.desconto_percentual <= 0:
            return Decimal("0.00")
        return (self.preco_base_congelado * self.desconto_percentual / Decimal("100")).quantize(Decimal("0.01"))

    def valor_base_mensal(self) -> Decimal:
        return (self.preco_base_congelado - self.valor_desconto_mensal()).quantize(Decimal("0.01"))


class UsoMunicipio(models.Model):
    municipio = models.OneToOneField("org.Municipio", on_delete=models.CASCADE, related_name="uso_atual")

    secretarias_ativas = models.PositiveIntegerField(default=0)
    usuarios_ativos = models.PositiveIntegerField(default=0)
    alunos_ativos = models.PositiveIntegerField(default=0)
    atendimentos_ano = models.PositiveIntegerField(default=0)

    ano_referencia = models.PositiveIntegerField(default=timezone.now().year)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Uso municipal"
        verbose_name_plural = "Usos municipais"

    def __str__(self) -> str:
        return f"Uso {self.municipio} ({self.ano_referencia})"


class AssinaturaQuotaExtra(models.Model):
    class Tipo(models.TextChoices):
        SECRETARIAS = "SECRETARIAS", "Secretarias"
        USUARIOS = "USUARIOS", "Usuários"
        ALUNOS = "ALUNOS", "Alunos"
        ATENDIMENTOS = "ATENDIMENTOS", "Atendimentos"

    class Origem(models.TextChoices):
        UPGRADE = "UPGRADE", "Upgrade"
        BONUS = "BONUS", "Bônus"
        MANUAL = "MANUAL", "Manual"

    assinatura = models.ForeignKey(AssinaturaMunicipio, on_delete=models.CASCADE, related_name="quotas_extras")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    quantidade = models.PositiveIntegerField(default=1)
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.UPGRADE)
    descricao = models.CharField(max_length=180, blank=True, default="")

    inicio_vigencia = models.DateField(default=timezone.localdate)
    fim_vigencia = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotas_extras_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quota extra"
        verbose_name_plural = "Quotas extras"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["assinatura", "tipo", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.assinatura.municipio} • {self.get_tipo_display()} +{self.quantidade}"


class AssinaturaAddon(models.Model):
    assinatura = models.ForeignKey(AssinaturaMunicipio, on_delete=models.CASCADE, related_name="addons")
    addon = models.ForeignKey(AddonCatalogo, on_delete=models.PROTECT, related_name="assinaturas")
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario_congelado = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    inicio_vigencia = models.DateField(default=timezone.localdate)
    fim_vigencia = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Addon da assinatura"
        verbose_name_plural = "Addons da assinatura"
        ordering = ["addon__nome"]
        constraints = [
            models.UniqueConstraint(fields=["assinatura", "addon"], name="uniq_assinatura_addon"),
        ]

    def __str__(self) -> str:
        return f"{self.assinatura.municipio} • {self.addon.nome}"


class SolicitacaoUpgrade(models.Model):
    class Tipo(models.TextChoices):
        SECRETARIAS = "SECRETARIAS", "+ secretarias"
        USUARIOS = "USUARIOS", "+ usuários"
        ALUNOS = "ALUNOS", "+ alunos"
        ATENDIMENTOS = "ATENDIMENTOS", "+ atendimentos"
        ADDON = "ADDON", "Addon"
        TROCA_PLANO = "TROCA_PLANO", "Troca de plano"

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        SOLICITADO = "SOLICITADO", "Solicitado"
        APROVADO = "APROVADO", "Aprovado"
        RECUSADO = "RECUSADO", "Recusado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="solicitacoes_upgrade")
    assinatura = models.ForeignKey(
        AssinaturaMunicipio,
        on_delete=models.PROTECT,
        related_name="solicitacoes_upgrade",
    )

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    addon = models.ForeignKey(
        AddonCatalogo,
        on_delete=models.PROTECT,
        related_name="solicitacoes_upgrade",
        null=True,
        blank=True,
    )
    quantidade = models.PositiveIntegerField(default=1)

    plano_destino = models.ForeignKey(
        PlanoMunicipal,
        on_delete=models.PROTECT,
        related_name="solicitacoes_migracao",
        null=True,
        blank=True,
    )

    valor_mensal_calculado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    valor_one_time = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    observacao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SOLICITADO)

    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="upgrades_solicitados",
    )
    solicitado_em = models.DateTimeField(auto_now_add=True)

    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="upgrades_aprovados",
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Solicitação de upgrade"
        verbose_name_plural = "Solicitações de upgrade"
        ordering = ["-solicitado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["tipo", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.get_tipo_display()} • {self.status}"


class FaturaMunicipio(models.Model):
    class Status(models.TextChoices):
        ABERTA = "ABERTA", "Aberta"
        FECHADA = "FECHADA", "Fechada"
        PAGA = "PAGA", "Paga"
        CANCELADA = "CANCELADA", "Cancelada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="faturas")
    assinatura = models.ForeignKey(AssinaturaMunicipio, on_delete=models.PROTECT, related_name="faturas")

    competencia = models.DateField(help_text="Competência no 1º dia do mês")
    vencimento = models.DateField(null=True, blank=True)

    valor_base = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    valor_adicionais = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    valor_desconto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTA)
    observacao = models.TextField(blank=True, default="")

    gerada_em = models.DateTimeField(auto_now_add=True)
    paga_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Fatura"
        verbose_name_plural = "Faturas"
        ordering = ["-competencia", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["assinatura", "competencia"], name="uniq_fatura_assinatura_competencia"),
        ]
        indexes = [
            models.Index(fields=["municipio", "competencia"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.competencia:%m/%Y} • R$ {self.valor_total}"
