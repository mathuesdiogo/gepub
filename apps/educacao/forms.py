from django import forms

from core.rbac import get_profile, is_admin, scope_filter_turmas

from org.models import Unidade
from .models import Turma, Aluno, Matricula


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = [
            "unidade",
            "nome",
            "ano_letivo",
            "turno",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        self.fields["unidade"].queryset = Unidade.objects.filter(ativo=True).order_by("nome")

        # Admin vê tudo
        if not self.user or not getattr(self.user, "is_authenticated", False) or is_admin(self.user):
            return

        p = get_profile(self.user)
        if not p:
            return

        # UNIDADE: trava na própria unidade (e desabilita o campo)
        if p.role == "UNIDADE" and getattr(p, "unidade_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(id=p.unidade_id)
            self.fields["unidade"].initial = p.unidade_id
            self.fields["unidade"].disabled = True
            return

        # SECRETARIA: unidades da secretaria
        if p.role == "SECRETARIA" and getattr(p, "secretaria_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria_id=p.secretaria_id)
            return

        # MUNICIPAL / NEE / LEITURA: unidades do município
        if getattr(p, "municipio_id", None):
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(
                secretaria__municipio_id=p.municipio_id
            )


class AlunoForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = "__all__"


class MatriculaForm(forms.ModelForm):
    class Meta:
        model = Matricula
        fields = [
        "turma",
        "data_matricula",
        "situacao",
    ]

        

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
