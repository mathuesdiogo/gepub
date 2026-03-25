from __future__ import annotations

from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.org.models import Municipio, Unidade
from .models_diario import AVALIACAO_MODO_CHOICES, AVALIACAO_TIPO_CHOICES


def _to_minutes(value: time) -> int:
    return int(value.hour) * 60 + int(value.minute)


def _ranges_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    return _to_minutes(start_a) < _to_minutes(end_b) and _to_minutes(start_b) < _to_minutes(end_a)


def _current_year() -> int:
    return timezone.localdate().year


class InformaticaCurso(models.Model):
    class Modalidade(models.TextChoices):
        COMPLEMENTAR = "COMPLEMENTAR", "Complementar"
        LIVRE = "LIVRE", "Livre"
        PROFISSIONALIZANTE = "PROFISSIONALIZANTE", "Profissionalizante"

    municipio = models.ForeignKey(
        Municipio,
        on_delete=models.PROTECT,
        related_name="informatica_cursos",
    )
    nome = models.CharField(max_length=180)
    descricao = models.TextField(blank=True, default="")
    modalidade = models.CharField(max_length=30, choices=Modalidade.choices, default=Modalidade.COMPLEMENTAR)
    carga_horaria_total = models.PositiveIntegerField(default=80)
    faixa_etaria = models.CharField(max_length=100, blank=True, default="")
    ano_escolar_permitido = models.CharField(max_length=160, blank=True, default="")

    aulas_por_semana = models.PositiveSmallIntegerField(default=2)
    duracao_bloco_minutos = models.PositiveSmallIntegerField(default=60)
    minutos_aula_efetiva = models.PositiveSmallIntegerField(default=45)
    minutos_intervalo_tecnico = models.PositiveSmallIntegerField(default=15)
    max_alunos_por_turma = models.PositiveSmallIntegerField(default=12)
    permitir_multiplas_turmas_por_aluno = models.BooleanField(default=False)

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Curso de informática"
        verbose_name_plural = "Cursos de informática"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["municipio", "ativo"]),
            models.Index(fields=["nome"]),
            models.Index(fields=["ativo"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["municipio", "nome"], name="uniq_informatica_curso_nome_municipio"),
        ]

    def clean(self):
        errors: dict[str, str] = {}
        if self.aulas_por_semana != 2:
            errors["aulas_por_semana"] = "O curso deve ter exatamente 2 aulas por semana."
        if self.minutos_aula_efetiva + self.minutos_intervalo_tecnico != self.duracao_bloco_minutos:
            errors["duracao_bloco_minutos"] = "Duração do bloco deve ser igual a aula efetiva + intervalo técnico."
        if self.max_alunos_por_turma > 12:
            errors["max_alunos_por_turma"] = "Máximo permitido por regra operacional é 12 alunos por turma."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.nome} ({self.municipio.nome})"


class InformaticaLaboratorio(models.Model):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"
        INATIVO = "INATIVO", "Inativo"

    nome = models.CharField(max_length=180)
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="laboratorios_informatica",
    )
    endereco = models.CharField(max_length=220, blank=True, default="")
    quantidade_computadores = models.PositiveSmallIntegerField(default=0)
    capacidade_operacional = models.PositiveSmallIntegerField(default=12)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO)
    responsavel_local = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="laboratorios_informatica_responsavel",
    )
    observacoes = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Laboratório de informática"
        verbose_name_plural = "Laboratórios de informática"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["ativo"]),
            models.Index(fields=["unidade"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["unidade", "nome"], name="uniq_lab_informatica_unidade_nome"),
        ]

    def clean(self):
        errors: dict[str, str] = {}
        if self.unidade_id and self.unidade.tipo != Unidade.Tipo.EDUCACAO:
            errors["unidade"] = "Selecione uma unidade do tipo Educação."
        if self.capacidade_operacional < 1:
            errors["capacidade_operacional"] = "Informe capacidade operacional maior que zero."
        if self.capacidade_operacional > 12:
            errors["capacidade_operacional"] = "Capacidade operacional não pode ultrapassar 12 por regra do curso."
        if self.quantidade_computadores and self.capacidade_operacional > self.quantidade_computadores:
            errors["capacidade_operacional"] = "Capacidade operacional não pode exceder a quantidade de computadores."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.nome} ({self.unidade.nome})"


