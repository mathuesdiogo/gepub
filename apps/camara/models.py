from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def _current_year() -> int:
    return timezone.localdate().year


def camara_upload_to(instance, filename: str) -> str:
    model_key = instance.__class__.__name__.lower()
    return f"camara/{model_key}/{timezone.now():%Y/%m}/{filename}"


class CamaraScopedModel(models.Model):
    class Contexto(models.TextChoices):
        PREFEITURA = "prefeitura", "Prefeitura"
        CAMARA = "camara", "Câmara"

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        PUBLICADO = "PUBLICADO", "Publicado"
        INATIVO = "INATIVO", "Inativo"
        ARQUIVADO = "ARQUIVADO", "Arquivado"

    municipio = models.ForeignKey(
        "org.Municipio",
        on_delete=models.PROTECT,
        db_column="tenant_id",
        related_name="%(app_label)s_%(class)s_items",
    )
    contexto = models.CharField(max_length=20, choices=Contexto.choices, default=Contexto.CAMARA)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RASCUNHO)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLICADO and not self.published_at:
            self.published_at = timezone.now()
        if self.status != self.Status.PUBLICADO and self.published_at and not kwargs.get("force_insert"):
            pass
        super().save(*args, **kwargs)


class CamaraConfig(CamaraScopedModel):
    nome_portal = models.CharField(max_length=180, default="Portal da Câmara Municipal")
    historia = models.TextField(blank=True, default="")
    missao = models.TextField(blank=True, default="")
    competencias_legislativo = models.TextField(blank=True, default="")
    estrutura_administrativa = models.TextField(blank=True, default="")
    contatos = models.TextField(blank=True, default="")
    endereco = models.CharField(max_length=220, blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    horario_atendimento = models.CharField(max_length=140, blank=True, default="")
    youtube_canal_url = models.URLField(blank=True, default="")
    youtube_live_url = models.URLField(blank=True, default="")
    youtube_playlist_url = models.URLField(blank=True, default="")
    transparencia_url_externa = models.URLField(blank=True, default="")

    class Meta:
        db_table = "camara_config"
        verbose_name = "Configuração da Câmara"
        verbose_name_plural = "Configurações da Câmara"
        ordering = ["municipio__nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio"], name="uniq_camara_config_municipio"),
        ]

    def __str__(self) -> str:
        return f"Configuração Câmara • {self.municipio.nome}"


class Vereador(CamaraScopedModel):
    nome_completo = models.CharField(max_length=180)
    nome_parlamentar = models.CharField(max_length=120, blank=True, default="")
    foto = models.ImageField(upload_to=camara_upload_to, blank=True, null=True)
    partido = models.CharField(max_length=20, blank=True, default="")
    biografia = models.TextField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    mandato_inicio = models.DateField(null=True, blank=True)
    mandato_fim = models.DateField(null=True, blank=True)
    agenda_publica = models.TextField(blank=True, default="")
    redes_sociais = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "vereadores"
        verbose_name = "Vereador"
        verbose_name_plural = "Vereadores"
        ordering = ["nome_completo", "id"]
        indexes = [
            models.Index(fields=["municipio", "status", "nome_completo"]),
            models.Index(fields=["partido"]),
        ]

    def __str__(self) -> str:
        return self.nome_parlamentar or self.nome_completo


