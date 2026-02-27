from __future__ import annotations

from django.conf import settings
from django.db import models


class Dataset(models.Model):
    class Fonte(models.TextChoices):
        CSV = "CSV", "CSV"
        XLSX = "XLSX", "Excel (.xlsx)"
        GOOGLE_SHEETS = "GOOGLE_SHEETS", "Google Sheets"
        PDF = "PDF", "PDF"
        DOCX = "DOCX", "Word (.docx)"

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        VALIDADO = "VALIDADO", "Validado"
        PUBLICADO = "PUBLICADO", "Publicado"
        ARQUIVADO = "ARQUIVADO", "Arquivado"

    class Visibilidade(models.TextChoices):
        INTERNO = "INTERNO", "Interno"
        PUBLICO = "PUBLICO", "Público"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="bi_datasets")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="bi_datasets",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="bi_datasets",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="bi_datasets",
        null=True,
        blank=True,
    )

    nome = models.CharField(max_length=180)
    descricao = models.TextField(blank=True, default="")
    categoria = models.CharField(max_length=80, blank=True, default="")
    fonte = models.CharField(max_length=20, choices=Fonte.choices, default=Fonte.CSV)
    visibilidade = models.CharField(max_length=12, choices=Visibilidade.choices, default=Visibilidade.INTERNO)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RASCUNHO)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_datasets_criados",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_datasets_atualizados",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dataset BI"
        verbose_name_plural = "Datasets BI"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status", "criado_em"]),
            models.Index(fields=["categoria"]),
            models.Index(fields=["visibilidade"]),
        ]

    def __str__(self) -> str:
        return self.nome


class DatasetVersion(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PROCESSANDO = "PROCESSANDO", "Processando"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        ERRO = "ERRO", "Erro"

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="versoes")
    numero = models.PositiveIntegerField(default=1)
    fonte = models.CharField(max_length=20, choices=Dataset.Fonte.choices, default=Dataset.Fonte.CSV)

    arquivo_original = models.FileField(upload_to="paineis/original/%Y/%m/", blank=True, null=True)
    arquivo_tratado = models.FileField(upload_to="paineis/tratado/%Y/%m/", blank=True, null=True)

    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDENTE)
    schema_json = models.JSONField(default=dict, blank=True)
    profile_json = models.JSONField(default=dict, blank=True)
    preview_json = models.JSONField(default=list, blank=True)
    logs = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_versoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    processado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Versão do dataset"
        verbose_name_plural = "Versões do dataset"
        ordering = ["-numero", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["dataset", "numero"], name="uniq_bi_dataset_versao"),
        ]
        indexes = [
            models.Index(fields=["dataset", "status", "criado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.nome} • v{self.numero}"


class DatasetColumn(models.Model):
    class Tipo(models.TextChoices):
        TEXTO = "TEXTO", "Texto"
        NUMERO = "NUMERO", "Número"
        DATA = "DATA", "Data"
        BOOLEANO = "BOOLEANO", "Booleano"

    class Papel(models.TextChoices):
        DIMENSAO = "DIMENSAO", "Dimensão"
        MEDIDA = "MEDIDA", "Medida"

    versao = models.ForeignKey(DatasetVersion, on_delete=models.CASCADE, related_name="colunas")
    nome = models.CharField(max_length=140)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.TEXTO)
    papel = models.CharField(max_length=12, choices=Papel.choices, default=Papel.DIMENSAO)
    sensivel = models.BooleanField(default=False)
    obrigatoria = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=1)
    amostra = models.CharField(max_length=140, blank=True, default="")

    class Meta:
        verbose_name = "Coluna do dataset"
        verbose_name_plural = "Colunas do dataset"
        ordering = ["ordem", "id"]
        constraints = [
            models.UniqueConstraint(fields=["versao", "nome"], name="uniq_bi_versao_coluna"),
        ]
        indexes = [
            models.Index(fields=["versao", "papel"]),
            models.Index(fields=["sensivel"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.get_tipo_display()})"


class Dashboard(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="dashboards")
    nome = models.CharField(max_length=160)
    descricao = models.TextField(blank=True, default="")
    tema = models.CharField(max_length=40, default="institucional")
    layout_json = models.JSONField(default=dict, blank=True)
    ativo = models.BooleanField(default=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_dashboards_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dashboard BI"
        verbose_name_plural = "Dashboards BI"
        ordering = ["-atualizado_em", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["dataset", "nome"], name="uniq_bi_dataset_dashboard_nome"),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.nome} • {self.nome}"


class Chart(models.Model):
    class Tipo(models.TextChoices):
        KPI = "KPI", "KPI"
        LINHA = "LINHA", "Série temporal"
        BARRA = "BARRA", "Barras"
        TABELA = "TABELA", "Tabela"
        PIZZA = "PIZZA", "Pizza"

    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="graficos")
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.KPI)
    titulo = models.CharField(max_length=140)
    ordem = models.PositiveIntegerField(default=1)
    config_json = models.JSONField(default=dict, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Gráfico"
        verbose_name_plural = "Gráficos"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return f"{self.dashboard.nome} • {self.titulo}"


class QueryCache(models.Model):
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="query_cache")
    chave = models.CharField(max_length=120)
    parametros_json = models.JSONField(default=dict, blank=True)
    resultado_json = models.JSONField(default=dict, blank=True)
    hits = models.PositiveIntegerField(default=0)
    expira_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cache de consulta BI"
        verbose_name_plural = "Cache de consultas BI"
        ordering = ["-criado_em", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["dataset", "chave"], name="uniq_bi_query_cache_chave"),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.nome} • {self.chave}"


class ExportJob(models.Model):
    class Formato(models.TextChoices):
        PDF = "PDF", "PDF"
        PNG = "PNG", "PNG"
        CSV = "CSV", "CSV"
        ZIP = "ZIP", "Pacote ZIP"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        PROCESSANDO = "PROCESSANDO", "Processando"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        ERRO = "ERRO", "Erro"

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="exports")
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exports",
    )
    formato = models.CharField(max_length=10, choices=Formato.choices, default=Formato.PDF)
    filtros_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDENTE)
    arquivo = models.FileField(upload_to="paineis/exports/%Y/%m/", blank=True, null=True)
    log = models.TextField(blank=True, default="")

    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bi_exports_solicitados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Exportação BI"
        verbose_name_plural = "Exportações BI"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["dataset", "status", "criado_em"]),
            models.Index(fields=["formato", "criado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.nome} • {self.formato} • {self.status}"
