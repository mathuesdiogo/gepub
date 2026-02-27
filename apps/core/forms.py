# apps/core/forms.py
from __future__ import annotations

from django import forms

from .models import (
    AlunoAviso,
    AlunoArquivo,
    InstitutionalPageConfig,
    InstitutionalSlide,
    InstitutionalMethodStep,
    InstitutionalServiceCard,
    PortalMunicipalConfig,
    PortalBanner,
    PortalPaginaPublica,
    PortalMenuPublico,
    PortalHomeBloco,
    PortalTransparenciaArquivo,
    PortalNoticia,
    DiarioOficialEdicao,
    ConcursoPublico,
    ConcursoEtapa,
    CamaraMateria,
    CamaraSessao,
)


class AlunoAvisoForm(forms.ModelForm):
    class Meta:
        model = AlunoAviso
        fields = [
            "titulo",
            "texto",
            "aluno",
            "turma",
            "unidade",
            "secretaria",
            "municipio",
            "ativo",
        ]


class AlunoArquivoForm(forms.ModelForm):
    class Meta:
        model = AlunoArquivo
        fields = [
            "titulo",
            "descricao",
            "arquivo",
            "aluno",
            "turma",
            "unidade",
            "secretaria",
            "municipio",
            "ativo",
        ]


class InstitutionalPageConfigForm(forms.ModelForm):
    class Meta:
        model = InstitutionalPageConfig
        fields = [
            "ativo",
            "marca_nome",
            "marca_logo",
            "nav_metodo_label",
            "nav_planos_label",
            "nav_servicos_label",
            "nav_simulador_label",
            "botao_login_label",
            "hero_kicker",
            "hero_titulo",
            "hero_descricao",
            "hero_cta_primario_label",
            "hero_cta_primario_link",
            "hero_cta_secundario_label",
            "hero_cta_secundario_link",
            "oferta_tag",
            "oferta_titulo",
            "oferta_descricao",
            "metodo_kicker",
            "metodo_titulo",
            "metodo_cta_label",
            "metodo_cta_link",
            "planos_kicker",
            "planos_titulo",
            "planos_descricao",
            "planos_cta_label",
            "planos_cta_link",
            "servicos_kicker",
            "servicos_titulo",
            "servicos_cta_label",
            "servicos_cta_link",
            "rodape_texto",
        ]
        widgets = {
            "hero_titulo": forms.Textarea(attrs={"rows": 2}),
            "hero_descricao": forms.Textarea(attrs={"rows": 3}),
            "oferta_titulo": forms.Textarea(attrs={"rows": 3}),
            "oferta_descricao": forms.Textarea(attrs={"rows": 3}),
            "metodo_titulo": forms.Textarea(attrs={"rows": 2}),
            "planos_titulo": forms.Textarea(attrs={"rows": 2}),
            "planos_descricao": forms.Textarea(attrs={"rows": 3}),
            "servicos_titulo": forms.Textarea(attrs={"rows": 2}),
        }


class InstitutionalSlideForm(forms.ModelForm):
    class Meta:
        model = InstitutionalSlide
        fields = [
            "titulo",
            "subtitulo",
            "descricao",
            "imagem",
            "icone",
            "cta_label",
            "cta_link",
            "ordem",
            "ativo",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }


class InstitutionalMethodStepForm(forms.ModelForm):
    class Meta:
        model = InstitutionalMethodStep
        fields = [
            "titulo",
            "descricao",
            "icone",
            "ordem",
            "ativo",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }


class InstitutionalServiceCardForm(forms.ModelForm):
    class Meta:
        model = InstitutionalServiceCard
        fields = [
            "titulo",
            "descricao",
            "icone",
            "ordem",
            "ativo",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }


class PortalMunicipalConfigForm(forms.ModelForm):
    class Meta:
        model = PortalMunicipalConfig
        fields = [
            "titulo_portal",
            "subtitulo_portal",
            "mensagem_boas_vindas",
            "logo",
            "brasao",
            "cor_primaria",
            "cor_secundaria",
            "endereco",
            "telefone",
            "email",
            "horario_atendimento",
        ]
        widgets = {
            "mensagem_boas_vindas": forms.Textarea(attrs={"rows": 3}),
        }


class PortalBannerForm(forms.ModelForm):
    class Meta:
        model = PortalBanner
        fields = [
            "titulo",
            "subtitulo",
            "imagem",
            "link",
            "ordem",
            "ativo",
        ]


class PortalPaginaPublicaForm(forms.ModelForm):
    class Meta:
        model = PortalPaginaPublica
        fields = [
            "titulo",
            "slug",
            "resumo",
            "conteudo",
            "mostrar_no_menu",
            "mostrar_no_rodape",
            "ordem",
            "publicado",
        ]
        widgets = {
            "resumo": forms.Textarea(attrs={"rows": 3}),
            "conteudo": forms.Textarea(attrs={"rows": 8}),
        }


