from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class BeneficioTipo(models.Model):
    class Area(models.TextChoices):
        EDUCACAO = "EDUCACAO", "Educação"
        SAUDE = "SAUDE", "Saúde"
        ASSISTENCIA = "ASSISTENCIA", "Assistência Social"
        ESPORTE = "ESPORTE", "Esporte"
        OUTRA = "OUTRA", "Outra"

    class Categoria(models.TextChoices):
        KIT_ESCOLAR = "KIT_ESCOLAR", "Kit escolar"
        CESTA_BASICA = "CESTA_BASICA", "Cesta básica"
        UNIFORME = "UNIFORME", "Uniforme"
        EQUIPAMENTO = "EQUIPAMENTO", "Equipamento"
        ALIMENTACAO = "ALIMENTACAO", "Alimentação"
        TRANSPORTE = "TRANSPORTE", "Transporte"
        OUTRO = "OUTRO", "Outro"

    class Periodicidade(models.TextChoices):
        UNICA = "UNICA", "Única"
        MENSAL = "MENSAL", "Mensal"
        BIMESTRAL = "BIMESTRAL", "Bimestral"
        ANUAL = "ANUAL", "Anual"
        SOB_DEMANDA = "SOB_DEMANDA", "Sob demanda"

    class PublicoAlvo(models.TextChoices):
        INFANTIL = "INFANTIL", "Infantil"
        FUNDAMENTAL = "FUNDAMENTAL", "Fundamental"
        EJA = "EJA", "EJA"
        PROGRAMAS = "PROGRAMAS", "Programas"
        NEE = "NEE", "NEE"
        TODOS = "TODOS", "Todos"

    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="beneficios_tipos")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="beneficios_tipos",
        null=True,
        blank=True,
    )
    area = models.CharField(max_length=20, choices=Area.choices, default=Area.EDUCACAO, db_index=True)
    nome = models.CharField(max_length=180)
    categoria = models.CharField(max_length=24, choices=Categoria.choices, default=Categoria.KIT_ESCOLAR)
    publico_alvo = models.CharField(max_length=20, choices=PublicoAlvo.choices, default=PublicoAlvo.TODOS)
    periodicidade = models.CharField(max_length=20, choices=Periodicidade.choices, default=Periodicidade.UNICA)
    elegibilidade_json = models.JSONField(default=dict, blank=True)
    exige_assinatura = models.BooleanField(default=False)
    exige_foto = models.BooleanField(default=False)
    exige_justificativa = models.BooleanField(default=False)
    permite_segunda_via = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO, db_index=True)
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_tipos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tipo de benefício"
        verbose_name_plural = "Tipos de benefício"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["municipio", "area", "nome"],
                name="uniq_beneficio_tipo_nome_municipio_area",
            )
        ]
        indexes = [
            models.Index(fields=["municipio", "area", "status"]),
            models.Index(fields=["categoria"]),
            models.Index(fields=["publico_alvo"]),
        ]

    def __str__(self) -> str:
        return self.nome


class BeneficioTipoItem(models.Model):
    beneficio = models.ForeignKey(BeneficioTipo, on_delete=models.CASCADE, related_name="itens")
    item_estoque = models.ForeignKey(
        "almoxarifado.AlmoxarifadoCadastro",
        on_delete=models.PROTECT,
        related_name="beneficios_composicao",
        null=True,
        blank=True,
    )
    item_manual = models.CharField(max_length=180, blank=True, default="")
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unidade = models.CharField(max_length=20, blank=True, default="UN")
    permite_substituicao = models.BooleanField(default=False)
    observacao = models.CharField(max_length=220, blank=True, default="")
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Item da composição do benefício"
        verbose_name_plural = "Itens da composição do benefício"
        ordering = ["ordem", "id"]
        indexes = [
            models.Index(fields=["beneficio", "ativo"]),
        ]

    def clean(self):
        has_estoque = bool(self.item_estoque_id)
        has_manual = bool((self.item_manual or "").strip())
        if has_estoque == has_manual:
            raise ValidationError("Informe item de estoque ou item manual (apenas um).")

    @property
    def item_nome(self) -> str:
        if self.item_estoque_id:
            return self.item_estoque.nome
        return (self.item_manual or "").strip()

    def __str__(self) -> str:
        return f"{self.beneficio.nome} • {self.item_nome}"


