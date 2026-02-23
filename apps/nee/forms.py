from __future__ import annotations

from django import forms
from django.forms.models import fields_for_model

from .models import TipoNecessidade, AlunoNecessidade, ApoioMatricula

# ============================================================
# Imports "enterprise" (isolados) — NÃO deixar um model quebrar os outros.
# ============================================================

try:
    from .models import LaudoNEE  # type: ignore
except Exception:  # pragma: no cover
    LaudoNEE = None  # type: ignore

try:
    from .models import RecursoNEE  # type: ignore
except Exception:  # pragma: no cover
    RecursoNEE = None  # type: ignore

try:
    from .models import AcompanhamentoNEE  # type: ignore
except Exception:  # pragma: no cover
    AcompanhamentoNEE = None  # type: ignore

# Models Plano Clínico (Enterprise)
try:
    from .models import PlanoClinicoNEE, ObjetivoPlanoNEE, EvolucaoPlanoNEE
except Exception:  # pragma: no cover
    PlanoClinicoNEE = None  # type: ignore
    ObjetivoPlanoNEE = None  # type: ignore
    EvolucaoPlanoNEE = None  # type: ignore


def _model_has_field(model, field_name: str) -> bool:
    if model is None:
        return False
    return field_name in {f.name for f in model._meta.fields}


def _rebuild_fields(form: forms.ModelForm, model, field_names: list[str]) -> None:
    """Reconstrói *de verdade* `form.fields` a partir do model.

    Motivo: quando `Meta.fields = []`, Django cria `form.fields = {}`.
    Alterar `form._meta.fields` depois do `super().__init__()` não recria os campos.
    Então a gente seta `_meta.fields` e RECONSTRÓI `form.fields` via `fields_for_model`.
    """
    if model is None:
        return

    valid = [n for n in field_names if _model_has_field(model, n)]
    form._meta.fields = valid  # type: ignore[attr-defined]

    generated = fields_for_model(model, fields=valid)

    # preserva campos declarados manualmente (se existirem)
    manual = {k: v for k, v in form.fields.items() if k not in generated}

    # substitui por completo para evitar "sumir campo" em ciclos de patch
    form.fields = {}
    form.fields.update(generated)
    form.fields.update(manual)


# ============================================================
# BÁSICOS
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

        _rebuild_fields(self, AlunoNecessidade, [
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

        _rebuild_fields(self, ApoioMatricula, [
            "matricula",
            "tipo",
            "descricao",
            "observacao",
            "carga_horaria",
            "carga_horaria_semanal",
            "ativo",
        ])

        if "descricao" in self.fields:
            self.fields["descricao"].widget = forms.TextInput(attrs={"placeholder": "Descrição (opcional)"})
        if "observacao" in self.fields:
            self.fields["observacao"].widget = forms.Textarea(attrs={"rows": 3, "placeholder": "Observação (opcional)"})
        if "carga_horaria" in self.fields:
            self.fields["carga_horaria"].widget = forms.NumberInput(attrs={"min": 1, "placeholder": "Horas"})
        if "carga_horaria_semanal" in self.fields:
            self.fields["carga_horaria_semanal"].widget = forms.NumberInput(attrs={"min": 1, "placeholder": "Horas/semana"})


# ============================================================
# ENTERPRISE
# ============================================================

class LaudoNEEForm(forms.ModelForm):
    class Meta:
        model = LaudoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if LaudoNEE is None:
            raise RuntimeError("Model LaudoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        # aluno é setado pela view (aluno_id na URL) — NÃO renderizar select gigante
        _rebuild_fields(self, LaudoNEE, [
            "numero",
            "data_emissao",
            "validade",
            "profissional",
            "documento",
            "texto",
        ])

        if "numero" in self.fields:
            self.fields["numero"].widget = forms.TextInput(attrs={"placeholder": "Número do laudo (opcional)"})
        if "profissional" in self.fields:
            self.fields["profissional"].widget = forms.TextInput(attrs={"placeholder": "Profissional responsável (opcional)"})
        if "texto" in self.fields:
            self.fields["texto"].widget = forms.Textarea(attrs={"rows": 4, "placeholder": "Descrição / parecer (opcional)"})


class RecursoNEEForm(forms.ModelForm):
    class Meta:
        model = RecursoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if RecursoNEE is None:
            raise RuntimeError("Model RecursoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        # aluno é setado pela view (aluno_id na URL) — NÃO renderizar select gigante
        _rebuild_fields(self, RecursoNEE, [
            "nome",
            "status",
            "observacao",
        ])

        if "observacao" in self.fields:
            self.fields["observacao"].widget = forms.Textarea(attrs={"rows": 3, "placeholder": "Observação (opcional)"})


class AcompanhamentoNEEForm(forms.ModelForm):
    class Meta:
        model = AcompanhamentoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if AcompanhamentoNEE is None:
            raise RuntimeError("Model AcompanhamentoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        # aluno/autor são setados pela view (aluno_id na URL; autor=request.user)
        _rebuild_fields(self, AcompanhamentoNEE, [
            "data",
            "tipo_evento",
            "visibilidade",
            "descricao",
        ])

        if "descricao" in self.fields:
            self.fields["descricao"].widget = forms.Textarea(attrs={"rows": 4, "placeholder": "Descreva o evento..."})
# ============================================================
# Plano Clínico NEE (Enterprise)
# ============================================================

class PlanoClinicoNEEForm(forms.ModelForm):
    class Meta:
        model = PlanoClinicoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if PlanoClinicoNEE is None:
            raise RuntimeError("Model PlanoClinicoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        _set_fields(self, PlanoClinicoNEE, [
            "data_inicio",
            "data_revisao",
            "responsavel",
            "objetivo_geral",
            "observacao",
        ])

        if "objetivo_geral" in self.fields:
            self.fields["objetivo_geral"].widget = forms.Textarea(attrs={"rows": 3})
        if "observacao" in self.fields:
            self.fields["observacao"].widget = forms.Textarea(attrs={"rows": 3})


class ObjetivoPlanoNEEForm(forms.ModelForm):
    class Meta:
        model = ObjetivoPlanoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if ObjetivoPlanoNEE is None:
            raise RuntimeError("Model ObjetivoPlanoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        _set_fields(self, ObjetivoPlanoNEE, [
            "area",
            "descricao",
            "meta",
            "prazo",
            "status",
        ])

        if "descricao" in self.fields:
            self.fields["descricao"].widget = forms.Textarea(attrs={"rows": 3})


class EvolucaoPlanoNEEForm(forms.ModelForm):
    class Meta:
        model = EvolucaoPlanoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        if EvolucaoPlanoNEE is None:
            raise RuntimeError("Model EvolucaoPlanoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        _set_fields(self, EvolucaoPlanoNEE, [
            "data",
            "descricao",
            "avaliacao",
            "profissional",
        ])

        if "descricao" in self.fields:
            self.fields["descricao"].widget = forms.Textarea(attrs={"rows": 3})