class InformaticaGradeHorario(models.Model):
    class TipoGrade(models.TextChoices):
        PADRAO_SEMANAL = "PADRAO_SEMANAL", "Semanal em 2 dias"
        ESPECIAL_SEXTA = "ESPECIAL_SEXTA", "Especial de sexta-feira"

    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"

    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        INATIVA = "INATIVA", "Inativa"

    class DiaSemana(models.IntegerChoices):
        SEGUNDA = 0, "Segunda"
        TERCA = 1, "Terça"
        QUARTA = 2, "Quarta"
        QUINTA = 3, "Quinta"
        SEXTA = 4, "Sexta"
        SABADO = 5, "Sábado"

    nome = models.CharField(max_length=180)
    codigo = models.CharField(max_length=60)
    descricao = models.TextField(blank=True, default="")
    tipo_grade = models.CharField(max_length=30, choices=TipoGrade.choices, default=TipoGrade.PADRAO_SEMANAL)

    laboratorio = models.ForeignKey(
        InformaticaLaboratorio,
        on_delete=models.PROTECT,
        related_name="grades_horario",
    )
    turno = models.CharField(max_length=10, choices=Turno.choices, default=Turno.MANHA)
    dia_semana_1 = models.IntegerField(choices=DiaSemana.choices)
    dia_semana_2 = models.IntegerField(
        choices=DiaSemana.choices,
        null=True,
        blank=True,
    )
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()

    duracao_total_minutos = models.PositiveSmallIntegerField(default=60)
    duracao_aula_minutos = models.PositiveSmallIntegerField(default=45)
    duracao_intervalo_minutos = models.PositiveSmallIntegerField(default=15)
    pausa_interna_opcional_minutos = models.PositiveSmallIntegerField(default=0)
    professor_principal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grades_informatica_principais",
    )

    ano_letivo = models.PositiveIntegerField(default=timezone.localdate().year)
    periodo_letivo = models.CharField(max_length=80, blank=True, default="")
    capacidade_maxima = models.PositiveSmallIntegerField(default=12)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVA)
    observacoes = models.TextField(blank=True, default="")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Grade de horário (informática)"
        verbose_name_plural = "Grades de horário (informática)"
        ordering = ["-ano_letivo", "laboratorio__nome", "hora_inicio", "codigo"]
        indexes = [
            models.Index(fields=["laboratorio", "status", "ano_letivo"]),
            models.Index(fields=["turno", "status"]),
            models.Index(fields=["tipo_grade", "status"]),
            models.Index(fields=["dia_semana_1", "dia_semana_2"]),
            models.Index(fields=["ativo"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["laboratorio", "codigo", "ano_letivo"],
                name="uniq_grade_informatica_lab_codigo_ano",
            ),
        ]

    @property
    def quantidade_encontros_semana(self) -> int:
        return 1 if self.tipo_grade == self.TipoGrade.ESPECIAL_SEXTA else 2

    @property
    def dias_semana(self) -> list[int]:
        days = [int(self.dia_semana_1)]
        if self.dia_semana_2 is not None:
            days.append(int(self.dia_semana_2))
        return days

    @property
    def encontro_unico_semana(self) -> bool:
        return self.quantidade_encontros_semana == 1

    def clean(self):
        errors: dict[str, str] = {}

        if self.hora_inicio and self.hora_fim and self.hora_fim <= self.hora_inicio:
            errors["hora_fim"] = "Horário final deve ser maior que o horário inicial."

        duracao_total = int(self.duracao_total_minutos or 0)
        duracao_aula = int(self.duracao_aula_minutos or 0)
        duracao_intervalo = int(self.duracao_intervalo_minutos or 0)

        if self.hora_inicio and self.hora_fim:
            duracao_horario = _to_minutes(self.hora_fim) - _to_minutes(self.hora_inicio)
            if duracao_horario != duracao_total:
                errors["duracao_total_minutos"] = "A duração total deve corresponder ao intervalo entre início e fim."
        if duracao_aula + duracao_intervalo != duracao_total:
            errors["duracao_total_minutos"] = "Duração total deve ser igual a aula + intervalo técnico."
        if self.capacidade_maxima > 12:
            errors["capacidade_maxima"] = "Capacidade máxima não pode ultrapassar 12 alunos."

        if self.tipo_grade == self.TipoGrade.PADRAO_SEMANAL:
            if self.dia_semana_2 is None:
                errors["dia_semana_2"] = "A grade padrão precisa de 2 dias fixos por semana."
            if self.dia_semana_1 is not None and self.dia_semana_2 is not None and int(self.dia_semana_1) == int(self.dia_semana_2):
                errors["dia_semana_2"] = "Os dois dias da semana devem ser diferentes."
            if duracao_total != 60:
                errors["duracao_total_minutos"] = "Na grade padrão o bloco deve ter 60 minutos."
            if duracao_aula != 45 or duracao_intervalo != 15:
                errors["duracao_aula_minutos"] = "Na grade padrão use 45 minutos de aula e 15 de intervalo."

        if self.tipo_grade == self.TipoGrade.ESPECIAL_SEXTA:
            if self.dia_semana_1 is None or int(self.dia_semana_1) != int(self.DiaSemana.SEXTA):
                errors["dia_semana_1"] = "A grade especial deve ser fixa na sexta-feira."
            if self.dia_semana_2 is not None:
                errors["dia_semana_2"] = "A grade especial de sexta aceita apenas 1 dia semanal."
            if duracao_total <= 60:
                errors["duracao_total_minutos"] = "A grade especial de sexta deve ter duração ampliada (maior que 60 min)."

        if self.laboratorio_id and self.capacidade_maxima > self.laboratorio.capacidade_operacional:
            errors["capacidade_maxima"] = "Capacidade da grade excede a capacidade operacional do laboratório."

        # Conflitos por laboratório e professor (agenda oficial reutilizável)
        if self.laboratorio_id:
            base_qs = (
                InformaticaGradeHorario.objects.filter(
                    laboratorio_id=self.laboratorio_id,
                    ano_letivo=self.ano_letivo,
                    status=self.Status.ATIVA,
                    ativo=True,
                )
                .exclude(pk=self.pk)
            )
            for other in base_qs:
                for d1 in self.dias_semana:
                    for d2 in other.dias_semana:
                        if int(d1) != int(d2):
                            continue
                        if _ranges_overlap(self.hora_inicio, self.hora_fim, other.hora_inicio, other.hora_fim):
                            errors["hora_inicio"] = "Conflito com outra grade ativa no mesmo laboratório."
                            break
                    if errors:
                        break
                if errors:
                    break

        if self.professor_principal_id:
            prof_qs = (
                InformaticaGradeHorario.objects.filter(
                    professor_principal_id=self.professor_principal_id,
                    ano_letivo=self.ano_letivo,
                    status=self.Status.ATIVA,
                    ativo=True,
                )
                .exclude(pk=self.pk)
            )
            for other in prof_qs:
                for d1 in self.dias_semana:
                    for d2 in other.dias_semana:
                        if int(d1) != int(d2):
                            continue
                        if _ranges_overlap(self.hora_inicio, self.hora_fim, other.hora_inicio, other.hora_fim):
                            errors["professor_principal"] = "Professor já está alocado em grade no mesmo horário."
                            break
                    if errors:
                        break
                if errors:
                    break

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.codigo} • {self.nome}"


