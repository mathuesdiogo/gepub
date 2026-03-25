from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PatrimonioCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class Categoria(models.TextChoices):
        IMOVEL = "IMOVEL", "Imóvel"
        MOVEL = "MOVEL", "Móvel"
        INFORMATICA = "INFORMATICA", "Informática"
        VEICULO = "VEICULO", "Veículo"
        OUTRO = "OUTRO", "Outro"

    class Situacao(models.TextChoices):
        EM_USO = "EM_USO", "Em uso"
        ESTOQUE = "ESTOQUE", "Em estoque"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"
        BAIXADO = "BAIXADO", "Baixado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="patrimonio_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="patrimonio_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="patrimonio_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="patrimonio_cadastros",
        null=True,
        blank=True,
    )
    local_estrutural = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="patrimonio_cadastros",
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=40)
    tombo = models.CharField(max_length=40, blank=True, default="")
    nome = models.CharField(max_length=180)
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.MOVEL)
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.EM_USO)
    data_aquisicao = models.DateField(default=timezone.localdate)
    valor_aquisicao = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estado_conservacao = models.CharField(max_length=40, blank=True, default="Bom")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrimonio_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bem patrimonial"
        verbose_name_plural = "Bens patrimoniais"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_patrimonio_cadastro_municipio_codigo"),
            models.UniqueConstraint(
                fields=["municipio", "tombo"],
                condition=~models.Q(tombo=""),
                name="uniq_patrimonio_tombo_municipio",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["municipio", "situacao"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["tombo"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"

    def clean(self):
        errors: dict[str, str] = {}
        if self.secretaria_id and self.secretaria.municipio_id != self.municipio_id:
            errors["secretaria"] = "Secretaria fora do município selecionado."
        if self.unidade_id and self.secretaria_id and self.unidade.secretaria_id != self.secretaria_id:
            errors["unidade"] = "Unidade deve pertencer à secretaria selecionada."
        if self.setor_id and self.unidade_id and self.setor.unidade_id != self.unidade_id:
            errors["setor"] = "Setor deve pertencer à unidade selecionada."
        if self.local_estrutural_id and self.unidade_id and self.local_estrutural.unidade_id != self.unidade_id:
            errors["local_estrutural"] = "Local estrutural deve pertencer à unidade selecionada."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PatrimonioMovimentacao(models.Model):
    class Tipo(models.TextChoices):
        TRANSFERENCIA = "TRANSFERENCIA", "Transferência"
        MANUTENCAO = "MANUTENCAO", "Manutenção"
        BAIXA = "BAIXA", "Baixa"
        INVENTARIO = "INVENTARIO", "Inventário"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="patrimonio_movimentacoes")
    bem = models.ForeignKey(PatrimonioCadastro, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.TRANSFERENCIA)
    data_movimento = models.DateField(default=timezone.localdate)
    unidade_origem = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="patrimonio_movimentacoes_origem",
        null=True,
        blank=True,
    )
    unidade_destino = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="patrimonio_movimentacoes_destino",
        null=True,
        blank=True,
    )
    local_origem = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="patrimonio_movimentacoes_origem",
        null=True,
        blank=True,
    )
    local_destino = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="patrimonio_movimentacoes_destino",
        null=True,
        blank=True,
    )
    valor_movimento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrimonio_movimentacoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Movimentação patrimonial"
        verbose_name_plural = "Movimentações patrimoniais"
        ordering = ["-data_movimento", "-id"]
        indexes = [
            models.Index(fields=["municipio", "tipo"]),
            models.Index(fields=["bem", "data_movimento"]),
        ]

    def __str__(self):
        return f"{self.bem.nome} • {self.get_tipo_display()} • {self.data_movimento}"

    def clean(self):
        errors: dict[str, str] = {}
        if self.bem_id and self.bem.municipio_id != self.municipio_id:
            errors["bem"] = "Bem fora do município selecionado."
        if self.unidade_origem_id and self.unidade_origem.secretaria.municipio_id != self.municipio_id:
            errors["unidade_origem"] = "Unidade de origem fora do município selecionado."
        if self.unidade_destino_id and self.unidade_destino.secretaria.municipio_id != self.municipio_id:
            errors["unidade_destino"] = "Unidade de destino fora do município selecionado."
        if self.local_origem_id and self.unidade_origem_id and self.local_origem.unidade_id != self.unidade_origem_id:
            errors["local_origem"] = "Local de origem deve pertencer à unidade de origem."
        if self.local_destino_id and self.unidade_destino_id and self.local_destino.unidade_id != self.unidade_destino_id:
            errors["local_destino"] = "Local de destino deve pertencer à unidade de destino."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PatrimonioInventario(models.Model):
    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        CONCLUIDO = "CONCLUIDO", "Concluído"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="patrimonio_inventarios")
    codigo = models.CharField(max_length=40)
    referencia = models.CharField(max_length=120, blank=True, default="")
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="patrimonio_inventarios",
        null=True,
        blank=True,
    )
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="patrimonio_inventarios",
        null=True,
        blank=True,
    )
    local_estrutural = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="patrimonio_inventarios",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTO)
    total_bens = models.PositiveIntegerField(default=0)
    total_bens_ativos = models.PositiveIntegerField(default=0)
    observacao = models.TextField(blank=True, default="")
    concluido_em = models.DateTimeField(null=True, blank=True)
    concluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrimonio_inventarios_concluidos",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patrimonio_inventarios_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventário patrimonial"
        verbose_name_plural = "Inventários patrimoniais"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_patrimonio_inventario_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
        ]

    def __str__(self):
        return f"{self.codigo} • {self.get_status_display()}"

    def clean(self):
        errors: dict[str, str] = {}
        if self.secretaria_id and self.secretaria.municipio_id != self.municipio_id:
            errors["secretaria"] = "Secretaria fora do município selecionado."
        if self.unidade_id and self.secretaria_id and self.unidade.secretaria_id != self.secretaria_id:
            errors["unidade"] = "Unidade deve pertencer à secretaria selecionada."
        if self.local_estrutural_id and self.unidade_id and self.local_estrutural.unidade_id != self.unidade_id:
            errors["local_estrutural"] = "Local estrutural deve pertencer à unidade selecionada."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class BemPatrimonial(models.Model):
    class EstadoConservacao(models.TextChoices):
        NOVO = "NOVO", "Novo"
        BOM = "BOM", "Bom"
        REGULAR = "REGULAR", "Regular"
        RUIM = "RUIM", "Ruim"
        INSERVIVEL = "INSERVIVEL", "Inservível"

    class Situacao(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"
        BAIXADO = "BAIXADO", "Baixado"
        EXTRAVIADO = "EXTRAVIADO", "Extraviado"
        EMPRESTADO = "EMPRESTADO", "Emprestado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="bens_patrimoniais")
    secretaria = models.ForeignKey("org.Secretaria", on_delete=models.PROTECT, related_name="bens_patrimoniais")
    unidade = models.ForeignKey("org.Unidade", on_delete=models.PROTECT, related_name="bens_patrimoniais")
    local_estrutural = models.ForeignKey("org.LocalEstrutural", on_delete=models.PROTECT, related_name="bens_patrimoniais")
    numero_tombamento = models.CharField(max_length=60)
    descricao = models.CharField(max_length=220)
    categoria = models.CharField(max_length=80, blank=True, default="")
    marca = models.CharField(max_length=80, blank=True, default="")
    modelo = models.CharField(max_length=80, blank=True, default="")
    numero_serie = models.CharField(max_length=120, blank=True, default="")
    data_aquisicao = models.DateField(default=timezone.localdate)
    valor_aquisicao = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    origem_aquisicao = models.CharField(max_length=120, blank=True, default="")
    fornecedor = models.CharField(max_length=180, blank=True, default="")
    estado_conservacao = models.CharField(
        max_length=20,
        choices=EstadoConservacao.choices,
        default=EstadoConservacao.BOM,
    )
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.ATIVO)
    responsavel_atual = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bens_patrimoniais_responsavel",
    )
    observacoes = models.TextField(blank=True, default="")
    foto = models.ImageField(upload_to="patrimonio/bens/", null=True, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bem patrimonial (novo)"
        verbose_name_plural = "Bens patrimoniais (novo)"
        ordering = ["descricao"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "numero_tombamento"],
                name="uniq_bem_patrimonial_tombamento_municipio",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "secretaria", "unidade"]),
            models.Index(fields=["situacao", "ativo"]),
            models.Index(fields=["categoria"]),
        ]

    def __str__(self) -> str:
        return f"{self.numero_tombamento} - {self.descricao}"

    def clean(self):
        errors: dict[str, str] = {}
        if self.secretaria_id and self.secretaria.municipio_id != self.municipio_id:
            errors["secretaria"] = "Secretaria fora do município selecionado."
        if self.unidade_id and self.unidade.secretaria_id != self.secretaria_id:
            errors["unidade"] = "Unidade deve pertencer à secretaria selecionada."
        if self.local_estrutural_id and self.local_estrutural.unidade_id != self.unidade_id:
            errors["local_estrutural"] = "Local estrutural deve pertencer à unidade selecionada."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Baixa é lógica: o bem permanece registrado.
        if self.situacao == self.Situacao.BAIXADO:
            self.ativo = False
        self.full_clean()
        super().save(*args, **kwargs)


