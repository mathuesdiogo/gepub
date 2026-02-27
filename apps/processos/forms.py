from __future__ import annotations

from django import forms

from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import ProcessoAdministrativo, ProcessoAndamento


class ProcessoAdministrativoForm(forms.ModelForm):
    class Meta:
        model = ProcessoAdministrativo
        fields = [
            "secretaria",
            "unidade",
            "setor",
            "numero",
            "tipo",
            "assunto",
            "solicitante_nome",
            "descricao",
            "status",
            "responsavel_atual",
            "data_abertura",
            "prazo_final",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["PROCESSO_TIPO"],
            )
            aplicar_sugestoes_em_campo(
                self,
                "tipo",
                sugestoes.get("PROCESSO_TIPO"),
            )


class ProcessoAndamentoForm(forms.ModelForm):
    class Meta:
        model = ProcessoAndamento
        fields = ["tipo", "setor_origem", "setor_destino", "despacho", "prazo", "data_evento"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            setores_qs = self.fields["setor_origem"].queryset.filter(unidade__secretaria__municipio=municipio)
            self.fields["setor_origem"].queryset = setores_qs
            self.fields["setor_destino"].queryset = setores_qs
