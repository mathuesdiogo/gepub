from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class RhCadastro(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"

    class Regime(models.TextChoices):
        ESTATUTARIO = "ESTATUTARIO", "Estatutário"
        CLT = "CLT", "CLT"
        COMISSIONADO = "COMISSIONADO", "Comissionado"
        TEMPORARIO = "TEMPORARIO", "Temporário"

    class SituacaoFuncional(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        FERIAS = "FERIAS", "Férias"
        AFASTADO = "AFASTADO", "Afastado"
        CEDIDO = "CEDIDO", "Cedido"
        DESLIGADO = "DESLIGADO", "Desligado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_cadastros")
    secretaria = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="rh_cadastros",
        null=True,
        blank=True,
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="rh_cadastros",
        null=True,
        blank=True,
    )
    setor = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="rh_cadastros",
        null=True,
        blank=True,
    )

    servidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_cadastros",
    )
    codigo = models.CharField(max_length=40)
    matricula = models.CharField(max_length=40, blank=True, default="")
    nome = models.CharField(max_length=180)
    cargo = models.CharField(max_length=120, blank=True, default="")
    funcao = models.CharField(max_length=120, blank=True, default="")
    regime = models.CharField(max_length=20, choices=Regime.choices, default=Regime.ESTATUTARIO)
    data_admissao = models.DateField(default=timezone.localdate)
    situacao_funcional = models.CharField(
        max_length=20,
        choices=SituacaoFuncional.choices,
        default=SituacaoFuncional.ATIVO,
    )
    salario_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    data_desligamento = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    observacao = models.TextField(blank=True, default="")

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_cadastros_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Servidor funcional"
        verbose_name_plural = "Servidores funcionais"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "codigo"], name="uniq_rh_cadastro_municipio_codigo"),
            models.UniqueConstraint(
                fields=["municipio", "matricula"],
                condition=~models.Q(matricula=""),
                name="uniq_rh_matricula_municipio",
            ),
        ]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["municipio", "situacao_funcional"]),
            models.Index(fields=["codigo"]),
            models.Index(fields=["matricula"]),
            models.Index(fields=["nome"]),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} - {self.nome}"


class RhMovimentacao(models.Model):
    class Tipo(models.TextChoices):
        ADMISSAO = "ADMISSAO", "Admissão"
        LOTACAO = "LOTACAO", "Mudança de lotação"
        FERIAS = "FERIAS", "Férias"
        AFASTAMENTO = "AFASTAMENTO", "Afastamento"
        PROGRESSAO = "PROGRESSAO", "Progressão"
        DESLIGAMENTO = "DESLIGAMENTO", "Desligamento"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        RECUSADA = "RECUSADA", "Recusada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_movimentacoes")
    servidor = models.ForeignKey(RhCadastro, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.LOTACAO)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(null=True, blank=True)
    secretaria_destino = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="rh_movimentacoes_destino",
        null=True,
        blank=True,
    )
    unidade_destino = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="rh_movimentacoes_destino",
        null=True,
        blank=True,
    )
    setor_destino = models.ForeignKey(
        "org.Setor",
        on_delete=models.PROTECT,
        related_name="rh_movimentacoes_destino",
        null=True,
        blank=True,
    )
    observacao = models.TextField(blank=True, default="")
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_movimentacoes_aprovadas",
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_movimentacoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Movimentação funcional"
        verbose_name_plural = "Movimentações funcionais"
        ordering = ["-data_inicio", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status", "tipo"]),
            models.Index(fields=["servidor", "data_inicio"]),
        ]

    def __str__(self):
        return f"{self.servidor.nome} • {self.get_tipo_display()} • {self.data_inicio}"