class MesaDiretora(CamaraScopedModel):
    class Cargo(models.TextChoices):
        PRESIDENTE = "PRESIDENTE", "Presidente"
        VICE_PRESIDENTE = "VICE_PRESIDENTE", "Vice-presidente"
        PRIMEIRO_SECRETARIO = "PRIMEIRO_SECRETARIO", "1º Secretário"
        SEGUNDO_SECRETARIO = "SEGUNDO_SECRETARIO", "2º Secretário"
        MEMBRO = "MEMBRO", "Membro"

    vereador = models.ForeignKey(
        Vereador,
        on_delete=models.PROTECT,
        related_name="mesa_diretora_cargos",
    )
    cargo = models.CharField(max_length=24, choices=Cargo.choices, default=Cargo.MEMBRO)
    legislatura = models.CharField(max_length=40, blank=True, default="")
    periodo_inicio = models.DateField(null=True, blank=True)
    periodo_fim = models.DateField(null=True, blank=True)
    observacao = models.CharField(max_length=220, blank=True, default="")

    class Meta:
        db_table = "mesa_diretora"
        verbose_name = "Mesa diretora"
        verbose_name_plural = "Mesa diretora"
        ordering = ["-periodo_inicio", "cargo", "id"]
        indexes = [
            models.Index(fields=["municipio", "cargo", "periodo_inicio"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_cargo_display()} • {self.vereador}"


class Comissao(CamaraScopedModel):
    class Tipo(models.TextChoices):
        PERMANENTE = "PERMANENTE", "Permanente"
        TEMPORARIA = "TEMPORARIA", "Temporária"

    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.PERMANENTE)
    nome = models.CharField(max_length=180)
    descricao = models.TextField(blank=True, default="")
    presidente = models.ForeignKey(
        Vereador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comissoes_presididas",
    )
    relator = models.ForeignKey(
        Vereador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comissoes_relatadas",
    )
    periodo_inicio = models.DateField(null=True, blank=True)
    periodo_fim = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "comissoes"
        verbose_name = "Comissão"
        verbose_name_plural = "Comissões"
        ordering = ["nome", "id"]
        indexes = [
            models.Index(fields=["municipio", "tipo", "status"]),
        ]

    def __str__(self) -> str:
        return self.nome


class ComissaoMembro(CamaraScopedModel):
    class Papel(models.TextChoices):
        PRESIDENTE = "PRESIDENTE", "Presidente"
        RELATOR = "RELATOR", "Relator"
        MEMBRO = "MEMBRO", "Membro"
        SUPLENTE = "SUPLENTE", "Suplente"

    comissao = models.ForeignKey(Comissao, on_delete=models.CASCADE, related_name="membros")
    vereador = models.ForeignKey(Vereador, on_delete=models.PROTECT, related_name="vinculos_comissoes")
    papel = models.CharField(max_length=16, choices=Papel.choices, default=Papel.MEMBRO)
    periodo_inicio = models.DateField(null=True, blank=True)
    periodo_fim = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "comissao_membros"
        verbose_name = "Membro da comissão"
        verbose_name_plural = "Membros da comissão"
        ordering = ["comissao__nome", "papel", "vereador__nome_completo"]
        constraints = [
            models.UniqueConstraint(
                fields=["comissao", "vereador", "papel"],
                name="uniq_comissao_membro_papel",
            )
        ]
        indexes = [
            models.Index(fields=["municipio", "comissao", "vereador"]),
        ]

    def __str__(self) -> str:
        return f"{self.comissao} • {self.vereador}"


class Sessao(CamaraScopedModel):
    class Tipo(models.TextChoices):
        ORDINARIA = "ORDINARIA", "Ordinária"
        EXTRAORDINARIA = "EXTRAORDINARIA", "Extraordinária"
        SOLENE = "SOLENE", "Solene"
        AUDIENCIA_PUBLICA = "AUDIENCIA_PUBLICA", "Audiência Pública"

    class Situacao(models.TextChoices):
        AGENDADA = "AGENDADA", "Agendada"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        REALIZADA = "REALIZADA", "Realizada"
        CANCELADA = "CANCELADA", "Cancelada"

    tipo = models.CharField(max_length=18, choices=Tipo.choices, default=Tipo.ORDINARIA)
    numero = models.CharField(max_length=20)
    ano = models.PositiveIntegerField(default=_current_year)
    titulo = models.CharField(max_length=220)
    data_hora = models.DateTimeField(default=timezone.now)
    local = models.CharField(max_length=220, blank=True, default="")
    situacao = models.CharField(max_length=20, choices=Situacao.choices, default=Situacao.AGENDADA)
    ordem_dia = models.TextField(blank=True, default="")
    pauta = models.TextField(blank=True, default="")
    resultado = models.TextField(blank=True, default="")
    presenca_json = models.JSONField(default=list, blank=True)
    link_transmissao = models.URLField(blank=True, default="")

    class Meta:
        db_table = "sessoes"
        verbose_name = "Sessão"
        verbose_name_plural = "Sessões"
        ordering = ["-data_hora", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "tipo", "numero", "ano"],
                name="uniq_sessao_numero_ano",
            )
        ]
        indexes = [
            models.Index(fields=["municipio", "data_hora"]),
            models.Index(fields=["situacao", "data_hora"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.numero}/{self.ano}"


class SessaoDocumento(CamaraScopedModel):
    class Tipo(models.TextChoices):
        PAUTA = "PAUTA", "Pauta"
        ATA = "ATA", "Ata"
        ANEXO = "ANEXO", "Anexo"
        RESULTADO = "RESULTADO", "Resultado"

    sessao = models.ForeignKey(Sessao, on_delete=models.CASCADE, related_name="documentos")
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.ANEXO)
    titulo = models.CharField(max_length=180)
    descricao = models.TextField(blank=True, default="")
    arquivo = models.FileField(upload_to=camara_upload_to, blank=True, null=True)
    link_externo = models.URLField(blank=True, default="")

    class Meta:
        db_table = "sessao_documentos"
        verbose_name = "Documento de sessão"
        verbose_name_plural = "Documentos de sessão"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["municipio", "sessao", "tipo"]),
        ]

    def clean(self):
        super().clean()
        if not self.arquivo and not (self.link_externo or "").strip():
            raise ValidationError({"arquivo": "Anexe um arquivo ou informe um link externo."})

    def __str__(self) -> str:
        return f"{self.sessao} • {self.titulo}"


