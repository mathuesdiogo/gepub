from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class FinanceiroExercicio(models.Model):
    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        ENCERRADO = "ENCERRADO", "Encerrado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="financeiro_exercicios")
    ano = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ABERTO)
    inicio_em = models.DateField(default=timezone.localdate)
    fim_em = models.DateField(null=True, blank=True)
    fechamento_mensal_ate = models.PositiveSmallIntegerField(default=0)
    observacoes = models.TextField(blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Exercício financeiro"
        verbose_name_plural = "Exercícios financeiros"
        ordering = ["-ano", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "ano"], name="uniq_fin_exercicio_municipio_ano"),
        ]
        indexes = [
            models.Index(fields=["municipio", "ano"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.municipio} • {self.ano}"


class FinanceiroUnidadeGestora(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="financeiro_ugs")
    codigo = models.CharField(max_length=20)
    nome = models.CharField(max_length=180)

    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="financeiro_ugs",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="financeiro_ugs",
        null=True,
        blank=True,
    )

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unidade gestora"
        verbose_name_plural = "Unidades gestoras"
        ordering = ["codigo", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_fin_ug_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "ativo"]),
            models.Index(fields=["codigo"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} • {self.nome}"


class FinanceiroContaBancaria(models.Model):
    class TipoConta(models.TextChoices):
        MOVIMENTO = "MOVIMENTO", "Movimento"
        VINCULADA = "VINCULADA", "Vinculada"
        APLICACAO = "APLICACAO", "Aplicação"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="financeiro_contas")
    unidade_gestora = models.ForeignKey(
        FinanceiroUnidadeGestora,
        on_delete=models.PROTECT,
        related_name="contas_bancarias",
    )

    banco_codigo = models.CharField(max_length=10, blank=True, default="")
    banco_nome = models.CharField(max_length=120)
    agencia = models.CharField(max_length=20)
    conta = models.CharField(max_length=30)
    tipo_conta = models.CharField(max_length=12, choices=TipoConta.choices, default=TipoConta.MOVIMENTO)

    saldo_atual = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conta bancária"
        verbose_name_plural = "Contas bancárias"
        ordering = ["banco_nome", "agencia", "conta"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidade_gestora", "banco_codigo", "agencia", "conta"],
                name="uniq_fin_conta_ug_banco_agencia_conta",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "ativo"]),
            models.Index(fields=["banco_codigo", "agencia", "conta"]),
        ]

    def __str__(self) -> str:
        return f"{self.banco_nome} {self.agencia}/{self.conta}"


class OrcFonteRecurso(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="orc_fontes")
    codigo = models.CharField(max_length=20)
    nome = models.CharField(max_length=180)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fonte de recurso"
        verbose_name_plural = "Fontes de recurso"
        ordering = ["codigo", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_fin_fonte_municipio_codigo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} • {self.nome}"


class OrcDotacao(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="orc_dotacoes")
    exercicio = models.ForeignKey(FinanceiroExercicio, on_delete=models.PROTECT, related_name="dotacoes")
    unidade_gestora = models.ForeignKey(FinanceiroUnidadeGestora, on_delete=models.PROTECT, related_name="dotacoes")

    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="orc_dotacoes",
        null=True,
        blank=True,
    )

    programa_codigo = models.CharField(max_length=30)
    programa_nome = models.CharField(max_length=180)
    acao_codigo = models.CharField(max_length=30)
    acao_nome = models.CharField(max_length=180)
    elemento_despesa = models.CharField(max_length=30)
    fonte = models.ForeignKey(OrcFonteRecurso, on_delete=models.PROTECT, related_name="dotacoes")

    valor_inicial = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    valor_atualizado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    valor_empenhado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    valor_liquidado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    valor_pago = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dotação orçamentária"
        verbose_name_plural = "Dotações orçamentárias"
        ordering = ["-exercicio__ano", "programa_codigo", "acao_codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "exercicio",
                    "unidade_gestora",
                    "programa_codigo",
                    "acao_codigo",
                    "elemento_despesa",
                    "fonte",
                ],
                name="uniq_fin_dotacao_chave_orc",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "exercicio"]),
            models.Index(fields=["ativo"]),
        ]

    @property
    def saldo_disponivel(self) -> Decimal:
        return (self.valor_atualizado - self.valor_empenhado).quantize(Decimal("0.01"))

    def __str__(self) -> str:
        return f"{self.exercicio.ano} • {self.programa_codigo}/{self.acao_codigo}"