class PortalMenuPublicoForm(forms.ModelForm):
    class Meta:
        model = PortalMenuPublico
        fields = [
            "titulo",
            "tipo_destino",
            "rota_interna",
            "pagina",
            "url_externa",
            "abrir_em_nova_aba",
            "posicao",
            "ordem",
            "ativo",
        ]

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo_destino")
        rota = cleaned.get("rota_interna")
        pagina = cleaned.get("pagina")
        externa = (cleaned.get("url_externa") or "").strip()

        if tipo == PortalMenuPublico.TipoDestino.INTERNO and not rota:
            self.add_error("rota_interna", "Selecione a rota interna.")
        if tipo == PortalMenuPublico.TipoDestino.PAGINA and not pagina:
            self.add_error("pagina", "Selecione uma página pública.")
        if tipo == PortalMenuPublico.TipoDestino.EXTERNO and not externa:
            self.add_error("url_externa", "Informe a URL externa.")
        return cleaned


class PortalHomeBlocoForm(forms.ModelForm):
    class Meta:
        model = PortalHomeBloco
        fields = [
            "titulo",
            "descricao",
            "icone",
            "link",
            "ordem",
            "ativo",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
        }


class PortalTransparenciaArquivoForm(forms.ModelForm):
    class Meta:
        model = PortalTransparenciaArquivo
        fields = [
            "categoria",
            "titulo",
            "descricao",
            "competencia",
            "data_referencia",
            "formato",
            "arquivo",
            "link_externo",
            "publico",
            "ordem",
            "publicado_em",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_referencia": forms.DateInput(attrs={"type": "date"}),
            "publicado_em": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned = super().clean()
        formato = cleaned.get("formato")
        arquivo = cleaned.get("arquivo")
        link_externo = (cleaned.get("link_externo") or "").strip()

        if formato == PortalTransparenciaArquivo.Formato.LINK:
            if not link_externo:
                self.add_error("link_externo", "Informe o link externo para o formato LINK.")
        elif not arquivo and not self.instance.pk:
            self.add_error("arquivo", "Anexe um arquivo para este formato.")
        return cleaned


class PortalNoticiaForm(forms.ModelForm):
    class Meta:
        model = PortalNoticia
        fields = [
            "titulo",
            "slug",
            "resumo",
            "conteudo",
            "categoria",
            "imagem",
            "destaque",
            "publicado",
            "publicado_em",
        ]
        widgets = {
            "resumo": forms.Textarea(attrs={"rows": 3}),
            "conteudo": forms.Textarea(attrs={"rows": 8}),
            "publicado_em": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class DiarioOficialEdicaoForm(forms.ModelForm):
    class Meta:
        model = DiarioOficialEdicao
        fields = [
            "numero",
            "data_publicacao",
            "resumo",
            "arquivo_pdf",
            "publicado",
        ]
        widgets = {
            "data_publicacao": forms.DateInput(attrs={"type": "date"}),
        }


class ConcursoPublicoForm(forms.ModelForm):
    class Meta:
        model = ConcursoPublico
        fields = [
            "titulo",
            "tipo",
            "status",
            "descricao",
            "edital_arquivo",
            "inicio_inscricao",
            "fim_inscricao",
            "publicado",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 5}),
            "inicio_inscricao": forms.DateInput(attrs={"type": "date"}),
            "fim_inscricao": forms.DateInput(attrs={"type": "date"}),
        }


class ConcursoEtapaForm(forms.ModelForm):
    class Meta:
        model = ConcursoEtapa
        fields = [
            "titulo",
            "descricao",
            "data_inicio",
            "data_fim",
            "arquivo",
            "ordem",
            "publicado",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }


class CamaraMateriaForm(forms.ModelForm):
    class Meta:
        model = CamaraMateria
        fields = [
            "tipo",
            "numero",
            "ano",
            "ementa",
            "descricao",
            "status",
            "arquivo",
            "publicado",
            "data_publicacao",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 5}),
            "data_publicacao": forms.DateInput(attrs={"type": "date"}),
        }


class CamaraSessaoForm(forms.ModelForm):
    class Meta:
        model = CamaraSessao
        fields = [
            "titulo",
            "data_sessao",
            "pauta",
            "ata_arquivo",
            "video_url",
            "publicado",
        ]
        widgets = {
            "pauta": forms.Textarea(attrs={"rows": 5}),
            "data_sessao": forms.DateInput(attrs={"type": "date"}),
        }
