from __future__ import annotations

from django import forms

from apps.org.models import Setor
from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import OuvidoriaCadastro, OuvidoriaResposta, OuvidoriaTramitacao


class OuvidoriaCadastroForm(forms.ModelForm):
    class Meta:
        model = OuvidoriaCadastro
        fields = [
            "protocolo",
            "assunto",
            "tipo",
            "prioridade",
            "descricao",
            "solicitante_nome",
            "solicitante_email",
            "solicitante_telefone",
            "secretaria",
            "unidade",
            "setor",
            "prazo_resposta",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["CHAMADO_TIPO", "PRIORIDADE"],
            )
            aplicar_sugestoes_em_campo(self, "tipo", sugestoes.get("CHAMADO_TIPO"))
            aplicar_sugestoes_em_campo(self, "prioridade", sugestoes.get("PRIORIDADE"))


class OuvidoriaTramitacaoForm(forms.ModelForm):
    class Meta:
        model = OuvidoriaTramitacao
        fields = ["chamado", "setor_origem", "setor_destino", "despacho", "ciencia"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["chamado"].queryset = OuvidoriaCadastro.objects.filter(municipio=municipio).exclude(
                status=OuvidoriaCadastro.Status.CONCLUIDO
            )
            setores = Setor.objects.filter(unidade__secretaria__municipio=municipio, ativo=True)
            self.fields["setor_origem"].queryset = setores
            self.fields["setor_destino"].queryset = setores


class OuvidoriaRespostaForm(forms.ModelForm):
    class Meta:
        model = OuvidoriaResposta
        fields = ["chamado", "resposta", "publico"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["chamado"].queryset = OuvidoriaCadastro.objects.filter(municipio=municipio).exclude(
                status=OuvidoriaCadastro.Status.CONCLUIDO
            )