class RhDocumento(models.Model):
    class Tipo(models.TextChoices):
        PORTARIA = "PORTARIA", "Portaria"
        TERMO = "TERMO", "Termo"
        ATO = "ATO", "Ato"
        NOMEACAO = "NOMEACAO", "Nomeação"
        OUTRO = "OUTRO", "Outro"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_documentos")
    servidor = models.ForeignKey(RhCadastro, on_delete=models.CASCADE, related_name="documentos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.PORTARIA)
    numero = models.CharField(max_length=60)
    data_documento = models.DateField(default=timezone.localdate)
    descricao = models.TextField(blank=True, default="")
    arquivo = models.FileField(upload_to="rh/documentos/", blank=True, null=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_documentos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Documento funcional"
        verbose_name_plural = "Documentos funcionais"
        ordering = ["-data_documento", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_rh_documento_municipio_numero"),
        ]
        indexes = [
            models.Index(fields=["municipio", "tipo", "data_documento"]),
        ]

    def __str__(self):
        return f"{self.numero} • {self.servidor.nome}"


class RhRemanejamentoEdital(models.Model):
    class TipoServidor(models.TextChoices):
        DOCENTE = "DOCENTE", "Docente"
        TAE = "TAE", "Técnico-administrativo"
        AMBOS = "AMBOS", "Docente e técnico-administrativo"

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        ABERTO = "ABERTO", "Aberto para inscrições"
        ENCERRADO = "ENCERRADO", "Encerrado"
        ARQUIVADO = "ARQUIVADO", "Arquivado"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_remanejamento_editais")
    numero = models.CharField(max_length=40)
    titulo = models.CharField(max_length=180)
    tipo_servidor = models.CharField(max_length=20, choices=TipoServidor.choices, default=TipoServidor.AMBOS)
    inscricao_inicio = models.DateTimeField()
    inscricao_fim = models.DateTimeField()
    recurso_inicio = models.DateTimeField(null=True, blank=True)
    recurso_fim = models.DateTimeField(null=True, blank=True)
    resultado_em = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RASCUNHO)
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_remanejamento_editais_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Edital de remanejamento"
        verbose_name_plural = "Editais de remanejamento"
        ordering = ["-inscricao_inicio", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "numero"], name="uniq_rh_remanejamento_numero_municipio"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status", "inscricao_inicio"]),
        ]

    def __str__(self) -> str:
        return f"{self.numero} • {self.titulo}"

    @property
    def inscricao_aberta(self) -> bool:
        now = timezone.now()
        return self.status == self.Status.ABERTO and self.inscricao_inicio <= now <= self.inscricao_fim

    @property
    def recurso_aberto(self) -> bool:
        if not (self.recurso_inicio and self.recurso_fim):
            return False
        now = timezone.now()
        return self.recurso_inicio <= now <= self.recurso_fim

    def clean(self):
        if self.inscricao_fim and self.inscricao_inicio and self.inscricao_fim < self.inscricao_inicio:
            raise ValidationError({"inscricao_fim": "Fim da inscrição não pode ser menor que o início."})
        if self.recurso_inicio and self.recurso_fim and self.recurso_fim < self.recurso_inicio:
            raise ValidationError({"recurso_fim": "Fim do recurso não pode ser menor que o início."})


