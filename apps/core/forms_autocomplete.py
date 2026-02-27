# apps/core/forms_autocomplete.py
from __future__ import annotations

from typing import Any, Iterable, Optional

from django import forms
from django.urls import reverse_lazy


class AutocompleteFillWidget(forms.MultiWidget):
    """
    Renderiza 2 inputs em UM campo:
      - _0: input texto (busca/autocomplete)
      - _1: hidden com o ID (valor real)

    O autocomplete.js do GEPUB vai atuar no input texto, e quando selecionar
    preenche o hidden via:
      data-autocomplete-mode="fill"
      data-autocomplete-fill-target="#<id_do_hidden>"
    """

    def __init__(
        self,
        *,
        url_name: str,
        min_chars: int = 2,
        max_items: int = 5,
        attrs: Optional[dict[str, Any]] = None,
    ):
        self.url = reverse_lazy(url_name)
        self.min_chars = int(min_chars)
        self.max_items = int(max_items)

        widgets = (
            forms.TextInput(),
            forms.HiddenInput(),
        )
        super().__init__(widgets, attrs)

    def get_context(self, name: str, value: Any, attrs: dict[str, Any]):
        ctx = super().get_context(name, value, attrs)

        # IDs reais renderizados pelo Django em MultiWidget:
        # - texto: id_<name>_0
        # - hidden: id_<name>_1
        text_attrs = ctx["widget"]["subwidgets"][0]["attrs"]
        hidden_attrs = ctx["widget"]["subwidgets"][1]["attrs"]

        hidden_id = hidden_attrs.get("id")  # ex: id_aluno_1

        # Liga no seu autocomplete institucional
        text_attrs.update(
            {
                "data-autocomplete-url": str(self.url),
                "data-autocomplete-mode": "fill",
                "data-autocomplete-fill-target": f"#{hidden_id}" if hidden_id else "",
                "data-autocomplete-min": str(self.min_chars),
                "data-autocomplete-max": str(self.max_items),
                "autocomplete": "off",
            }
        )

        return ctx

    def decompress(self, value: Any):
        """
        value pode ser:
          - None
          - um model (Aluno)
          - um id (int/str)
        Retornamos: [texto, id]
        """
        if value is None:
            return ["", ""]
        # Model instance
        if hasattr(value, "pk"):
            label = getattr(value, "nome", str(value))
            return [label, value.pk]
        # ID direto
        return ["", value]


class AutocompleteModelChoiceField(forms.MultiValueField):
    """
    Campo definitivo:
      aluno = AutocompleteModelChoiceField(queryset=Aluno.objects.all(), url_name="educacao:api_alunos_suggest")

    - Renderiza input texto + hidden id
    - No POST, usa o hidden id pra validar e devolver a instância
    """

    widget: AutocompleteFillWidget

    def __init__(
        self,
        *,
        queryset,
        url_name: str,
        label: str = "",
        required: bool = True,
        min_chars: int = 2,
        max_items: int = 5,
        help_text: str = "",
        **kwargs,
    ):
        self._queryset = queryset

        fields = (
            forms.CharField(required=False),  # texto (decorativo)
            forms.ModelChoiceField(queryset=queryset, required=required),  # id real -> instance
        )

        widget = AutocompleteFillWidget(
            url_name=url_name,
            min_chars=min_chars,
            max_items=max_items,
        )

        super().__init__(
            fields=fields,
            required=required,
            label=label,
            help_text=help_text,
            widget=widget,
            require_all_fields=False,
            **kwargs,
        )

    def compress(self, data_list: Iterable[Any]):
        """
        data_list = [texto, instance]
        Retorna a instance, que é o que o ModelForm precisa.
        """
        if not data_list:
            return None
        instance = data_list[1]
        if self.required and not instance:
            raise forms.ValidationError("Selecione um item válido nas sugestões.")
        return instance