class Proposicao(CamaraScopedModel):
    class Tipo(models.TextChoices):
        PROJETO_LEI = "PROJETO_LEI", "Projeto de Lei"
        PROJETO_RESOLUCAO = "PROJETO_RESOLUCAO", "Projeto de Resolução"
        REQUERIMENTO = "REQUERIMENTO", "Requerimento"
        INDICACAO = "INDICACAO", "Indicação"
        MOCACAO = "MOCACAO", "Moção"
        EMENDA = "EMENDA", "Emenda"
        DECRETO_LEGISLATIVO = "DECRETO_LEGISLATIVO", "Decreto Legislativo"
        PARECER = "PARECER", "Parecer"
        VETO = "VETO", "Veto"
        OUTRO = "OUTRO", "Outro"

    tipo = models.CharField(max_length=24, choices=Tipo.choices, default=Tipo.OUTRO)
    numero = models.CharField(max_length=20)
    ano = models.PositiveIntegerField(default=_current_year)
    ementa = models.CharField(max_length=220)
    texto_completo = models.TextField(blank=True, default="")
    situacao = models.CharField(max_length=80, blank=True, default="")
    tramitacao_resumo = models.TextField(blank=True, default="")
    comissao = models.ForeignKey(
        Comissao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposicoes",
    )
    sessao = models.ForeignKey(
        Sessao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposicoes",
    )
    arquivo = models.FileField(upload_to=camara_upload_to, blank=True, null=True)
    entrada_em = models.DateField(default=timezone.localdate)

    class Meta:
        db_table = "proposicoes"
        verbose_name = "Proposição"
        verbose_name_plural = "Proposições"
        ordering = ["-ano", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "tipo", "numero", "ano"],
                name="uniq_proposicao_numero_ano",
            )
        ]
        indexes = [
            models.Index(fields=["municipio", "tipo", "situacao"]),
            models.Index(fields=["entrada_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.numero}/{self.ano}"


class ProposicaoAutor(CamaraScopedModel):
    class Papel(models.TextChoices):
        AUTOR = "AUTOR", "Autor"
        COAUTOR = "COAUTOR", "Coautor"
        RELATOR = "RELATOR", "Relator"

    proposicao = models.ForeignKey(Proposicao, on_delete=models.CASCADE, related_name="autores")
    vereador = models.ForeignKey(
        Vereador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposicoes_autoria",
    )
    nome_livre = models.CharField(max_length=180, blank=True, default="")
    papel = models.CharField(max_length=10, choices=Papel.choices, default=Papel.AUTOR)

    class Meta:
        db_table = "proposicao_autores"
        verbose_name = "Autor de proposição"
        verbose_name_plural = "Autores de proposição"
        ordering = ["proposicao", "papel", "id"]
        indexes = [
            models.Index(fields=["municipio", "proposicao", "papel"]),
        ]

    def clean(self):
        super().clean()
        if not self.vereador and not (self.nome_livre or "").strip():
            raise ValidationError({"nome_livre": "Informe um vereador ou autor livre."})

    def __str__(self) -> str:
        return f"{self.proposicao} • {self.vereador or self.nome_livre}"


class ProposicaoTramitacao(CamaraScopedModel):
    proposicao = models.ForeignKey(Proposicao, on_delete=models.CASCADE, related_name="tramitacoes")
    data_evento = models.DateField(default=timezone.localdate)
    etapa = models.CharField(max_length=140)
    descricao = models.TextField(blank=True, default="")
    situacao = models.CharField(max_length=80, blank=True, default="")
    comissao = models.ForeignKey(
        Comissao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tramitacoes_proposicoes",
    )
    sessao = models.ForeignKey(
        Sessao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tramitacoes_proposicoes",
    )
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "proposicao_tramitacoes"
        verbose_name = "Tramitação de proposição"
        verbose_name_plural = "Tramitações de proposição"
        ordering = ["-data_evento", "-ordem", "-id"]
        indexes = [
            models.Index(fields=["municipio", "proposicao", "data_evento"]),
        ]

    def __str__(self) -> str:
        return f"{self.proposicao} • {self.etapa}"


class Ata(CamaraScopedModel):
    sessao = models.ForeignKey(Sessao, on_delete=models.SET_NULL, null=True, blank=True, related_name="atas")
    numero = models.CharField(max_length=20)
    ano = models.PositiveIntegerField(default=_current_year)
    titulo = models.CharField(max_length=220)
    resumo = models.TextField(blank=True, default="")
    arquivo = models.FileField(upload_to=camara_upload_to, blank=True, null=True)
    data_documento = models.DateField(default=timezone.localdate)

    class Meta:
        db_table = "atas"
        verbose_name = "Ata"
        verbose_name_plural = "Atas"
        ordering = ["-data_documento", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero", "ano"], name="uniq_ata_numero_ano"),
        ]
        indexes = [
            models.Index(fields=["municipio", "data_documento"]),
        ]

    def __str__(self) -> str:
        return f"Ata {self.numero}/{self.ano}"


class Pauta(CamaraScopedModel):
    sessao = models.ForeignKey(Sessao, on_delete=models.SET_NULL, null=True, blank=True, related_name="pautas")
    numero = models.CharField(max_length=20)
    ano = models.PositiveIntegerField(default=_current_year)
    titulo = models.CharField(max_length=220)
    descricao = models.TextField(blank=True, default="")
    arquivo = models.FileField(upload_to=camara_upload_to, blank=True, null=True)
    data_documento = models.DateField(default=timezone.localdate)

    class Meta:
        db_table = "pautas"
        verbose_name = "Pauta"
        verbose_name_plural = "Pautas"
        ordering = ["-data_documento", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero", "ano"], name="uniq_pauta_numero_ano"),
        ]
        indexes = [
            models.Index(fields=["municipio", "data_documento"]),
        ]

    def __str__(self) -> str:
        return f"Pauta {self.numero}/{self.ano}"


class NoticiaCamara(CamaraScopedModel):
    class Categoria(models.TextChoices):
        INSTITUCIONAL = "INSTITUCIONAL", "Institucional"
        SESSAO = "SESSAO", "Sessão"
        PROPOSICOES = "PROPOSICOES", "Proposições"
        EVENTO = "EVENTO", "Evento"
        OUTRA = "OUTRA", "Outra"

    titulo = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, blank=True, default="")
    resumo = models.TextField(blank=True, default="")
    conteudo = models.TextField(blank=True, default="")
    categoria = models.CharField(max_length=16, choices=Categoria.choices, default=Categoria.INSTITUCIONAL)
    imagem = models.ImageField(upload_to=camara_upload_to, blank=True, null=True)
    destaque_home = models.BooleanField(default=False)
    autor_nome = models.CharField(max_length=140, blank=True, default="")
    vereador = models.ForeignKey(
        Vereador,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="noticias_relacionadas",
    )
    sessao = models.ForeignKey(
        Sessao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="noticias_relacionadas",
    )

    class Meta:
        db_table = "noticias_camara"
        verbose_name = "Notícia da Câmara"
        verbose_name_plural = "Notícias da Câmara"
        ordering = ["-published_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "slug"], name="uniq_noticia_camara_slug"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status", "published_at"]),
            models.Index(fields=["categoria"]),
        ]

    def save(self, *args, **kwargs):
        base = slugify(self.titulo or "noticia-camara").strip("-") or "noticia-camara"
        if not self.slug:
            self.slug = base
        self.slug = slugify(self.slug).strip("-") or base
        candidate = self.slug[:240]
        qs = type(self).objects.filter(municipio=self.municipio).exclude(pk=self.pk)
        index = 2
        while qs.filter(slug=candidate).exists():
            suffix = f"-{index}"
            candidate = f"{base[: max(1, 240 - len(suffix))]}{suffix}"
            index += 1
        self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.titulo


