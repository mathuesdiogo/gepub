from __future__ import annotations

import json

from django import forms

from apps.almoxarifado.models import AlmoxarifadoCadastro
from apps.org.models import Secretaria, Unidade

from .models import Aluno, Turma
from .models_beneficios import (
    BeneficioCampanha,
    BeneficioCampanhaAluno,
    BeneficioEdital,
    BeneficioEditalCriterio,
    BeneficioEditalDocumento,
    BeneficioEditalInscricao,
    BeneficioEditalInscricaoDocumento,
    BeneficioEditalRecurso,
    BeneficioEntrega,
    BeneficioEntregaItem,
    BeneficioRecorrenciaCiclo,
    BeneficioRecorrenciaPlano,
    BeneficioTipo,
    BeneficioTipoItem,
)


class BeneficioTipoForm(forms.ModelForm):
    class Meta:
        model = BeneficioTipo
        fields = [
            "secretaria",
            "area",
            "nome",
            "categoria",
            "publico_alvo",
            "periodicidade",
            "elegibilidade_json",
            "exige_assinatura",
            "exige_foto",
            "exige_justificativa",
            "permite_segunda_via",
            "status",
            "observacao",
        ]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3}),
            "elegibilidade_json": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["secretaria"].queryset = Secretaria.objects.filter(municipio=municipio)

    def clean_elegibilidade_json(self):
        value = self.cleaned_data.get("elegibilidade_json")
        if value in ("", None):
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except Exception as exc:
                raise forms.ValidationError("JSON de elegibilidade inválido.") from exc
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Use um objeto JSON (ex.: {\"serie\": \"5A\"}).")
            return parsed
        return {}


class BeneficioTipoItemForm(forms.ModelForm):
    class Meta:
        model = BeneficioTipoItem
        fields = [
            "item_estoque",
            "item_manual",
            "quantidade",
            "unidade",
            "permite_substituicao",
            "observacao",
            "ordem",
            "ativo",
        ]

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if municipio is not None:
            self.fields["item_estoque"].queryset = AlmoxarifadoCadastro.objects.filter(
                municipio=municipio,
                status=AlmoxarifadoCadastro.Status.ATIVO,
            ).order_by("nome")


class BeneficioCampanhaForm(forms.ModelForm):
    class Meta:
        model = BeneficioCampanha
        fields = [
            "secretaria",
            "unidade",
            "area",
            "nome",
            "beneficio",
            "data_inicio",
            "data_fim",
            "quantidade_planejada",
            "origem",
            "centro_custo",
            "referencia",
            "status",
            "observacao",
        ]
        widgets = {
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["beneficio"].queryset = BeneficioTipo.objects.none()
        self.fields["secretaria"].queryset = Secretaria.objects.none()
        self.fields["unidade"].queryset = Unidade.objects.none()
        if municipio is not None:
            self.fields["beneficio"].queryset = BeneficioTipo.objects.filter(municipio=municipio).order_by("nome")
            self.fields["secretaria"].queryset = Secretaria.objects.filter(municipio=municipio, ativo=True).order_by("nome")
            self.fields["unidade"].queryset = Unidade.objects.filter(
                secretaria__municipio=municipio,
                tipo=Unidade.Tipo.EDUCACAO,
                ativo=True,
            ).order_by("nome")


class BeneficioCampanhaAlunoForm(forms.ModelForm):
    class Meta:
        model = BeneficioCampanhaAluno
        fields = ["aluno", "turma", "status", "justificativa"]
        widgets = {"justificativa": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, alunos_qs=None, turmas_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["aluno"].queryset = alunos_qs if alunos_qs is not None else Aluno.objects.none()
        self.fields["turma"].queryset = turmas_qs if turmas_qs is not None else Turma.objects.none()


class BeneficioEntregaForm(forms.ModelForm):
    class Meta:
        model = BeneficioEntrega
        fields = [
            "secretaria",
            "unidade",
            "area",
            "aluno",
            "campanha",
            "beneficio",
            "data_hora",
            "recebedor_tipo",
            "recebedor_nome",
            "recebedor_documento",
            "recebedor_telefone",
            "assinatura_confirmada",
            "foto_entrega",
            "comprovante_anexo",
            "local_entrega",
            "observacao",
            "justificativa",
            "segunda_via",
            "status",
        ]
        widgets = {
            "data_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "observacao": forms.Textarea(attrs={"rows": 3}),
            "justificativa": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, municipio=None, alunos_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["aluno"].queryset = alunos_qs if alunos_qs is not None else Aluno.objects.none()
        self.fields["campanha"].queryset = BeneficioCampanha.objects.none()
        self.fields["beneficio"].queryset = BeneficioTipo.objects.none()
        self.fields["secretaria"].queryset = Secretaria.objects.none()
        self.fields["unidade"].queryset = Unidade.objects.none()
        if municipio is not None:
            self.fields["campanha"].queryset = BeneficioCampanha.objects.filter(municipio=municipio).order_by("-id")
            self.fields["beneficio"].queryset = BeneficioTipo.objects.filter(municipio=municipio).order_by("nome")
            self.fields["secretaria"].queryset = Secretaria.objects.filter(municipio=municipio, ativo=True).order_by("nome")
            self.fields["unidade"].queryset = Unidade.objects.filter(
                secretaria__municipio=municipio,
                tipo=Unidade.Tipo.EDUCACAO,
                ativo=True,
            ).order_by("nome")


class BeneficioEntregaItemForm(forms.ModelForm):
    class Meta:
        model = BeneficioEntregaItem
        fields = [
            "composicao_item",
            "item_estoque",
            "item_nome",
            "quantidade_planejada",
            "quantidade_entregue",
            "unidade",
            "pendente",
            "substituido",
            "motivo_substituicao",
            "observacao",
        ]
        widgets = {
            "motivo_substituicao": forms.TextInput(attrs={"placeholder": "Obrigatório quando substituído"}),
        }

    def __init__(self, *args, entrega=None, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["composicao_item"].queryset = BeneficioTipoItem.objects.none()
        self.fields["item_estoque"].queryset = AlmoxarifadoCadastro.objects.none()
        if entrega is not None:
            self.fields["composicao_item"].queryset = BeneficioTipoItem.objects.filter(
                beneficio=entrega.beneficio, ativo=True
            ).order_by("ordem", "id")
        if municipio is not None:
            self.fields["item_estoque"].queryset = AlmoxarifadoCadastro.objects.filter(
                municipio=municipio,
                status=AlmoxarifadoCadastro.Status.ATIVO,
            ).order_by("nome")

    def clean(self):
        cleaned = super().clean()
        substituido = bool(cleaned.get("substituido"))
        motivo = (cleaned.get("motivo_substituicao") or "").strip()
        if substituido and not motivo:
            self.add_error("motivo_substituicao", "Informe o motivo da substituição.")
        return cleaned


class BeneficioEditalForm(forms.ModelForm):
    class Meta:
        model = BeneficioEdital
        fields = [
            "secretaria",
            "area",
            "titulo",
            "numero_ano",
            "beneficio",
            "publico_alvo",
            "abrangencia",
            "escolas",
            "inscricao_inicio",
            "inscricao_fim",
            "analise_inicio",
            "analise_fim",
            "resultado_preliminar_data",
            "prazo_recurso_data",
            "resultado_final_data",
            "texto",
            "anexo",
            "status",
        ]
        widgets = {
            "texto": forms.Textarea(attrs={"rows": 5}),
            "escolas": forms.SelectMultiple(attrs={"size": 8}),
        }

    def __init__(self, *args, municipio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["beneficio"].queryset = BeneficioTipo.objects.none()
        self.fields["secretaria"].queryset = Secretaria.objects.none()
        self.fields["escolas"].queryset = Unidade.objects.none()
        if municipio is not None:
            self.fields["beneficio"].queryset = BeneficioTipo.objects.filter(municipio=municipio).order_by("nome")
            self.fields["secretaria"].queryset = Secretaria.objects.filter(municipio=municipio, ativo=True).order_by("nome")
            self.fields["escolas"].queryset = Unidade.objects.filter(
                secretaria__municipio=municipio,
                tipo=Unidade.Tipo.EDUCACAO,
                ativo=True,
            ).order_by("nome")


class BeneficioEditalCriterioForm(forms.ModelForm):
    class Meta:
        model = BeneficioEditalCriterio
        fields = ["nome", "tipo", "fonte_dado", "regra", "peso", "exige_comprovacao", "ordem", "ativo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fonte_dado"].widget = forms.Select(
            choices=[
                ("cadastro", "Cadastro integrado (automático)"),
                ("declaracao", "Declaração do inscrito (marcação)"),
                ("documento", "Comprovação documental"),
                ("saude", "Dados de Saúde integrados"),
                ("manual", "Manual (avaliação posterior)"),
            ]
        )
        self.fields["fonte_dado"].help_text = (
            "Use 'cadastro' para cálculo automático por regra (ex.: aluno.ativo == true). "
            "Use 'declaracao' para critérios como Bolsa Família com marcação no ato da inscrição."
        )
        self.fields["regra"].help_text = (
            "Formato sugerido: caminho operador valor (ex.: aluno.ativo == true, "
            "matricula.situacao == ATIVA, saude.possui_cadastro == true)."
        )


class BeneficioEditalDocumentoForm(forms.ModelForm):
    class Meta:
        model = BeneficioEditalDocumento
        fields = ["nome", "obrigatorio", "formatos_aceitos", "prazo_entrega", "permite_declaracao", "ordem"]


class BeneficioEditalInscricaoForm(forms.ModelForm):
    usar_documentos_cadastro = forms.BooleanField(
        required=False,
        initial=True,
        label="Aproveitar documentos existentes do cadastro (Educação/Saúde)",
    )

    class Meta:
        model = BeneficioEditalInscricao
        fields = ["edital", "aluno", "escola", "turma", "justificativa"]
        widgets = {
            "justificativa": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, municipio=None, alunos_qs=None, edital=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.edital_obj = edital or self.initial.get("edital") or getattr(self.instance, "edital", None)
        self.criterios_meta: list[dict] = []
        self.documentos_meta: list[dict] = []

        self.fields["aluno"].queryset = alunos_qs if alunos_qs is not None else Aluno.objects.none()
        self.fields["edital"].queryset = BeneficioEdital.objects.none()
        self.fields["escola"].queryset = Unidade.objects.none()
        self.fields["turma"].queryset = Turma.objects.none()
        if municipio is not None:
            self.fields["edital"].queryset = BeneficioEdital.objects.filter(municipio=municipio).order_by("-id")
            self.fields["escola"].queryset = Unidade.objects.filter(
                secretaria__municipio=municipio,
                tipo=Unidade.Tipo.EDUCACAO,
                ativo=True,
            ).order_by("nome")
            self.fields["turma"].queryset = Turma.objects.filter(
                unidade__secretaria__municipio=municipio,
                unidade__tipo=Unidade.Tipo.EDUCACAO,
                ativo=True,
            ).order_by("-ano_letivo", "nome")
        if self.edital_obj:
            self.fields["edital"].initial = self.edital_obj
            self.fields["edital"].widget = forms.HiddenInput()

            for criterio in self.edital_obj.criterios.filter(ativo=True).order_by("ordem", "id"):
                check_name = f"criterio_{criterio.pk}_marcado"
                value_name = f"criterio_{criterio.pk}_valor"
                file_name = f"criterio_{criterio.pk}_arquivo"
                fonte = (criterio.fonte_dado or "").strip().lower()
                is_manual = fonte in {"declaracao", "documento", "manual", ""}
                has_valor = fonte in {"manual"} and bool((criterio.regra or "").strip())

                if is_manual:
                    self.fields[check_name] = forms.BooleanField(
                        required=False,
                        label=f"{criterio.nome} ({criterio.get_tipo_display()})",
                    )
                if has_valor:
                    self.fields[value_name] = forms.CharField(
                        required=False,
                        label=f"Valor informado para '{criterio.nome}'",
                    )
                if criterio.exige_comprovacao:
                    self.fields[file_name] = forms.FileField(
                        required=False,
                        label=f"Comprovação do critério: {criterio.nome}",
                    )
                self.criterios_meta.append(
                    {
                        "id": criterio.pk,
                        "obj": criterio,
                        "check_name": check_name if is_manual else "",
                        "value_name": value_name if has_valor else "",
                        "file_name": file_name if criterio.exige_comprovacao else "",
                        "is_manual": is_manual,
                    }
                )

            for requisito in self.edital_obj.documentos.order_by("ordem", "id"):
                file_name = f"documento_{requisito.pk}_arquivo"
                self.fields[file_name] = forms.FileField(
                    required=False,
                    label=f"Documento: {requisito.nome}" + (" (obrigatório)" if requisito.obrigatorio else ""),
                )
                self.documentos_meta.append(
                    {
                        "id": requisito.pk,
                        "obj": requisito,
                        "file_name": file_name,
                    }
                )

    def get_respostas_criterios(self) -> dict[int, dict]:
        data: dict[int, dict] = {}
        for meta in self.criterios_meta:
            cid = int(meta["id"])
            check_name = meta["check_name"]
            value_name = meta["value_name"]
            data[cid] = {
                "marcado": self.cleaned_data.get(check_name) if check_name else False,
                "valor": self.cleaned_data.get(value_name) if value_name else "",
            }
        return data

    def get_uploads_documentos(self) -> dict[int, object]:
        data: dict[int, object] = {}
        for meta in self.documentos_meta:
            rid = int(meta["id"])
            file_name = meta["file_name"]
            if file_name and self.cleaned_data.get(file_name):
                data[rid] = self.cleaned_data.get(file_name)
        return data

    def get_uploads_criterios(self) -> dict[int, object]:
        data: dict[int, object] = {}
        for meta in self.criterios_meta:
            cid = int(meta["id"])
            file_name = meta["file_name"]
            if file_name and self.cleaned_data.get(file_name):
                data[cid] = self.cleaned_data.get(file_name)
        return data


class BeneficioEditalInscricaoDocumentoForm(forms.ModelForm):
    class Meta:
        model = BeneficioEditalInscricaoDocumento
        fields = ["requisito", "descricao", "arquivo", "aprovado", "observacao"]
        widgets = {"observacao": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, inscricao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requisito"].queryset = BeneficioEditalDocumento.objects.none()
        if inscricao is not None:
            self.fields["requisito"].queryset = inscricao.edital.documentos.order_by("ordem", "id")


class BeneficioEditalRecursoForm(forms.ModelForm):
    class Meta:
        model = BeneficioEditalRecurso
        fields = ["texto", "arquivo", "status", "parecer"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 3}), "parecer": forms.Textarea(attrs={"rows": 3})}


class BeneficioEditalInscricaoAnaliseForm(forms.ModelForm):
    class Meta:
        model = BeneficioEditalInscricao
        fields = ["status", "pontuacao", "justificativa"]
        widgets = {
            "justificativa": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].help_text = "Defina o status final após a análise da secretaria."
        self.fields["pontuacao"].help_text = "Pode ajustar manualmente a pontuação quando necessário."


class BeneficioRecorrenciaPlanoForm(forms.ModelForm):
    class Meta:
        model = BeneficioRecorrenciaPlano
        fields = [
            "secretaria",
            "unidade",
            "area",
            "beneficio",
            "aluno",
            "inscricao",
            "data_inicio",
            "data_fim",
            "numero_ciclos",
            "frequencia",
            "intervalo_dias",
            "geracao_automatica",
            "permite_segunda_via",
            "status",
            "observacao",
        ]
        widgets = {"observacao": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, municipio=None, alunos_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["aluno"].queryset = alunos_qs if alunos_qs is not None else Aluno.objects.none()
        self.fields["beneficio"].queryset = BeneficioTipo.objects.none()
        self.fields["inscricao"].queryset = BeneficioEditalInscricao.objects.none()
        self.fields["secretaria"].queryset = Secretaria.objects.none()
        self.fields["unidade"].queryset = Unidade.objects.none()
        if municipio is not None:
            self.fields["beneficio"].queryset = BeneficioTipo.objects.filter(municipio=municipio).order_by("nome")
            self.fields["inscricao"].queryset = BeneficioEditalInscricao.objects.filter(
                edital__municipio=municipio
            ).order_by("-id")
            self.fields["secretaria"].queryset = Secretaria.objects.filter(municipio=municipio, ativo=True).order_by("nome")
            self.fields["unidade"].queryset = Unidade.objects.filter(
                secretaria__municipio=municipio,
                tipo=Unidade.Tipo.EDUCACAO,
                ativo=True,
            ).order_by("nome")


class BeneficioRecorrenciaCicloForm(forms.ModelForm):
    class Meta:
        model = BeneficioRecorrenciaCiclo
        fields = ["numero", "data_prevista", "status", "motivo"]
        widgets = {"motivo": forms.Textarea(attrs={"rows": 2})}
