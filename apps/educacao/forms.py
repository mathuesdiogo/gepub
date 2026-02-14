from django import forms

from apps.core.rbac import get_profile, is_admin, scope_filter_turmas
from apps.org.models import Unidade
from .models import Turma, Aluno, Matricula
from apps.educacao.models import Matricula, Aluno, Turma  # ajuste se seus imports forem diferentes


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
    """
    Cria Aluno e já seleciona uma Turma para matricular no mesmo POST.
    Isso evita o aluno "sumir" do escopo (porque o escopo de Aluno é por matrícula).
    """
    turma = forms.ModelChoiceField(
        queryset=Turma.objects.none(),
        required=True,  # ✅ recomendado: aluno não fica "solto"
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
        ).order_by("-ano_letivo", "nome")  # ✅ removido filtro ativo=True

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
            "observacao",
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
        
class MatriculaQuickForm(forms.ModelForm):
    aluno = forms.ModelChoiceField(queryset=Aluno.objects.all(), label="Aluno", required=True)
    unidade = forms.ModelChoiceField(queryset=Unidade.objects.all(), label="Unidade (Escola)", required=True)

    class Meta:
        model = Matricula
        fields = ["aluno", "unidade", "turma", "data_matricula"]  # remova data_matricula se não existir

    def __init__(self, *args, aluno_qs=None, turma_qs=None, unidade_qs=None, **kwargs):
        super().__init__(*args, **kwargs)

        if aluno_qs is not None:
            self.fields["aluno"].queryset = aluno_qs

        if unidade_qs is not None:
            self.fields["unidade"].queryset = unidade_qs

        # Turmas começam vazias até escolher unidade
        self.fields["turma"].queryset = Turma.objects.none()

        # Se unidade já veio (GET ou POST), filtra turmas por unidade
        unidade_id = None
        if self.data.get("unidade"):
            unidade_id = self.data.get("unidade")
        elif self.initial.get("unidade"):
            unidade_id = self.initial.get("unidade")

        if unidade_id and str(unidade_id).isdigit():
            base = turma_qs if turma_qs is not None else Turma.objects.all()
            self.fields["turma"].queryset = base.filter(unidade_id=int(unidade_id)).order_by("-ano_letivo", "nome")

        if "data_matricula" in self.fields:
            self.fields["data_matricula"].widget.attrs.setdefault("placeholder", "dd/mm/aaaa")