class AgendaLegislativa(CamaraScopedModel):
    class Tipo(models.TextChoices):
        SESSAO = "SESSAO", "Sessão"
        COMISSAO = "COMISSAO", "Reunião de comissão"
        AUDIENCIA = "AUDIENCIA", "Audiência pública"
        EVENTO = "EVENTO", "Evento institucional"

    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.EVENTO)
    titulo = models.CharField(max_length=220)
    descricao = models.TextField(blank=True, default="")
    inicio = models.DateTimeField(default=timezone.now)
    fim = models.DateTimeField(null=True, blank=True)
    local = models.CharField(max_length=180, blank=True, default="")
    sessao = models.ForeignKey(
        Sessao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agenda_itens",
    )
    comissao = models.ForeignKey(
        Comissao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agenda_itens",
    )

    class Meta:
        db_table = "agenda_legislativa"
        verbose_name = "Agenda legislativa"
        verbose_name_plural = "Agenda legislativa"
        ordering = ["inicio", "id"]
        indexes = [
            models.Index(fields=["municipio", "inicio"]),
            models.Index(fields=["tipo", "inicio"]),
        ]

    def __str__(self) -> str:
        return self.titulo


class Transmissao(CamaraScopedModel):
    class StatusTransmissao(models.TextChoices):
        PROGRAMADA = "PROGRAMADA", "Programada"
        AO_VIVO = "AO_VIVO", "Ao vivo"
        ENCERRADA = "ENCERRADA", "Encerrada"

    titulo = models.CharField(max_length=220)
    canal_url = models.URLField(blank=True, default="")
    live_url = models.URLField(blank=True, default="")
    playlist_url = models.URLField(blank=True, default="")
    status_transmissao = models.CharField(
        max_length=12,
        choices=StatusTransmissao.choices,
        default=StatusTransmissao.PROGRAMADA,
    )
    inicio_previsto = models.DateTimeField(null=True, blank=True)
    inicio_real = models.DateTimeField(null=True, blank=True)
    fim_real = models.DateTimeField(null=True, blank=True)
    sessao = models.ForeignKey(
        Sessao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transmissoes",
    )
    destaque_home = models.BooleanField(default=False)

    class Meta:
        db_table = "transmissoes"
        verbose_name = "Transmissão"
        verbose_name_plural = "Transmissões"
        ordering = ["-inicio_previsto", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status_transmissao", "inicio_previsto"]),
        ]

    def __str__(self) -> str:
        return self.titulo


