from __future__ import annotations

from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def _current_year() -> int:
    return timezone.localdate().year


class ProgramaComplementar(models.Model):
    class Tipo(models.TextChoices):
        INFORMATICA = "INFORMATICA", "Informática"
        BALLET = "BALLET", "Ballet"
        REFORCO = "REFORCO", "Reforço"
        OFICINA = "OFICINA", "Oficina"
        PROJETO = "PROJETO", "Projeto"
        ESPORTE = "ESPORTE", "Esporte"
        CULTURA = "CULTURA", "Cultura"
        APOIO_PEDAGOGICO = "APOIO_PEDAGOGICO", "Apoio pedagógico"
        OUTRO = "OUTRO", "Outro"

    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"
        ENCERRADO = "ENCERRADO", "Encerrado"

    nome = models.CharField(max_length=180)
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.OUTRO)
    slug = models.SlugField(max_length=120, unique=True)
    descricao = models.TextField(blank=True, default="")
    objetivo = models.TextField(blank=True, default="")
    publico_alvo = models.CharField(max_length=180, blank=True, default="")
    faixa_etaria_min = models.PositiveSmallIntegerField(null=True, blank=True)
    faixa_etaria_max = models.PositiveSmallIntegerField(null=True, blank=True)
    exige_vinculo_escolar_ativo = models.BooleanField(default=True)
    permite_multiplas_participacoes = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO, db_index=True)
    secretaria_responsavel = models.ForeignKey(
        "org.Secretaria",
        on_delete=models.PROTECT,
        related_name="programas_complementares",
        null=True,
        blank=True,
    )
    unidade_gestora = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="programas_complementares_gestora",
        null=True,
        blank=True,
    )
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Programa complementar"
        verbose_name_plural = "Programas complementares"
        ordering = ["nome", "id"]
        indexes = [
            models.Index(fields=["tipo", "status"]),
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
        ]

    def clean(self):
        errors = {}
        if self.faixa_etaria_min is not None and self.faixa_etaria_max is not None:
            if int(self.faixa_etaria_max) < int(self.faixa_etaria_min):
                errors["faixa_etaria_max"] = "A faixa etária máxima não pode ser menor que a mínima."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome or "")
            self.slug = base or f"programa-{self.pk or ''}".strip("-")
        self.slug = (self.slug or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nome


class ProgramaComplementarOferta(models.Model):
    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"
        INTEGRAL = "INTEGRAL", "Integral"
        FLEXIVEL = "FLEXIVEL", "Flexível"

    class Status(models.TextChoices):
        PLANEJADA = "PLANEJADA", "Planejada"
        ATIVA = "ATIVA", "Ativa"
        ENCERRADA = "ENCERRADA", "Encerrada"
        CANCELADA = "CANCELADA", "Cancelada"

    programa = models.ForeignKey(
        "educacao.ProgramaComplementar",
        on_delete=models.PROTECT,
        related_name="ofertas",
    )
    unidade = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="programas_complementares_ofertas",
    )
    ano_letivo = models.PositiveIntegerField(default=_current_year, db_index=True)
    codigo = models.CharField(max_length=60)
    nome = models.CharField(max_length=180)
    turno = models.CharField(max_length=15, choices=Turno.choices, default=Turno.MANHA)
    capacidade_maxima = models.PositiveSmallIntegerField(default=20)
    idade_minima = models.PositiveSmallIntegerField(null=True, blank=True)
    idade_maxima = models.PositiveSmallIntegerField(null=True, blank=True)
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programas_complementares_ofertas_responsavel",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANEJADA, db_index=True)
    exige_vinculo_escolar_ativo = models.BooleanField(default=True)
    permite_sobreposicao_horario = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True, default="")
    legacy_informatica_turma = models.OneToOneField(
        "educacao.InformaticaTurma",
        on_delete=models.SET_NULL,
        related_name="programa_complementar_oferta",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Oferta do programa complementar"
        verbose_name_plural = "Ofertas dos programas complementares"
        ordering = ["-ano_letivo", "programa__nome", "codigo", "id"]
        constraints = [
            models.UniqueConstraint(fields=["programa", "codigo", "ano_letivo"], name="uniq_prog_comp_oferta_codigo_ano"),
        ]
        indexes = [
            models.Index(fields=["programa", "status"]),
            models.Index(fields=["unidade", "status"]),
            models.Index(fields=["ano_letivo", "status"]),
        ]

    @property
    def vagas_ocupadas(self) -> int:
        return self.participacoes.filter(status=ProgramaComplementarParticipacao.Status.ATIVO).count()

    @property
    def vagas_disponiveis(self) -> int:
        return max(0, int(self.capacidade_maxima or 0) - int(self.vagas_ocupadas))

    def clean(self):
        errors = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            errors["data_fim"] = "A data final não pode ser anterior à data inicial."
        if self.idade_minima is not None and self.idade_maxima is not None:
            if int(self.idade_maxima) < int(self.idade_minima):
                errors["idade_maxima"] = "A idade máxima não pode ser menor que a idade mínima."
        if self.capacidade_maxima < 1:
            errors["capacidade_maxima"] = "A capacidade máxima deve ser maior que zero."
        if self.unidade_id and getattr(self.unidade, "tipo", None) != "EDUCACAO":
            errors["unidade"] = "A oferta deve estar vinculada a uma unidade de Educação."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.codigo} • {self.nome}"


