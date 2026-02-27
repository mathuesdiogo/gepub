from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.org.models import Unidade, Setor
from apps.core.security import derive_cpf_security_fields, mask_cpf, resolve_cpf_digits


class EspecialidadeSaude(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    cbo = models.CharField(max_length=20, blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Especialidade"
        verbose_name_plural = "Especialidades"
        ordering = ["nome"]
        indexes = [models.Index(fields=["nome"]), models.Index(fields=["ativo"])]

    def __str__(self):
        return self.nome


class SalaSaude(models.Model):
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="salas_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    setor = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        related_name="salas_saude",
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=120)
    capacidade = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sala de Atendimento"
        verbose_name_plural = "Salas de Atendimento"
        ordering = ["unidade__nome", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["unidade", "nome"], name="uniq_sala_saude_unidade_nome"),
        ]
        indexes = [models.Index(fields=["ativo"])]

    def __str__(self):
        return f"{self.nome} ({self.unidade})"


class ProfissionalSaude(models.Model):
    class Cargo(models.TextChoices):
        MEDICO = "MEDICO", "Médico"
        ENFERMEIRO = "ENFERMEIRO", "Enfermeiro"
        TECNICO = "TECNICO", "Técnico"
        AGENTE = "AGENTE", "Agente de Saúde"
        ADMIN = "ADMIN", "Administrativo"
        OUTROS = "OUTROS", "Outros"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="profissionais_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    especialidade = models.ForeignKey(
        EspecialidadeSaude,
        on_delete=models.PROTECT,
        related_name="profissionais",
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=180)
    cpf = models.CharField(max_length=14, blank=True, default="")
    cpf_enc = models.TextField(blank=True, default="")
    cpf_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    cpf_last4 = models.CharField(max_length=4, blank=True, default="")
    conselho_numero = models.CharField(max_length=60, blank=True, default="")
    cbo = models.CharField(max_length=20, blank=True, default="")
    carga_horaria_semanal = models.PositiveIntegerField(default=20)
    cargo = models.CharField(max_length=20, choices=Cargo.choices)
    telefone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Profissional de Saúde"
        verbose_name_plural = "Profissionais de Saúde"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["nome"]),
            models.Index(fields=["cargo"]),
            models.Index(fields=["ativo"]),
        ]


    def save(self, *args, **kwargs):
        cpf_digits = resolve_cpf_digits(self.cpf, self.cpf_enc)
        cpf_enc, cpf_hash, cpf_last4 = derive_cpf_security_fields(cpf_digits)
        if cpf_digits:
            if cpf_enc:
                self.cpf_enc = cpf_enc
            if cpf_hash:
                self.cpf_hash = cpf_hash
        else:
            self.cpf_enc = ""
            self.cpf_hash = ""
        self.cpf_last4 = cpf_last4
        self.cpf = mask_cpf(cpf_digits)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class AtendimentoSaude(models.Model):
    class Tipo(models.TextChoices):
        CONSULTA = "CONSULTA", "Consulta"
        PROCEDIMENTO = "PROCEDIMENTO", "Procedimento"
        VACINA = "VACINA", "Vacina"
        VISITA = "VISITA", "Visita domiciliar"
        TRIAGEM = "TRIAGEM", "Triagem"
        OUTROS = "OUTROS", "Outros"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="atendimentos_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    profissional = models.ForeignKey(
        ProfissionalSaude,
        on_delete=models.PROTECT,
        related_name="atendimentos",
    )

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="atendimentos_saude",
        null=True,
        blank=True,
    )

    data = models.DateField(default=timezone.localdate)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CONSULTA)

    paciente_nome = models.CharField(max_length=180)
    paciente_cpf = models.CharField(max_length=14, blank=True, default="")
    paciente_cpf_enc = models.TextField(blank=True, default="")
    paciente_cpf_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    paciente_cpf_last4 = models.CharField(max_length=4, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    cid = models.CharField("CID (opcional)", max_length=20, blank=True, default="")

    class Meta:
        verbose_name = "Atendimento"
        verbose_name_plural = "Atendimentos"
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["data"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["paciente_nome"]),
        ]


    def save(self, *args, **kwargs):
        # Mantém compatibilidade com telas antigas: preenche paciente_* a partir do aluno quando existir.
        if self.aluno_id:
            try:
                nome = getattr(self.aluno, "nome", "") or ""
                cpf = resolve_cpf_digits(
                    getattr(self.aluno, "cpf", ""),
                    getattr(self.aluno, "cpf_enc", ""),
                )
                if nome and not (self.paciente_nome or "").strip():
                    self.paciente_nome = nome
                if cpf and not (self.paciente_cpf or "").strip():
                    self.paciente_cpf = cpf
            except Exception:
                pass

        paciente_digits = resolve_cpf_digits(self.paciente_cpf, self.paciente_cpf_enc)
        paciente_enc, paciente_hash, paciente_last4 = derive_cpf_security_fields(paciente_digits)
        if paciente_digits:
            if paciente_enc:
                self.paciente_cpf_enc = paciente_enc
            if paciente_hash:
                self.paciente_cpf_hash = paciente_hash
        else:
            self.paciente_cpf_enc = ""
            self.paciente_cpf_hash = ""
        self.paciente_cpf_last4 = paciente_last4
        self.paciente_cpf = mask_cpf(paciente_digits)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.paciente_nome} — {self.get_tipo_display()} ({self.data})"