class InformaticaTurma(models.Model):
    class Turno(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"

    class Status(models.TextChoices):
        PLANEJADA = "PLANEJADA", "Planejada"
        ATIVA = "ATIVA", "Ativa"
        ENCERRADA = "ENCERRADA", "Encerrada"
        CANCELADA = "CANCELADA", "Cancelada"

    curso = models.ForeignKey(
        InformaticaCurso,
        on_delete=models.PROTECT,
        related_name="turmas",
    )
    grade_horario = models.ForeignKey(
        InformaticaGradeHorario,
        on_delete=models.PROTECT,
        related_name="turmas",
        null=True,
        blank=True,
    )
    laboratorio = models.ForeignKey(
        InformaticaLaboratorio,
        on_delete=models.PROTECT,
        related_name="turmas",
    )
    codigo = models.CharField(max_length=60)
    nome = models.CharField(max_length=180, blank=True, default="")
    turno = models.CharField(max_length=10, choices=Turno.choices, default=Turno.MANHA)
    instrutor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="turmas_informatica_instrutor",
    )
    ano_letivo = models.PositiveIntegerField(default=timezone.localdate().year)
    periodo_letivo = models.CharField(max_length=80, blank=True, default="")
    modalidade_oferta = models.CharField(max_length=30, default="PADRAO_SEMANAL")
    carga_horaria_semanal_minutos = models.PositiveSmallIntegerField(default=120)
    encontro_unico_semana = models.BooleanField(default=False)
    max_vagas = models.PositiveSmallIntegerField(default=12)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANEJADA)
    permite_aluno_externo = models.BooleanField(default=True)
    permite_sobreposicao_horario = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Turma de informática"
        verbose_name_plural = "Turmas de informática"
        ordering = ["-ano_letivo", "codigo"]
        indexes = [
            models.Index(fields=["curso", "ano_letivo"]),
            models.Index(fields=["laboratorio", "turno"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["curso", "codigo", "ano_letivo"], name="uniq_turma_informatica_codigo_ano"),
        ]

    @property
    def encontros_ativos_qs(self):
        return self.encontros.filter(ativo=True).order_by("dia_semana", "hora_inicio")

    @property
    def encontros_ativos_count(self) -> int:
        return self.encontros.filter(ativo=True).count()

    @property
    def vagas_ocupadas(self) -> int:
        return self.matriculas.filter(status=InformaticaMatricula.Status.MATRICULADO).count()

    @property
    def vagas_livres(self) -> int:
        return max(0, int(self.max_vagas) - int(self.vagas_ocupadas))

    @property
    def quantidade_encontros_semana(self) -> int:
        if self.grade_horario_id:
            return self.grade_horario.quantidade_encontros_semana
        return 2

    def clean(self):
        errors: dict[str, str] = {}
        if not self.grade_horario_id:
            errors["grade_horario"] = "Toda turma deve estar vinculada a uma grade de horários."
        if self.max_vagas > 12:
            errors["max_vagas"] = "Cada turma pode ter no máximo 12 alunos."
        if self.curso_id and self.max_vagas > self.curso.max_alunos_por_turma:
            errors["max_vagas"] = "Máximo de vagas excede a configuração do curso."
        if self.laboratorio_id and self.max_vagas > self.laboratorio.capacidade_operacional:
            errors["max_vagas"] = "Máximo de vagas excede a capacidade operacional do laboratório."
        if self.grade_horario_id and self.max_vagas > self.grade_horario.capacidade_maxima:
            errors["max_vagas"] = "Máximo de vagas excede a capacidade da grade selecionada."
        if self.curso_id and self.laboratorio_id:
            curso_municipio_id = self.curso.municipio_id
            lab_municipio_id = self.laboratorio.unidade.secretaria.municipio_id
            if curso_municipio_id and lab_municipio_id and int(curso_municipio_id) != int(lab_municipio_id):
                errors["laboratorio"] = "Curso e laboratório precisam pertencer ao mesmo município."
        if self.grade_horario_id and self.laboratorio_id and self.grade_horario.laboratorio_id != self.laboratorio_id:
            errors["grade_horario"] = "A grade selecionada pertence a outro laboratório."
        if self.grade_horario_id:
            if self.grade_horario.status != InformaticaGradeHorario.Status.ATIVA or not self.grade_horario.ativo:
                errors["grade_horario"] = "Selecione uma grade ativa."
            turma_ativa_usando_grade = (
                InformaticaTurma.objects.filter(
                    grade_horario_id=self.grade_horario_id,
                    status__in=[self.Status.PLANEJADA, self.Status.ATIVA],
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if turma_ativa_usando_grade:
                errors["grade_horario"] = "Esta grade já está vinculada a outra turma ativa/planejada."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.nome:
            self.nome = self.codigo
        if self.grade_horario_id:
            self.laboratorio_id = self.grade_horario.laboratorio_id
            self.turno = self.grade_horario.turno
            self.modalidade_oferta = self.grade_horario.tipo_grade
            self.carga_horaria_semanal_minutos = int(self.grade_horario.duracao_total_minutos) * int(
                self.grade_horario.quantidade_encontros_semana
            )
            self.encontro_unico_semana = bool(self.grade_horario.encontro_unico_semana)
            # Regra operacional: a turma sempre segue o professor principal da grade.
            if self.grade_horario.professor_principal_id:
                self.instrutor_id = self.grade_horario.professor_principal_id
            if not self.periodo_letivo and self.grade_horario.periodo_letivo:
                self.periodo_letivo = self.grade_horario.periodo_letivo
            if int(self.ano_letivo or 0) != int(self.grade_horario.ano_letivo):
                self.ano_letivo = self.grade_horario.ano_letivo
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.codigo} ({self.ano_letivo})"


class InformaticaEncontroSemanal(models.Model):
    class DiaSemana(models.IntegerChoices):
        SEGUNDA = 0, "Segunda"
        TERCA = 1, "Terça"
        QUARTA = 2, "Quarta"
        QUINTA = 3, "Quinta"
        SEXTA = 4, "Sexta"
        SABADO = 5, "Sábado"

    turma = models.ForeignKey(
        InformaticaTurma,
        on_delete=models.CASCADE,
        related_name="encontros",
    )
    grade_horario = models.ForeignKey(
        InformaticaGradeHorario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encontros_semanais",
    )
    dia_semana = models.IntegerField(choices=DiaSemana.choices)
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    minutos_aula_efetiva = models.PositiveSmallIntegerField(default=45)
    minutos_intervalo_tecnico = models.PositiveSmallIntegerField(default=15)
    tipo_encontro = models.CharField(max_length=30, default="REGULAR")
    formato_especial = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Encontro semanal da turma"
        verbose_name_plural = "Encontros semanais da turma"
        ordering = ["dia_semana", "hora_inicio"]
        indexes = [
            models.Index(fields=["dia_semana", "hora_inicio", "hora_fim"]),
            models.Index(fields=["turma", "ativo"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["turma", "dia_semana"], name="uniq_encontro_turma_dia"),
        ]

    def clean(self):
        errors: dict[str, str] = {}
        if self.hora_fim <= self.hora_inicio:
            errors["hora_fim"] = "Horário final deve ser maior que horário inicial."

        duracao = _to_minutes(self.hora_fim) - _to_minutes(self.hora_inicio)
        if duracao != (int(self.minutos_aula_efetiva) + int(self.minutos_intervalo_tecnico)):
            errors["hora_fim"] = "Bloco deve respeitar aula efetiva + intervalo técnico."
        if self.grade_horario_id and duracao != int(self.grade_horario.duracao_total_minutos):
            errors["hora_fim"] = "Horário do encontro deve respeitar a duração da grade."

        if self.turma_id:
            conflitos_lab = (
                InformaticaEncontroSemanal.objects.select_related("turma", "turma__laboratorio")
                .filter(
                    ativo=True,
                    dia_semana=self.dia_semana,
                    turma__laboratorio_id=self.turma.laboratorio_id,
                    turma__status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
                    turma__ano_letivo=self.turma.ano_letivo,
                )
                .exclude(pk=self.pk)
                .exclude(turma_id=self.turma_id)
            )
            for item in conflitos_lab:
                if _ranges_overlap(self.hora_inicio, self.hora_fim, item.hora_inicio, item.hora_fim):
                    errors["hora_inicio"] = "Conflito de horário com outra turma no mesmo laboratório."
                    break

            if self.turma.instrutor_id:
                conflitos_prof = (
                    InformaticaEncontroSemanal.objects.select_related("turma")
                    .filter(
                        ativo=True,
                        dia_semana=self.dia_semana,
                        turma__instrutor_id=self.turma.instrutor_id,
                        turma__status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
                        turma__ano_letivo=self.turma.ano_letivo,
                    )
                    .exclude(pk=self.pk)
                    .exclude(turma_id=self.turma_id)
                )
                for item in conflitos_prof:
                    if _ranges_overlap(self.hora_inicio, self.hora_fim, item.hora_inicio, item.hora_fim):
                        errors["hora_inicio"] = "Conflito de horário com o mesmo professor/instrutor."
                        break

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.turma.codigo} • {self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fim:%H:%M}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.turma_id:
            from .services_programas import ProgramasComplementaresService

            ProgramasComplementaresService.sync_informatica_offer_schedule(turma=self.turma)

    def delete(self, *args, **kwargs):
        turma = self.turma if self.turma_id else None
        super().delete(*args, **kwargs)
        if turma is not None:
            from .services_programas import ProgramasComplementaresService

            ProgramasComplementaresService.sync_informatica_offer_schedule(turma=turma)


class InformaticaSolicitacaoVaga(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        LISTA_ESPERA = "LISTA_ESPERA", "Lista de espera"
        RECUSADA = "RECUSADA", "Recusada"
        CANCELADA = "CANCELADA", "Cancelada"

    class TurnoPreferido(models.TextChoices):
        MANHA = "MANHA", "Manhã"
        TARDE = "TARDE", "Tarde"
        NOITE = "NOITE", "Noite"
        QUALQUER = "QUALQUER", "Qualquer"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="informatica_solicitacoes",
    )
    escola_origem = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="informatica_solicitacoes_origem",
    )
    curso = models.ForeignKey(
        InformaticaCurso,
        on_delete=models.PROTECT,
        related_name="solicitacoes",
    )
    turno_preferido = models.CharField(max_length=10, choices=TurnoPreferido.choices, default=TurnoPreferido.QUALQUER)
    laboratorio_preferido = models.ForeignKey(
        InformaticaLaboratorio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitacoes_preferidas",
    )
    disponibilidade = models.CharField(max_length=200, blank=True, default="")
    origem_indicacao = models.CharField(max_length=80, blank=True, default="Escola")
    prioridade = models.PositiveSmallIntegerField(default=0)
    observacoes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    data_solicitacao = models.DateField(default=timezone.localdate)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="informatica_solicitacoes_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Solicitação de vaga (informática)"
        verbose_name_plural = "Solicitações de vaga (informática)"
        ordering = ["status", "-prioridade", "data_solicitacao", "id"]
        indexes = [
            models.Index(fields=["status", "data_solicitacao"]),
            models.Index(fields=["curso", "turno_preferido"]),
            models.Index(fields=["escola_origem"]),
        ]

    def clean(self):
        errors: dict[str, str] = {}
        if self.aluno_id and not self.aluno.ativo:
            errors["aluno"] = "Aluno inativo não pode solicitar vaga."
        if self.escola_origem_id and self.escola_origem.tipo != Unidade.Tipo.EDUCACAO:
            errors["escola_origem"] = "A escola de origem deve ser uma unidade de Educação."
        if self.curso_id and self.escola_origem_id:
            escola_municipio_id = self.escola_origem.secretaria.municipio_id
            if self.curso.municipio_id and escola_municipio_id and int(self.curso.municipio_id) != int(escola_municipio_id):
                errors["curso"] = "Curso e escola de origem devem pertencer ao mesmo município."
        if self.laboratorio_preferido_id and self.laboratorio_preferido.status != InformaticaLaboratorio.Status.ATIVO:
            errors["laboratorio_preferido"] = "Laboratório preferido está indisponível."
        if self.laboratorio_preferido_id and self.curso_id:
            lab_municipio_id = self.laboratorio_preferido.unidade.secretaria.municipio_id
            if self.curso.municipio_id and lab_municipio_id and int(self.curso.municipio_id) != int(lab_municipio_id):
                errors["laboratorio_preferido"] = "Laboratório preferido está fora do município do curso."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.aluno.nome} • {self.curso.nome}"