class ProgramaComplementarHorario(models.Model):
    class DiaSemana(models.IntegerChoices):
        SEGUNDA = 0, "Segunda"
        TERCA = 1, "Terça"
        QUARTA = 2, "Quarta"
        QUINTA = 3, "Quinta"
        SEXTA = 4, "Sexta"
        SABADO = 5, "Sábado"

    class FrequenciaTipo(models.TextChoices):
        SEMANAL = "SEMANAL", "Semanal"
        QUINZENAL = "QUINZENAL", "Quinzenal"
        MENSAL = "MENSAL", "Mensal"
        ESPECIFICA = "ESPECIFICA", "Data específica"

    oferta = models.ForeignKey(
        "educacao.ProgramaComplementarOferta",
        on_delete=models.CASCADE,
        related_name="horarios",
    )
    dia_semana = models.IntegerField(choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    frequencia_tipo = models.CharField(max_length=20, choices=FrequenciaTipo.choices, default=FrequenciaTipo.SEMANAL)
    turno = models.CharField(max_length=15, choices=ProgramaComplementarOferta.Turno.choices, blank=True, default="")
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Horário da oferta complementar"
        verbose_name_plural = "Horários das ofertas complementares"
        ordering = ["dia_semana", "hora_inicio", "id"]
        indexes = [
            models.Index(fields=["oferta", "ativo"]),
            models.Index(fields=["dia_semana", "hora_inicio", "hora_fim"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["oferta", "dia_semana", "hora_inicio", "hora_fim"],
                name="uniq_prog_comp_oferta_horario",
            ),
        ]

    def clean(self):
        errors = {}
        if self.hora_fim and self.hora_inicio and self.hora_fim <= self.hora_inicio:
            errors["hora_fim"] = "O horário final deve ser maior que o horário inicial."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.oferta.codigo} • {self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fim:%H:%M}"


class ProgramaComplementarParticipacao(models.Model):
    class Status(models.TextChoices):
        PRE_INSCRITO = "PRE_INSCRITO", "Pré-inscrito"
        ATIVO = "ATIVO", "Ativo"
        AGUARDANDO_VAGA = "AGUARDANDO_VAGA", "Aguardando vaga"
        TRANSFERIDO = "TRANSFERIDO", "Transferido"
        CONCLUIDO = "CONCLUIDO", "Concluído"
        CANCELADO = "CANCELADO", "Cancelado"
        DESLIGADO = "DESLIGADO", "Desligado"
        SUSPENSO = "SUSPENSO", "Suspenso"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="programas_complementares_participacoes",
    )
    matricula_institucional = models.ForeignKey(
        "educacao.MatriculaInstitucional",
        on_delete=models.PROTECT,
        related_name="programas_complementares_participacoes",
    )
    programa = models.ForeignKey(
        "educacao.ProgramaComplementar",
        on_delete=models.PROTECT,
        related_name="participacoes",
    )
    oferta = models.ForeignKey(
        "educacao.ProgramaComplementarOferta",
        on_delete=models.PROTECT,
        related_name="participacoes",
    )
    escola_origem = models.ForeignKey(
        "org.Unidade",
        on_delete=models.PROTECT,
        related_name="programas_complementares_participacoes_origem",
        null=True,
        blank=True,
    )
    ano_letivo = models.PositiveIntegerField(default=_current_year, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO, db_index=True)
    data_ingresso = models.DateField(default=timezone.localdate)
    data_saida = models.DateField(null=True, blank=True)
    motivo_saida = models.TextField(blank=True, default="")
    origem_vinculo = models.CharField(max_length=80, blank=True, default="MANUAL")
    observacoes = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programas_complementares_participacoes_criadas",
    )
    legacy_informatica_matricula = models.OneToOneField(
        "educacao.InformaticaMatricula",
        on_delete=models.SET_NULL,
        related_name="programa_complementar_participacao",
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Participação em programa complementar"
        verbose_name_plural = "Participações em programas complementares"
        ordering = ["-data_ingresso", "-id"]
        indexes = [
            models.Index(fields=["aluno", "status"]),
            models.Index(fields=["programa", "status"]),
            models.Index(fields=["oferta", "status"]),
            models.Index(fields=["matricula_institucional", "status"]),
        ]

    @classmethod
    def statuses_ativos(cls) -> list[str]:
        return [cls.Status.ATIVO]

    def clean(self):
        errors = {}
        if self.matricula_institucional_id and self.aluno_id:
            if self.matricula_institucional.aluno_id != self.aluno_id:
                errors["matricula_institucional"] = "A matrícula institucional informada não pertence ao aluno."
        if self.programa_id and self.oferta_id and self.oferta.programa_id != self.programa_id:
            errors["oferta"] = "A oferta informada não pertence ao programa selecionado."
        if self.data_saida and self.data_ingresso and self.data_saida < self.data_ingresso:
            errors["data_saida"] = "A data de saída não pode ser anterior à data de ingresso."
        if self.escola_origem_id and getattr(self.escola_origem, "tipo", None) != "EDUCACAO":
            errors["escola_origem"] = "A escola de origem precisa ser do tipo Educação."
        if self.oferta_id and self.status == self.Status.ATIVO:
            ocupadas = self.oferta.participacoes.filter(status=self.Status.ATIVO).exclude(pk=self.pk).count()
            if ocupadas >= int(self.oferta.capacidade_maxima or 0):
                errors["oferta"] = "A oferta selecionada está sem vagas disponíveis."
            if self.oferta.status != ProgramaComplementarOferta.Status.ATIVA:
                errors["oferta"] = "A oferta selecionada não está ativa."
            if self.programa_id and self.programa.status != ProgramaComplementar.Status.ATIVO:
                errors["programa"] = "O programa selecionado não está ativo."

            requires_school_link = bool(
                getattr(self.oferta, "exige_vinculo_escolar_ativo", False)
                or getattr(self.programa, "exige_vinculo_escolar_ativo", False)
            )
            if requires_school_link and self.aluno_id:
                from .models import Matricula

                if not Matricula.objects.filter(aluno_id=self.aluno_id, situacao=Matricula.Situacao.ATIVA).exists():
                    errors["aluno"] = "Somente alunos com vínculo escolar ativo podem participar."

            ref_date = self.data_ingresso or timezone.localdate()
            aluno_age = calculate_age(getattr(self.aluno, "data_nascimento", None), ref_date=ref_date) if self.aluno_id else None
            program_min = self.programa.faixa_etaria_min if self.programa_id else None
            program_max = self.programa.faixa_etaria_max if self.programa_id else None
            min_age = self.oferta.idade_minima if self.oferta_id and self.oferta.idade_minima is not None else program_min
            max_age = self.oferta.idade_maxima if self.oferta_id and self.oferta.idade_maxima is not None else program_max
            if aluno_age is not None and min_age is not None and int(aluno_age) < int(min_age):
                errors["aluno"] = "Aluno abaixo da faixa etária mínima da oferta."
            if aluno_age is not None and max_age is not None and int(aluno_age) > int(max_age):
                errors["aluno"] = "Aluno acima da faixa etária máxima da oferta."

            if self.aluno_id and self.oferta_id:
                from .services_schedule_conflicts import ScheduleConflictService

                result = ScheduleConflictService.validate_program_enrollment(
                    aluno=self.aluno,
                    oferta=self.oferta,
                    data_ingresso=self.data_ingresso,
                    exclude_programa_participacao_id=self.pk,
                )
                if result.has_conflict and result.blocking_mode == "block":
                    errors["oferta"] = result.message
        if errors:
            raise ValidationError(errors)

    @property
    def percentual_frequencia(self) -> float | None:
        total = self.frequencias.count()
        if total == 0:
            return None
        presentes = self.frequencias.filter(status_presenca=ProgramaComplementarFrequencia.StatusPresenca.PRESENTE).count()
        return float(presentes * 100.0 / total)

    def __str__(self) -> str:
        return f"{self.aluno.nome} • {self.programa.nome} • {self.get_status_display()}"


class ProgramaComplementarFrequencia(models.Model):
    class StatusPresenca(models.TextChoices):
        PRESENTE = "PRESENTE", "Presente"
        AUSENTE = "AUSENTE", "Ausente"
        JUSTIFICADO = "JUSTIFICADO", "Justificado"
        REPOSICAO = "REPOSICAO", "Reposição"
        ATRASO = "ATRASO", "Atraso"

    participacao = models.ForeignKey(
        "educacao.ProgramaComplementarParticipacao",
        on_delete=models.CASCADE,
        related_name="frequencias",
    )
    data_aula = models.DateField(default=timezone.localdate, db_index=True)
    status_presenca = models.CharField(max_length=20, choices=StatusPresenca.choices, default=StatusPresenca.PRESENTE)
    justificativa = models.TextField(blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programas_complementares_frequencias_registradas",
    )
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Frequência em programa complementar"
        verbose_name_plural = "Frequências em programas complementares"
        ordering = ["-data_aula", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["participacao", "data_aula"], name="uniq_prog_comp_frequencia_por_dia"),
        ]
        indexes = [
            models.Index(fields=["participacao", "data_aula"]),
            models.Index(fields=["status_presenca"]),
        ]

    def __str__(self) -> str:
        return f"{self.participacao.aluno.nome} • {self.data_aula:%d/%m/%Y} • {self.get_status_presenca_display()}"