class AgendamentoSaude(models.Model):
    class Tipo(models.TextChoices):
        PRIMEIRA_CONSULTA = "PRIMEIRA_CONSULTA", "Primeira consulta"
        RETORNO = "RETORNO", "Retorno"
        PROCEDIMENTO = "PROCEDIMENTO", "Procedimento"
        ENCAIXE = "ENCAIXE", "Encaixe"

    class Status(models.TextChoices):
        MARCADO = "MARCADO", "Marcado"
        CONFIRMADO = "CONFIRMADO", "Confirmado"
        ATENDIDO = "ATENDIDO", "Atendido"
        FALTA = "FALTA", "Falta"
        CANCELADO = "CANCELADO", "Cancelado"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="agendamentos_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    profissional = models.ForeignKey(
        ProfissionalSaude,
        on_delete=models.PROTECT,
        related_name="agendamentos",
    )
    especialidade = models.ForeignKey(
        EspecialidadeSaude,
        on_delete=models.PROTECT,
        related_name="agendamentos",
        null=True,
        blank=True,
    )
    sala = models.ForeignKey(
        SalaSaude,
        on_delete=models.PROTECT,
        related_name="agendamentos",
        null=True,
        blank=True,
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="agendamentos_saude",
        null=True,
        blank=True,
    )
    paciente_nome = models.CharField(max_length=180)
    paciente_cpf = models.CharField(max_length=14, blank=True, default="")
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.PRIMEIRA_CONSULTA)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.MARCADO, db_index=True)
    motivo = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"
        ordering = ["-inicio", "-id"]
        indexes = [models.Index(fields=["inicio"]), models.Index(fields=["status"])]

    def __str__(self):
        if hasattr(self.inicio, "strftime"):
            when = self.inicio.strftime("%d/%m/%Y %H:%M")
        else:
            when = str(self.inicio)
        return f"{self.paciente_nome} — {when}"


class DocumentoClinicoSaude(models.Model):
    class Tipo(models.TextChoices):
        ATESTADO = "ATESTADO", "Atestado"
        DECLARACAO = "DECLARACAO", "Declaração"
        ENCAMINHAMENTO = "ENCAMINHAMENTO", "Encaminhamento"
        RELATORIO = "RELATORIO", "Relatório"
        LAUDO = "LAUDO", "Laudo"
        RECEITA = "RECEITA", "Receita"

    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="documentos_clinicos",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    titulo = models.CharField(max_length=180)
    conteudo = models.TextField()
    documento_emitido = models.ForeignKey(
        "core.DocumentoEmitido",
        on_delete=models.PROTECT,
        related_name="documentos_clinicos_saude",
        null=True,
        blank=True,
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="documentos_clinicos_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Documento Clínico"
        verbose_name_plural = "Documentos Clínicos"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["tipo"]), models.Index(fields=["criado_em"])]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.titulo}"


