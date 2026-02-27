from django import forms
from django.urls import reverse
from apps.educacao.models import Aluno
from apps.org.models import Unidade
from .models import (
    AlergiaSaude,
    AgendamentoSaude,
    AnexoAtendimentoSaude,
    AtendimentoSaude,
    BloqueioAgendaSaude,
    CheckInSaude,
    CidSaude,
    DocumentoClinicoSaude,
    DispensacaoSaude,
    EncaminhamentoSaude,
    EvolucaoClinicaSaude,
    ExameColetaSaude,
    ExamePedidoSaude,
    ExameResultadoSaude,
    EspecialidadeSaude,
    FilaEsperaSaude,
    GradeAgendaSaude,
    InternacaoRegistroSaude,
    InternacaoSaude,
    MedicamentoUsoContinuoSaude,
    PacienteSaude,
    ProcedimentoSaude,
    ProgramaSaude,
    PrescricaoItemSaude,
    PrescricaoSaude,
    ProblemaAtivoSaude,
    ProfissionalSaude,
    SalaSaude,
    TriagemSaude,
    VacinacaoSaude,
)


class UnidadeSaudeForm(forms.ModelForm):
    """
    Form de Unidade (org.Unidade) usado em views_unidades.py.
    IMPORTANTe: views_unidades força obj.tipo = Unidade.Tipo.SAUDE no save,
    então aqui não expomos o campo 'tipo' no formulário.
    """
    class Meta:
        model = Unidade
        fields = [
            "nome",
            "codigo_inep",
            "cnpj",
            "telefone",
            "email",
            "endereco",
            "ativo",
            "secretaria",
        ]


class ProfissionalSaudeForm(forms.ModelForm):
    class Meta:
        model = ProfissionalSaude
        fields = [
            "nome",
            "unidade",
            "especialidade",
            "cargo",
            "conselho_numero",
            "cbo",
            "carga_horaria_semanal",
            "cpf",
            "telefone",
            "email",
            "ativo",
        ]


class EspecialidadeSaudeForm(forms.ModelForm):
    class Meta:
        model = EspecialidadeSaude
        fields = ["nome", "cbo", "ativo"]


class SalaSaudeForm(forms.ModelForm):
    class Meta:
        model = SalaSaude
        fields = ["unidade", "setor", "nome", "capacidade", "ativo"]


