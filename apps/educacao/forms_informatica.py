from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.core.rbac import (
    get_profile,
    is_admin,
    role_scope_base,
    scope_filter_alunos,
    scope_filter_unidades,
)
from apps.org.models import Unidade

from .models import Aluno, Matricula
from .models_informatica import (
    InformaticaAulaDiario,
    InformaticaCurso,
    InformaticaEncontroSemanal,
    InformaticaGradeHorario,
    InformaticaLaboratorio,
    InformaticaListaEspera,
    InformaticaMatricula,
    InformaticaSolicitacaoVaga,
    InformaticaTurma,
)


def _unidades_educacao_scope(user):
    base_qs = Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO, ativo=True).select_related(
        "secretaria", "secretaria__municipio"
    )

    if is_admin(user):
        return base_qs.order_by("nome")

    profile = get_profile(user)
    base = role_scope_base(getattr(profile, "role", None) if profile else None)
    if base == "PROFESSOR":
        municipio_ids = _municipio_ids_scope(user)
        if municipio_ids:
            return base_qs.filter(secretaria__municipio_id__in=municipio_ids).order_by("nome")

    return scope_filter_unidades(user, base_qs).order_by("nome")


def _municipio_ids_scope(user) -> list[int]:
    ids: set[int] = set()
    if is_admin(user):
        return list(
            Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO)
            .values_list("secretaria__municipio_id", flat=True)
            .distinct()
        )

    unidades_ids = scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
    ).values_list("secretaria__municipio_id", flat=True)
    ids.update([int(i) for i in unidades_ids if i])

    profile = get_profile(user)
    if profile and profile.municipio_id:
        ids.add(int(profile.municipio_id))
    if profile and profile.secretaria_id:
        sec_municipio = getattr(getattr(profile, "secretaria", None), "municipio_id", None)
        if sec_municipio:
            ids.add(int(sec_municipio))
    if profile and profile.unidade_id:
        unidade_municipio = getattr(getattr(getattr(profile, "unidade", None), "secretaria", None), "municipio_id", None)
        if unidade_municipio:
            ids.add(int(unidade_municipio))

    turmas_instrutor_ids = InformaticaTurma.objects.filter(instrutor=user).values_list("curso__municipio_id", flat=True).distinct()
    ids.update([int(i) for i in turmas_instrutor_ids if i])
    return sorted(ids)


def cursos_scope(user):
    qs = InformaticaCurso.objects.select_related("municipio").all()
    if is_admin(user):
        return qs
    municipio_ids = _municipio_ids_scope(user)
    if not municipio_ids:
        return qs.none()
    return qs.filter(municipio_id__in=municipio_ids)


def laboratorios_scope(user):
    qs = InformaticaLaboratorio.objects.select_related(
        "unidade", "unidade__secretaria", "unidade__secretaria__municipio"
    )
    if is_admin(user):
        return qs
    return qs.filter(unidade_id__in=_unidades_educacao_scope(user).values_list("id", flat=True))


def grades_scope(user):
    qs = InformaticaGradeHorario.objects.select_related(
        "laboratorio",
        "laboratorio__unidade",
        "laboratorio__unidade__secretaria",
        "laboratorio__unidade__secretaria__municipio",
        "professor_principal",
    )
    if is_admin(user):
        return qs
    return qs.filter(laboratorio_id__in=laboratorios_scope(user).values_list("id", flat=True))


def turmas_scope(user):
    qs = InformaticaTurma.objects.select_related(
        "curso",
        "curso__municipio",
        "grade_horario",
        "laboratorio",
        "laboratorio__unidade",
        "instrutor",
    )
    if is_admin(user):
        return qs

    profile = get_profile(user)
    base = role_scope_base(getattr(profile, "role", None) if profile else None)
    if base == "PROFESSOR":
        return qs.filter(instrutor=user)

    return qs.filter(laboratorio_id__in=laboratorios_scope(user).values_list("id", flat=True))


def alunos_scope(user):
    return scope_filter_alunos(user, Aluno.objects.filter(ativo=True)).order_by("nome")


