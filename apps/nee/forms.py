from __future__ import annotations

from django import forms

from .models import (
    TipoNecessidade,
    AlunoNecessidade,
    ApoioMatricula,
)

# Models premium (podem existir no seu NEE enterprise)
try:
    from .models import LaudoNEE, RecursoNEE, AcompanhamentoNEE
except Exception:  # pragma: no cover
    LaudoNEE = None  # type: ignore
    RecursoNEE = None  # type: ignore
    AcompanhamentoNEE = None  # type: ignore


def _model_has_field(model, field_name: str) -> bool:
    if model is None:
        return False
    return field_name in {f.name for f in model._meta.fields}


def _set_fields(form: forms.ModelForm, model, field_names: list[str]) -> None:
    # Só mantém campos que existem no model (evita FieldError)
    valid = [n for n in field_names if _model_has_field(model, n)]
    form._meta.fields = valid  # type: ignore[attr-defined]


# ============================================================
# Básicos (usados também pelo app Educação)
# ============================================================

class TipoNecessidadeForm(forms.ModelForm):
    class Meta:
        model = TipoNecessidade
        fields = ["nome", "ativo"] if _model_has_field(TipoNecessidade, "ativo") else ["nome"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: TEA, TDAH, Def. Intelectual..."}),
        }


class AlunoNecessidadeForm(forms.ModelForm):
    class Meta:
        model = AlunoNecessidade
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        _set_fields(self, AlunoNecessidade, [
            "tipo",
            "cid",
            "observacao",
            "ativo",
        ])

        if "cid" in self.fields:
            self.fields["cid"].widget = forms.TextInput(attrs={"placeholder": "Ex.: F84.0 (opcional)"})
        if "observacao" in self.fields:
            self.fields["observacao"].widget = forms.Textarea(attrs={"rows": 3, "placeholder": "Observações (opcional)"})


class ApoioMatriculaForm(forms.ModelForm):
    class Meta:
        model = ApoioMatricula
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Nota: carga_horaria_semanal só entra se existir no model
        _set_fields(self, ApoioMatricula, [
            "matricula",
            "tipo",
            "descricao",
            "observacao",
            "carga_horaria_semanal",
            "ativo",
        ])

        if "descricao" in self.fields:
            self.fields["descricao"].widget = forms.TextInput(attrs={"placeholder": "Descrição (opcional)"})
        if "observacao" in self.fields:
            self.fields["observacao"].widget = forms.Textarea(attrs={"rows": 3, "placeholder": "Observação (opcional)"})
        if "carga_horaria_semanal" in self.fields:
            self.fields["carga_horaria_semanal"].widget = forms.NumberInput(attrs={"min": 1, "placeholder": "Horas/semana"})


# ============================================================
# Premium / Enterprise (views_* importam estes nomes)
# ============================================================

class LaudoNEEForm(forms.ModelForm):
    class Meta:
        model = LaudoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if LaudoNEE is None:
            raise RuntimeError("Model LaudoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        _set_fields(self, LaudoNEE, [
            "aluno",
            "numero",
            "data_emissao",
            "validade",
            "profissional",
            "documento",
            "texto",
            "ativo",
        ])

        if "texto" in self.fields:
            self.fields["texto"].widget = forms.Textarea(attrs={"rows": 4})


class RecursoNEEForm(forms.ModelForm):
    class Meta:
        model = RecursoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if RecursoNEE is None:
            raise RuntimeError("Model RecursoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        _set_fields(self, RecursoNEE, [
            "aluno",
            "nome",
            "status",
            "observacao",
            "ativo",
        ])

        if "observacao" in self.fields:
            self.fields["observacao"].widget = forms.Textarea(attrs={"rows": 3})


class AcompanhamentoNEEForm(forms.ModelForm):
    class Meta:
        model = AcompanhamentoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if AcompanhamentoNEE is None:
            raise RuntimeError("Model AcompanhamentoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        _set_fields(self, AcompanhamentoNEE, [
            "aluno",
            "data",
            "tipo_evento",
            "descricao",
            "visibilidade",
        ])

        if "descricao" in self.fields:
            self.fields["descricao"].widget = forms.Textarea(attrs={"rows": 4})