class RhRemanejamentoInscricao(models.Model):
    class Status(models.TextChoices):
        VALIDA = "VALIDA", "Válida"
        CANCELADA = "CANCELADA", "Cancelada"

    edital = models.ForeignKey(RhRemanejamentoEdital, on_delete=models.CASCADE, related_name="inscricoes")
    servidor = models.ForeignKey(RhCadastro, on_delete=models.CASCADE, related_name="inscricoes_remanejamento")
    disciplina_interesse = models.CharField(max_length=140, blank=True, default="")
    ingressou_mesma_disciplina = models.BooleanField(default=False)
    redistribuido = models.BooleanField(default=False)
    data_ingresso = models.DateField(null=True, blank=True)
    homologacao_dou = models.CharField(max_length=120, blank=True, default="")
    unidades_interesse = models.ManyToManyField("org.Unidade", related_name="inscricoes_remanejamento", blank=True)
    portaria_nomeacao = models.FileField(upload_to="rh/remanejamento/nomeacao/%Y/%m/", blank=True, null=True)
    portaria_lotacao = models.FileField(upload_to="rh/remanejamento/lotacao/%Y/%m/", blank=True, null=True)
    situacao_funcional_arquivo = models.FileField(upload_to="rh/remanejamento/situacao/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.VALIDA)
    motivo_cancelamento = models.TextField(blank=True, default="")
    protocolo = models.CharField(max_length=60, blank=True, default="", db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_inscricoes_remanejamento_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Inscrição de remanejamento"
        verbose_name_plural = "Inscrições de remanejamento"
        ordering = ["-criado_em", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["edital", "servidor"],
                condition=models.Q(status="VALIDA"),
                name="uniq_rh_remanejamento_inscricao_valida",
            ),
        ]
        indexes = [
            models.Index(fields=["edital", "status"]),
            models.Index(fields=["servidor", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.edital.numero} • {self.servidor.nome}"

    def clean(self):
        if self.edital_id and self.servidor_id and self.servidor.municipio_id != self.edital.municipio_id:
            raise ValidationError({"servidor": "Servidor não pertence ao município do edital."})


class RhRemanejamentoRecurso(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        DEFERIDO = "DEFERIDO", "Deferido"
        INDEFERIDO = "INDEFERIDO", "Indeferido"

    inscricao = models.ForeignKey(RhRemanejamentoInscricao, on_delete=models.CASCADE, related_name="recursos")
    texto = models.TextField()
    anexo = models.FileField(upload_to="rh/remanejamento/recursos/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    resposta = models.TextField(blank=True, default="")
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_recursos_remanejamento_respondidos",
    )
    respondido_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_recursos_remanejamento_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Recurso de remanejamento"
        verbose_name_plural = "Recursos de remanejamento"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["status", "criado_em"]),
        ]

    def __str__(self) -> str:
        return f"Recurso #{self.pk} • {self.inscricao.servidor.nome}"


class RhSubstituicaoServidor(models.Model):
    class Status(models.TextChoices):
        AGENDADA = "AGENDADA", "Agendada"
        VIGENTE = "VIGENTE", "Vigente"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        CANCELADA = "CANCELADA", "Cancelada"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_substituicoes")
    substituido = models.ForeignKey(
        RhCadastro,
        on_delete=models.PROTECT,
        related_name="substituicoes_como_substituido",
    )
    substituto = models.ForeignKey(
        RhCadastro,
        on_delete=models.PROTECT,
        related_name="substituicoes_como_substituto",
    )
    motivo = models.TextField()
    data_inicio = models.DateField(default=timezone.localdate)
    data_fim = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AGENDADA)
    modulos_liberados_json = models.JSONField(default=list, blank=True)
    setores_liberados = models.ManyToManyField("org.Setor", related_name="rh_substituicoes_liberadas", blank=True)
    grupos_liberados_json = models.JSONField(default=list, blank=True)
    tipos_conteudoportal_json = models.JSONField(default=list, blank=True)
    substituto_ja_tramitador = models.BooleanField(default=False)
    setor_original_substituto = models.ForeignKey(
        "org.Setor",
        on_delete=models.SET_NULL,
        related_name="rh_substituicoes_setor_original",
        null=True,
        blank=True,
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_substituicoes_operadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Substituição de servidor"
        verbose_name_plural = "Substituições de servidor"
        ordering = ["-data_inicio", "-id"]
        indexes = [
            models.Index(fields=["municipio", "status"]),
            models.Index(fields=["substituido", "data_inicio"]),
            models.Index(fields=["substituto", "data_inicio"]),
        ]

    def __str__(self) -> str:
        return f"{self.substituto.nome} substitui {self.substituido.nome}"

    def clean(self):
        if self.substituido_id and self.substituto_id and self.substituido_id == self.substituto_id:
            raise ValidationError({"substituto": "Substituto deve ser diferente do substituído."})
        if self.data_fim and self.data_inicio and self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "Data fim não pode ser menor que data início."})
        if self.substituido_id and self.municipio_id and self.substituido.municipio_id != self.municipio_id:
            raise ValidationError({"substituido": "Substituído não pertence ao município informado."})
        if self.substituto_id and self.municipio_id and self.substituto.municipio_id != self.municipio_id:
            raise ValidationError({"substituto": "Substituto não pertence ao município informado."})

    def sync_status(self, *, today=None) -> str:
        if self.status == self.Status.CANCELADA:
            return self.status
        now = today or timezone.localdate()
        if now < self.data_inicio:
            status = self.Status.AGENDADA
        elif self.data_inicio <= now <= self.data_fim:
            status = self.Status.VIGENTE
        else:
            status = self.Status.CONCLUIDA
        if self.status != status:
            self.status = status
            self.save(update_fields=["status", "atualizado_em"])
        return status


class RhPdpPlano(models.Model):
    class Status(models.TextChoices):
        COLETA = "COLETA", "Coleta"
        APROVACAO_LOCAL = "APROVACAO_LOCAL", "Aprovação local"
        APROVACAO_CENTRAL = "APROVACAO_CENTRAL", "Aprovação central"
        APROVADO = "APROVADO", "Aprovado"
        EXPORTADO_SIPEC = "EXPORTADO_SIPEC", "Exportado SIPEC"

    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_pdp_planos")
    ano = models.PositiveSmallIntegerField()
    titulo = models.CharField(max_length=180, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COLETA)
    inicio_coleta = models.DateField(null=True, blank=True)
    fim_coleta = models.DateField(null=True, blank=True)
    aprovado_por_autoridade = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_pdp_planos_aprovados",
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)
    enviado_sipec_em = models.DateTimeField(null=True, blank=True)
    observacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_pdp_planos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plano PDP"
        verbose_name_plural = "Planos PDP"
        ordering = ["-ano", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "ano"], name="uniq_rh_pdp_plano_municipio_ano"),
        ]
        indexes = [
            models.Index(fields=["municipio", "status", "ano"]),
        ]

    def __str__(self) -> str:
        return self.titulo or f"PDP {self.ano}"

    def clean(self):
        if self.fim_coleta and self.inicio_coleta and self.fim_coleta < self.inicio_coleta:
            raise ValidationError({"fim_coleta": "Fim da coleta não pode ser menor que o início."})


