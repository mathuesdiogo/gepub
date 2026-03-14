from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.core.rbac import can, get_profile, is_admin, role_scope_base, scope_filter_turmas, scope_filter_unidades
from apps.org.models import Unidade

from .models import (
    Aluno,
    AlunoCertificado,
    AlunoDocumento,
    CoordenacaoEnsino,
    Curso,
    CursoDisciplina,
    MatrizComponente,
    MatrizComponenteEquivalenciaGrupo,
    MatrizComponenteEquivalenciaItem,
    MatrizComponenteRelacao,
    MatrizCurricular,
    Matricula,
    MatriculaCurso,
    Turma,
)
from .models_notas import ComponenteCurricular


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = [
            "unidade",
            "nome",
            "ano_letivo",
            "turno",
            "modalidade",
            "etapa",
            "serie_ano",
            "forma_oferta",
            "matriz_curricular",
            "curso",
            "professores",
            "classe_especial",
            "bilingue_surdos",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Foco padrão da rede municipal: infantil + fundamental.
        self._apply_motor_principal_choices()

        self.fields["unidade"].queryset = Unidade.objects.filter(
            ativo=True,
            tipo=Unidade.Tipo.EDUCACAO,
        ).order_by("nome")
        self.fields["curso"].queryset = Curso.objects.filter(ativo=True).order_by("nome")
        self.fields["curso"].required = False
        self.fields["curso"].label = "Atividade/Curso extracurricular"
        self.fields["curso"].help_text = "Use apenas para turmas de atividade complementar."
        self.fields["professores"].required = False
        self.fields["professores"].help_text = (
            "Professores vinculados à turma. O sistema cria/atualiza automaticamente os diários da turma."
        )
        self.fields["professores"].queryset = get_user_model().objects.none()
        self.fields["matriz_curricular"].queryset = MatrizCurricular.objects.filter(ativo=True).select_related(
            "unidade",
            "unidade__secretaria",
        ).order_by("-ano_referencia", "nome")
        self.fields["matriz_curricular"].required = False
        self.fields["matriz_curricular"].label = "Matriz curricular"
        self.fields["matriz_curricular"].help_text = "Obrigatória para turmas regulares da educação infantil/fundamental."

        if not self.user or not getattr(self.user, "is_authenticated", False) or is_admin(self.user):
            self._apply_professores_queryset()
            return

        p = get_profile(self.user)
        if not p:
            self._apply_professores_queryset()
            return

        role_base = role_scope_base(getattr(p, "role", None))

        if role_base == "UNIDADE" and getattr(p, "unidade_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(id=p.unidade_id)
            self.fields["unidade"].initial = p.unidade_id
            self.fields["unidade"].disabled = True
            self.fields["matriz_curricular"].queryset = self.fields["matriz_curricular"].queryset.filter(
                unidade_id=p.unidade_id
            )
            self._apply_professores_queryset(unidade_id=p.unidade_id)
            return

        if role_base == "SECRETARIA" and getattr(p, "secretaria_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria_id=p.secretaria_id)
            self.fields["matriz_curricular"].queryset = self.fields["matriz_curricular"].queryset.filter(
                unidade__secretaria_id=p.secretaria_id
            )
            self._apply_professores_queryset(secretaria_id=p.secretaria_id)
            return

        if getattr(p, "municipio_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(
                secretaria__municipio_id=p.municipio_id
            )
            self.fields["matriz_curricular"].queryset = self.fields["matriz_curricular"].queryset.filter(
                unidade__secretaria__municipio_id=p.municipio_id
            )
            self._apply_professores_queryset(municipio_id=p.municipio_id)
            return

        self._apply_professores_queryset()

    def clean(self):
        cleaned = super().clean()
        modalidade = cleaned.get("modalidade")
        matriz = cleaned.get("matriz_curricular")
        curso = cleaned.get("curso")
        unidade = cleaned.get("unidade")
        professores = list(cleaned.get("professores") or [])

        if modalidade == Turma.Modalidade.ATIVIDADE_COMPLEMENTAR:
            cleaned["serie_ano"] = Turma.SerieAno.NAO_APLICA
            if not curso:
                self.add_error("curso", "Selecione o curso/atividade extracurricular.")
            if matriz:
                self.add_error("matriz_curricular", "Atividade complementar não deve usar matriz curricular.")
        else:
            if not matriz:
                self.add_error("matriz_curricular", "Selecione a matriz curricular da turma.")
            if curso:
                self.add_error("curso", "Turma regular não deve ter curso extracurricular vinculado.")
            if matriz:
                expected_serie = Turma.expected_serie_from_matriz(matriz)
                expected_etapa = Turma.expected_etapa_from_matriz(matriz)
                if expected_serie:
                    cleaned["serie_ano"] = expected_serie
                if expected_etapa:
                    cleaned["etapa"] = expected_etapa

        if matriz and unidade and matriz.unidade_id != unidade.id:
            self.add_error("matriz_curricular", "A matriz curricular selecionada pertence a outra unidade.")

        if unidade and getattr(unidade, "tipo", None) != Unidade.Tipo.EDUCACAO:
            self.add_error("unidade", "Selecione uma unidade do tipo Educação para criar turmas neste módulo.")

        if unidade and professores:
            municipio_id = getattr(getattr(unidade, "secretaria", None), "municipio_id", None)
            for professor in professores:
                profile = getattr(professor, "profile", None)
                if profile is None:
                    self.add_error("professores", f"{professor.username}: perfil não encontrado.")
                    continue

                prof_municipio_id = (
                    profile.municipio_id
                    or getattr(getattr(profile.secretaria, "municipio", None), "id", None)
                    or getattr(getattr(getattr(profile.unidade, "secretaria", None), "municipio", None), "id", None)
                )
                if municipio_id and prof_municipio_id and int(prof_municipio_id) != int(municipio_id):
                    self.add_error(
                        "professores",
                        f"{professor.username}: professor está vinculado a outro município.",
                    )
                elif getattr(profile, "unidade_id", None) and profile.unidade_id != unidade.id:
                    self.add_error(
                        "professores",
                        f"{professor.username}: professor vinculado a outra unidade.",
                    )

        return cleaned

    def _apply_professores_queryset(
        self,
        *,
        municipio_id: int | None = None,
        secretaria_id: int | None = None,
        unidade_id: int | None = None,
    ):
        user_model = get_user_model()
        qs = user_model.objects.filter(
            is_active=True,
            profile__ativo=True,
            profile__bloqueado=False,
        ).filter(
            Q(profile__role="PROFESSOR") | Q(profile__role="EDU_PROF")
        )

        if unidade_id:
            qs = qs.filter(profile__unidade_id=unidade_id)
        elif secretaria_id:
            qs = qs.filter(
                Q(profile__secretaria_id=secretaria_id)
                | Q(profile__unidade__secretaria_id=secretaria_id)
            )
        elif municipio_id:
            qs = qs.filter(
                Q(profile__municipio_id=municipio_id)
                | Q(profile__secretaria__municipio_id=municipio_id)
                | Q(profile__unidade__secretaria__municipio_id=municipio_id)
            )

        self.fields["professores"].queryset = qs.distinct().order_by(
            "first_name", "last_name", "username"
        )

    def _apply_motor_principal_choices(self):
        modalidade_choices = Turma.modalidades_motor_principal_choices()
        etapa_choices = Turma.etapas_motor_principal_choices()
        serie_choices = Turma.series_motor_principal_choices()

        # Preserva valores legados já existentes para edição, sem expor como opção padrão.
        current_modalidade = getattr(self.instance, "modalidade", None)
        if current_modalidade and current_modalidade not in {v for v, _ in modalidade_choices}:
            modalidade_choices.append((current_modalidade, f"{self.instance.get_modalidade_display()} (legado)"))

        current_etapa = getattr(self.instance, "etapa", None)
        if current_etapa and current_etapa not in {v for v, _ in etapa_choices}:
            etapa_choices.append((current_etapa, f"{self.instance.get_etapa_display()} (legado)"))

        current_serie = getattr(self.instance, "serie_ano", None)
        if current_serie and current_serie not in {v for v, _ in serie_choices}:
            serie_choices.append((current_serie, f"{self.instance.get_serie_ano_display()} (legado)"))

        self.fields["modalidade"].choices = modalidade_choices
        self.fields["etapa"].choices = etapa_choices
        self.fields["serie_ano"].choices = serie_choices

        self.fields["modalidade"].help_text = (
            "Use Educação Infantil ou Ensino Regular para turmas-base. "
            "Atividade Complementar apenas para trilhas extracurriculares."
        )


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            "nome",
            "codigo",
            "modalidade_oferta",
            "eixo_tecnologico",
            "carga_horaria",
            "ativo",
        ]


class CursoDisciplinaForm(forms.ModelForm):
    class Meta:
        model = CursoDisciplina
        fields = [
            "nome",
            "tipo_aula",
            "carga_horaria",
            "ordem",
            "obrigatoria",
            "ementa",
            "ativo",
        ]
        widgets = {
            "ementa": forms.Textarea(attrs={"rows": 2}),
        }


class MatrizCurricularForm(forms.ModelForm):
    class Meta:
        model = MatrizCurricular
        fields = [
            "unidade",
            "nome",
            "etapa_base",
            "serie_ano",
            "ano_referencia",
            "carga_horaria_anual",
            "dias_letivos_previstos",
            "ativo",
            "observacao",
        ]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidade"].queryset = Unidade.objects.filter(ativo=True, tipo=Unidade.Tipo.EDUCACAO).order_by("nome")
        if user and getattr(user, "is_authenticated", False) and not is_admin(user):
            self.fields["unidade"].queryset = scope_filter_unidades(user, self.fields["unidade"].queryset)


class MatrizComponenteForm(forms.ModelForm):
    class Meta:
        model = MatrizComponente
        fields = [
            "componente",
            "ordem",
            "carga_horaria_anual",
            "aulas_semanais",
            "obrigatoria",
            "ativo",
            "observacao",
        ]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["componente"].queryset = ComponenteCurricular.objects.filter(ativo=True).order_by("nome")


class MatrizComponenteRelacaoForm(forms.ModelForm):
    class Meta:
        model = MatrizComponenteRelacao
        fields = [
            "tipo",
            "origem",
            "destino",
            "ativo",
            "observacao",
        ]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, matriz=None, allow_equivalencia=True, **kwargs):
        super().__init__(*args, **kwargs)
        componentes_qs = MatrizComponente.objects.select_related("componente", "matriz").none()
        if matriz is not None:
            componentes_qs = MatrizComponente.objects.select_related("componente", "matriz").filter(matriz=matriz).order_by(
                "ordem", "componente__nome"
            )
        if not allow_equivalencia:
            self.fields["tipo"].choices = [
                (value, label)
                for value, label in self.fields["tipo"].choices
                if value != MatrizComponenteRelacao.Tipo.EQUIVALENCIA
            ]
        self.fields["origem"].queryset = componentes_qs
        self.fields["destino"].queryset = componentes_qs
        self.fields["origem"].label_from_instance = (
            lambda item: f"{item.ordem:02d} • {item.componente.nome}" if item.ordem is not None else item.componente.nome
        )
        self.fields["destino"].label_from_instance = (
            lambda item: f"{item.ordem:02d} • {item.componente.nome}" if item.ordem is not None else item.componente.nome
        )


class MatrizEquivalenciaGrupoForm(forms.ModelForm):
    class Meta:
        model = MatrizComponenteEquivalenciaGrupo
        fields = [
            "nome",
            "minimo_componentes",
            "ativo",
            "observacao",
        ]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }


