from django import forms
from django.core.exceptions import ValidationError

from .models import (
    TipoNecessidade,
    AlunoNecessidade,
    ApoioMatricula,
    LaudoNEE,
    AcompanhamentoNEE,
    RecursoNEE,
)


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
        self._aluno_ctx = aluno

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        aluno = getattr(self, "_aluno_ctx", None)

        if not tipo or aluno is None:
            return cleaned

        qs = AlunoNecessidade.objects.filter(aluno=aluno, tipo=tipo)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("Esse tipo de necessidade já está cadastrado para este aluno.")

        return cleaned


class LaudoNEEForm(forms.ModelForm):
    class Meta:
        model = LaudoNEE
        fields = ["tipo", "numero", "emissor", "data_emissao", "validade", "arquivo", "observacao", "ativo"]
        widgets = {
            "numero": forms.TextInput(attrs={"placeholder": "Número do laudo (se houver)"}),
            "emissor": forms.TextInput(attrs={"placeholder": "Ex.: Neuropediatra / Psicólogo(a) / Equipe"} ),
            "data_emissao": forms.DateInput(attrs={"type": "date"}),
            "validade": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 3, "placeholder": "Observações (opcional)"}),
        }

    def __init__(self, *args, aluno=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._aluno_ctx = aluno

    def save(self, commit=True):
        obj = super().save(commit=False)
        if getattr(self, "_aluno_ctx", None) is not None and obj.aluno_id is None:
            obj.aluno = self._aluno_ctx
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class RecursoNEEForm(forms.ModelForm):
    class Meta:
        model = RecursoNEE
        fields = ["nome", "categoria", "descricao", "ativo"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Sala de recursos, material ampliado..."}),
            "categoria": forms.TextInput(attrs={"placeholder": "Ex.: Tecnologia assistiva (opcional)"}),
            "descricao": forms.Textarea(attrs={"rows": 3, "placeholder": "Detalhes (opcional)"}),
        }

    def __init__(self, *args, aluno=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._aluno_ctx = aluno

    def save(self, commit=True):
        obj = super().save(commit=False)
        if getattr(self, "_aluno_ctx", None) is not None and obj.aluno_id is None:
            obj.aluno = self._aluno_ctx
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class AcompanhamentoNEEForm(forms.ModelForm):
    class Meta:
        model = AcompanhamentoNEE
        fields = ["necessidade", "profissional", "data", "titulo", "descricao", "status", "ativo"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "titulo": forms.TextInput(attrs={"placeholder": "Ex.: Reunião com família / Ajuste de apoio / Evolução"}),
            "descricao": forms.Textarea(attrs={"rows": 4, "placeholder": "Registro do acompanhamento (opcional)"}),
        }

    def __init__(self, *args, aluno=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._aluno_ctx = aluno

        # Limita opções de necessidade ao aluno do contexto
        if aluno is not None and "necessidade" in self.fields:
            self.fields["necessidade"].queryset = (
                self.fields["necessidade"].queryset.select_related("tipo").filter(aluno=aluno).order_by("-id")
            )

    def save(self, commit=True):
        obj = super().save(commit=False)
        if getattr(self, "_aluno_ctx", None) is not None and obj.aluno_id is None:
            obj.aluno = self._aluno_ctx
        if commit:
            obj.save()
            self.save_m2m()
        return obj


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

        if aluno is not None:
            self.fields["matricula"].queryset = (
                self.fields["matricula"].queryset
                .select_related("turma", "turma__unidade")
                .filter(aluno=aluno)
                .order_by("-id")
            )