class OrcCreditoAdicional(models.Model):
    class Tipo(models.TextChoices):
        SUPLEMENTAR = "SUPLEMENTAR", "Suplementar"
        ESPECIAL = "ESPECIAL", "Especial"
        EXTRAORDINARIO = "EXTRAORDINARIO", "Extraordinário"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="orc_creditos_adicionais")
    exercicio = models.ForeignKey(FinanceiroExercicio, on_delete=models.PROTECT, related_name="creditos_adicionais")
    dotacao = models.ForeignKey(OrcDotacao, on_delete=models.PROTECT, related_name="creditos_adicionais")

    tipo = models.CharField(max_length=16, choices=Tipo.choices, default=Tipo.SUPLEMENTAR)
    numero_ato = models.CharField(max_length=60)
    data_ato = models.DateField(default=timezone.localdate)
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    origem_recurso = models.CharField(max_length=180, blank=True, default="")
    descricao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="creditos_adicionais_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Crédito adicional"
        verbose_name_plural = "Créditos adicionais"
        ordering = ["-data_ato", "-id"]
        indexes = [
            models.Index(fields=["municipio", "exercicio", "data_ato"]),
            models.Index(fields=["tipo", "data_ato"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} • {self.numero_ato}"


class DespEmpenho(models.Model):
    class Tipo(models.TextChoices):
        ORDINARIO = "ORDINARIO", "Ordinário"
        GLOBAL = "GLOBAL", "Global"
        ESTIMATIVO = "ESTIMATIVO", "Estimativo"

    class Status(models.TextChoices):
        EMPENHADO = "EMPENHADO", "Empenhado"
        LIQUIDADO = "LIQUIDADO", "Liquidado"
        PAGO = "PAGO", "Pago"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="desp_empenhos")
    exercicio = models.ForeignKey(FinanceiroExercicio, on_delete=models.PROTECT, related_name="empenhos")
    unidade_gestora = models.ForeignKey(FinanceiroUnidadeGestora, on_delete=models.PROTECT, related_name="empenhos")
    dotacao = models.ForeignKey(OrcDotacao, on_delete=models.PROTECT, related_name="empenhos")

    numero = models.CharField(max_length=40)
    data_empenho = models.DateField(default=timezone.localdate)

    fornecedor_nome = models.CharField(max_length=180)
    fornecedor_documento = models.CharField(max_length=30, blank=True, default="")
    objeto = models.TextField(blank=True, default="")

    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.ORDINARIO)
    valor_empenhado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    valor_liquidado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    valor_pago = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EMPENHADO)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empenhos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empenho"
        verbose_name_plural = "Empenhos"
        ordering = ["-data_empenho", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["exercicio", "numero"], name="uniq_fin_empenho_exercicio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "exercicio"]),
            models.Index(fields=["status", "data_empenho"]),
        ]

    @property
    def saldo_a_liquidar(self) -> Decimal:
        return (self.valor_empenhado - self.valor_liquidado).quantize(Decimal("0.01"))

    @property
    def saldo_a_pagar(self) -> Decimal:
        return (self.valor_liquidado - self.valor_pago).quantize(Decimal("0.01"))

    def __str__(self) -> str:
        return f"Empenho {self.numero}/{self.exercicio.ano}"


class DespLiquidacao(models.Model):
    empenho = models.ForeignKey(DespEmpenho, on_delete=models.CASCADE, related_name="liquidacoes")
    numero = models.CharField(max_length=40)
    data_liquidacao = models.DateField(default=timezone.localdate)
    documento_fiscal = models.CharField(max_length=60, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    valor_liquidado = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liquidacoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Liquidação"
        verbose_name_plural = "Liquidações"
        ordering = ["-data_liquidacao", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["empenho", "numero"], name="uniq_fin_liquidacao_empenho_numero"),
        ]

    def __str__(self) -> str:
        return f"Liquidação {self.numero} • {self.empenho.numero}"


class DespPagamento(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PAGO = "PAGO", "Pago"
        ESTORNADO = "ESTORNADO", "Estornado"

    liquidacao = models.ForeignKey(DespLiquidacao, on_delete=models.CASCADE, related_name="pagamentos")
    conta_bancaria = models.ForeignKey(
        FinanceiroContaBancaria,
        on_delete=models.PROTECT,
        related_name="pagamentos",
        null=True,
        blank=True,
    )

    ordem_pagamento = models.CharField(max_length=60, blank=True, default="")
    data_pagamento = models.DateField(default=timezone.localdate)
    valor_pago = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PAGO)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagamentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        ordering = ["-data_pagamento", "-id"]

    def __str__(self) -> str:
        return f"Pagamento {self.valor_pago} • {self.liquidacao.numero}"