class InformaticaListaEspera(models.Model):
    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        CONVOCADA = "CONVOCADA", "Convocada"
        ENCERRADA = "ENCERRADA", "Encerrada"

    solicitacao = models.OneToOneField(
        InformaticaSolicitacaoVaga,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="item_lista_espera",
    )
    curso = models.ForeignKey(
        InformaticaCurso,
        on_delete=models.PROTECT,
        related_name="lista_espera",
    )
    turma_preferida = models.ForeignKey(
        InformaticaTurma,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lista_espera_preferencial",
    )
    laboratorio_preferido = models.ForeignKey(
        InformaticaLaboratorio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lista_espera_preferencial",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="informatica_lista_espera",
    )
    escola_origem = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="informatica_lista_espera_origem",
    )
    turno_preferido = models.CharField(max_length=10, choices=InformaticaSolicitacaoVaga.TurnoPreferido.choices, default=InformaticaSolicitacaoVaga.TurnoPreferido.QUALQUER)
    prioridade = models.PositiveSmallIntegerField(default=0)
    posicao = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVA)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lista de espera (informática)"
        verbose_name_plural = "Lista de espera (informática)"
        ordering = ["curso", "posicao", "id"]
        indexes = [
            models.Index(fields=["curso", "status", "posicao"]),
            models.Index(fields=["aluno", "status"]),
        ]

    def __str__(self) -> str:
        return f"#{self.posicao} • {self.aluno.nome}"