class MovimentacaoPatrimonial(models.Model):
    class TipoMovimentacao(models.TextChoices):
        TRANSFERENCIA_INTERNA = "TRANSFERENCIA_INTERNA", "Transferência interna"
        TRANSFERENCIA_UNIDADE = "TRANSFERENCIA_UNIDADE", "Transferência entre unidades"
        TRANSFERENCIA_SECRETARIA = "TRANSFERENCIA_SECRETARIA", "Transferência entre secretarias"
        MANUTENCAO = "MANUTENCAO", "Manutenção"
        RETORNO_MANUTENCAO = "RETORNO_MANUTENCAO", "Retorno de manutenção"
        BAIXA = "BAIXA", "Baixa"
        EMPRESTIMO = "EMPRESTIMO", "Empréstimo"
        DEVOLUCAO = "DEVOLUCAO", "Devolução"
        INVENTARIO_AJUSTE = "INVENTARIO_AJUSTE", "Ajuste de inventário"

    bem = models.ForeignKey(BemPatrimonial, on_delete=models.CASCADE, related_name="movimentacoes")
    local_origem = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="movimentacoes_patrimoniais_origem",
        null=True,
        blank=True,
    )
    local_destino = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="movimentacoes_patrimoniais_destino",
        null=True,
        blank=True,
    )
    unidade_origem = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="movimentacoes_patrimoniais_origem",
        null=True,
        blank=True,
    )
    unidade_destino = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="movimentacoes_patrimoniais_destino",
        null=True,
        blank=True,
    )
    secretaria_origem = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="movimentacoes_patrimoniais_origem",
        null=True,
        blank=True,
    )
    secretaria_destino = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="movimentacoes_patrimoniais_destino",
        null=True,
        blank=True,
    )
    tipo_movimentacao = models.CharField(max_length=30, choices=TipoMovimentacao.choices)
    data_movimentacao = models.DateTimeField(default=timezone.now)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes_patrimoniais_responsavel",
    )
    autorizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes_patrimoniais_autorizador",
    )
    motivo = models.CharField(max_length=220, blank=True, default="")
    documento_referencia = models.CharField(max_length=80, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimentação patrimonial (novo)"
        verbose_name_plural = "Movimentações patrimoniais (novo)"
        ordering = ["-data_movimentacao", "-id"]
        indexes = [
            models.Index(fields=["tipo_movimentacao", "data_movimentacao"]),
            models.Index(fields=["bem", "data_movimentacao"]),
        ]

    def __str__(self) -> str:
        return f"{self.bem} • {self.get_tipo_movimentacao_display()}"

    def clean(self):
        if self.local_destino_id and self.local_origem_id and self.local_destino_id == self.local_origem_id:
            raise ValidationError({"local_destino": "Origem e destino não podem ser iguais."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class InventarioPatrimonial(models.Model):
    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        CONCLUIDO = "CONCLUIDO", "Concluído"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="inventarios_patrimoniais")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="inventarios_patrimoniais",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="inventarios_patrimoniais",
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=180)
    data_abertura = models.DateField(default=timezone.localdate)
    data_fechamento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTO)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventarios_patrimoniais_responsavel",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inventário patrimonial (novo)"
        verbose_name_plural = "Inventários patrimoniais (novo)"
        ordering = ["-data_abertura", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["secretaria", "unidade"]),
        ]

    def __str__(self) -> str:
        return self.nome


class InventarioItem(models.Model):
    class StatusConferencia(models.TextChoices):
        LOCALIZADO = "LOCALIZADO", "Localizado"
        NAO_LOCALIZADO = "NAO_LOCALIZADO", "Não localizado"
        DIVERGENTE = "DIVERGENTE", "Divergente"
        DANIFICADO = "DANIFICADO", "Danificado"

    inventario = models.ForeignKey(InventarioPatrimonial, on_delete=models.CASCADE, related_name="itens")
    bem = models.ForeignKey(BemPatrimonial, on_delete=models.PROTECT, related_name="inventario_itens")
    localizacao_encontrada = models.CharField(max_length=220, blank=True, default="")
    status_conferencia = models.CharField(
        max_length=20,
        choices=StatusConferencia.choices,
        default=StatusConferencia.LOCALIZADO,
    )
    observacao = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Item de inventário patrimonial"
        verbose_name_plural = "Itens de inventário patrimonial"
        constraints = [
            models.UniqueConstraint(
                fields=["inventario", "bem"],
                name="uniq_inventario_item_bem",
            ),
        ]
        indexes = [
            models.Index(fields=["status_conferencia"]),
        ]

    def __str__(self) -> str:
        return f"{self.inventario} • {self.bem}"