class AuditoriaAcessoProntuarioSaude(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="acessos_prontuario_saude",
    )
    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="auditoria_acessos",
        null=True,
        blank=True,
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="auditoria_prontuario_saude",
        null=True,
        blank=True,
    )
    acao = models.CharField(max_length=60, default="VISUALIZACAO")
    ip = models.CharField(max_length=64, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Auditoria de Acesso ao Prontuário"
        verbose_name_plural = "Auditoria de Acesso ao Prontuário"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["criado_em"]), models.Index(fields=["acao"])]


class TriagemSaude(models.Model):
    atendimento = models.OneToOneField(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="triagem",
    )
    pa_sistolica = models.PositiveIntegerField(null=True, blank=True)
    pa_diastolica = models.PositiveIntegerField(null=True, blank=True)
    frequencia_cardiaca = models.PositiveIntegerField(null=True, blank=True)
    temperatura = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    saturacao_o2 = models.PositiveIntegerField(null=True, blank=True)
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    altura_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    classificacao_risco = models.CharField(max_length=40, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Triagem"
        verbose_name_plural = "Triagens"
        ordering = ["-atendimento__data", "-id"]

    def __str__(self):
        return f"Triagem — {self.atendimento}"


class EvolucaoClinicaSaude(models.Model):
    class Tipo(models.TextChoices):
        MEDICO = "MEDICO", "Médico"
        ENFERMAGEM = "ENFERMAGEM", "Enfermagem"
        MULTIPROFISSIONAL = "MULTIPROFISSIONAL", "Multiprofissional"

    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="evolucoes_clinicas",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.MULTIPROFISSIONAL)
    texto = models.TextField()
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="evolucoes_clinicas_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evolução Clínica"
        verbose_name_plural = "Evoluções Clínicas"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["criado_em"]), models.Index(fields=["tipo"])]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.atendimento}"


class ProblemaAtivoSaude(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        CONTROLADO = "CONTROLADO", "Controlado"
        RESOLVIDO = "RESOLVIDO", "Resolvido"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="problemas_ativos_saude",
    )
    descricao = models.CharField(max_length=180)
    cid = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO)
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Problema Ativo"
        verbose_name_plural = "Problemas Ativos"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["cid"])]

    def __str__(self):
        return f"{self.descricao} — {self.aluno}"


class AlergiaSaude(models.Model):
    class Gravidade(models.TextChoices):
        LEVE = "LEVE", "Leve"
        MODERADA = "MODERADA", "Moderada"
        GRAVE = "GRAVE", "Grave"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="alergias_saude",
    )
    agente = models.CharField(max_length=180)
    reacao = models.CharField(max_length=180, blank=True, default="")
    gravidade = models.CharField(max_length=20, choices=Gravidade.choices, default=Gravidade.LEVE)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alergia"
        verbose_name_plural = "Alergias"
        ordering = ["agente"]
        indexes = [models.Index(fields=["gravidade"]), models.Index(fields=["ativo"])]

    def __str__(self):
        return f"{self.agente} — {self.aluno}"


class AnexoAtendimentoSaude(models.Model):
    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="anexos_clinicos",
    )
    titulo = models.CharField(max_length=180)
    arquivo = models.FileField(upload_to="saude/anexos/")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="anexos_atendimento_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Anexo de Atendimento"
        verbose_name_plural = "Anexos de Atendimento"
        ordering = ["-criado_em", "-id"]

    def __str__(self):
        return self.titulo