class MatrizEquivalenciaItemForm(forms.ModelForm):
    class Meta:
        model = MatrizComponenteEquivalenciaItem
        fields = [
            "componente",
            "ordem",
            "ativo",
        ]

    def __init__(self, *args, matriz=None, grupo=None, **kwargs):
        super().__init__(*args, **kwargs)
        componentes_qs = MatrizComponente.objects.select_related("componente", "matriz").none()
        if matriz is not None:
            componentes_qs = MatrizComponente.objects.select_related("componente", "matriz").filter(
                matriz=matriz,
                ativo=True,
            )
        if grupo is not None:
            usados = grupo.itens.values_list("componente_id", flat=True)
            componentes_qs = componentes_qs.exclude(pk__in=usados)
        self.fields["componente"].queryset = componentes_qs.order_by("ordem", "componente__nome")
        self.fields["componente"].label_from_instance = (
            lambda item: f"{item.ordem:02d} • {item.componente.nome}" if item.ordem is not None else item.componente.nome
        )


class CoordenacaoEnsinoForm(forms.ModelForm):
    class Meta:
        model = CoordenacaoEnsino
        fields = [
            "coordenador",
            "unidade",
            "modalidade",
            "etapa",
            "inicio",
            "fim",
            "observacao",
            "ativo",
        ]
        widgets = {
            "inicio": forms.DateInput(attrs={"type": "date"}),
            "fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        self.fields["coordenador"].queryset = user_model.objects.filter(is_active=True).order_by("username")
        self.fields["unidade"].queryset = Unidade.objects.filter(ativo=True, tipo=Unidade.Tipo.EDUCACAO).order_by("nome")

        if user and getattr(user, "is_authenticated", False) and not is_admin(user):
            self.fields["unidade"].queryset = scope_filter_unidades(user, self.fields["unidade"].queryset)


class AlunoForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = [
            "nome",
            "foto",
            "data_nascimento",
            "cpf",
            "nis",
            "nome_mae",
            "nome_pai",
            "telefone",
            "email",
            "endereco",
            "ativo",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(
                attrs={
                    "type": "date",
                    "title": "Selecione no calendário ou digite a data",
                }
            ),
            "cpf": forms.TextInput(
                attrs={
                    "placeholder": "123.456.789-00",
                    "inputmode": "numeric",
                    "maxlength": "14",
                    "autocomplete": "off",
                    "title": "Formato: 123.456.789-00",
                }
            ),
            "telefone": forms.TextInput(
                attrs={
                    "placeholder": "(98) 99999-9999",
                    "inputmode": "tel",
                    "title": "Ex.: (98) 99999-9999",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "nome@exemplo.com",
                    "inputmode": "email",
                    "title": "Ex.: nome@exemplo.com",
                }
            ),
            "nis": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: 12345678901",
                    "inputmode": "numeric",
                    "title": "Digite apenas números (se houver)",
                }
            ),
        }

    def clean_cpf(self):
        cpf = (self.cleaned_data.get("cpf") or "").strip()
        if not cpf:
            return ""
        digits = "".join(ch for ch in cpf if ch.isdigit())
        if len(digits) != 11:
            raise ValidationError("CPF inválido. Deve conter 11 dígitos.")
        return digits