class TransparenciaCamaraItem(CamaraScopedModel):
    class Categoria(models.TextChoices):
        DESPESAS = "DESPESAS", "Despesas"
        CONTRATOS = "CONTRATOS", "Contratos"
        LICITACOES = "LICITACOES", "Licitações"
        DIARIAS = "DIARIAS", "Diárias"
        FOLHA = "FOLHA", "Folha"
        ESTRUTURA = "ESTRUTURA", "Estrutura administrativa"
        ATOS = "ATOS", "Atos oficiais"
        RELATORIOS = "RELATORIOS", "Relatórios"
        OUTROS = "OUTROS", "Outros"

    class Formato(models.TextChoices):
        PDF = "PDF", "PDF"
        CSV = "CSV", "CSV"
        XLSX = "XLSX", "XLSX"
        JSON = "JSON", "JSON"
        LINK = "LINK", "Link"

    categoria = models.CharField(max_length=16, choices=Categoria.choices, default=Categoria.OUTROS)
    titulo = models.CharField(max_length=220)
    descricao = models.TextField(blank=True, default="")
    competencia = models.CharField(max_length=7, blank=True, default="")
    data_referencia = models.DateField(null=True, blank=True)
    valor = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    formato = models.CharField(max_length=10, choices=Formato.choices, default=Formato.PDF)
    arquivo = models.FileField(upload_to=camara_upload_to, blank=True, null=True)
    link_externo = models.URLField(blank=True, default="")
    dados = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "transparencia_camara_items"
        verbose_name = "Item de transparência da Câmara"
        verbose_name_plural = "Itens de transparência da Câmara"
        ordering = ["categoria", "-published_at", "-id"]
        indexes = [
            models.Index(fields=["municipio", "categoria", "status"]),
            models.Index(fields=["competencia"]),
        ]

    def clean(self):
        super().clean()
        if self.formato == self.Formato.LINK and not (self.link_externo or "").strip():
            raise ValidationError({"link_externo": "Informe o link externo para formato LINK."})
        if self.formato != self.Formato.LINK and not self.arquivo and not self.pk:
            raise ValidationError({"arquivo": "Anexe um arquivo para este item."})

    def __str__(self) -> str:
        return f"{self.get_categoria_display()} • {self.titulo}"


