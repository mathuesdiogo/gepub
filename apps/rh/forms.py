from __future__ import annotations

from django import forms

from apps.accounts.models import Profile
from apps.org.models import Secretaria, Setor, Unidade
from apps.org.services.cadastros_base import aplicar_sugestoes_em_campo, mapear_sugestoes_por_categoria

from .models import (
    RhCadastro,
    RhDocumento,
    RhMovimentacao,
    RhPdpNecessidade,
    RhPdpPlano,
    RhRemanejamentoEdital,
    RhRemanejamentoInscricao,
    RhRemanejamentoRecurso,
    RhSubstituicaoServidor,
)


class RhCadastroForm(forms.ModelForm):
    class Meta:
        model = RhCadastro
        fields = [
            "servidor",
            "secretaria",
            "unidade",
            "setor",
            "codigo",
            "matricula",
            "nome",
            "cargo",
            "funcao",
            "regime",
            "data_admissao",
            "situacao_funcional",
            "salario_base",
            "data_desligamento",
            "status",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)
            self.fields["servidor"].queryset = (
                self.fields["servidor"]
                .queryset.filter(profile__municipio=municipio, profile__ativo=True)
                .exclude(profile__role=Profile.Role.ALUNO)
            )
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["CARGO", "CARGO_FUNCAO"],
            )
            aplicar_sugestoes_em_campo(self, "cargo", sugestoes.get("CARGO") or sugestoes.get("CARGO_FUNCAO"))
            aplicar_sugestoes_em_campo(self, "funcao", sugestoes.get("CARGO_FUNCAO") or sugestoes.get("CARGO"))
        self.fields["servidor"].required = False

    def clean(self):
        cleaned = super().clean()
        unidade = cleaned.get("unidade")
        setor = cleaned.get("setor")
        desligamento = cleaned.get("data_desligamento")
        admissao = cleaned.get("data_admissao")
        situacao = cleaned.get("situacao_funcional")
        matricula = (cleaned.get("matricula") or "").strip()

        if setor and unidade and setor.unidade_id != unidade.id:
            self.add_error("setor", "O setor informado não pertence à unidade selecionada.")
        if admissao and desligamento and desligamento < admissao:
            self.add_error("data_desligamento", "Data de desligamento não pode ser menor que a data de admissão.")
        if situacao == RhCadastro.SituacaoFuncional.DESLIGADO and not desligamento:
            self.add_error("data_desligamento", "Informe a data de desligamento para situação desligado.")
        if not matricula:
            cleaned["matricula"] = (cleaned.get("codigo") or "").strip()
        return cleaned


class RhMovimentacaoForm(forms.ModelForm):
    class Meta:
        model = RhMovimentacao
        fields = [
            "servidor",
            "tipo",
            "data_inicio",
            "data_fim",
            "secretaria_destino",
            "unidade_destino",
            "setor_destino",
            "observacao",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            self.fields["servidor"].queryset = RhCadastro.objects.filter(municipio=municipio, status=RhCadastro.Status.ATIVO)
            self.fields["secretaria_destino"].queryset = Secretaria.objects.filter(municipio=municipio, ativo=True)
            self.fields["unidade_destino"].queryset = Unidade.objects.filter(secretaria__municipio=municipio, ativo=True)
            self.fields["setor_destino"].queryset = Setor.objects.filter(unidade__secretaria__municipio=municipio, ativo=True)

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("data_inicio")
        fim = cleaned.get("data_fim")
        unidade = cleaned.get("unidade_destino")
        setor = cleaned.get("setor_destino")
        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "Data final não pode ser menor que a data inicial.")
        if setor and unidade and setor.unidade_id != unidade.id:
            self.add_error("setor_destino", "O setor destino deve pertencer à unidade destino.")
        return cleaned


class RhDocumentoForm(forms.ModelForm):
    class Meta:
        model = RhDocumento
        fields = ["servidor", "tipo", "numero", "data_documento", "descricao", "arquivo"]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["servidor"].queryset = RhCadastro.objects.filter(municipio=municipio).order_by("nome")
            sugestoes = mapear_sugestoes_por_categoria(
                municipio_id=municipio.id,
                categorias=["DOCUMENTO_TIPO"],
            )
            aplicar_sugestoes_em_campo(self, "tipo", sugestoes.get("DOCUMENTO_TIPO"))