class InformaticaMatricula(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADA = "APROVADA", "Aprovada"
        MATRICULADO = "MATRICULADO", "Matriculado"
        LISTA_ESPERA = "LISTA_ESPERA", "Lista de espera"
        TRANSFERIDO = "TRANSFERIDO", "Transferido"
        CANCELADO = "CANCELADO", "Cancelado"
        CONCLUIDO = "CONCLUIDO", "Concluído"

    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="informatica_matriculas",
    )
    escola_origem = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        related_name="informatica_matriculas_origem",
    )
    curso = models.ForeignKey(
        InformaticaCurso,
        on_delete=models.PROTECT,
        related_name="matriculas",
    )
    turma = models.ForeignKey(
        InformaticaTurma,
        on_delete=models.PROTECT,
        related_name="matriculas",
    )
    data_matricula = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.MATRICULADO)
    origem_indicacao = models.CharField(max_length=80, blank=True, default="Escola")
    prioridade = models.PositiveSmallIntegerField(default=0)
    externo_laboratorio = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True, default="")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="informatica_matriculas_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Matrícula do curso de informática"
        verbose_name_plural = "Matrículas do curso de informática"
        ordering = ["-data_matricula", "-id"]
        indexes = [
            models.Index(fields=["curso", "status"]),
            models.Index(fields=["turma", "status"]),
            models.Index(fields=["aluno", "status"]),
        ]

    @classmethod
    def statuses_ativos(cls) -> list[str]:
        return [cls.Status.APROVADA, cls.Status.MATRICULADO]

    def clean(self):
        errors: dict[str, str] = {}
        if self.turma_id and self.curso_id and self.turma.curso_id != self.curso_id:
            errors["curso"] = "Curso da matrícula deve ser o mesmo da turma selecionada."
        if self.escola_origem_id and self.escola_origem.tipo != Unidade.Tipo.EDUCACAO:
            errors["escola_origem"] = "A escola de origem deve ser uma unidade de Educação."

        if self.turma_id and self.escola_origem_id:
            turma_municipio_id = self.turma.laboratorio.unidade.secretaria.municipio_id
            escola_municipio_id = self.escola_origem.secretaria.municipio_id
            if turma_municipio_id and escola_municipio_id and int(turma_municipio_id) != int(escola_municipio_id):
                errors["escola_origem"] = "Escola de origem deve pertencer ao mesmo município da turma."

        if self.turma_id and self.status == self.Status.MATRICULADO:
            expected = int(self.turma.quantidade_encontros_semana)
            if self.turma.encontros_ativos_count != expected:
                errors["turma"] = f"Turma deve ter exatamente {expected} encontro(s) semanal(is) ativo(s)."

            ocupadas = self.turma.matriculas.filter(status=self.Status.MATRICULADO).exclude(pk=self.pk).count()
            if ocupadas >= self.turma.max_vagas:
                errors["turma"] = "Turma sem vagas disponíveis (limite atingido)."

        if self.aluno_id and self.curso_id and self.status in self.statuses_ativos():
            if not self.curso.permitir_multiplas_turmas_por_aluno:
                exists = (
                    InformaticaMatricula.objects.filter(
                        aluno_id=self.aluno_id,
                        curso_id=self.curso_id,
                        status__in=self.statuses_ativos(),
                    )
                    .exclude(pk=self.pk)
                    .exists()
                )
                if exists:
                    errors["aluno"] = "Aluno já possui matrícula ativa neste curso."

        if self.aluno_id and self.status == self.Status.MATRICULADO:
            conflitos = (
                InformaticaMatricula.objects.select_related("turma")
                .filter(
                    aluno_id=self.aluno_id,
                    status=self.Status.MATRICULADO,
                )
                .exclude(pk=self.pk)
            )
            meus_encontros = list(self.turma.encontros_ativos_qs) if self.turma_id else []
            for item in conflitos:
                for meu in meus_encontros:
                    for outro in item.turma.encontros_ativos_qs:
                        if meu.dia_semana == outro.dia_semana and _ranges_overlap(meu.hora_inicio, meu.hora_fim, outro.hora_inicio, outro.hora_fim):
                            errors["aluno"] = "Conflito de horário com outra atividade do aluno."
                            break
                    if errors:
                        break
                if errors:
                    break

        if self.aluno_id and self.turma_id and self.status in self.statuses_ativos():
            from .services_schedule_conflicts import ScheduleConflictService

            result = ScheduleConflictService.validate_informatica_enrollment(
                aluno=self.aluno,
                turma=self.turma,
                data_matricula=self.data_matricula,
                exclude_informatica_matricula_id=self.pk,
            )
            if result.has_conflict and result.blocking_mode == "block":
                errors["aluno"] = result.message

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.turma_id:
            self.curso_id = self.turma.curso_id
            escola_lab_id = self.turma.laboratorio.unidade_id
            self.externo_laboratorio = bool(self.escola_origem_id and escola_lab_id and int(self.escola_origem_id) != int(escola_lab_id))
        super().save(*args, **kwargs)
        if self.aluno_id and self.turma_id and self.status in self.statuses_ativos():
            from .services_matricula_institucional import InstitutionalEnrollmentService

            unidade = getattr(getattr(self.turma, "laboratorio", None), "unidade", None)
            InstitutionalEnrollmentService.ensure_for_student(
                aluno=self.aluno,
                unidade=unidade,
                ano_referencia=self.turma.ano_letivo,
            )
        if self.aluno_id and self.turma_id:
            from .services_programas import ProgramasComplementaresService

            ProgramasComplementaresService.sync_informatica_matricula(
                matricula=self,
                usuario=getattr(self, "criado_por", None),
            )

    def __str__(self) -> str:
        return f"{self.aluno.nome} • {self.turma.codigo}"