class BeneficioCampanha(models.Model):
    class Origem(models.TextChoices):
        COMPRA = "COMPRA", "Compra"
        DOACAO = "DOACAO", "Doação"
        PROGRAMA = "PROGRAMA", "Programa"
        ESTOQUE = "ESTOQUE", "Estoque existente"

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        EM_EXECUCAO = "EM_EXECUCAO", "Em execução"
        FINALIZADA = "FINALIZADA", "Finalizada"
        CANCELADA = "CANCELADA", "Cancelada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="beneficios_campanhas")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="beneficios_campanhas",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="beneficios_campanhas",
        null=True,
        blank=True,
    )
    area = models.CharField(max_length=20, choices=BeneficioTipo.Area.choices, default=BeneficioTipo.Area.EDUCACAO)
    nome = models.CharField(max_length=220)
    beneficio = models.ForeignKey(BeneficioTipo, on_delete=models.PROTECT, related_name="campanhas")
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    quantidade_planejada = models.PositiveIntegerField(default=0)
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.ESTOQUE)
    centro_custo = models.CharField(max_length=120, blank=True, default="")
    referencia = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.RASCUNHO, db_index=True)
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_campanhas_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Campanha de distribuição"
        verbose_name_plural = "Campanhas de distribuição"
        ordering = ["-data_inicio", "-id"]
        indexes = [
            models.Index(fields=["municipio", "area", "status"]),
            models.Index(fields=["beneficio", "status"]),
        ]

    def __str__(self) -> str:
        return self.nome


class BeneficioCampanhaAluno(models.Model):
    class Status(models.TextChoices):
        SELECIONADO = "SELECIONADO", "Selecionado"
        PENDENTE = "PENDENTE", "Pendente"
        ENTREGUE = "ENTREGUE", "Entregue"
        INAPTO = "INAPTO", "Inapto"

    campanha = models.ForeignKey(BeneficioCampanha, on_delete=models.CASCADE, related_name="alunos")
    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="beneficios_campanhas")
    turma = models.ForeignKey("educacao.Turma", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.SELECIONADO)
    justificativa = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Aluno da campanha"
        verbose_name_plural = "Alunos da campanha"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["campanha", "aluno"], name="uniq_beneficio_campanha_aluno"),
        ]
        indexes = [
            models.Index(fields=["campanha", "status"]),
            models.Index(fields=["aluno", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.campanha.nome} • {self.aluno.nome}"


class BeneficioEntrega(models.Model):
    class Status(models.TextChoices):
        AGENDADO = "AGENDADO", "Agendado"
        PENDENTE = "PENDENTE", "Pendente"
        ENTREGUE = "ENTREGUE", "Entregue"
        RECUSADO = "RECUSADO", "Recusado"
        ESTORNADO = "ESTORNADO", "Estornado"

    class RecebedorTipo(models.TextChoices):
        ALUNO = "ALUNO", "Aluno"
        RESPONSAVEL = "RESPONSAVEL", "Responsável"
        SERVIDOR = "SERVIDOR", "Servidor/Representante"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="beneficios_entregas")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="beneficios_entregas",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="beneficios_entregas",
        null=True,
        blank=True,
    )
    area = models.CharField(max_length=20, choices=BeneficioTipo.Area.choices, default=BeneficioTipo.Area.EDUCACAO)
    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="beneficios_entregas")
    campanha = models.ForeignKey(
        BeneficioCampanha,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entregas",
    )
    beneficio = models.ForeignKey(BeneficioTipo, on_delete=models.PROTECT, related_name="entregas")
    plano_recorrencia = models.ForeignKey(
        "educacao.BeneficioRecorrenciaPlano",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entregas",
    )
    ciclo_recorrencia = models.ForeignKey(
        "educacao.BeneficioRecorrenciaCiclo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entregas",
    )
    data_hora = models.DateTimeField(default=timezone.now)
    responsavel_entrega = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_entregas_registradas",
    )
    recebedor_tipo = models.CharField(max_length=20, choices=RecebedorTipo.choices, default=RecebedorTipo.RESPONSAVEL)
    recebedor_nome = models.CharField(max_length=180, blank=True, default="")
    recebedor_documento = models.CharField(max_length=60, blank=True, default="")
    recebedor_telefone = models.CharField(max_length=40, blank=True, default="")
    assinatura_confirmada = models.BooleanField(default=False)
    foto_entrega = models.ImageField(upload_to="educacao/beneficios/fotos/", blank=True, null=True)
    comprovante_anexo = models.FileField(upload_to="educacao/beneficios/comprovantes/", blank=True, null=True)
    comprovante_hash = models.CharField(max_length=80, blank=True, default="")
    local_entrega = models.CharField(max_length=180, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    justificativa = models.TextField(blank=True, default="")
    segunda_via = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE, db_index=True)
    estornado_em = models.DateTimeField(null=True, blank=True)
    estornado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_entregas_estornadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Entrega de benefício"
        verbose_name_plural = "Entregas de benefício"
        ordering = ["-data_hora", "-id"]
        indexes = [
            models.Index(fields=["municipio", "area", "status"]),
            models.Index(fields=["aluno", "beneficio", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno.nome} • {self.beneficio.nome} • {self.get_status_display()}"


class BeneficioEntregaItem(models.Model):
    entrega = models.ForeignKey(BeneficioEntrega, on_delete=models.CASCADE, related_name="itens")
    composicao_item = models.ForeignKey(
        BeneficioTipoItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_entrega",
    )
    item_estoque = models.ForeignKey(
        "almoxarifado.AlmoxarifadoCadastro",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="itens_entrega_beneficio",
    )
    item_nome = models.CharField(max_length=180)
    quantidade_planejada = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantidade_entregue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unidade = models.CharField(max_length=20, blank=True, default="UN")
    pendente = models.BooleanField(default=False)
    substituido = models.BooleanField(default=False)
    motivo_substituicao = models.CharField(max_length=220, blank=True, default="")
    observacao = models.CharField(max_length=220, blank=True, default="")

    class Meta:
        verbose_name = "Item da entrega"
        verbose_name_plural = "Itens da entrega"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["entrega", "pendente"]),
            models.Index(fields=["item_estoque"]),
        ]

    def __str__(self) -> str:
        return f"{self.item_nome} • {self.quantidade_entregue}"