class PrescricaoSaude(models.Model):
    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        ALTERADA = "ALTERADA", "Alterada"
        CANCELADA = "CANCELADA", "Cancelada"

    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="prescricoes",
    )
    versao = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVA)
    observacoes = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prescricoes_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Prescrição"
        verbose_name_plural = "Prescrições"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["versao"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"Prescrição v{self.versao} — {self.atendimento}"


class PrescricaoItemSaude(models.Model):
    prescricao = models.ForeignKey(
        PrescricaoSaude,
        on_delete=models.CASCADE,
        related_name="itens",
    )
    medicamento = models.CharField(max_length=180)
    dose = models.CharField(max_length=120, blank=True, default="")
    via = models.CharField(max_length=80, blank=True, default="")
    frequencia = models.CharField(max_length=120, blank=True, default="")
    duracao = models.CharField(max_length=120, blank=True, default="")
    orientacoes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Item da Prescrição"
        verbose_name_plural = "Itens da Prescrição"
        ordering = ["id"]

    def __str__(self):
        return self.medicamento


class ExamePedidoSaude(models.Model):
    class Prioridade(models.TextChoices):
        ROTINA = "ROTINA", "Rotina"
        URGENTE = "URGENTE", "Urgente"

    class Status(models.TextChoices):
        SOLICITADO = "SOLICITADO", "Solicitado"
        COLETADO = "COLETADO", "Coletado"
        RESULTADO = "RESULTADO", "Com resultado"

    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="exames_pedidos",
    )
    nome_exame = models.CharField(max_length=180)
    prioridade = models.CharField(max_length=20, choices=Prioridade.choices, default=Prioridade.ROTINA)
    justificativa = models.TextField(blank=True, default="")
    hipotese_diagnostica = models.CharField(max_length=180, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SOLICITADO)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="exames_pedidos_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pedido de Exame"
        verbose_name_plural = "Pedidos de Exame"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["prioridade"])]

    def __str__(self):
        return self.nome_exame


class ExameResultadoSaude(models.Model):
    pedido = models.OneToOneField(
        ExamePedidoSaude,
        on_delete=models.CASCADE,
        related_name="resultado",
    )
    texto_resultado = models.TextField(blank=True, default="")
    arquivo = models.FileField(upload_to="saude/exames/", blank=True, null=True)
    data_resultado = models.DateField(default=timezone.localdate)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resultados_exames_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Resultado de Exame"
        verbose_name_plural = "Resultados de Exame"
        ordering = ["-data_resultado", "-id"]

    def __str__(self):
        return f"Resultado — {self.pedido.nome_exame}"


class GradeAgendaSaude(models.Model):
    class DiaSemana(models.IntegerChoices):
        SEGUNDA = 0, "Segunda"
        TERCA = 1, "Terça"
        QUARTA = 2, "Quarta"
        QUINTA = 3, "Quinta"
        SEXTA = 4, "Sexta"
        SABADO = 5, "Sábado"
        DOMINGO = 6, "Domingo"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="grades_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    profissional = models.ForeignKey(
        ProfissionalSaude,
        on_delete=models.PROTECT,
        related_name="grades",
    )
    sala = models.ForeignKey(
        SalaSaude,
        on_delete=models.PROTECT,
        related_name="grades",
        null=True,
        blank=True,
    )
    especialidade = models.ForeignKey(
        EspecialidadeSaude,
        on_delete=models.PROTECT,
        related_name="grades",
        null=True,
        blank=True,
    )
    dia_semana = models.IntegerField(choices=DiaSemana.choices)
    inicio = models.TimeField()
    fim = models.TimeField()
    duracao_minutos = models.PositiveIntegerField(default=30)
    intervalo_minutos = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Grade de Agenda"
        verbose_name_plural = "Grades de Agenda"
        ordering = ["profissional__nome", "dia_semana", "inicio"]
        indexes = [models.Index(fields=["dia_semana"]), models.Index(fields=["ativo"])]

    def __str__(self):
        return f"{self.profissional} — {self.get_dia_semana_display()} {self.inicio}-{self.fim}"


