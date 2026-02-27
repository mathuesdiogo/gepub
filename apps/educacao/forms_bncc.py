from __future__ import annotations

from django import forms


def bncc_option_label(obj, max_chars: int = 110) -> str:
    descricao = (getattr(obj, "descricao", "") or "").strip()
    if descricao and len(descricao) > max_chars:
        descricao = descricao[: max_chars - 3].rstrip() + "..."
    if descricao:
        return f"{obj.codigo} - {descricao}"
    return str(getattr(obj, "codigo", ""))


class BNCCModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return bncc_option_label(obj)


class BNCCModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return bncc_option_label(obj)
