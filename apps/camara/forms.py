from __future__ import annotations

from django import forms

from .models import (
    AgendaLegislativa,
    Ata,
    CamaraConfig,
    CamaraOuvidoriaManifestacao,
    Comissao,
    ComissaoMembro,
    DocumentoCamara,
    MesaDiretora,
    NoticiaCamara,
    Pauta,
    Proposicao,
    ProposicaoAutor,
    ProposicaoTramitacao,
    Sessao,
    SessaoDocumento,
    TransparenciaCamaraItem,
    Transmissao,
    Vereador,
)


class CamaraConfigForm(forms.ModelForm):
    class Meta:
        model = CamaraConfig
        fields = [
            "nome_portal",
            "historia",
            "missao",
            "competencias_legislativo",
            "estrutura_administrativa",
            "contatos",
            "endereco",
            "telefone",
            "email",
            "horario_atendimento",
            "youtube_canal_url",
            "youtube_live_url",
            "youtube_playlist_url",
            "transparencia_url_externa",
            "status",
            "published_at",
        ]
        widgets = {
            "historia": forms.Textarea(attrs={"rows": 4}),
            "missao": forms.Textarea(attrs={"rows": 3}),
            "competencias_legislativo": forms.Textarea(attrs={"rows": 4}),
            "estrutura_administrativa": forms.Textarea(attrs={"rows": 4}),
            "contatos": forms.Textarea(attrs={"rows": 3}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class VereadorForm(forms.ModelForm):
    class Meta:
        model = Vereador
        fields = [
            "nome_completo",
            "nome_parlamentar",
            "foto",
            "partido",
            "biografia",
            "email",
            "telefone",
            "mandato_inicio",
            "mandato_fim",
            "agenda_publica",
            "status",
            "published_at",
        ]
        widgets = {
            "biografia": forms.Textarea(attrs={"rows": 4}),
            "agenda_publica": forms.Textarea(attrs={"rows": 3}),
            "mandato_inicio": forms.DateInput(attrs={"type": "date"}),
            "mandato_fim": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class MesaDiretoraForm(forms.ModelForm):
    class Meta:
        model = MesaDiretora
        fields = [
            "vereador",
            "cargo",
            "legislatura",
            "periodo_inicio",
            "periodo_fim",
            "observacao",
            "status",
            "published_at",
        ]
        widgets = {
            "periodo_inicio": forms.DateInput(attrs={"type": "date"}),
            "periodo_fim": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class ComissaoForm(forms.ModelForm):
    class Meta:
        model = Comissao
        fields = [
            "tipo",
            "nome",
            "descricao",
            "presidente",
            "relator",
            "periodo_inicio",
            "periodo_fim",
            "status",
            "published_at",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "periodo_inicio": forms.DateInput(attrs={"type": "date"}),
            "periodo_fim": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class ComissaoMembroForm(forms.ModelForm):
    class Meta:
        model = ComissaoMembro
        fields = [
            "comissao",
            "vereador",
            "papel",
            "periodo_inicio",
            "periodo_fim",
            "status",
            "published_at",
        ]
        widgets = {
            "periodo_inicio": forms.DateInput(attrs={"type": "date"}),
            "periodo_fim": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class SessaoForm(forms.ModelForm):
    class Meta:
        model = Sessao
        fields = [
            "tipo",
            "numero",
            "ano",
            "titulo",
            "data_hora",
            "local",
            "situacao",
            "ordem_dia",
            "pauta",
            "resultado",
            "link_transmissao",
            "status",
            "published_at",
        ]
        widgets = {
            "data_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ordem_dia": forms.Textarea(attrs={"rows": 4}),
            "pauta": forms.Textarea(attrs={"rows": 4}),
            "resultado": forms.Textarea(attrs={"rows": 3}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class SessaoDocumentoForm(forms.ModelForm):
    class Meta:
        model = SessaoDocumento
        fields = [
            "sessao",
            "tipo",
            "titulo",
            "descricao",
            "arquivo",
            "link_externo",
            "status",
            "published_at",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class ProposicaoForm(forms.ModelForm):
    class Meta:
        model = Proposicao
        fields = [
            "tipo",
            "numero",
            "ano",
            "ementa",
            "texto_completo",
            "situacao",
            "tramitacao_resumo",
            "comissao",
            "sessao",
            "arquivo",
            "entrada_em",
            "status",
            "published_at",
        ]
        widgets = {
            "texto_completo": forms.Textarea(attrs={"rows": 6}),
            "tramitacao_resumo": forms.Textarea(attrs={"rows": 4}),
            "entrada_em": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class ProposicaoAutorForm(forms.ModelForm):
    class Meta:
        model = ProposicaoAutor
        fields = [
            "proposicao",
            "vereador",
            "nome_livre",
            "papel",
            "status",
            "published_at",
        ]
        widgets = {
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class ProposicaoTramitacaoForm(forms.ModelForm):
    class Meta:
        model = ProposicaoTramitacao
        fields = [
            "proposicao",
            "data_evento",
            "etapa",
            "descricao",
            "situacao",
            "comissao",
            "sessao",
            "ordem",
            "status",
            "published_at",
        ]
        widgets = {
            "data_evento": forms.DateInput(attrs={"type": "date"}),
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class AtaForm(forms.ModelForm):
    class Meta:
        model = Ata
        fields = [
            "sessao",
            "numero",
            "ano",
            "titulo",
            "resumo",
            "arquivo",
            "data_documento",
            "status",
            "published_at",
        ]
        widgets = {
            "resumo": forms.Textarea(attrs={"rows": 4}),
            "data_documento": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class PautaForm(forms.ModelForm):
    class Meta:
        model = Pauta
        fields = [
            "sessao",
            "numero",
            "ano",
            "titulo",
            "descricao",
            "arquivo",
            "data_documento",
            "status",
            "published_at",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_documento": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class NoticiaCamaraForm(forms.ModelForm):
    class Meta:
        model = NoticiaCamara
        fields = [
            "titulo",
            "slug",
            "resumo",
            "conteudo",
            "categoria",
            "imagem",
            "destaque_home",
            "autor_nome",
            "vereador",
            "sessao",
            "status",
            "published_at",
        ]
        widgets = {
            "resumo": forms.Textarea(attrs={"rows": 3}),
            "conteudo": forms.Textarea(attrs={"rows": 8}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class AgendaLegislativaForm(forms.ModelForm):
    class Meta:
        model = AgendaLegislativa
        fields = [
            "tipo",
            "titulo",
            "descricao",
            "inicio",
            "fim",
            "local",
            "sessao",
            "comissao",
            "status",
            "published_at",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fim": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class TransmissaoForm(forms.ModelForm):
    class Meta:
        model = Transmissao
        fields = [
            "titulo",
            "canal_url",
            "live_url",
            "playlist_url",
            "status_transmissao",
            "inicio_previsto",
            "inicio_real",
            "fim_real",
            "sessao",
            "destaque_home",
            "status",
            "published_at",
        ]
        widgets = {
            "inicio_previsto": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "inicio_real": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "fim_real": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class TransparenciaCamaraItemForm(forms.ModelForm):
    class Meta:
        model = TransparenciaCamaraItem
        fields = [
            "categoria",
            "titulo",
            "descricao",
            "competencia",
            "data_referencia",
            "valor",
            "formato",
            "arquivo",
            "link_externo",
            "dados",
            "status",
            "published_at",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_referencia": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class DocumentoCamaraForm(forms.ModelForm):
    class Meta:
        model = DocumentoCamara
        fields = [
            "categoria",
            "titulo",
            "descricao",
            "data_documento",
            "formato",
            "arquivo",
            "link_externo",
            "status",
            "published_at",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_documento": forms.DateInput(attrs={"type": "date"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class CamaraOuvidoriaManifestacaoForm(forms.ModelForm):
    class Meta:
        model = CamaraOuvidoriaManifestacao
        fields = [
            "protocolo",
            "tipo",
            "assunto",
            "mensagem",
            "solicitante_nome",
            "solicitante_email",
            "solicitante_telefone",
            "status_atendimento",
            "resposta",
            "respondido_em",
            "status",
            "published_at",
        ]
        widgets = {
            "mensagem": forms.Textarea(attrs={"rows": 4}),
            "resposta": forms.Textarea(attrs={"rows": 4}),
            "respondido_em": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