class AtendimentoSaudeForm(forms.ModelForm):
    """
    Versão definitiva (GEPUB) usando autocomplete institucional (modo fill do autocomplete.js),
    sem carregar todos os alunos no <select>.

    Pré-requisitos:
      - import reverse no topo do arquivo: from django.urls import reverse
      - import Aluno no topo do arquivo: from apps.educacao.models import Aluno
      - import AtendimentoSaude no topo do arquivo: from .models import AtendimentoSaude
    """

    aluno_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    aluno_busca = forms.CharField(
        required=False,
        label="Aluno (Educação)",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Digite o nome do aluno…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = AtendimentoSaude
        fields = [
            "aluno_id",
            "aluno_busca",
            "unidade",
            "profissional",
            "data",
            "tipo",
            "cid",
            "observacoes",
            "paciente_nome",
            "paciente_cpf",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        profissionais_qs = kwargs.pop("profissionais_qs", None)
        super().__init__(*args, **kwargs)

        # Autocomplete institucional (seu autocomplete.js suporta MODE=fill)
        self.fields["aluno_busca"].widget.attrs.update(
            {
                "data-autocomplete-url": reverse("educacao:api_alunos_suggest"),
                "data-autocomplete-mode": "fill",
                "data-autocomplete-fill-target": "#id_aluno_id",
                "data-autocomplete-min": "2",
                "data-autocomplete-max": "5",
            }
        )

        if unidades_qs is not None and "unidade" in self.fields:
            self.fields["unidade"].queryset = unidades_qs

        if profissionais_qs is not None and "profissional" in self.fields:
            self.fields["profissional"].queryset = profissionais_qs

        # Compatibilidade: paciente_* pode ficar em branco se aluno vier preenchido
        if "paciente_nome" in self.fields:
            self.fields["paciente_nome"].required = False
        if "paciente_cpf" in self.fields:
            self.fields["paciente_cpf"].required = False

        # Edição: pré-popula
        if getattr(self.instance, "aluno_id", None):
            self.initial["aluno_id"] = self.instance.aluno_id
            self.initial["aluno_busca"] = getattr(self.instance.aluno, "nome", "")

    def clean(self):
        cleaned = super().clean()

        aluno_id = cleaned.get("aluno_id")
        aluno_busca = (cleaned.get("aluno_busca") or "").strip()

        aluno = None
        if aluno_id:
            aluno = Aluno.objects.filter(id=aluno_id).first()
            if not aluno:
                self.add_error("aluno_busca", "Aluno inválido.")
        else:
            # Se digitou e não selecionou, força seleção correta
            if aluno_busca:
                self.add_error("aluno_busca", "Selecione um aluno nas sugestões.")

        cleaned["aluno_obj"] = aluno

        # Se escolheu aluno, pode preencher paciente_nome automaticamente (compatibilidade)
        if aluno and not cleaned.get("paciente_nome"):
            cleaned["paciente_nome"] = aluno.nome

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)

        aluno = self.cleaned_data.get("aluno_obj")
        obj.aluno = aluno  # pode ser None

        if commit:
            obj.save()
        return obj


class AgendamentoSaudeForm(forms.ModelForm):
    aluno_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    aluno_busca = forms.CharField(
        required=False,
        label="Aluno (Educação)",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Digite o nome do aluno…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = AgendamentoSaude
        fields = [
            "aluno_id",
            "aluno_busca",
            "unidade",
            "profissional",
            "especialidade",
            "sala",
            "inicio",
            "fim",
            "tipo",
            "status",
            "motivo",
            "paciente_nome",
            "paciente_cpf",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        profissionais_qs = kwargs.pop("profissionais_qs", None)
        super().__init__(*args, **kwargs)

        self.fields["aluno_busca"].widget.attrs.update(
            {
                "data-autocomplete-url": reverse("educacao:api_alunos_suggest"),
                "data-autocomplete-mode": "fill",
                "data-autocomplete-fill-target": "#id_aluno_id",
                "data-autocomplete-min": "2",
                "data-autocomplete-max": "5",
            }
        )

        if unidades_qs is not None and "unidade" in self.fields:
            self.fields["unidade"].queryset = unidades_qs

        if profissionais_qs is not None and "profissional" in self.fields:
            self.fields["profissional"].queryset = profissionais_qs

        if "paciente_nome" in self.fields:
            self.fields["paciente_nome"].required = False
        if "paciente_cpf" in self.fields:
            self.fields["paciente_cpf"].required = False

        if getattr(self.instance, "aluno_id", None):
            self.initial["aluno_id"] = self.instance.aluno_id
            self.initial["aluno_busca"] = getattr(self.instance.aluno, "nome", "")

    def clean(self):
        cleaned = super().clean()

        aluno_id = cleaned.get("aluno_id")
        aluno_busca = (cleaned.get("aluno_busca") or "").strip()
        inicio = cleaned.get("inicio")
        fim = cleaned.get("fim")

        aluno = None
        if aluno_id:
            aluno = Aluno.objects.filter(id=aluno_id).first()
            if not aluno:
                self.add_error("aluno_busca", "Aluno inválido.")
        elif aluno_busca:
            self.add_error("aluno_busca", "Selecione um aluno nas sugestões.")

        if inicio and fim and fim <= inicio:
            self.add_error("fim", "Data/hora final deve ser maior que a inicial.")

        cleaned["aluno_obj"] = aluno

        if aluno and not cleaned.get("paciente_nome"):
            cleaned["paciente_nome"] = aluno.nome

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.aluno = self.cleaned_data.get("aluno_obj")
        if commit:
            obj.save()
        return obj


class GradeAgendaSaudeForm(forms.ModelForm):
    class Meta:
        model = GradeAgendaSaude
        fields = [
            "unidade",
            "profissional",
            "sala",
            "especialidade",
            "dia_semana",
            "inicio",
            "fim",
            "duracao_minutos",
            "intervalo_minutos",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        profissionais_qs = kwargs.pop("profissionais_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["unidade"].queryset = unidades_qs
        if profissionais_qs is not None:
            self.fields["profissional"].queryset = profissionais_qs

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("inicio")
        fim = cleaned.get("fim")
        if inicio and fim and fim <= inicio:
            self.add_error("fim", "Horário final deve ser maior que o inicial.")
        return cleaned


class BloqueioAgendaSaudeForm(forms.ModelForm):
    class Meta:
        model = BloqueioAgendaSaude
        fields = [
            "unidade",
            "profissional",
            "sala",
            "inicio",
            "fim",
            "motivo",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        profissionais_qs = kwargs.pop("profissionais_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["unidade"].queryset = unidades_qs
        if profissionais_qs is not None:
            self.fields["profissional"].queryset = profissionais_qs

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("inicio")
        fim = cleaned.get("fim")
        if inicio and fim and fim <= inicio:
            self.add_error("fim", "Data/hora final deve ser maior que a inicial.")
        return cleaned


class FilaEsperaSaudeForm(forms.ModelForm):
    class Meta:
        model = FilaEsperaSaude
        fields = [
            "unidade",
            "especialidade",
            "aluno",
            "paciente_nome",
            "paciente_contato",
            "prioridade",
            "status",
            "observacoes",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["unidade"].queryset = unidades_qs


class ProcedimentoSaudeForm(forms.ModelForm):
    class Meta:
        model = ProcedimentoSaude
        fields = [
            "atendimento",
            "tipo",
            "descricao",
            "materiais",
            "intercorrencias",
            "realizado_em",
        ]


class VacinacaoSaudeForm(forms.ModelForm):
    class Meta:
        model = VacinacaoSaude
        fields = [
            "atendimento",
            "vacina",
            "dose",
            "lote",
            "fabricante",
            "unidade_aplicadora",
            "aplicador",
            "data_aplicacao",
            "reacoes",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        profissionais_qs = kwargs.pop("profissionais_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["unidade_aplicadora"].queryset = unidades_qs
        if profissionais_qs is not None:
            self.fields["aplicador"].queryset = profissionais_qs


class EncaminhamentoSaudeForm(forms.ModelForm):
    class Meta:
        model = EncaminhamentoSaude
        fields = [
            "atendimento",
            "unidade_origem",
            "unidade_destino",
            "especialidade_destino",
            "prioridade",
            "status",
            "justificativa",
            "observacoes_regulacao",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["unidade_origem"].queryset = unidades_qs
            self.fields["unidade_destino"].queryset = unidades_qs


class CidSaudeForm(forms.ModelForm):
    class Meta:
        model = CidSaude
        fields = ["codigo", "descricao", "ativo"]


class ProgramaSaudeForm(forms.ModelForm):
    class Meta:
        model = ProgramaSaude
        fields = ["nome", "tipo", "ativo"]


class PacienteSaudeForm(forms.ModelForm):
    class Meta:
        model = PacienteSaude
        fields = [
            "unidade_referencia",
            "aluno",
            "programa",
            "nome",
            "data_nascimento",
            "sexo",
            "cartao_sus",
            "cpf",
            "telefone",
            "email",
            "endereco",
            "responsavel_nome",
            "responsavel_telefone",
            "vulnerabilidades",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["unidade_referencia"].queryset = unidades_qs


class CheckInSaudeForm(forms.ModelForm):
    class Meta:
        model = CheckInSaude
        fields = [
            "unidade",
            "agendamento",
            "atendimento",
            "paciente",
            "paciente_nome",
            "motivo_visita",
            "queixa_principal",
            "classificacao_risco",
            "pa_sistolica",
            "pa_diastolica",
            "frequencia_cardiaca",
            "temperatura",
            "saturacao_o2",
            "status",
            "chegada_em",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["unidade"].queryset = unidades_qs
            self.fields["paciente"].queryset = PacienteSaude.objects.filter(
                unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)
            ).order_by("nome")
            self.fields["atendimento"].queryset = AtendimentoSaude.objects.filter(
                unidade_id__in=unidades_qs.values_list("id", flat=True)
            ).order_by("-data", "-id")
            self.fields["agendamento"].queryset = AgendamentoSaude.objects.filter(
                unidade_id__in=unidades_qs.values_list("id", flat=True)
            ).order_by("-inicio", "-id")


class MedicamentoUsoContinuoSaudeForm(forms.ModelForm):
    class Meta:
        model = MedicamentoUsoContinuoSaude
        fields = [
            "paciente",
            "medicamento",
            "dose",
            "via",
            "frequencia",
            "inicio",
            "fim",
            "observacoes",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["paciente"].queryset = PacienteSaude.objects.filter(
                unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)
            ).order_by("nome")


class DispensacaoSaudeForm(forms.ModelForm):
    class Meta:
        model = DispensacaoSaude
        fields = [
            "unidade",
            "atendimento",
            "paciente",
            "medicamento",
            "quantidade",
            "unidade_medida",
            "lote",
            "validade",
            "orientacoes",
            "dispensado_em",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            scoped_ids = unidades_qs.values_list("id", flat=True)
            self.fields["unidade"].queryset = unidades_qs
            self.fields["paciente"].queryset = PacienteSaude.objects.filter(unidade_referencia_id__in=scoped_ids).order_by("nome")
            self.fields["atendimento"].queryset = AtendimentoSaude.objects.filter(unidade_id__in=scoped_ids).order_by("-data", "-id")


class ExameColetaSaudeForm(forms.ModelForm):
    class Meta:
        model = ExameColetaSaude
        fields = [
            "pedido",
            "status",
            "data_coleta",
            "local_coleta",
            "encaminhado_para",
            "observacoes",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["pedido"].queryset = ExamePedidoSaude.objects.filter(
                atendimento__unidade_id__in=unidades_qs.values_list("id", flat=True)
            ).order_by("-criado_em", "-id")


class InternacaoSaudeForm(forms.ModelForm):
    class Meta:
        model = InternacaoSaude
        fields = [
            "unidade",
            "paciente",
            "profissional_responsavel",
            "tipo",
            "status",
            "data_admissao",
            "data_alta",
            "leito",
            "motivo",
            "resumo_alta",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        profissionais_qs = kwargs.pop("profissionais_qs", None)
        super().__init__(*args, **kwargs)
        if unidades_qs is not None:
            self.fields["unidade"].queryset = unidades_qs
            self.fields["paciente"].queryset = PacienteSaude.objects.filter(
                unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)
            ).order_by("nome")
        if profissionais_qs is not None:
            self.fields["profissional_responsavel"].queryset = profissionais_qs


class InternacaoRegistroSaudeForm(forms.ModelForm):
    class Meta:
        model = InternacaoRegistroSaude
        fields = ["tipo", "texto"]


class DocumentoClinicoSaudeForm(forms.ModelForm):
    class Meta:
        model = DocumentoClinicoSaude
        fields = ["tipo", "titulo", "conteudo"]


class TriagemSaudeForm(forms.ModelForm):
    class Meta:
        model = TriagemSaude
        fields = [
            "pa_sistolica",
            "pa_diastolica",
            "frequencia_cardiaca",
            "temperatura",
            "saturacao_o2",
            "peso_kg",
            "altura_cm",
            "classificacao_risco",
            "observacoes",
        ]


class EvolucaoClinicaSaudeForm(forms.ModelForm):
    class Meta:
        model = EvolucaoClinicaSaude
        fields = ["tipo", "texto"]


class ProblemaAtivoSaudeForm(forms.ModelForm):
    class Meta:
        model = ProblemaAtivoSaude
        fields = ["descricao", "cid", "status", "observacoes"]


class AlergiaSaudeForm(forms.ModelForm):
    class Meta:
        model = AlergiaSaude
        fields = ["agente", "reacao", "gravidade", "ativo"]


class AnexoAtendimentoSaudeForm(forms.ModelForm):
    class Meta:
        model = AnexoAtendimentoSaude
        fields = ["titulo", "arquivo"]


class PrescricaoSaudeForm(forms.ModelForm):
    class Meta:
        model = PrescricaoSaude
        fields = ["observacoes"]


class PrescricaoItemSaudeForm(forms.ModelForm):
    class Meta:
        model = PrescricaoItemSaude
        fields = ["medicamento", "dose", "via", "frequencia", "duracao", "orientacoes"]


class ExamePedidoSaudeForm(forms.ModelForm):
    class Meta:
        model = ExamePedidoSaude
        fields = ["nome_exame", "prioridade", "justificativa", "hipotese_diagnostica"]


class ExameResultadoSaudeForm(forms.ModelForm):
    class Meta:
        model = ExameResultadoSaude
        fields = ["texto_resultado", "arquivo", "data_resultado"]