class AlunoCreateComTurmaForm(AlunoForm):
    ORIGEM_INGRESSO_CHOICES = [
        ("DIRETO", "Ingresso direto"),
        ("PROCESSO_SELETIVO", "Processo seletivo"),
    ]

    turma = forms.ModelChoiceField(
        queryset=Turma.objects.none(),
        required=True,
        label="Turma",
        help_text="Selecione a turma para já matricular o aluno.",
    )
    origem_ingresso = forms.ChoiceField(
        label="Origem do ingresso",
        choices=ORIGEM_INGRESSO_CHOICES,
        initial="DIRETO",
    )
    processo_numero = forms.CharField(
        label="Número do processo seletivo",
        required=False,
        max_length=40,
    )
    processo_assunto = forms.CharField(
        label="Assunto do processo",
        required=False,
        max_length=180,
        initial="Ingresso de aluno",
    )
    edital_referencia = forms.CharField(
        label="Edital (opcional)",
        required=False,
        max_length=80,
    )
    observacao_ingresso = forms.CharField(
        label="Observação do ingresso",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        qs = Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
            "curso",
        ).order_by("-ano_letivo", "nome")

        if self.user and getattr(self.user, "is_authenticated", False) and not is_admin(self.user):
            qs = scope_filter_turmas(self.user, qs)

        self.fields["turma"].queryset = qs

    def clean(self):
        cleaned = super().clean()
        origem = (cleaned.get("origem_ingresso") or "DIRETO").strip().upper()
        processo_numero = (cleaned.get("processo_numero") or "").strip()
        processo_assunto = (cleaned.get("processo_assunto") or "").strip()

        if origem == "PROCESSO_SELETIVO":
            if not processo_numero:
                self.add_error("processo_numero", "Informe o número do processo seletivo.")
            if not processo_assunto:
                self.add_error("processo_assunto", "Informe o assunto do processo seletivo.")
        else:
            cleaned["processo_numero"] = ""
            cleaned["processo_assunto"] = ""
            cleaned["edital_referencia"] = ""
            cleaned["observacao_ingresso"] = ""
        return cleaned


