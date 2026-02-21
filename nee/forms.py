from django import forms
from django.core.exceptions import ValidationError

from .models import TipoNecessidade, AlunoNecessidade, ApoioMatricula


class TipoNecessidadeForm(forms.ModelForm):
    class Meta:
        model = TipoNecessidade
        fields = ["nome", "ativo"]
        widgets = {
            "nome": forms.TextInput(
                attrs={"placeholder": "Ex.: TEA, TDAH, Def. Intelectual..."}
            ),
        }


class AlunoNecessidadeForm(forms.ModelForm):
    class Meta:
        model = AlunoNecessidade
        fields = ["tipo", "cid", "observacao", "ativo"]
        widgets = {
            "cid": forms.TextInput(attrs={"placeholder": "Ex.: F84.0 (opcional)"}),
            "observacao": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Observações (opcional)"}
            ),
        }

    def __init__(self, *args, aluno=None, **kwargs):
        super().__init__(*args, **kwargs)
        # guarda o aluno do contexto (pra validar duplicidade)
        self._aluno_ctx = aluno

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        aluno = getattr(self, "_aluno_ctx", None)

        if not tipo or aluno is None:
            return cleaned

        # Se estiver editando um registro existente, ignora ele mesmo
        qs = AlunoNecessidade.objects.filter(aluno=aluno, tipo=tipo)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("Esse tipo de necessidade já está cadastrado para este aluno.")

        return cleaned


class ApoioMatriculaForm(forms.ModelForm):
    class Meta:
        model = ApoioMatricula
        fields = ["matricula", "tipo", "descricao", "carga_horaria_semanal", "ativo"]
        widgets = {
            "descricao": forms.TextInput(
                attrs={"placeholder": "Ex.: AEE 2x por semana"}
            ),
            "carga_horaria_semanal": forms.NumberInput(
                attrs={"min": 0, "placeholder": "Ex.: 5"}
            ),
        }

    def __init__(self, *args, aluno=None, **kwargs):
        super().__init__(*args, **kwargs)

        # 🔒 Mostra só as matrículas do aluno atual
        if aluno is not None:
            self.fields["matricula"].queryset = (
                self.fields["matricula"].queryset
                .select_related("turma", "turma__unidade")
                .filter(aluno=aluno)
                .order_by("-id")
            )