class RhRemanejamentoEditalForm(forms.ModelForm):
    class Meta:
        model = RhRemanejamentoEdital
        fields = [
            "numero",
            "titulo",
            "tipo_servidor",
            "inscricao_inicio",
            "inscricao_fim",
            "recurso_inicio",
            "recurso_fim",
            "resultado_em",
            "status",
            "observacao",
        ]
        widgets = {
            "inscricao_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "inscricao_fim": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "recurso_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "recurso_fim": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "resultado_em": forms.DateInput(attrs={"type": "date"}),
        }


class RhRemanejamentoInscricaoForm(forms.ModelForm):
    class Meta:
        model = RhRemanejamentoInscricao
        fields = [
            "servidor",
            "disciplina_interesse",
            "ingressou_mesma_disciplina",
            "redistribuido",
            "data_ingresso",
            "homologacao_dou",
            "unidades_interesse",
            "portaria_nomeacao",
            "portaria_lotacao",
            "situacao_funcional_arquivo",
        ]
        widgets = {
            "data_ingresso": forms.DateInput(attrs={"type": "date"}),
            "unidades_interesse": forms.SelectMultiple(attrs={"size": 8}),
        }

    def __init__(self, *args, municipio=None, user=None, is_manager=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        self.user = user
        self.is_manager = bool(is_manager)

        if municipio is not None:
            self.fields["servidor"].queryset = RhCadastro.objects.filter(
                municipio=municipio,
                status=RhCadastro.Status.ATIVO,
            ).order_by("nome")
            self.fields["unidades_interesse"].queryset = Unidade.objects.filter(
                secretaria__municipio=municipio,
                ativo=True,
            ).order_by("nome")

        if not self.is_manager and user is not None:
            self.fields["servidor"].queryset = self.fields["servidor"].queryset.filter(servidor=user)
            own = self.fields["servidor"].queryset.first()
            if own:
                self.fields["servidor"].initial = own
                self.fields["servidor"].disabled = True

    def clean(self):
        cleaned = super().clean()
        servidor = cleaned.get("servidor")
        unidades = cleaned.get("unidades_interesse")
        disciplina = (cleaned.get("disciplina_interesse") or "").strip()

        if self.municipio and servidor and servidor.municipio_id != self.municipio.id:
            self.add_error("servidor", "Servidor fora do município selecionado.")

        if servidor and servidor.servidor_id and self.user and not self.is_manager and servidor.servidor_id != self.user.id:
            self.add_error("servidor", "Você só pode realizar sua própria inscrição.")

        if unidades and self.municipio:
            invalidas = [u for u in unidades if u.secretaria.municipio_id != self.municipio.id]
            if invalidas:
                self.add_error("unidades_interesse", "Há unidades fora do município.")

        if self.instance.pk is None:
            if not cleaned.get("portaria_nomeacao"):
                self.add_error("portaria_nomeacao", "Anexo obrigatório.")
            if not cleaned.get("portaria_lotacao"):
                self.add_error("portaria_lotacao", "Anexo obrigatório.")
            if not cleaned.get("situacao_funcional_arquivo"):
                self.add_error("situacao_funcional_arquivo", "Anexo obrigatório.")

        if servidor and "DOCENTE" in (servidor.cargo or "").upper() and not disciplina:
            self.add_error("disciplina_interesse", "Para docente, informe a disciplina de interesse.")

        return cleaned


class RhRemanejamentoRecursoForm(forms.ModelForm):
    class Meta:
        model = RhRemanejamentoRecurso
        fields = ["texto", "anexo"]
        widgets = {
            "texto": forms.Textarea(attrs={"rows": 4}),
        }


class RhSubstituicaoServidorForm(forms.ModelForm):
    modulos_liberados_texto = forms.CharField(
        required=False,
        label="Módulos liberados",
        help_text="Informe um módulo por linha (ex.: Administracao::Protocolo).",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    grupos_liberados_texto = forms.CharField(
        required=False,
        label="Grupos liberados",
        help_text="Opcional. Informe um grupo por linha.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    tipos_conteudoportal_texto = forms.CharField(
        required=False,
        label="Tipos de edital/documento",
        help_text="Opcional. Informe um tipo por linha.",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    class Meta:
        model = RhSubstituicaoServidor
        fields = [
            "substituido",
            "substituto",
            "motivo",
            "data_inicio",
            "data_fim",
            "setores_liberados",
            "substituto_ja_tramitador",
        ]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
            "setores_liberados": forms.SelectMultiple(attrs={"size": 8}),
            "motivo": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        if municipio is not None:
            servidores_qs = RhCadastro.objects.filter(
                municipio=municipio,
                status=RhCadastro.Status.ATIVO,
            ).order_by("nome")
            self.fields["substituido"].queryset = servidores_qs
            self.fields["substituto"].queryset = servidores_qs
            self.fields["setores_liberados"].queryset = Setor.objects.filter(
                unidade__secretaria__municipio=municipio,
                ativo=True,
            ).order_by("nome")

        if self.instance.pk:
            self.fields["modulos_liberados_texto"].initial = "\n".join(self.instance.modulos_liberados_json or [])
            self.fields["grupos_liberados_texto"].initial = "\n".join(self.instance.grupos_liberados_json or [])
            self.fields["tipos_conteudoportal_texto"].initial = "\n".join(self.instance.tipos_conteudoportal_json or [])

    @staticmethod
    def _split_lines(value: str) -> list[str]:
        items = []
        for raw in (value or "").splitlines():
            txt = raw.strip()
            if txt and txt not in items:
                items.append(txt)
        return items

    def clean(self):
        cleaned = super().clean()
        sub_a = cleaned.get("substituido")
        sub_b = cleaned.get("substituto")
        inicio = cleaned.get("data_inicio")
        fim = cleaned.get("data_fim")
        setores = cleaned.get("setores_liberados")

        if sub_a and sub_b and sub_a.pk == sub_b.pk:
            self.add_error("substituto", "Substituto deve ser diferente do substituído.")

        if inicio and fim and fim < inicio:
            self.add_error("data_fim", "Data fim não pode ser menor que data início.")

        if self.municipio and sub_a and sub_a.municipio_id != self.municipio.id:
            self.add_error("substituido", "Substituído não pertence ao município.")
        if self.municipio and sub_b and sub_b.municipio_id != self.municipio.id:
            self.add_error("substituto", "Substituto não pertence ao município.")

        if setores and self.municipio:
            invalidos = [s for s in setores if s.unidade.secretaria.municipio_id != self.municipio.id]
            if invalidos:
                self.add_error("setores_liberados", "Há setores fora do município.")

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.modulos_liberados_json = self._split_lines(self.cleaned_data.get("modulos_liberados_texto", ""))
        obj.grupos_liberados_json = self._split_lines(self.cleaned_data.get("grupos_liberados_texto", ""))
        obj.tipos_conteudoportal_json = self._split_lines(self.cleaned_data.get("tipos_conteudoportal_texto", ""))
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class RhPdpPlanoForm(forms.ModelForm):
    class Meta:
        model = RhPdpPlano
        fields = ["ano", "titulo", "inicio_coleta", "fim_coleta", "status", "observacao"]
        widgets = {
            "inicio_coleta": forms.DateInput(attrs={"type": "date"}),
            "fim_coleta": forms.DateInput(attrs={"type": "date"}),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }


class RhPdpNecessidadeForm(forms.ModelForm):
    class Meta:
        model = RhPdpNecessidade
        fields = [
            "tipo_submissao",
            "setor_lotacao",
            "area_estrategica",
            "area_tematica",
            "objeto_tematico",
            "necessidade_a_ser_atendida",
            "acao_transversal",
            "unidades_organizacionais",
            "publico_alvo",
            "competencia_associada",
            "enfoque_desenvolvimento",
            "tipo_aprendizagem",
            "especificacao_tipo_aprendizagem",
            "modalidade",
            "titulo_acao",
            "termino_previsto",
            "quantidade_prevista_servidores",
            "carga_horaria_individual_prevista",
            "custo_tipo",
            "custo_individual_previsto",
            "precisa_prof_substituto",
            "precisa_afastamento",
            "licenca_capacitacao",
            "pode_ser_atendida_cfs",
        ]
        widgets = {
            "necessidade_a_ser_atendida": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, municipio=None, is_manager=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        self.is_manager = bool(is_manager)
        if municipio is not None:
            self.fields["setor_lotacao"].queryset = Setor.objects.filter(
                unidade__secretaria__municipio=municipio,
                ativo=True,
            ).order_by("nome")
        if not self.is_manager:
            self.fields["tipo_submissao"].initial = RhPdpNecessidade.TipoSubmissao.INDIVIDUAL
            self.fields["tipo_submissao"].disabled = True