class InformaticaMatriculaMovimentacao(models.Model):
    class Tipo(models.TextChoices):
        CRIACAO = "CRIACAO", "Criação"
        REMANEJAMENTO = "REMANEJAMENTO", "Remanejamento"
        CANCELAMENTO = "CANCELAMENTO", "Cancelamento"
        REATIVACAO = "REATIVACAO", "Reativação"
        SITUACAO = "SITUACAO", "Mudança de situação"

    matricula = models.ForeignKey(
        InformaticaMatricula,
        on_delete=models.CASCADE,
        related_name="movimentacoes",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.PROTECT,
        related_name="movimentacoes_matricula_informatica",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentacoes_matricula_informatica",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.SITUACAO)
    turma_origem = models.ForeignKey(
        "educacao.InformaticaTurma",
        on_delete=models.PROTECT,
        related_name="movimentacoes_origem_matricula",
        null=True,
        blank=True,
    )
    turma_destino = models.ForeignKey(
        "educacao.InformaticaTurma",
        on_delete=models.PROTECT,
        related_name="movimentacoes_destino_matricula",
        null=True,
        blank=True,
    )
    status_anterior = models.CharField(max_length=20, blank=True, default="")
    status_novo = models.CharField(max_length=20, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimentação de matrícula (informática)"
        verbose_name_plural = "Movimentações de matrícula (informática)"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["aluno"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["criado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.aluno.nome} • {self.get_tipo_display()} • {self.criado_em:%d/%m/%Y %H:%M}"


class InformaticaPlanoEnsinoProfessor(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        SUBMETIDO = "SUBMETIDO", "Aguardando aprovação"
        APROVADO = "APROVADO", "Aguardando homologação"
        HOMOLOGADO = "HOMOLOGADO", "Homologado"
        DEVOLVIDO = "DEVOLVIDO", "Devolvido para ajustes"

    turma = models.ForeignKey(
        InformaticaTurma,
        on_delete=models.CASCADE,
        related_name="planos_ensino",
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="planos_ensino_informatica",
    )
    ano_letivo = models.PositiveIntegerField(default=_current_year, db_index=True)
    titulo = models.CharField(max_length=180, default="Plano de Ensino • Informática")
    ementa = models.TextField(blank=True, default="")
    objetivos = models.TextField(blank=True, default="")
    metodologia = models.TextField(blank=True, default="")
    criterios_avaliacao = models.TextField(blank=True, default="")
    cronograma = models.TextField(blank=True, default="")
    referencias = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RASCUNHO, db_index=True)
    submetido_em = models.DateTimeField(null=True, blank=True)
    aprovado_em = models.DateTimeField(null=True, blank=True)
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_ensino_info_aprovados",
    )
    homologado_em = models.DateTimeField(null=True, blank=True)
    homologado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_ensino_info_homologados",
    )
    devolvido_em = models.DateTimeField(null=True, blank=True)
    devolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_ensino_info_devolvidos",
    )
    motivo_devolucao = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plano de ensino (informática)"
        verbose_name_plural = "Planos de ensino (informática)"
        ordering = ["-atualizado_em", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["turma", "professor"],
                name="uniq_plano_ensino_informatica_turma_professor",
            )
        ]
        indexes = [
            models.Index(fields=["professor", "status"]),
            models.Index(fields=["ano_letivo", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.turma.codigo} • {self.ano_letivo} • {self.get_status_display()}"

    @property
    def pode_editar_professor(self) -> bool:
        return self.status in {self.Status.RASCUNHO, self.Status.DEVOLVIDO}

    def submeter(self):
        self.status = self.Status.SUBMETIDO
        self.submetido_em = timezone.now()
        self.aprovado_em = None
        self.aprovado_por = None
        self.homologado_em = None
        self.homologado_por = None
        self.devolvido_em = None
        self.devolvido_por = None
        self.motivo_devolucao = ""

    def aprovar(self, usuario=None):
        self.status = self.Status.APROVADO
        self.aprovado_em = timezone.now()
        self.aprovado_por = usuario
        self.devolvido_em = None
        self.devolvido_por = None
        self.motivo_devolucao = ""

    def homologar(self, usuario=None):
        self.status = self.Status.HOMOLOGADO
        self.homologado_em = timezone.now()
        self.homologado_por = usuario
        if not self.aprovado_em:
            self.aprovado_em = timezone.now()
            self.aprovado_por = usuario
        self.devolvido_em = None
        self.devolvido_por = None
        self.motivo_devolucao = ""

    def devolver(self, usuario=None, motivo: str = ""):
        self.status = self.Status.DEVOLVIDO
        self.devolvido_em = timezone.now()
        self.devolvido_por = usuario
        self.motivo_devolucao = (motivo or "").strip()
        self.homologado_em = None
        self.homologado_por = None

    def cancelar_submissao(self):
        self.status = self.Status.RASCUNHO
        self.submetido_em = None
        self.aprovado_em = None
        self.aprovado_por = None
        self.homologado_em = None
        self.homologado_por = None
        self.devolvido_em = None
        self.devolvido_por = None
        self.motivo_devolucao = ""


class InformaticaAvaliacao(models.Model):
    turma = models.ForeignKey(
        InformaticaTurma,
        on_delete=models.CASCADE,
        related_name="avaliacoes",
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacoes_informatica",
    )
    tipo = models.CharField(
        max_length=20,
        choices=AVALIACAO_TIPO_CHOICES,
        default="OUTRO",
    )
    sigla = models.CharField(max_length=12, blank=True, default="")
    titulo = models.CharField(max_length=180)
    descricao = models.TextField(blank=True, default="")
    modo_registro = models.CharField(
        max_length=12,
        choices=AVALIACAO_MODO_CHOICES,
        default="NOTA",
        db_index=True,
    )
    peso = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    nota_maxima = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    data = models.DateField(default=timezone.localdate)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Avaliação (informática)"
        verbose_name_plural = "Avaliações (informática)"
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["turma", "data"]),
            models.Index(fields=["professor", "ativo"]),
            models.Index(fields=["ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.turma.codigo} • {self.titulo}"


class InformaticaNota(models.Model):
    avaliacao = models.ForeignKey(
        InformaticaAvaliacao,
        on_delete=models.CASCADE,
        related_name="notas",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="notas_informatica",
    )
    valor = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    conceito = models.CharField(max_length=4, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Nota de avaliação (informática)"
        verbose_name_plural = "Notas de avaliação (informática)"
        ordering = ["aluno__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["avaliacao", "aluno"],
                name="uniq_informatica_nota_avaliacao_aluno",
            )
        ]
        indexes = [
            models.Index(fields=["avaliacao", "aluno"]),
        ]

    def clean(self):
        modo = getattr(getattr(self, "avaliacao", None), "modo_registro", "NOTA")
        if modo == "CONCEITO":
            if not (self.conceito or "").strip():
                raise ValidationError({"conceito": "Informe um conceito para esta avaliação."})
            self.valor = None
        else:
            self.conceito = ""
        matriculado = InformaticaMatricula.objects.filter(
            turma_id=self.avaliacao.turma_id,
            aluno_id=self.aluno_id,
            status=InformaticaMatricula.Status.MATRICULADO,
        ).exists()
        if not matriculado:
            raise ValidationError({"aluno": "Aluno não está matriculado ativamente nesta turma de informática."})

    def __str__(self) -> str:
        return f"{self.avaliacao} • {self.aluno.nome}"


class InformaticaAulaDiario(models.Model):
    class Status(models.TextChoices):
        PREVISTA = "PREVISTA", "Prevista"
        REALIZADA = "REALIZADA", "Realizada"
        CANCELADA = "CANCELADA", "Cancelada"
        REMARCADA = "REMARCADA", "Remarcada"
        REPOSTA = "REPOSTA", "Reposta"

    class TipoEncontro(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        ESPECIAL_SEXTA = "ESPECIAL_SEXTA", "Especial de sexta"
        REPOSICAO = "REPOSICAO", "Reposição"

    turma = models.ForeignKey(
        InformaticaTurma,
        on_delete=models.CASCADE,
        related_name="aulas",
    )
    encontro = models.ForeignKey(
        InformaticaEncontroSemanal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aulas",
    )
    data_aula = models.DateField(default=timezone.localdate)
    conteudo_ministrado = models.TextField(blank=True, default="")
    atividade_realizada = models.TextField(blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    anexo = models.FileField(upload_to="educacao/informatica/diario/%Y/%m/", blank=True, null=True)
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="informatica_aulas_ministradas",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREVISTA)
    tipo_encontro = models.CharField(max_length=20, choices=TipoEncontro.choices, default=TipoEncontro.REGULAR)
    duracao_total_minutos = models.PositiveSmallIntegerField(default=60)
    pausa_interna_minutos = models.PositiveSmallIntegerField(default=0)
    formato_especial = models.BooleanField(default=False)
    encerrada = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Aula/diário do curso de informática"
        verbose_name_plural = "Aulas/diário do curso de informática"
        ordering = ["-data_aula", "-id"]
        indexes = [
            models.Index(fields=["turma", "data_aula"]),
            models.Index(fields=["encerrada"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["turma", "data_aula"], name="uniq_informatica_aula_turma_data"),
        ]

    def clean(self):
        errors: dict[str, str] = {}
        if self.encontro_id:
            if int(self.data_aula.weekday()) != int(self.encontro.dia_semana):
                errors["data_aula"] = "Data da aula não corresponde ao dia da semana do encontro selecionado."
            if self.encontro.turma_id != self.turma_id:
                errors["encontro"] = "Encontro selecionado não pertence à turma."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.turma.codigo} • {self.data_aula:%d/%m/%Y}"


class InformaticaFrequencia(models.Model):
    aula = models.ForeignKey(
        InformaticaAulaDiario,
        on_delete=models.CASCADE,
        related_name="frequencias",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.CASCADE,
        related_name="informatica_frequencias",
    )
    presente = models.BooleanField(default=True)
    justificativa = models.CharField(max_length=220, blank=True, default="")
    observacao = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Frequência da aula de informática"
        verbose_name_plural = "Frequências das aulas de informática"
        ordering = ["aula", "aluno__nome"]
        indexes = [
            models.Index(fields=["aula", "aluno"]),
            models.Index(fields=["presente"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["aula", "aluno"], name="uniq_informatica_freq_aula_aluno"),
        ]

    def clean(self):
        matriculado = InformaticaMatricula.objects.filter(
            turma_id=self.aula.turma_id,
            aluno_id=self.aluno_id,
            status=InformaticaMatricula.Status.MATRICULADO,
        ).exists()
        if not matriculado:
            raise ValidationError({"aluno": "Aluno não está matriculado ativamente nesta turma."})

    def __str__(self) -> str:
        return f"{self.aula} • {self.aluno.nome}"


class InformaticaOcorrencia(models.Model):
    class Tipo(models.TextChoices):
        INFRAESTRUTURA = "INFRAESTRUTURA", "Infraestrutura"
        PEDAGOGICA = "PEDAGOGICA", "Pedagógica"
        DISCIPLINAR = "DISCIPLINAR", "Disciplinar"
        FREQUENCIA = "FREQUENCIA", "Frequência"
        OUTRA = "OUTRA", "Outra"

    turma = models.ForeignKey(
        InformaticaTurma,
        on_delete=models.CASCADE,
        related_name="ocorrencias",
    )
    aula = models.ForeignKey(
        InformaticaAulaDiario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias",
    )
    aluno = models.ForeignKey(
        "educacao.Aluno",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="informatica_ocorrencias",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OUTRA)
    descricao = models.TextField()
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="informatica_ocorrencias_registradas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ocorrência da aula de informática"
        verbose_name_plural = "Ocorrências das aulas de informática"
        ordering = ["-criado_em", "-id"]
        indexes = [
            models.Index(fields=["turma", "tipo"]),
            models.Index(fields=["aluno"]),
        ]

    def __str__(self) -> str:
        return f"{self.turma.codigo} • {self.get_tipo_display()}"


class InformaticaAlertaFrequencia(models.Model):
    class Tipo(models.TextChoices):
        BAIXA_FREQUENCIA = "BAIXA_FREQUENCIA", "Baixa frequência (< 75%)"
        FALTAS_CONSECUTIVAS = "FALTAS_CONSECUTIVAS", "Faltas consecutivas (>= 3)"

    matricula = models.ForeignKey(
        InformaticaMatricula,
        on_delete=models.CASCADE,
        related_name="alertas_frequencia",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    percentual_frequencia = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    faltas_consecutivas = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    gerado_em = models.DateTimeField(auto_now_add=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Alerta de frequência (informática)"
        verbose_name_plural = "Alertas de frequência (informática)"
        ordering = ["-gerado_em", "-id"]
        indexes = [
            models.Index(fields=["matricula", "ativo"]),
            models.Index(fields=["tipo", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.matricula} • {self.get_tipo_display()}"