class BeneficioEdital(models.Model):
    class Abrangencia(models.TextChoices):
        MUNICIPIO = "MUNICIPIO", "Município"
        ESCOLAS = "ESCOLAS", "Escolas específicas"

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        PUBLICADO = "PUBLICADO", "Publicado"
        INSCRICOES_ENCERRADAS = "INSCRICOES_ENCERRADAS", "Inscrições encerradas"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        RESULTADO_PRELIMINAR = "RESULTADO_PRELIMINAR", "Resultado preliminar"
        EM_RECURSOS = "EM_RECURSOS", "Em recursos"
        RESULTADO_FINAL = "RESULTADO_FINAL", "Resultado final"
        ENCERRADO = "ENCERRADO", "Encerrado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="beneficios_editais")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="beneficios_editais",
        null=True,
        blank=True,
    )
    area = models.CharField(max_length=20, choices=BeneficioTipo.Area.choices, default=BeneficioTipo.Area.EDUCACAO)
    titulo = models.CharField(max_length=220)
    numero_ano = models.CharField(max_length=30)
    beneficio = models.ForeignKey(BeneficioTipo, on_delete=models.PROTECT, related_name="editais")
    publico_alvo = models.CharField(max_length=20, choices=BeneficioTipo.PublicoAlvo.choices, default=BeneficioTipo.PublicoAlvo.TODOS)
    abrangencia = models.CharField(max_length=20, choices=Abrangencia.choices, default=Abrangencia.MUNICIPIO)
    escolas = models.ManyToManyField("org.Unidade", blank=True, related_name="beneficios_editais")
    inscricao_inicio = models.DateField(null=True, blank=True)
    inscricao_fim = models.DateField(null=True, blank=True)
    analise_inicio = models.DateField(null=True, blank=True)
    analise_fim = models.DateField(null=True, blank=True)
    resultado_preliminar_data = models.DateField(null=True, blank=True)
    prazo_recurso_data = models.DateField(null=True, blank=True)
    resultado_final_data = models.DateField(null=True, blank=True)
    texto = models.TextField(blank=True, default="")
    anexo = models.FileField(upload_to="educacao/beneficios/editais/", blank=True, null=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.RASCUNHO, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_editais_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Edital de benefício"
        verbose_name_plural = "Editais de benefício"
        ordering = ["-criado_em", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero_ano"], name="uniq_beneficio_edital_numero_municipio")
        ]
        indexes = [
            models.Index(fields=["municipio", "area", "status"]),
            models.Index(fields=["beneficio", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.numero_ano} • {self.titulo}"


class BeneficioEditalCriterio(models.Model):
    class Tipo(models.TextChoices):
        ELIMINATORIO = "ELIMINATORIO", "Eliminatório"
        PONTUACAO = "PONTUACAO", "Pontuação"

    edital = models.ForeignKey(BeneficioEdital, on_delete=models.CASCADE, related_name="criterios")
    nome = models.CharField(max_length=180)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.ELIMINATORIO)
    fonte_dado = models.CharField(max_length=80, blank=True, default="")
    regra = models.CharField(max_length=220, blank=True, default="")
    peso = models.IntegerField(default=0)
    exige_comprovacao = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Critério do edital"
        verbose_name_plural = "Critérios do edital"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return self.nome


class BeneficioEditalDocumento(models.Model):
    edital = models.ForeignKey(BeneficioEdital, on_delete=models.CASCADE, related_name="documentos")
    nome = models.CharField(max_length=160)
    obrigatorio = models.BooleanField(default=True)
    formatos_aceitos = models.CharField(max_length=120, blank=True, default="pdf,jpg,png")
    prazo_entrega = models.DateField(null=True, blank=True)
    permite_declaracao = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Documento exigido do edital"
        verbose_name_plural = "Documentos exigidos do edital"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return self.nome


class BeneficioEditalInscricao(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        ENVIADA = "ENVIADA", "Enviada"
        DOC_PENDENTE = "DOC_PENDENTE", "Documentação pendente"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        APTO = "APTO", "Apto"
        INAPTO = "INAPTO", "Inapto"
        CLASSIFICADO = "CLASSIFICADO", "Classificado"
        NAO_CLASSIFICADO = "NAO_CLASSIFICADO", "Não classificado"
        CONVOCADO = "CONVOCADO", "Convocado"
        RECURSO = "RECURSO", "Recurso solicitado"
        FINAL_DEFERIDO = "FINAL_DEFERIDO", "Resultado final deferido"
        FINAL_INDEFERIDO = "FINAL_INDEFERIDO", "Resultado final indeferido"

    edital = models.ForeignKey(BeneficioEdital, on_delete=models.CASCADE, related_name="inscricoes")
    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="beneficios_inscricoes")
    escola = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="beneficios_inscricoes",
        null=True,
        blank=True,
    )
    turma = models.ForeignKey("educacao.Turma", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    data_hora = models.DateTimeField(default=timezone.now)
    dados_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENVIADA, db_index=True)
    pontuacao = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    justificativa = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_inscricoes_criadas",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_inscricoes_atualizadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inscrição do edital"
        verbose_name_plural = "Inscrições do edital"
        ordering = ["-data_hora", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["edital", "aluno"], name="uniq_beneficio_inscricao_edital_aluno"),
        ]
        indexes = [
            models.Index(fields=["edital", "status"]),
            models.Index(fields=["aluno", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.edital.numero_ano} • {self.aluno.nome}"


class BeneficioEditalInscricaoDocumento(models.Model):
    inscricao = models.ForeignKey(BeneficioEditalInscricao, on_delete=models.CASCADE, related_name="documentos")
    requisito = models.ForeignKey(
        BeneficioEditalDocumento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_enviados",
    )
    descricao = models.CharField(max_length=160, blank=True, default="")
    arquivo = models.FileField(upload_to="educacao/beneficios/inscricoes/")
    aprovado = models.BooleanField(null=True, blank=True)
    observacao = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento da inscrição"
        verbose_name_plural = "Documentos da inscrição"
        ordering = ["-criado_em", "-id"]

    def __str__(self) -> str:
        return f"Doc inscrição #{self.inscricao_id}"


class BeneficioEditalRecurso(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        DEFERIDO = "DEFERIDO", "Deferido"
        INDEFERIDO = "INDEFERIDO", "Indeferido"

    inscricao = models.ForeignKey(BeneficioEditalInscricao, on_delete=models.CASCADE, related_name="recursos")
    texto = models.TextField()
    arquivo = models.FileField(upload_to="educacao/beneficios/recursos/", blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    parecer = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_recursos_criados",
    )
    analisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_recursos_analisados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    analisado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Recurso do edital"
        verbose_name_plural = "Recursos do edital"
        ordering = ["-criado_em", "-id"]

    def __str__(self) -> str:
        return f"Recurso inscrição #{self.inscricao_id}"


class BeneficioRecorrenciaPlano(models.Model):
    class Frequencia(models.TextChoices):
        MENSAL = "MENSAL", "Mensal"
        QUINZENAL = "QUINZENAL", "Quinzenal"
        SEMANAL = "SEMANAL", "Semanal"
        INTERVALO_DIAS = "INTERVALO_DIAS", "A cada X dias"

    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        PAUSADA = "PAUSADA", "Pausada"
        FINALIZADA = "FINALIZADA", "Finalizada"
        CANCELADA = "CANCELADA", "Cancelada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="beneficios_recorrencias")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="beneficios_recorrencias",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="beneficios_recorrencias",
        null=True,
        blank=True,
    )
    area = models.CharField(max_length=20, choices=BeneficioTipo.Area.choices, default=BeneficioTipo.Area.EDUCACAO)
    beneficio = models.ForeignKey(BeneficioTipo, on_delete=models.PROTECT, related_name="recorrencias")
    aluno = models.ForeignKey("educacao.Aluno", on_delete=models.PROTECT, related_name="beneficios_recorrencias")
    inscricao = models.ForeignKey(
        BeneficioEditalInscricao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_recorrencia",
    )
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    numero_ciclos = models.PositiveIntegerField(null=True, blank=True)
    frequencia = models.CharField(max_length=20, choices=Frequencia.choices, default=Frequencia.MENSAL)
    intervalo_dias = models.PositiveIntegerField(default=30)
    geracao_automatica = models.BooleanField(default=True)
    permite_segunda_via = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ATIVA, db_index=True)
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_recorrencias_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plano de recorrência"
        verbose_name_plural = "Planos de recorrência"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["beneficio", "status"]),
            models.Index(fields=["aluno", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.beneficio.nome} • {self.aluno.nome}"


class BeneficioRecorrenciaCiclo(models.Model):
    class Status(models.TextChoices):
        PREVISTA = "PREVISTA", "Prevista"
        SEPARADA = "SEPARADA", "Separada"
        ENTREGUE = "ENTREGUE", "Entregue"
        ATRASADA = "ATRASADA", "Atrasada"
        PULADA = "PULADA", "Pulada"
        CANCELADA = "CANCELADA", "Cancelada"

    plano = models.ForeignKey(BeneficioRecorrenciaPlano, on_delete=models.CASCADE, related_name="ciclos")
    numero = models.PositiveIntegerField(default=1)
    data_prevista = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PREVISTA, db_index=True)
    motivo = models.TextField(blank=True, default="")
    entrega = models.ForeignKey(
        BeneficioEntrega,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ciclos_recorrencia",
    )
    responsavel_confirmacao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beneficios_ciclos_confirmados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ciclo da recorrência"
        verbose_name_plural = "Ciclos da recorrência"
        ordering = ["data_prevista", "numero", "id"]
        constraints = [
            models.UniqueConstraint(fields=["plano", "numero"], name="uniq_beneficio_recorrencia_plano_numero"),
        ]
        indexes = [
            models.Index(fields=["plano", "status"]),
            models.Index(fields=["data_prevista", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.plano} • ciclo {self.numero}"