class DocumentoCamara(CamaraScopedModel):
    class Categoria(models.TextChoices):
        ATA = "ATA", "Ata"
        PAUTA = "PAUTA", "Pauta"
        EDITAL = "EDITAL", "Edital"
        PORTARIA = "PORTARIA", "Portaria"
        RESOLUCAO = "RESOLUCAO", "Resolução"
        ADMINISTRATIVO = "ADMINISTRATIVO", "Administrativo"
        OUTRO = "OUTRO", "Outro"

    class Formato(models.TextChoices):
        PDF = "PDF", "PDF"
        CSV = "CSV", "CSV"
        XLSX = "XLSX", "XLSX"
        JSON = "JSON", "JSON"
        LINK = "LINK", "Link"

    categoria = models.CharField(max_length=16, choices=Categoria.choices, default=Categoria.OUTRO)
    titulo = models.CharField(max_length=220)
    descricao = models.TextField(blank=True, default="")
    data_documento = models.DateField(default=timezone.localdate)
    formato = models.CharField(max_length=10, choices=Formato.choices, default=Formato.PDF)
    arquivo = models.FileField(upload_to=camara_upload_to, blank=True, null=True)
    link_externo = models.URLField(blank=True, default="")

    class Meta:
        db_table = "documentos_camara"
        verbose_name = "Documento da Câmara"
        verbose_name_plural = "Documentos da Câmara"
        ordering = ["-data_documento", "-id"]
        indexes = [
            models.Index(fields=["municipio", "categoria", "data_documento"]),
        ]

    def clean(self):
        super().clean()
        if self.formato == self.Formato.LINK and not (self.link_externo or "").strip():
            raise ValidationError({"link_externo": "Informe o link externo para formato LINK."})
        if self.formato != self.Formato.LINK and not self.arquivo and not self.pk:
            raise ValidationError({"arquivo": "Anexe um arquivo para o documento."})

    def __str__(self) -> str:
        return self.titulo


class CamaraOuvidoriaManifestacao(CamaraScopedModel):
    class Tipo(models.TextChoices):
        CONTATO = "CONTATO", "Contato"
        SOLICITACAO = "SOLICITACAO", "Solicitação"
        PEDIDO_INFORMACAO = "PEDIDO_INFORMACAO", "Pedido de informação"
        DENUNCIA = "DENUNCIA", "Denúncia"

    class StatusAtendimento(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        RESPONDIDO = "RESPONDIDO", "Respondido"
        ENCERRADO = "ENCERRADO", "Encerrado"

    protocolo = models.CharField(max_length=40)
    tipo = models.CharField(max_length=18, choices=Tipo.choices, default=Tipo.CONTATO)
    assunto = models.CharField(max_length=180)
    mensagem = models.TextField()
    solicitante_nome = models.CharField(max_length=180)
    solicitante_email = models.EmailField(blank=True, default="")
    solicitante_telefone = models.CharField(max_length=40, blank=True, default="")
    status_atendimento = models.CharField(
        max_length=16,
        choices=StatusAtendimento.choices,
        default=StatusAtendimento.ABERTO,
    )
    resposta = models.TextField(blank=True, default="")
    respondido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "camara_ouvidoria_manifestacoes"
        verbose_name = "Manifestação da ouvidoria da Câmara"
        verbose_name_plural = "Manifestações da ouvidoria da Câmara"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "protocolo"], name="uniq_camara_ouvidoria_protocolo"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status_atendimento", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.protocolo} • {self.assunto}"