class BloqueioAgendaSaude(models.Model):
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="bloqueios_agenda_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    profissional = models.ForeignKey(
        ProfissionalSaude,
        on_delete=models.PROTECT,
        related_name="bloqueios_agenda",
        null=True,
        blank=True,
    )
    sala = models.ForeignKey(
        SalaSaude,
        on_delete=models.PROTECT,
        related_name="bloqueios_agenda",
        null=True,
        blank=True,
    )
    inicio = models.DateTimeField()
    fim = models.DateTimeField()
    motivo = models.CharField(max_length=180)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bloqueios_agenda_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bloqueio de Agenda"
        verbose_name_plural = "Bloqueios de Agenda"
        ordering = ["-inicio", "-id"]
        indexes = [models.Index(fields=["inicio"]), models.Index(fields=["fim"])]

    def __str__(self):
        return f"Bloqueio {self.inicio:%d/%m %H:%M} - {self.fim:%d/%m %H:%M}"


class FilaEsperaSaude(models.Model):
    class Prioridade(models.TextChoices):
        BAIXA = "BAIXA", "Baixa"
        MEDIA = "MEDIA", "Média"
        ALTA = "ALTA", "Alta"

    class Status(models.TextChoices):
        AGUARDANDO = "AGUARDANDO", "Aguardando"
        CHAMADO = "CHAMADO", "Chamado"
        CONVERTIDO = "CONVERTIDO", "Convertido em agendamento"
        CANCELADO = "CANCELADO", "Cancelado"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="fila_espera_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    especialidade = models.ForeignKey(
        EspecialidadeSaude,
        on_delete=models.PROTECT,
        related_name="fila_espera",
        null=True,
        blank=True,
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="fila_espera_saude",
        null=True,
        blank=True,
    )
    paciente_nome = models.CharField(max_length=180)
    paciente_contato = models.CharField(max_length=80, blank=True, default="")
    prioridade = models.CharField(max_length=20, choices=Prioridade.choices, default=Prioridade.MEDIA)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AGUARDANDO)
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    chamado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Fila de Espera"
        verbose_name_plural = "Fila de Espera"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["prioridade"])]

    def __str__(self):
        return f"{self.paciente_nome} — {self.get_status_display()}"


class AuditoriaAlteracaoSaude(models.Model):
    entidade = models.CharField(max_length=80)
    objeto_id = models.CharField(max_length=64)
    campo = models.CharField(max_length=80)
    valor_anterior = models.TextField(blank=True, default="")
    valor_novo = models.TextField(blank=True, default="")
    justificativa = models.TextField()
    alterado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="alteracoes_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Auditoria de Alteração Clínica"
        verbose_name_plural = "Auditoria de Alterações Clínicas"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["entidade"]), models.Index(fields=["criado_em"])]

    def __str__(self):
        return f"{self.entidade}#{self.objeto_id} — {self.campo}"


class ProcedimentoSaude(models.Model):
    class Tipo(models.TextChoices):
        AMBULATORIAL = "AMBULATORIAL", "Ambulatorial"
        CURATIVO = "CURATIVO", "Curativo"
        ADMINISTRACAO_MED = "ADMINISTRACAO_MED", "Administração de medicamento"
        COLETA = "COLETA", "Coleta"
        OUTROS = "OUTROS", "Outros"

    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="procedimentos",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.AMBULATORIAL)
    descricao = models.CharField(max_length=180)
    materiais = models.TextField(blank=True, default="")
    intercorrencias = models.TextField(blank=True, default="")
    realizado_em = models.DateTimeField(default=timezone.now)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="procedimentos_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Procedimento"
        verbose_name_plural = "Procedimentos"
        ordering = ["-realizado_em", "-id"]
        indexes = [models.Index(fields=["tipo"]), models.Index(fields=["realizado_em"])]

    def __str__(self):
        return f"{self.descricao} — {self.atendimento.paciente_nome}"


