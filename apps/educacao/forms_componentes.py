from __future__ import annotations

from django import forms

from .forms_bncc import bncc_option_label
from .models_notas import BNCCCodigo, ComponenteCurricular


class ComponenteCurricularForm(forms.ModelForm):
    codigo_bncc_referencia = forms.ChoiceField(
        required=False,
        label="Código BNCC de referência",
        choices=[("", "Selecione um código BNCC")],
    )

    class Meta:
        model = ComponenteCurricular
        fields = [
            "nome",
            "sigla",
            "modalidade_bncc",
            "etapa_bncc",
            "area_codigo_bncc",
            "codigo_bncc_referencia",
            "ativo",
        ]
        widgets = {
            "codigo_bncc_referencia": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        modalidade = ""
        etapa = ""
        area = ""
        if self.data:
            modalidade = (self.data.get("modalidade_bncc") or "").strip()
            etapa = (self.data.get("etapa_bncc") or "").strip()
            area = (self.data.get("area_codigo_bncc") or "").strip().upper()
        elif self.instance and self.instance.pk:
            modalidade = (self.instance.modalidade_bncc or "").strip()
            etapa = (self.instance.etapa_bncc or "").strip()
            area = (self.instance.area_codigo_bncc or "").strip().upper()

        qs = BNCCCodigo.objects.filter(ativo=True).order_by("codigo")
        if modalidade:
            qs = qs.filter(modalidade=modalidade)
        if etapa:
            qs = qs.filter(etapa=etapa)
        if area:
            qs = qs.filter(area_codigo=area)

        selected_ref = ""
        if self.data.get("codigo_bncc_referencia"):
            selected_ref = (self.data.get("codigo_bncc_referencia") or "").strip().upper()
        elif self.instance and self.instance.pk:
            selected_ref = (self.instance.codigo_bncc_referencia or "").strip().upper()

        if selected_ref and not qs.filter(codigo=selected_ref).exists():
            qs = (qs | BNCCCodigo.objects.filter(codigo=selected_ref, ativo=True)).distinct()

        qs = qs.order_by("codigo")
        self.bncc_options_total = qs.count()
        self.fields["codigo_bncc_referencia"].choices = [("", "Selecione um código BNCC")] + [
            (obj.codigo, bncc_option_label(obj))
            for obj in qs
        ]
        if selected_ref:
            self.fields["codigo_bncc_referencia"].initial = selected_ref

        self.fields["area_codigo_bncc"].help_text = "Ex.: LP, MA, CI, HI, GE, AR, ER, CG, EO, ET, TS, EF, LGG, CHS, CNT"
        self.fields["codigo_bncc_referencia"].help_text = "Selecione o código principal do componente."

    def clean_codigo_bncc_referencia(self):
        codigo = (self.cleaned_data.get("codigo_bncc_referencia") or "").strip().upper()
        if codigo and not BNCCCodigo.objects.filter(codigo=codigo, ativo=True).exists():
            raise forms.ValidationError("Selecione um código BNCC válido.")
        return codigo

    def _sync_bncc_referencia(self):
        if not self.instance.pk:
            return
        codigo = (self.cleaned_data.get("codigo_bncc_referencia") or "").strip().upper()
        if not codigo:
            self.instance.bncc_codigos.clear()
            return
        ref_qs = BNCCCodigo.objects.filter(codigo=codigo, ativo=True)
        self.instance.bncc_codigos.set(ref_qs)

    def save(self, commit=True):
        obj = super().save(commit=commit)
        if commit:
            self._sync_bncc_referencia()
        return obj