class DespRestosPagar(models.Model):
    class Tipo(models.TextChoices):
        PROCESSADO = "PROCESSADO", "Processado"
        NAO_PROCESSADO = "NAO_PROCESSADO", "Não processado"

    class Status(models.TextChoices):
        INSCRITO = "INSCRITO", "Inscrito"
        PARCIAL = "PARCIAL", "Pago parcialmente"
        PAGO = "PAGO", "Pago"
        CANCELADO = "CANCELADO", "Cancelado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="desp_restos_pagar")
    exercicio_origem = models.ForeignKey(FinanceiroExercicio, on_delete=models.PROTECT, related_name="restos_origem")
    exercicio_inscricao = models.ForeignKey(FinanceiroExercicio, on_delete=models.PROTECT, related_name="restos_inscricao")
    empenho = models.ForeignKey(DespEmpenho, on_delete=models.PROTECT, related_name="restos_pagar")

    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.PROCESSADO)
    numero_inscricao = models.CharField(max_length=40)
    data_inscricao = models.DateField(default=timezone.localdate)
    valor_inscrito = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    valor_pago = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INSCRITO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restos_pagar_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Restos a pagar"
        verbose_name_plural = "Restos a pagar"
        ordering = ["-data_inscricao", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["exercicio_inscricao", "numero_inscricao"],
                name="uniq_fin_restos_exercicio_numero_inscricao",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "exercicio_inscricao", "status"]),
            models.Index(fields=["empenho", "status"]),
        ]

    @property
    def saldo_a_pagar(self) -> Decimal:
        return (self.valor_inscrito - self.valor_pago).quantize(Decimal("0.01"))

    def __str__(self) -> str:
        return f"RP {self.numero_inscricao} • {self.empenho.numero}"


class DespPagamentoResto(models.Model):
    class Status(models.TextChoices):
        PAGO = "PAGO", "Pago"
        ESTORNADO = "ESTORNADO", "Estornado"

    resto = models.ForeignKey(DespRestosPagar, on_delete=models.CASCADE, related_name="pagamentos")
    conta_bancaria = models.ForeignKey(
        FinanceiroContaBancaria,
        on_delete=models.PROTECT,
        related_name="pagamentos_restos",
        null=True,
        blank=True,
    )
    ordem_pagamento = models.CharField(max_length=60, blank=True, default="")
    data_pagamento = models.DateField(default=timezone.localdate)
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PAGO)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagamentos_restos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pagamento de resto a pagar"
        verbose_name_plural = "Pagamentos de restos a pagar"
        ordering = ["-data_pagamento", "-id"]
        indexes = [
            models.Index(fields=["status", "data_pagamento"]),
        ]

    def __str__(self) -> str:
        return f"Pagamento RP {self.valor} • {self.resto.numero_inscricao}"


class TesExtratoImportacao(models.Model):
    class Formato(models.TextChoices):
        CSV = "CSV", "CSV"
        OFX = "OFX", "OFX"

    class Status(models.TextChoices):
        PROCESSADA = "PROCESSADA", "Processada"
        FALHA = "FALHA", "Falha"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="tes_extrato_importacoes")
    exercicio = models.ForeignKey(FinanceiroExercicio, on_delete=models.PROTECT, related_name="extrato_importacoes")
    conta_bancaria = models.ForeignKey(
        FinanceiroContaBancaria,
        on_delete=models.PROTECT,
        related_name="extrato_importacoes",
    )

    formato = models.CharField(max_length=8, choices=Formato.choices, default=Formato.CSV)
    arquivo_nome = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROCESSADA)
    observacao = models.TextField(blank=True, default="")

    periodo_inicio = models.DateField(null=True, blank=True)
    periodo_fim = models.DateField(null=True, blank=True)
    total_itens = models.PositiveIntegerField(default=0)
    total_creditos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_debitos = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extratos_importados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Importação de extrato"
        verbose_name_plural = "Importações de extrato"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "exercicio", "criado_em"]),
            models.Index(fields=["conta_bancaria", "status"]),
        ]

    def __str__(self) -> str:
        return f"Extrato {self.formato} • {self.conta_bancaria} • {self.criado_em:%d/%m/%Y}"


