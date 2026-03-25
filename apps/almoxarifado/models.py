from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class AlmoxarifadoCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class UnidadeMedida(models.TextChoices):
        UN = "UN", "Unidade"
        CX = "CX", "Caixa"
        KG = "KG", "Quilo"
        LT = "LT", "Litro"
        MT = "MT", "Metro"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="almoxarifado_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="almoxarifado_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="almoxarifado_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="almoxarifado_cadastros",
        null=True,
        blank=True,
    )
    local_estrutural = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="almoxarifado_cadastros",
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=40)
    nome = models.CharField(max_length=180)
    unidade_medida = models.CharField(max_length=4, choices=UnidadeMedida.choices, default=UnidadeMedida.UN)
    estoque_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo_atual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_medio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Item de estoque"
        verbose_name_plural = "Itens de estoque"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_almoxarifado_cadastro_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["codigo"]),
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


class AlmoxarifadoMovimento(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SAIDA = "SAIDA", "Saída"
        AJUSTE = "AJUSTE", "Ajuste"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="almoxarifado_movimentos")
    item = models.ForeignKey(AlmoxarifadoCadastro, on_delete=models.CASCADE, related_name="movimentos")
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.ENTRADA)
    data_movimento = models.DateField(default=timezone.localdate)
    quantidade = models.DecimalField(max_digits=12, decimal_places=2)
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    documento = models.CharField(max_length=60, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_movimentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Movimento de estoque"
        verbose_name_plural = "Movimentos de estoque"
        ordering = ["-data_movimento", "-id"]
        indexes = [
            models.Index(fields=["municipio", "tipo"]),
            models.Index(fields=["item", "data_movimento"]),
        ]

    def __str__(self):
        return f"{self.item.codigo} • {self.get_tipo_display()} • {self.quantidade}"


class AlmoxarifadoRequisicao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        ATENDIDA = "ATENDIDA", "Atendida"
        CANCELADA = "CANCELADA", "Cancelada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="almoxarifado_requisicoes")
    numero = models.CharField(max_length=40)
    item = models.ForeignKey(AlmoxarifadoCadastro, on_delete=models.PROTECT, related_name="requisicoes")
    secretaria_solicitante = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="almoxarifado_requisicoes",
        null=True,
        blank=True,
    )
    unidade_solicitante = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="almoxarifado_requisicoes",
        null=True,
        blank=True,
    )
    setor_solicitante = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="almoxarifado_requisicoes",
        null=True,
        blank=True,
    )
    local_solicitante = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="almoxarifado_requisicoes_legado",
        null=True,
        blank=True,
    )
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    justificativa = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_requisicoes_aprovadas",
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)
    atendido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_requisicoes_atendidas",
    )
    atendido_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="almoxarifado_requisicoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Requisição de almoxarifado"
        verbose_name_plural = "Requisições de almoxarifado"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_almoxarifado_req_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["item", "status"]),
        ]

    def __str__(self):
        return f"{self.numero} • {self.item.codigo} • {self.get_status_display()}"

    def clean(self):
        errors: dict[str, str] = {}
        if self.secretaria_solicitante_id and self.secretaria_solicitante.municipio_id != self.municipio_id:
            errors["secretaria_solicitante"] = "Secretaria solicitante fora do município selecionado."
        if (
            self.unidade_solicitante_id
            and self.secretaria_solicitante_id
            and self.unidade_solicitante.secretaria_id != self.secretaria_solicitante_id
        ):
            errors["unidade_solicitante"] = "Unidade solicitante deve pertencer à secretaria solicitante."
        if self.setor_solicitante_id and self.unidade_solicitante_id and self.setor_solicitante.unidade_id != self.unidade_solicitante_id:
            errors["setor_solicitante"] = "Setor solicitante deve pertencer à unidade solicitante."
        if self.local_solicitante_id and self.unidade_solicitante_id and self.local_solicitante.unidade_id != self.unidade_solicitante_id:
            errors["local_solicitante"] = "Local solicitante deve pertencer à unidade solicitante."
        if self.item_id and self.item.municipio_id != self.municipio_id:
            errors["item"] = "Item fora do município selecionado."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class AlmoxarifadoLocal(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="almoxarifado_locais")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="almoxarifado_locais",
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="almoxarifado_locais",
    )
    local_estrutural = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="almoxarifado_locais",
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=180)
    tipo = models.CharField(max_length=60, blank=True, default="ALMOXARIFADO")
    responsavel = models.CharField(max_length=180, blank=True, default="")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Local de almoxarifado"
        verbose_name_plural = "Locais de almoxarifado"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidade", "nome"],
                name="uniq_almox_local_unidade_nome",
            )
        ]
        indexes = [
            models.Index(fields=["municipio", "secretaria", "unidade"]),
            models.Index(fields=["ativo"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return self.nome

    def clean(self):
        if self.unidade_id and self.secretaria_id and self.unidade.secretaria_id != self.secretaria_id:
            raise ValidationError({"unidade": "A unidade deve pertencer à secretaria selecionada."})
        if self.secretaria_id and self.municipio_id and self.secretaria.municipio_id != self.municipio_id:
            raise ValidationError({"secretaria": "A secretaria deve pertencer ao município selecionado."})
        if self.local_estrutural_id and self.local_estrutural.unidade_id != self.unidade_id:
            raise ValidationError({"local_estrutural": "O local estrutural deve pertencer à unidade selecionada."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProdutoEstoque(models.Model):
    class UnidadeMedida(models.TextChoices):
        UN = "UN", "Unidade"
        CX = "CX", "Caixa"
        KG = "KG", "Quilo"
        LT = "LT", "Litro"
        MT = "MT", "Metro"
        PCT = "PCT", "Pacote"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="estoque_produtos")
    categoria = models.CharField(max_length=80, blank=True, default="")
    nome = models.CharField(max_length=180)
    descricao = models.TextField(blank=True, default="")
    unidade_medida = models.CharField(max_length=4, choices=UnidadeMedida.choices, default=UnidadeMedida.UN)
    codigo_interno = models.CharField(max_length=40)
    sku = models.CharField(max_length=80, blank=True, default="")
    controla_lote = models.BooleanField(default=False)
    controla_validade = models.BooleanField(default=False)
    estoque_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produto de estoque"
        verbose_name_plural = "Produtos de estoque"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo_interno"], name="uniq_produto_estoque_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "ativo"]),
            models.Index(fields=["nome"]),
            models.Index(fields=["categoria"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo_interno} - {self.nome}"


class EstoqueSaldo(models.Model):
    produto = models.ForeignKey(ProdutoEstoque, on_delete=models.CASCADE, related_name="saldos")
    almoxarifado_local = models.ForeignKey(AlmoxarifadoLocal, on_delete=models.CASCADE, related_name="saldos")
    quantidade_atual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantidade_reservada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantidade_disponivel = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Saldo de estoque"
        verbose_name_plural = "Saldos de estoque"
        constraints = [
            models.UniqueConstraint(
                fields=["produto", "almoxarifado_local"],
                name="uniq_estoque_saldo_produto_local",
            ),
        ]
        indexes = [
            models.Index(fields=["produto", "almoxarifado_local"]),
            models.Index(fields=["quantidade_disponivel"]),
        ]

    def __str__(self) -> str:
        return f"{self.produto} @ {self.almoxarifado_local}"

    def clean(self):
        if self.quantidade_atual < 0:
            raise ValidationError({"quantidade_atual": "Quantidade atual não pode ser negativa."})
        if self.quantidade_reservada < 0:
            raise ValidationError({"quantidade_reservada": "Quantidade reservada não pode ser negativa."})
        if self.quantidade_reservada > self.quantidade_atual:
            raise ValidationError({"quantidade_reservada": "Quantidade reservada não pode exceder a atual."})

    def save(self, *args, **kwargs):
        self.quantidade_disponivel = self.quantidade_atual - self.quantidade_reservada
        self.full_clean()
        super().save(*args, **kwargs)


class MovimentacaoEstoque(models.Model):
    class TipoMovimentacao(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SAIDA = "SAIDA", "Saída"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferência"
        AJUSTE = "AJUSTE", "Ajuste"
        DEVOLUCAO = "DEVOLUCAO", "Devolução"
        PERDA = "PERDA", "Perda"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="estoque_movimentacoes")
    tipo_movimentacao = models.CharField(max_length=20, choices=TipoMovimentacao.choices, default=TipoMovimentacao.ENTRADA)
    produto = models.ForeignKey(ProdutoEstoque, on_delete=models.PROTECT, related_name="movimentacoes")
    almoxarifado_origem = models.ForeignKey(
        AlmoxarifadoLocal,
        on_delete=models.PROTECT,
        related_name="movimentacoes_origem",
        null=True,
        blank=True,
    )
    almoxarifado_destino = models.ForeignKey(
        AlmoxarifadoLocal,
        on_delete=models.PROTECT,
        related_name="movimentacoes_destino",
        null=True,
        blank=True,
    )
    quantidade = models.DecimalField(max_digits=12, decimal_places=2)
    data_movimentacao = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estoque_movimentacoes",
    )
    motivo = models.CharField(max_length=220, blank=True, default="")
    documento_referencia = models.CharField(max_length=80, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimentação de estoque"
        verbose_name_plural = "Movimentações de estoque"
        ordering = ["-data_movimentacao", "-id"]
        indexes = [
            models.Index(fields=["municipio", "tipo_movimentacao"]),
            models.Index(fields=["produto", "data_movimentacao"]),
        ]

    def __str__(self) -> str:
        return f"{self.produto} • {self.get_tipo_movimentacao_display()} • {self.quantidade}"

    def clean(self):
        errors: dict[str, str] = {}
        if self.quantidade <= 0:
            errors["quantidade"] = "Quantidade deve ser maior que zero."

        if self.tipo_movimentacao == self.TipoMovimentacao.TRANSFERENCIA:
            if not self.almoxarifado_origem_id or not self.almoxarifado_destino_id:
                errors["almoxarifado_destino"] = "Transferência exige origem e destino."
            if self.almoxarifado_origem_id and self.almoxarifado_origem_id == self.almoxarifado_destino_id:
                errors["almoxarifado_destino"] = "Origem e destino devem ser diferentes."

        if self.tipo_movimentacao in {self.TipoMovimentacao.SAIDA, self.TipoMovimentacao.PERDA} and not self.almoxarifado_origem_id:
            errors["almoxarifado_origem"] = "Saída/perda exige almoxarifado de origem."
        if self.tipo_movimentacao in {self.TipoMovimentacao.ENTRADA, self.TipoMovimentacao.DEVOLUCAO} and not self.almoxarifado_destino_id:
            errors["almoxarifado_destino"] = "Entrada/devolução exige almoxarifado de destino."

        if self.almoxarifado_origem_id and self.almoxarifado_origem.municipio_id != self.municipio_id:
            errors["almoxarifado_origem"] = "Origem fora do município selecionado."
        if self.almoxarifado_destino_id and self.almoxarifado_destino.municipio_id != self.municipio_id:
            errors["almoxarifado_destino"] = "Destino fora do município selecionado."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RequisicaoEstoque(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        ENVIADA = "ENVIADA", "Enviada"
        APROVADA = "APROVADA", "Aprovada"
        PARCIAL = "PARCIAL", "Parcialmente atendida"
        ATENDIDA = "ATENDIDA", "Atendida"
        CANCELADA = "CANCELADA", "Cancelada"
        RECUSADA = "RECUSADA", "Recusada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="estoque_requisicoes")
    numero = models.CharField(max_length=40)
    secretaria = models.ForeignKey("org.Secretaria", on_delete=models.PROTECT, related_name="estoque_requisicoes")
    unidade_solicitante = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="estoque_requisicoes_solicitadas",
    )
    local_solicitante = models.ForeignKey(
        "org.LocalEstrutural",
        on_delete=models.PROTECT,
        related_name="estoque_requisicoes_solicitadas",
        null=True,
        blank=True,
    )
    produto = models.ForeignKey(ProdutoEstoque, on_delete=models.PROTECT, related_name="requisicoes")
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RASCUNHO)
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estoque_requisicoes_solicitadas",
    )
    aprovador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="estoque_requisicoes_aprovadas",
    )
    data_solicitacao = models.DateTimeField(default=timezone.now)
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Requisição de estoque"
        verbose_name_plural = "Requisições de estoque"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_requisicao_estoque_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["secretaria", "unidade_solicitante"]),
        ]

    def __str__(self) -> str:
        return f"{self.numero} • {self.produto} • {self.get_status_display()}"

    def clean(self):
        errors: dict[str, str] = {}
        if self.secretaria_id and self.secretaria.municipio_id != self.municipio_id:
            errors["secretaria"] = "Secretaria fora do município selecionado."
        if self.unidade_solicitante_id and self.unidade_solicitante.secretaria_id != self.secretaria_id:
            errors["unidade_solicitante"] = "A unidade solicitante deve pertencer à secretaria."
        if self.local_solicitante_id and self.local_solicitante.unidade_id != self.unidade_solicitante_id:
            errors["local_solicitante"] = "O local solicitante deve pertencer à unidade solicitante."
        if self.produto_id and self.produto.municipio_id != self.municipio_id:
            errors["produto"] = "Produto fora do município selecionado."
        if self.quantidade <= 0:
            errors["quantidade"] = "Quantidade deve ser maior que zero."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