class VacinacaoSaude(models.Model):
    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="vacinacoes",
    )
    vacina = models.CharField(max_length=180)
    dose = models.CharField(max_length=60, blank=True, default="")
    lote = models.CharField(max_length=80, blank=True, default="")
    fabricante = models.CharField(max_length=120, blank=True, default="")
    unidade_aplicadora = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="vacinacoes_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    aplicador = models.ForeignKey(
        ProfissionalSaude,
        on_delete=models.PROTECT,
        related_name="vacinacoes_aplicadas",
        null=True,
        blank=True,
    )
    data_aplicacao = models.DateField(default=timezone.localdate)
    reacoes = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vacinacoes_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vacinação"
        verbose_name_plural = "Vacinação"
        ordering = ["-data_aplicacao", "-id"]
        indexes = [models.Index(fields=["data_aplicacao"]), models.Index(fields=["vacina"])]

    def __str__(self):
        return f"{self.vacina} — {self.atendimento.paciente_nome}"


class EncaminhamentoSaude(models.Model):
    class Prioridade(models.TextChoices):
        ROTINA = "ROTINA", "Rotina"
        PRIORITARIO = "PRIORITARIO", "Prioritário"
        URGENTE = "URGENTE", "Urgente"

    class Status(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        EM_ANALISE = "EM_ANALISE", "Em análise"
        AGENDADO = "AGENDADO", "Agendado"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        INDEFERIDO = "INDEFERIDO", "Indeferido"

    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="encaminhamentos",
    )
    unidade_origem = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="encaminhamentos_origem",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    unidade_destino = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="encaminhamentos_destino",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
        null=True,
        blank=True,
    )
    especialidade_destino = models.ForeignKey(
        EspecialidadeSaude,
        on_delete=models.PROTECT,
        related_name="encaminhamentos",
        null=True,
        blank=True,
    )
    prioridade = models.CharField(max_length=20, choices=Prioridade.choices, default=Prioridade.ROTINA)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTO)
    justificativa = models.TextField()
    observacoes_regulacao = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="encaminhamentos_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Encaminhamento"
        verbose_name_plural = "Encaminhamentos"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["prioridade"]), models.Index(fields=["criado_em"])]

    def __str__(self):
        return f"Encaminhamento {self.atendimento.paciente_nome} — {self.get_status_display()}"


class CidSaude(models.Model):
    codigo = models.CharField(max_length=12, unique=True)
    descricao = models.CharField(max_length=255)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "CID"
        verbose_name_plural = "CIDs"
        ordering = ["codigo"]
        indexes = [models.Index(fields=["codigo"]), models.Index(fields=["ativo"])]

    def __str__(self):
        return f"{self.codigo} — {self.descricao}"


class ProgramaSaude(models.Model):
    class Tipo(models.TextChoices):
        CONVENIO = "CONVENIO", "Convênio"
        PROGRAMA = "PROGRAMA", "Programa"

    nome = models.CharField(max_length=180)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.PROGRAMA)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Programa/Convênio"
        verbose_name_plural = "Programas/Convênios"
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["nome", "tipo"], name="uniq_programa_saude_nome_tipo")]
        indexes = [models.Index(fields=["tipo"]), models.Index(fields=["ativo"])]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