class TesExtratoItem(models.Model):
    importacao = models.ForeignKey(TesExtratoImportacao, on_delete=models.CASCADE, related_name="itens")
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="tes_extrato_itens")
    conta_bancaria = models.ForeignKey(
        FinanceiroContaBancaria,
        on_delete=models.PROTECT,
        related_name="extrato_itens",
    )

    data_movimento = models.DateField()
    documento = models.CharField(max_length=80, blank=True, default="")
    historico = models.CharField(max_length=255, blank=True, default="")
    identificador_externo = models.CharField(max_length=120, blank=True, default="")
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    saldo_informado = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Item de extrato"
        verbose_name_plural = "Itens de extrato"
        ordering = ["data_movimento", "id"]
        indexes = [
            models.Index(fields=["importacao", "data_movimento"]),
            models.Index(fields=["conta_bancaria", "valor"]),
            models.Index(fields=["municipio", "data_movimento"]),
        ]

    @property
    def tipo_movimento(self) -> str:
        if self.valor < 0:
            return "DÉBITO"
        if self.valor > 0:
            return "CRÉDITO"
        return "NEUTRO"

    def __str__(self) -> str:
        return f"{self.data_movimento:%d/%m/%Y} • {self.valor}"


class RecConciliacaoItem(models.Model):
    class ReferenciaTipo(models.TextChoices):
        RECEITA = "RECEITA", "Receita"
        PAGAMENTO = "PAGAMENTO", "Pagamento"
        PAGAMENTO_RP = "PAGAMENTO_RP", "Pagamento RP"
        AJUSTE = "AJUSTE", "Ajuste manual"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="conciliacoes_extrato")
    extrato_item = models.OneToOneField(TesExtratoItem, on_delete=models.CASCADE, related_name="conciliacao")
    referencia_tipo = models.CharField(max_length=16, choices=ReferenciaTipo.choices)

    receita = models.ForeignKey(
        "financeiro.RecArrecadacao",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="conciliacoes_extrato",
    )
    desp_pagamento = models.ForeignKey(
        "financeiro.DespPagamento",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="conciliacoes_extrato",
    )
    desp_pagamento_resto = models.ForeignKey(
        "financeiro.DespPagamentoResto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="conciliacoes_extrato",
    )
    observacao = models.CharField(max_length=200, blank=True, default="")

    conciliado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conciliacoes_realizadas",
    )
    conciliado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Conciliação de extrato"
        verbose_name_plural = "Conciliações de extrato"
        ordering = ["-conciliado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "referencia_tipo", "conciliado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_referencia_tipo_display()} • Item {self.extrato_item_id}"


class RecArrecadacao(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rec_arrecadacoes")
    exercicio = models.ForeignKey(FinanceiroExercicio, on_delete=models.PROTECT, related_name="arrecadacoes")
    unidade_gestora = models.ForeignKey(FinanceiroUnidadeGestora, on_delete=models.PROTECT, related_name="arrecadacoes")
    conta_bancaria = models.ForeignKey(
        FinanceiroContaBancaria,
        on_delete=models.PROTECT,
        related_name="arrecadacoes",
        null=True,
        blank=True,
    )

    data_arrecadacao = models.DateField(default=timezone.localdate)
    rubrica_codigo = models.CharField(max_length=30)
    rubrica_nome = models.CharField(max_length=180)
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    documento = models.CharField(max_length=60, blank=True, default="")
    origem = models.CharField(max_length=180, blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="arrecadacoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Arrecadação"
        verbose_name_plural = "Arrecadações"
        ordering = ["-data_arrecadacao", "-id"]
        indexes = [
            models.Index(fields=["municipio", "exercicio", "data_arrecadacao"]),
        ]

    def __str__(self) -> str:
        return f"Receita {self.rubrica_codigo} • {self.valor}"


class FinanceiroLogEvento(models.Model):
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="financeiro_logs")
    evento = models.CharField(max_length=60)
    entidade = models.CharField(max_length=60)
    entidade_id = models.CharField(max_length=40)
    antes = models.JSONField(default=dict, blank=True)
    depois = models.JSONField(default=dict, blank=True)
    observacao = models.CharField(max_length=200, blank=True, default="")

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financeiro_logs",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log financeiro"
        verbose_name_plural = "Logs financeiros"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "evento", "criado_em"]),
            models.Index(fields=["entidade", "entidade_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.evento} • {self.entidade}#{self.entidade_id}"