class ProgramaComplementarParticipacaoLog(models.Model):
    class Acao(models.TextChoices):
        CRIACAO = "CRIACAO", "Criação"
        ATUALIZACAO = "ATUALIZACAO", "Atualização"
        MUDANCA_STATUS = "MUDANCA_STATUS", "Mudança de status"
        FREQUENCIA = "FREQUENCIA", "Registro de frequência"

    participacao = models.ForeignKey(
        "educacao.ProgramaComplementarParticipacao",
        on_delete=models.CASCADE,
        related_name="logs",
    )
    acao = models.CharField(max_length=30, choices=Acao.choices, default=Acao.ATUALIZACAO)
    status_anterior = models.CharField(max_length=20, blank=True, default="")
    status_novo = models.CharField(max_length=20, blank=True, default="")
    executado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programas_complementares_logs",
    )
    executado_em = models.DateTimeField(auto_now_add=True)
    notas = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Log de participação em programa complementar"
        verbose_name_plural = "Logs de participação em programas complementares"
        ordering = ["-executado_em", "-id"]
        indexes = [
            models.Index(fields=["participacao", "executado_em"]),
            models.Index(fields=["acao"]),
        ]

    def __str__(self) -> str:
        return f"{self.participacao.aluno.nome} • {self.get_acao_display()} • {self.executado_em:%d/%m/%Y %H:%M}"


def calculate_age(birth_date: date | None, ref_date: date | None = None) -> int | None:
    if birth_date is None:
        return None
    ref = ref_date or timezone.localdate()
    years = ref.year - birth_date.year
    if (ref.month, ref.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(0, int(years))