class RhPdpNecessidade(models.Model):
    class TipoSubmissao(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        INSTITUCIONAL = "INSTITUCIONAL", "Institucional"

    class Modalidade(models.TextChoices):
        PRESENCIAL = "PRESENCIAL", "Presencial"
        EAD = "EAD", "A distância"
        SEMIPRESENCIAL = "SEMIPRESENCIAL", "Semipresencial"
        NAO_DEFINIDO = "NAO_DEFINIDO", "Não definido"

    class CustoTipo(models.TextChoices):
        SEM_ONUS = "SEM_ONUS", "Sem ônus"
        ONUS_LIMITADO = "ONUS_LIMITADO", "Ônus limitado"
        COM_ONUS = "COM_ONUS", "Com ônus"

    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        ENVIADA = "ENVIADA", "Enviada"
        APROVADA_LOCAL = "APROVADA_LOCAL", "Aprovada local"
        REJEITADA_LOCAL = "REJEITADA_LOCAL", "Rejeitada local"
        CONSOLIDADA_CENTRAL = "CONSOLIDADA_CENTRAL", "Consolidada central"
        APROVADA_CENTRAL = "APROVADA_CENTRAL", "Aprovada central"

    plano = models.ForeignKey(RhPdpPlano, on_delete=models.CASCADE, related_name="necessidades")
    municipio = models.ForeignKey("org.Municipio", on_delete=models.PROTECT, related_name="rh_pdp_necessidades")
    tipo_submissao = models.CharField(max_length=20, choices=TipoSubmissao.choices, default=TipoSubmissao.INDIVIDUAL)
    servidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_pdp_necessidades",
    )
    setor_lotacao = models.ForeignKey(
        "org.Setor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_pdp_necessidades",
    )
    area_estrategica = models.CharField(max_length=120)
    area_tematica = models.CharField(max_length=140)
    objeto_tematico = models.CharField(max_length=140)
    necessidade_a_ser_atendida = models.TextField()
    acao_transversal = models.BooleanField(default=False)
    unidades_organizacionais = models.CharField(max_length=220, blank=True, default="")
    publico_alvo = models.CharField(max_length=140, blank=True, default="")
    competencia_associada = models.CharField(max_length=220, blank=True, default="")
    enfoque_desenvolvimento = models.CharField(max_length=120, blank=True, default="")
    tipo_aprendizagem = models.CharField(max_length=120, blank=True, default="")
    especificacao_tipo_aprendizagem = models.CharField(max_length=120, blank=True, default="")
    modalidade = models.CharField(max_length=20, choices=Modalidade.choices, default=Modalidade.NAO_DEFINIDO)
    titulo_acao = models.CharField(max_length=180, blank=True, default="")
    termino_previsto = models.PositiveSmallIntegerField(null=True, blank=True)
    quantidade_prevista_servidores = models.PositiveIntegerField(default=1)
    carga_horaria_individual_prevista = models.CharField(max_length=20, default="00:00")
    custo_tipo = models.CharField(max_length=20, choices=CustoTipo.choices, default=CustoTipo.ONUS_LIMITADO)
    custo_individual_previsto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precisa_prof_substituto = models.BooleanField(default=False)
    precisa_afastamento = models.BooleanField(default=False)
    licenca_capacitacao = models.BooleanField(default=False)
    pode_ser_atendida_cfs = models.BooleanField(default=False)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RASCUNHO)
    analise_local_parecer = models.TextField(blank=True, default="")
    analise_central_parecer = models.TextField(blank=True, default="")
    analisado_local_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_pdp_necessidades_local",
    )
    analisado_local_em = models.DateTimeField(null=True, blank=True)
    analisado_central_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_pdp_necessidades_central",
    )
    analisado_central_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rh_pdp_necessidades_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Necessidade PDP"
        verbose_name_plural = "Necessidades PDP"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["plano", "status"]),
            models.Index(fields=["municipio", "status"]),
        ]

    def __str__(self) -> str:
        base = self.titulo_acao or self.necessidade_a_ser_atendida[:60]
        return f"{self.plano.ano} • {base}"
