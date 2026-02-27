from django import forms
from django.contrib.auth import get_user_model

from apps.core.rbac import get_profile, is_admin, scope_filter_turmas, scope_filter_unidades
from apps.org.models import Unidade

from .models import (
    Aluno,
    AlunoCertificado,
    AlunoDocumento,
    CoordenacaoEnsino,
    Curso,
    CursoDisciplina,
    Matricula,
    MatriculaCurso,
    Turma,
)


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
            "forma_oferta",
            "curso",
            "classe_especial",
            "bilingue_surdos",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["unidade"].queryset = Unidade.objects.filter(ativo=True).order_by("nome")
        self.fields["curso"].queryset = Curso.objects.filter(ativo=True).order_by("nome")

        if not self.user or not getattr(self.user, "is_authenticated", False) or is_admin(self.user):
            return

        p = get_profile(self.user)
        if not p:
            return

        if p.role == "UNIDADE" and getattr(p, "unidade_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(id=p.unidade_id)
            self.fields["unidade"].initial = p.unidade_id
            self.fields["unidade"].disabled = True
            return

        if p.role == "SECRETARIA" and getattr(p, "secretaria_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria_id=p.secretaria_id)
            return

        if getattr(p, "municipio_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(
                secretaria__municipio_id=p.municipio_id
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
        fields = "__all__"
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


class AlunoCreateComTurmaForm(AlunoForm):
    turma = forms.ModelChoiceField(
        queryset=Turma.objects.none(),
        required=True,
        label="Turma",
        help_text="Selecione a turma para já matricular o aluno.",
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


class MatriculaForm(forms.ModelForm):
    class Meta:
        model = Matricula
        fields = [
            "turma",
            "data_matricula",
            "situacao",
            "resultado_final",
            "concluinte",
            "observacao",
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

        turma_qs = Turma.objects.select_related("curso", "unidade").filter(ativo=True, curso__isnull=False).order_by(
            "-ano_letivo", "nome"
        )
        if user and getattr(user, "is_authenticated", False) and not is_admin(user):
            turma_qs = scope_filter_turmas(user, turma_qs)
        self.fields["turma"].queryset = turma_qs
        self.fields["turma"].required = False
        self.fields["turma"].empty_label = "Sem turma específica (somente curso)"

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