def _professores_scope(user):
    user_model = get_user_model()
    qs = user_model.objects.filter(is_active=True, profile__ativo=True, profile__bloqueado=False).filter(
        Q(profile__role="PROFESSOR") | Q(profile__role="EDU_PROF")
    )
    if is_admin(user):
        return qs.order_by("first_name", "last_name", "username")

    municipio_ids = _municipio_ids_scope(user)
    if municipio_ids:
        qs = qs.filter(
            Q(profile__municipio_id__in=municipio_ids)
            | Q(profile__secretaria__municipio_id__in=municipio_ids)
            | Q(profile__unidade__secretaria__municipio_id__in=municipio_ids)
        )

    return qs.distinct().order_by("first_name", "last_name", "username")


class InformaticaCursoForm(forms.ModelForm):
    class Meta:
        model = InformaticaCurso
        fields = [
            "nome",
            "descricao",
            "modalidade",
            "carga_horaria_total",
            "faixa_etaria",
            "ano_escolar_permitido",
            "aulas_por_semana",
            "duracao_bloco_minutos",
            "minutos_aula_efetiva",
            "minutos_intervalo_tecnico",
            "max_alunos_por_turma",
            "permitir_multiplas_turmas_por_aluno",
            "ativo",
        ]


class InformaticaLaboratorioForm(forms.ModelForm):
    class Meta:
        model = InformaticaLaboratorio
        fields = [
            "nome",
            "unidade",
            "endereco",
            "quantidade_computadores",
            "capacidade_operacional",
            "status",
            "responsavel_local",
            "observacoes",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["unidade"].queryset = _unidades_educacao_scope(self.user)
            self.fields["responsavel_local"].queryset = _professores_scope(self.user)


class InformaticaGradeHorarioForm(forms.ModelForm):
    class Meta:
        model = InformaticaGradeHorario
        fields = [
            "nome",
            "codigo",
            "descricao",
            "tipo_grade",
            "laboratorio",
            "turno",
            "dia_semana_1",
            "dia_semana_2",
            "hora_inicio",
            "hora_fim",
            "duracao_total_minutos",
            "duracao_aula_minutos",
            "duracao_intervalo_minutos",
            "pausa_interna_opcional_minutos",
            "professor_principal",
            "ano_letivo",
            "periodo_letivo",
            "capacidade_maxima",
            "status",
            "observacoes",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields["laboratorio"].queryset = laboratorios_scope(self.user).filter(ativo=True).order_by("nome")
            self.fields["professor_principal"].queryset = _professores_scope(self.user)

        self.fields["ano_letivo"].initial = timezone.localdate().year
        self.fields["hora_inicio"].widget = forms.TimeInput(attrs={"type": "time"})
        self.fields["hora_fim"].widget = forms.TimeInput(attrs={"type": "time"})

    def clean(self):
        cleaned = super().clean()
        tipo_grade = cleaned.get("tipo_grade")

        if tipo_grade == InformaticaGradeHorario.TipoGrade.ESPECIAL_SEXTA:
            cleaned["dia_semana_1"] = InformaticaGradeHorario.DiaSemana.SEXTA
            cleaned["dia_semana_2"] = None

        return cleaned


class InformaticaTurmaForm(forms.ModelForm):
    class Meta:
        model = InformaticaTurma
        fields = [
            "curso",
            "grade_horario",
            "codigo",
            "nome",
            "instrutor",
            "ano_letivo",
            "periodo_letivo",
            "max_vagas",
            "status",
            "permite_aluno_externo",
            "observacoes",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields["curso"].queryset = cursos_scope(self.user).filter(ativo=True).order_by("nome")
            self.fields["grade_horario"].queryset = grades_scope(self.user).filter(
                status=InformaticaGradeHorario.Status.ATIVA,
                ativo=True,
            ).order_by("laboratorio__nome", "hora_inicio", "codigo")
            self.fields["instrutor"].queryset = _professores_scope(self.user)

        self.fields["ano_letivo"].initial = timezone.localdate().year
        self.fields["grade_horario"].help_text = "A turma herda laboratório, turno, dias e horários da grade selecionada."

    def clean(self):
        cleaned = super().clean()
        curso = cleaned.get("curso")
        grade = cleaned.get("grade_horario")

        if curso and grade:
            grade_municipio_id = grade.laboratorio.unidade.secretaria.municipio_id
            if curso.municipio_id and grade_municipio_id and int(curso.municipio_id) != int(grade_municipio_id):
                self.add_error("grade_horario", "A grade precisa pertencer ao mesmo município do curso.")

            if int(cleaned.get("max_vagas") or 0) > int(grade.capacidade_maxima or 0):
                self.add_error("max_vagas", "Capacidade da turma não pode ultrapassar a capacidade da grade.")

            if int(cleaned.get("ano_letivo") or 0) != int(grade.ano_letivo or 0):
                cleaned["ano_letivo"] = grade.ano_letivo

            if not cleaned.get("periodo_letivo") and grade.periodo_letivo:
                cleaned["periodo_letivo"] = grade.periodo_letivo

        return cleaned


class InformaticaSolicitacaoForm(forms.ModelForm):
    class Meta:
        model = InformaticaSolicitacaoVaga
        fields = [
            "aluno",
            "escola_origem",
            "curso",
            "turno_preferido",
            "laboratorio_preferido",
            "disponibilidade",
            "origem_indicacao",
            "prioridade",
            "observacoes",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["aluno"].queryset = alunos_scope(self.user)
            self.fields["escola_origem"].queryset = _unidades_educacao_scope(self.user)
            self.fields["curso"].queryset = cursos_scope(self.user).filter(ativo=True).order_by("nome")
            self.fields["laboratorio_preferido"].queryset = laboratorios_scope(self.user).filter(ativo=True).order_by("nome")


class InformaticaMatriculaForm(forms.ModelForm):
    class Meta:
        model = InformaticaMatricula
        fields = [
            "aluno",
            "escola_origem",
            "turma",
            "status",
            "origem_indicacao",
            "prioridade",
            "observacoes",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            alunos_qs = alunos_scope(self.user)
            profile = get_profile(self.user)
            base = role_scope_base(getattr(profile, "role", None) if profile else None)
            if base == "PROFESSOR":
                municipio_ids = list(
                    turmas_scope(self.user).values_list("curso__municipio_id", flat=True).distinct()
                )
                if municipio_ids:
                    alunos_qs = (
                        Aluno.objects.filter(ativo=True)
                        .filter(
                            Q(matriculas__turma__unidade__secretaria__municipio_id__in=municipio_ids)
                            | Q(informatica_matriculas__turma__curso__municipio_id__in=municipio_ids)
                        )
                        .distinct()
                    )
                else:
                    alunos_qs = Aluno.objects.filter(ativo=True).none()

            selected_aluno_id = None
            if self.is_bound:
                raw = (self.data.get(self.add_prefix("aluno")) or "").strip()
                if raw.isdigit():
                    selected_aluno_id = int(raw)
            elif self.initial.get("aluno"):
                try:
                    selected_aluno_id = int(self.initial.get("aluno"))
                except (TypeError, ValueError):
                    selected_aluno_id = None
            elif self.instance and self.instance.pk and self.instance.aluno_id:
                selected_aluno_id = int(self.instance.aluno_id)

            if selected_aluno_id:
                alunos_qs = (alunos_qs | Aluno.objects.filter(pk=selected_aluno_id)).distinct()

            self.fields["aluno"].queryset = alunos_qs.order_by("nome")
            self.fields["escola_origem"].queryset = _unidades_educacao_scope(self.user)
            self.fields["escola_origem"].required = False
            self.fields["turma"].queryset = turmas_scope(self.user).filter(
                status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
                grade_horario__isnull=False,
            )
        self.fields["status"].initial = InformaticaMatricula.Status.MATRICULADO

    def clean(self):
        cleaned = super().clean()
        aluno = cleaned.get("aluno")
        escola_origem = cleaned.get("escola_origem")
        origem_indicacao = (cleaned.get("origem_indicacao") or "").strip()

        if aluno and not escola_origem:
            mat = (
                Matricula.objects.filter(aluno=aluno, situacao=Matricula.Situacao.ATIVA)
                .select_related("turma", "turma__unidade")
                .order_by("-id")
                .first()
            )
            unidade_origem = getattr(getattr(mat, "turma", None), "unidade", None)
            if unidade_origem is not None:
                cleaned["escola_origem"] = unidade_origem
                escola_origem = unidade_origem

        if aluno and not origem_indicacao:
            if escola_origem is not None:
                cleaned["origem_indicacao"] = f"Escola de origem: {escola_origem.nome}"[:80]
            else:
                cleaned["origem_indicacao"] = "Cadastro do aluno"

        return cleaned


class InformaticaMatriculaRemanejamentoForm(forms.Form):
    turma_destino = forms.ModelChoiceField(
        queryset=InformaticaTurma.objects.none(),
        label="Turma de destino",
    )
    motivo = forms.CharField(
        label="Motivo do remanejamento",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.matricula = kwargs.pop("matricula", None)
        super().__init__(*args, **kwargs)

        if self.user and self.matricula:
            self.fields["turma_destino"].queryset = (
                turmas_scope(self.user)
                .filter(
                    curso_id=self.matricula.curso_id,
                    status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA],
                    grade_horario__isnull=False,
                )
                .exclude(pk=self.matricula.turma_id)
                .order_by("-ano_letivo", "codigo")
            )

    def clean(self):
        cleaned = super().clean()
        turma_destino = cleaned.get("turma_destino")

        if not self.matricula:
            return cleaned

        if not turma_destino:
            self.add_error("turma_destino", "Selecione a turma de destino.")
            return cleaned

        if int(turma_destino.pk) == int(self.matricula.turma_id):
            self.add_error("turma_destino", "A turma de destino deve ser diferente da turma atual.")

        if int(turma_destino.curso_id) != int(self.matricula.curso_id):
            self.add_error("turma_destino", "O remanejamento deve ocorrer para turma do mesmo curso.")

        conflito = (
            InformaticaMatricula.objects.filter(
                aluno_id=self.matricula.aluno_id,
                turma_id=turma_destino.id,
                status__in=InformaticaMatricula.statuses_ativos(),
            )
            .exclude(pk=self.matricula.pk)
            .exists()
        )
        if conflito:
            self.add_error(
                "turma_destino",
                "Já existe matrícula ativa deste aluno na turma de destino.",
            )

        return cleaned


class InformaticaListaEsperaForm(forms.ModelForm):
    class Meta:
        model = InformaticaListaEspera
        fields = [
            "curso",
            "turma_preferida",
            "laboratorio_preferido",
            "aluno",
            "escola_origem",
            "turno_preferido",
            "prioridade",
            "posicao",
            "status",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["curso"].queryset = cursos_scope(self.user).filter(ativo=True)
            self.fields["turma_preferida"].queryset = turmas_scope(self.user)
            self.fields["laboratorio_preferido"].queryset = laboratorios_scope(self.user)
            self.fields["aluno"].queryset = alunos_scope(self.user)
            self.fields["escola_origem"].queryset = _unidades_educacao_scope(self.user)


class InformaticaAulaForm(forms.ModelForm):
    class Meta:
        model = InformaticaAulaDiario
        fields = [
            "turma",
            "encontro",
            "data_aula",
            "status",
            "tipo_encontro",
            "conteudo_ministrado",
            "atividade_realizada",
            "observacoes",
            "anexo",
            "pausa_interna_minutos",
            "encerrada",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if self.user:
            self.fields["turma"].queryset = turmas_scope(self.user).filter(
                status__in=[InformaticaTurma.Status.PLANEJADA, InformaticaTurma.Status.ATIVA]
            )

        turma_id = None
        if self.is_bound:
            turma_raw = (self.data.get(self.add_prefix("turma")) or "").strip()
            if turma_raw.isdigit():
                turma_id = int(turma_raw)
        elif self.instance and self.instance.pk:
            turma_id = self.instance.turma_id
        elif self.initial.get("turma"):
            turma_id = int(self.initial["turma"])

        encontros_qs = InformaticaEncontroSemanal.objects.filter(ativo=True)
        if turma_id:
            encontros_qs = encontros_qs.filter(turma_id=turma_id)
        else:
            encontros_qs = encontros_qs.none()

        self.fields["encontro"].queryset = encontros_qs.order_by("dia_semana", "hora_inicio")