class PacienteSaude(models.Model):
    class Sexo(models.TextChoices):
        FEMININO = "F", "Feminino"
        MASCULINO = "M", "Masculino"
        OUTRO = "O", "Outro"
        NAO_INFORMADO = "N", "Não informado"

    unidade_referencia = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="pacientes_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="pacientes_saude",
        null=True,
        blank=True,
    )
    programa = models.ForeignKey(
        ProgramaSaude,
        on_delete=models.PROTECT,
        related_name="pacientes",
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=180)
    data_nascimento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=1, choices=Sexo.choices, default=Sexo.NAO_INFORMADO)
    cartao_sus = models.CharField(max_length=32, blank=True, default="")
    cpf = models.CharField(max_length=14, blank=True, default="")
    cpf_enc = models.TextField(blank=True, default="")
    cpf_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    cpf_last4 = models.CharField(max_length=4, blank=True, default="")
    telefone = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    endereco = models.TextField(blank=True, default="")
    responsavel_nome = models.CharField(max_length=180, blank=True, default="")
    responsavel_telefone = models.CharField(max_length=40, blank=True, default="")
    vulnerabilidades = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["nome"]
        indexes = [models.Index(fields=["nome"]), models.Index(fields=["ativo"]), models.Index(fields=["cpf_hash"])]

    def save(self, *args, **kwargs):
        cpf_digits = resolve_cpf_digits(self.cpf, self.cpf_enc)
        cpf_enc, cpf_hash, cpf_last4 = derive_cpf_security_fields(cpf_digits)
        if cpf_digits:
            if cpf_enc:
                self.cpf_enc = cpf_enc
            if cpf_hash:
                self.cpf_hash = cpf_hash
        else:
            self.cpf_enc = ""
            self.cpf_hash = ""
        self.cpf_last4 = cpf_last4
        self.cpf = mask_cpf(cpf_digits)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class CheckInSaude(models.Model):
    class Status(models.TextChoices):
        AGUARDANDO_CLASSIFICACAO = "AGUARDANDO_CLASSIFICACAO", "Aguardando classificação"
        AGUARDANDO_ATENDIMENTO = "AGUARDANDO_ATENDIMENTO", "Aguardando atendimento"
        EM_ATENDIMENTO = "EM_ATENDIMENTO", "Em atendimento"
        FINALIZADO = "FINALIZADO", "Finalizado"
        CANCELADO = "CANCELADO", "Cancelado"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="checkins_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    agendamento = models.ForeignKey(
        AgendamentoSaude,
        on_delete=models.PROTECT,
        related_name="checkins",
        null=True,
        blank=True,
    )
    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="checkins",
        null=True,
        blank=True,
    )
    paciente = models.ForeignKey(
        PacienteSaude,
        on_delete=models.PROTECT,
        related_name="checkins",
        null=True,
        blank=True,
    )
    paciente_nome = models.CharField(max_length=180)
    motivo_visita = models.TextField(blank=True, default="")
    queixa_principal = models.TextField(blank=True, default="")
    classificacao_risco = models.CharField(max_length=40, blank=True, default="")
    pa_sistolica = models.PositiveIntegerField(null=True, blank=True)
    pa_diastolica = models.PositiveIntegerField(null=True, blank=True)
    frequencia_cardiaca = models.PositiveIntegerField(null=True, blank=True)
    temperatura = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    saturacao_o2 = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.AGUARDANDO_CLASSIFICACAO)
    chegada_em = models.DateTimeField(default=timezone.now)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkins_saude",
    )

    class Meta:
        verbose_name = "Check-in"
        verbose_name_plural = "Check-ins"
        ordering = ["-chegada_em", "-id"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["chegada_em"])]

    def __str__(self):
        return f"{self.paciente_nome} — {self.get_status_display()}"


class MedicamentoUsoContinuoSaude(models.Model):
    paciente = models.ForeignKey(
        PacienteSaude,
        on_delete=models.PROTECT,
        related_name="medicamentos_uso",
    )
    medicamento = models.CharField(max_length=180)
    dose = models.CharField(max_length=120, blank=True, default="")
    via = models.CharField(max_length=80, blank=True, default="")
    frequencia = models.CharField(max_length=120, blank=True, default="")
    inicio = models.DateField(null=True, blank=True)
    fim = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="medicamentos_uso_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medicamento em Uso Contínuo"
        verbose_name_plural = "Medicamentos em Uso Contínuo"
        ordering = ["paciente__nome", "medicamento"]
        indexes = [models.Index(fields=["ativo"]), models.Index(fields=["medicamento"])]

    def __str__(self):
        return f"{self.medicamento} — {self.paciente.nome}"


