from __future__ import annotations

from django import forms
from django.forms.models import fields_for_model

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
    """Define os campos do ModelForm de forma *real*.

    Importante: alterar apenas `form._meta.fields` depois do `super().__init__()`
    NÃO recria `form.fields`. Por isso, além de setar `_meta.fields`, nós também
    reconstruímos os campos via `fields_for_model`.
    """
    # Só mantém campos que existem no model (evita FieldError)
    valid = [n for n in field_names if _model_has_field(model, n)]
    form._meta.fields = valid  # type: ignore[attr-defined]

    # Reconstrói os campos do formulário (senão `form.fields` fica vazio)
    generated = fields_for_model(model, fields=valid)

    # Preserva campos já existentes (caso algum seja declarado manualmente)
    for name, field in generated.items():
        if name not in form.fields:
            form.fields[name] = field


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
        fields = ["tipo", "cid", "observacao", "ativo"]
        widgets = {
            "cid": forms.TextInput(attrs={"placeholder": "Ex.: F84.0 (opcional)"}),
            "observacao": forms.Textarea(attrs={"rows": 3, "placeholder": "Observações (opcional)"}),
        }


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
        fields = [
            "numero",
            "data_emissao",
            "validade",
            "profissional",
            "documento",
            "texto",
        ]
        widgets = {
            "numero": forms.TextInput(attrs={"placeholder": "Número do laudo (opcional)"}),
            "profissional": forms.TextInput(attrs={"placeholder": "Profissional responsável (opcional)"}),
            "texto": forms.Textarea(attrs={"rows": 4, "placeholder": "Descrição / parecer (opcional)"}),
        }


class RecursoNEEForm(forms.ModelForm):
    class Meta:
        model = RecursoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if RecursoNEE is None:
            raise RuntimeError("Model RecursoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        _set_fields(self, RecursoNEE, [
            "nome",
            "status",
            "observacao",
        ])

        if "nome" in self.fields:
            self.fields["nome"].widget = forms.TextInput(attrs={"placeholder": "Ex.: Sala de recursos, Material adaptado..."})
        if "observacao" in self.fields:
            self.fields["observacao"].widget = forms.Textarea(attrs={"rows": 3})


class AcompanhamentoNEEForm(forms.ModelForm):
    class Meta:
        model = AcompanhamentoNEE  # type: ignore[assignment]
        fields = ["data", "tipo_evento", "descricao", "visibilidade"]

    def __init__(self, *args, **kwargs):
        if AcompanhamentoNEE is None:
            raise RuntimeError("Model AcompanhamentoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        if "descricao" in self.fields:
            self.fields["descricao"].widget = forms.Textarea(attrs={"rows": 4})