from django import forms

from core.rbac import get_profile, is_admin

from .models import Turma, Aluno, Matricula


class TurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = ["unidade", "nome", "ano_letivo", "turno", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: 1º Ano A"}),
            "ano_letivo": forms.NumberInput(attrs={"min": 2000, "max": 2100}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is None:
            return

        if is_admin(user):
            return

        p = get_profile(user)
        if not p or not p.ativo:
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.none()
            return

        # UNIDADE: trava naquela unidade
        if p.role == "UNIDADE" and p.unidade_id:
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(id=p.unidade_id)
            self.fields["unidade"].initial = p.unidade_id

        # MUNICIPAL/NEE/LEITURA: limita ao município
        elif p.municipio_id:
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(
                secretaria__municipio_id=p.municipio_id
            )


class AlunoForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = [
            "nome",
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
            "nome": forms.TextInput(attrs={"placeholder": "Nome completo"}),
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "cpf": forms.TextInput(attrs={"placeholder": "000.000.000-00 (opcional)"}),
            "nis": forms.TextInput(attrs={"placeholder": "NIS (opcional)"}),
            "nome_mae": forms.TextInput(attrs={"placeholder": "Nome da mãe (opcional)"}),
            "nome_pai": forms.TextInput(attrs={"placeholder": "Nome do pai (opcional)"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(00) 0000-0000"}),
            "email": forms.EmailInput(attrs={"placeholder": "contato@..."}),
            "endereco": forms.Textarea(attrs={"rows": 3, "placeholder": "Endereço (opcional)"}),
        }


from core.rbac import scope_filter_turmas

class MatriculaForm(forms.ModelForm):
    class Meta:
        model = Matricula
        fields = ["turma", "data_matricula", "situacao", "observacao"]
        widgets = {
            "data_matricula": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 3, "placeholder": "Observação (opcional)"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # organiza o select de turmas
        qs = (
            self.fields["turma"].queryset
            .select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio")
            .order_by("-ano_letivo", "unidade__nome", "nome")
        )

        # ✅ aplica RBAC no select
        if user is not None:
            qs = scope_filter_turmas(user, qs)

        self.fields["turma"].queryset = qs


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # organiza o select de turmas
        self.fields["turma"].queryset = (
            self.fields["turma"].queryset.select_related("unidade")
            .order_by("-ano_letivo", "unidade__nome", "nome")
        )