class DispensacaoSaude(models.Model):
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="dispensacoes_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    atendimento = models.ForeignKey(
        AtendimentoSaude,
        on_delete=models.PROTECT,
        related_name="dispensacoes",
        null=True,
        blank=True,
    )
    paciente = models.ForeignKey(
        PacienteSaude,
        on_delete=models.PROTECT,
        related_name="dispensacoes",
    )
    medicamento = models.CharField(max_length=180)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    unidade_medida = models.CharField(max_length=40, default="un")
    lote = models.CharField(max_length=80, blank=True, default="")
    validade = models.DateField(null=True, blank=True)
    orientacoes = models.TextField(blank=True, default="")
    dispensado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dispensacoes_saude",
    )
    dispensado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Dispensação"
        verbose_name_plural = "Dispensações"
        ordering = ["-dispensado_em", "-id"]
        indexes = [models.Index(fields=["dispensado_em"]), models.Index(fields=["medicamento"])]

    def __str__(self):
        return f"{self.medicamento} — {self.paciente.nome}"


class ExameColetaSaude(models.Model):
    class Status(models.TextChoices):
        SOLICITADO = "SOLICITADO", "Solicitado"
        COLETA_AGENDADA = "COLETA_AGENDADA", "Coleta agendada"
        COLETADO = "COLETADO", "Coletado"
        ENCAMINHADO = "ENCAMINHADO", "Encaminhado"
        RESULTADO_RECEBIDO = "RESULTADO_RECEBIDO", "Resultado recebido"

    pedido = models.OneToOneField(
        ExamePedidoSaude,
        on_delete=models.CASCADE,
        related_name="fluxo_coleta",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SOLICITADO)
    data_coleta = models.DateTimeField(null=True, blank=True)
    local_coleta = models.CharField(max_length=180, blank=True, default="")
    encaminhado_para = models.CharField(max_length=180, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fluxos_exame_saude",
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fluxo de Exame"
        verbose_name_plural = "Fluxos de Exame"
        ordering = ["-atualizado_em", "-id"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.pedido.nome_exame} — {self.get_status_display()}"


class InternacaoSaude(models.Model):
    class Tipo(models.TextChoices):
        INTERNACAO = "INTERNACAO", "Internação"
        OBSERVACAO = "OBSERVACAO", "Observação"

    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        ALTA = "ALTA", "Alta"
        TRANSFERIDA = "TRANSFERIDA", "Transferida"
        OBITO = "OBITO", "Óbito"

    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="internacoes_saude",
        limit_choices_to={"tipo": Unidade.Tipo.SAUDE},
    )
    paciente = models.ForeignKey(
        PacienteSaude,
        on_delete=models.PROTECT,
        related_name="internacoes",
    )
    profissional_responsavel = models.ForeignKey(
        ProfissionalSaude,
        on_delete=models.PROTECT,
        related_name="internacoes_responsavel",
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OBSERVACAO)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVA)
    data_admissao = models.DateTimeField(default=timezone.now)
    data_alta = models.DateTimeField(null=True, blank=True)
    leito = models.CharField(max_length=80, blank=True, default="")
    motivo = models.TextField()
    resumo_alta = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="internacoes_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Internação/Observação"
        verbose_name_plural = "Internações/Observações"
        ordering = ["-data_admissao", "-id"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["tipo"]), models.Index(fields=["data_admissao"])]

    def __str__(self):
        return f"{self.paciente.nome} — {self.get_tipo_display()}"


class InternacaoRegistroSaude(models.Model):
    class Tipo(models.TextChoices):
        EVOLUCAO = "EVOLUCAO", "Evolução"
        PRESCRICAO_INTERNA = "PRESCRICAO_INTERNA", "Prescrição interna"

    internacao = models.ForeignKey(
        InternacaoSaude,
        on_delete=models.CASCADE,
        related_name="registros",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    texto = models.TextField()
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registros_internacao_saude",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Internação"
        verbose_name_plural = "Registros de Internação"
        ordering = ["-criado_em", "-id"]
        indexes = [models.Index(fields=["tipo"]), models.Index(fields=["criado_em"])]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.internacao.paciente.nome}"
