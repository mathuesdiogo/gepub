from __future__ import annotations

from django import forms
from django.forms.models import fields_for_model
from django.urls import reverse

from apps.educacao.models import Matricula
from apps.saude.models import ProfissionalSaude

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


def _set_fields(form: forms.ModelForm, model, field_names: list[str]) -> None:
    """
    Alias enterprise (compatível com patches antigos).
    Alguns trechos do NEE chamam `_set_fields`, mas a implementação real é `_rebuild_fields`.
    """
    _rebuild_fields(form, model, field_names)


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
        self.aluno = kwargs.pop("aluno", None)
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
        self.aluno = kwargs.pop("aluno", None)
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

        if "matricula" in self.fields:
            if self.aluno is not None:
                self.fields["matricula"].queryset = (
                    Matricula.objects
                    .select_related("aluno", "turma")
                    .filter(aluno=self.aluno)
                    .order_by("-id")
                )
            else:
                self.fields["matricula"].queryset = Matricula.objects.none()


# ============================================================
# ENTERPRISE
# ============================================================

class LaudoNEEForm(forms.ModelForm):
    # Autocomplete institucional (Saúde)
    profissional_saude_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    profissional_saude_busca = forms.CharField(
        required=False,
        label="Profissional (Saúde)",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Digite o nome do profissional…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = LaudoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        self.aluno = kwargs.pop("aluno", None)
        if LaudoNEE is None:
            raise RuntimeError("Model LaudoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        # ⚠️ NÃO inclui profissional_saude (evita <select> gigante)
        _rebuild_fields(self, LaudoNEE, [
            "numero",
            "data_emissao",
            "validade",
            "profissional",
            "documento",
            "texto",
        ])

        # Liga autocomplete (modo fill do seu autocomplete.js)
        self.fields["profissional_saude_busca"].widget.attrs.update({
            "data-autocomplete-url": reverse("saude:api_profissionais_suggest"),
            "data-autocomplete-mode": "fill",
            "data-autocomplete-fill-target": "#id_profissional_saude_id",
            "data-autocomplete-min": "2",
            "data-autocomplete-max": "5",
            "autocomplete": "off",
        })

        # Edição: pré-popula
        if getattr(self.instance, "profissional_saude_id", None):
            self.initial["profissional_saude_id"] = self.instance.profissional_saude_id
            try:
                self.initial["profissional_saude_busca"] = self.instance.profissional_saude.nome
            except Exception:
                pass

        if "numero" in self.fields:
            self.fields["numero"].widget = forms.TextInput(attrs={"placeholder": "Número do laudo (opcional)"})
        if "profissional" in self.fields:
            self.fields["profissional"].widget = forms.TextInput(attrs={"placeholder": "Profissional responsável (opcional)"})
        if "texto" in self.fields:
            self.fields["texto"].widget = forms.Textarea(attrs={"rows": 4, "placeholder": "Descrição / parecer (opcional)"})

    def clean(self):
        cleaned = super().clean()

        prof_id = cleaned.get("profissional_saude_id")
        prof_obj = None
        if prof_id:
            prof_obj = ProfissionalSaude.objects.filter(id=prof_id).first()
            if not prof_obj:
                self.add_error("profissional_saude_busca", "Profissional inválido.")

        cleaned["profissional_saude_obj"] = prof_obj
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.profissional_saude = self.cleaned_data.get("profissional_saude_obj")
        if commit:
            obj.save()
        return obj


class RecursoNEEForm(forms.ModelForm):
    class Meta:
        model = RecursoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        self.aluno = kwargs.pop("aluno", None)
        if RecursoNEE is None:
            raise RuntimeError("Model RecursoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

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
        self.aluno = kwargs.pop("aluno", None)
        if AcompanhamentoNEE is None:
            raise RuntimeError("Model AcompanhamentoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

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
    profissional_saude_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    profissional_saude_busca = forms.CharField(
        required=False,
        label="Profissional (Saúde)",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Digite o nome do profissional…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = PlanoClinicoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        self.aluno = kwargs.pop("aluno", None)
        if PlanoClinicoNEE is None:
            raise RuntimeError("Model PlanoClinicoNEE não existe no app NEE.")
        super().__init__(*args, **kwargs)

        # ⚠️ NÃO inclui profissional_saude (evita <select> gigante)
        _set_fields(self, PlanoClinicoNEE, [
            "data_inicio",
            "data_revisao",
            "responsavel",
            "objetivo_geral",
            "observacao",
        ])

        self.fields["profissional_saude_busca"].widget.attrs.update({
            "data-autocomplete-url": reverse("saude:api_profissionais_suggest"),
            "data-autocomplete-mode": "fill",
            "data-autocomplete-fill-target": "#id_profissional_saude_id",
            "data-autocomplete-min": "2",
            "data-autocomplete-max": "5",
            "autocomplete": "off",
        })

        if getattr(self.instance, "profissional_saude_id", None):
            self.initial["profissional_saude_id"] = self.instance.profissional_saude_id
            try:
                self.initial["profissional_saude_busca"] = self.instance.profissional_saude.nome
            except Exception:
                pass

        if "objetivo_geral" in self.fields:
            self.fields["objetivo_geral"].widget = forms.Textarea(attrs={"rows": 3})
        if "observacao" in self.fields:
            self.fields["observacao"].widget = forms.Textarea(attrs={"rows": 3})

    def clean(self):
        cleaned = super().clean()

        prof_id = cleaned.get("profissional_saude_id")
        prof_obj = None
        if prof_id:
            prof_obj = ProfissionalSaude.objects.filter(id=prof_id).first()
            if not prof_obj:
                self.add_error("profissional_saude_busca", "Profissional inválido.")

        cleaned["profissional_saude_obj"] = prof_obj
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.profissional_saude = self.cleaned_data.get("profissional_saude_obj")
        if commit:
            obj.save()
        return obj


class ObjetivoPlanoNEEForm(forms.ModelForm):
    class Meta:
        model = ObjetivoPlanoNEE  # type: ignore[assignment]
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        self.aluno = kwargs.pop("aluno", None)
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
        self.aluno = kwargs.pop("aluno", None)
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