class MatriculaForm(forms.ModelForm):
    override_requisitos = forms.BooleanField(
        required=False,
        label="Forçar matrícula ignorando pré-requisitos",
        help_text="Use apenas em casos excepcionais e com justificativa registrada.",
    )
    override_justificativa = forms.CharField(
        required=False,
        label="Justificativa do override",
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    class Meta:
        model = Matricula
        fields = [
            "turma",
            "data_matricula",
            "situacao",
            "resultado_final",
            "concluinte",
            "observacao",
            "override_requisitos",
            "override_justificativa",
        ]
        widgets = {
            "data_matricula": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        qs = Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        ).filter(ativo=True).order_by("-ano_letivo", "nome")

        if self.user and getattr(self.user, "is_authenticated", False) and not is_admin(self.user):
            qs = scope_filter_turmas(self.user, qs)

        self.fields["turma"].queryset = qs

        can_override = bool(self.user and can(self.user, "educacao.manage"))
        if not can_override:
            self.fields["override_requisitos"].widget = forms.HiddenInput()
            self.fields["override_justificativa"].widget = forms.HiddenInput()
        else:
            self.fields["override_justificativa"].help_text = (
                "Obrigatória quando o override for utilizado para liberar matrícula bloqueada."
            )

    def clean(self):
        cleaned = super().clean()
        wants_override = bool(cleaned.get("override_requisitos"))
        justificativa = (cleaned.get("override_justificativa") or "").strip()
        can_override = bool(self.user and can(self.user, "educacao.manage"))

        if wants_override and not can_override:
            self.add_error("override_requisitos", "Você não tem permissão para forçar matrícula.")

        if wants_override and not justificativa:
            self.add_error("override_justificativa", "Informe a justificativa para registrar o override.")

        if not wants_override:
            cleaned["override_justificativa"] = ""

        return cleaned


class MatriculaCursoForm(forms.ModelForm):
    class Meta:
        model = MatriculaCurso
        fields = [
            "curso",
            "turma",
            "data_matricula",
            "situacao",
            "data_conclusao",
            "nota_final",
            "frequencia_percentual",
            "observacao",
        ]
        widgets = {
            "data_matricula": forms.DateInput(attrs={"type": "date"}),
            "data_conclusao": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, aluno=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.aluno = aluno
        self.fields["curso"].queryset = Curso.objects.filter(ativo=True).order_by("nome")
        self.fields["curso"].label = "Atividade/Curso extracurricular"

        turma_qs = Turma.objects.select_related("curso", "unidade").filter(
            ativo=True,
            modalidade=Turma.Modalidade.ATIVIDADE_COMPLEMENTAR,
            curso__isnull=False,
        ).order_by(
            "-ano_letivo", "nome"
        )
        if user and getattr(user, "is_authenticated", False) and not is_admin(user):
            turma_qs = scope_filter_turmas(user, turma_qs)
        self.fields["turma"].queryset = turma_qs
        self.fields["turma"].required = False
        self.fields["turma"].empty_label = "Sem turma específica (somente atividade)"

    def clean(self):
        cleaned = super().clean()
        curso = cleaned.get("curso")
        turma = cleaned.get("turma")
        situacao = cleaned.get("situacao")
        data_matricula = cleaned.get("data_matricula")
        data_conclusao = cleaned.get("data_conclusao")

        if curso and turma:
            if not turma.curso_id:
                self.add_error("turma", "A turma selecionada não está vinculada a um curso.")
            elif turma.curso_id != curso.id:
                self.add_error("turma", "A turma selecionada pertence a outro curso.")

        if situacao == MatriculaCurso.Situacao.CONCLUIDO and not data_conclusao:
            self.add_error("data_conclusao", "Informe a data de conclusão para matrícula concluída.")

        if data_conclusao and data_matricula and data_conclusao < data_matricula:
            self.add_error("data_conclusao", "A data de conclusão não pode ser anterior à data de matrícula.")

        if self.aluno and curso:
            qs = MatriculaCurso.objects.filter(
                aluno=self.aluno,
                curso=curso,
                situacao__in=[MatriculaCurso.Situacao.MATRICULADO, MatriculaCurso.Situacao.EM_ANDAMENTO],
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if turma:
                qs = qs.filter(turma=turma)
            else:
                qs = qs.filter(turma__isnull=True)
            if qs.exists():
                self.add_error("curso", "Já existe matrícula ativa deste aluno para este curso/oferta.")

        return cleaned


class MatriculaQuickForm(forms.ModelForm):
    aluno = forms.ModelChoiceField(queryset=Aluno.objects.all(), label="Aluno", required=True)
    unidade = forms.ModelChoiceField(queryset=Unidade.objects.all(), label="Unidade (Escola)", required=True)

    class Meta:
        model = Matricula
        fields = [
            "aluno",
            "unidade",
            "turma",
            "data_matricula",
            "situacao",
        ]

    def __init__(self, *args, aluno_qs=None, turma_qs=None, unidade_qs=None, **kwargs):
        super().__init__(*args, **kwargs)

        if aluno_qs is not None:
            self.fields["aluno"].queryset = aluno_qs

        if unidade_qs is not None:
            self.fields["unidade"].queryset = unidade_qs

        self.fields["turma"].queryset = Turma.objects.none()

        unidade_id = None
        if self.data.get("unidade"):
            unidade_id = self.data.get("unidade")
        elif self.initial.get("unidade"):
            unidade_id = self.initial.get("unidade")

        if unidade_id and str(unidade_id).isdigit():
            base = turma_qs if turma_qs is not None else Turma.objects.all()
            self.fields["turma"].queryset = base.filter(unidade_id=int(unidade_id)).order_by("-ano_letivo", "nome")

        if "data_matricula" in self.fields:
            self.fields["data_matricula"].widget = forms.DateInput(attrs={"type": "date"})


class AlunoDocumentoForm(forms.ModelForm):
    class Meta:
        model = AlunoDocumento
        fields = [
            "tipo",
            "titulo",
            "numero_documento",
            "arquivo",
            "data_emissao",
            "validade",
            "observacao",
            "ativo",
        ]
        widgets = {
            "data_emissao": forms.DateInput(attrs={"type": "date"}),
            "validade": forms.DateInput(attrs={"type": "date"}),
        }


class AlunoCertificadoForm(forms.ModelForm):
    class Meta:
        model = AlunoCertificado
        fields = [
            "tipo",
            "titulo",
            "matricula",
            "curso",
            "data_emissao",
            "carga_horaria",
            "resultado_final",
            "observacao",
            "arquivo_pdf",
            "ativo",
        ]
        widgets = {
            "data_emissao": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, aluno=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["curso"].queryset = Curso.objects.filter(ativo=True).order_by("nome")
        self.fields["matricula"].queryset = Matricula.objects.none()
        if aluno is not None:
            self.fields["matricula"].queryset = (
                Matricula.objects.select_related("turma", "turma__unidade")
                .filter(aluno=aluno)
                .order_by("-turma__ano_letivo", "turma__nome")
            )
