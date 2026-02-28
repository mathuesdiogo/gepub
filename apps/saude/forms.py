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


def _configure_autocomplete_field(field, *, url: str, fill_target: str, min_chars: int = 2, max_items: int = 10):
    field.widget.attrs.update(
        {
            "autocomplete": "off",
            "data-autocomplete-url": url,
            "data-autocomplete-mode": "fill",
            "data-autocomplete-fill-target": fill_target,
            "data-autocomplete-min": str(min_chars),
            "data-autocomplete-max": str(max_items),
        }
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
        _configure_autocomplete_field(
            self.fields["aluno_busca"],
            url=reverse("saude:api_alunos_suggest"),
            fill_target="#id_aluno_id",
            min_chars=2,
            max_items=8,
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

        _configure_autocomplete_field(
            self.fields["aluno_busca"],
            url=reverse("saude:api_alunos_suggest"),
            fill_target="#id_aluno_id",
            min_chars=2,
            max_items=8,
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
    aluno_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    aluno_busca = forms.CharField(
        required=False,
        label="Aluno (Educação)",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Digite nome, CPF ou NIS do aluno…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = FilaEsperaSaude
        fields = [
            "unidade",
            "especialidade",
            "aluno_id",
            "aluno_busca",
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

        _configure_autocomplete_field(
            self.fields["aluno_busca"],
            url=reverse("saude:api_alunos_suggest"),
            fill_target="#id_aluno_id",
            min_chars=2,
            max_items=8,
        )

        if getattr(self.instance, "aluno_id", None):
            self.initial["aluno_id"] = self.instance.aluno_id
            self.initial["aluno_busca"] = getattr(self.instance.aluno, "nome", "")

    def clean(self):
        cleaned = super().clean()

        aluno_id = cleaned.get("aluno_id")
        aluno_busca = (cleaned.get("aluno_busca") or "").strip()

        aluno = None
        if aluno_id:
            aluno = Aluno.objects.filter(pk=aluno_id).first()
            if not aluno:
                self.add_error("aluno_busca", "Aluno inválido.")
        elif aluno_busca:
            self.add_error("aluno_busca", "Selecione um aluno válido nas sugestões.")

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


class ProcedimentoSaudeForm(forms.ModelForm):
    atendimento_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    atendimento_busca = forms.CharField(
        required=False,
        label="Atendimento",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar atendimento por paciente, CPF ou número…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = ProcedimentoSaude
        fields = [
            "atendimento_id",
            "atendimento_busca",
            "tipo",
            "descricao",
            "materiais",
            "intercorrencias",
            "realizado_em",
        ]

    def __init__(self, *args, **kwargs):
        unidades_qs = kwargs.pop("unidades_qs", None)
        super().__init__(*args, **kwargs)

        self._atendimentos_qs = AtendimentoSaude.objects.all()
        if unidades_qs is not None:
            self._atendimentos_qs = self._atendimentos_qs.filter(
                unidade_id__in=unidades_qs.values_list("id", flat=True)
            )

        _configure_autocomplete_field(
            self.fields["atendimento_busca"],
            url=reverse("saude:api_atendimentos_suggest"),
            fill_target="#id_atendimento_id",
            min_chars=2,
            max_items=10,
        )

        if getattr(self.instance, "atendimento_id", None):
            self.initial["atendimento_id"] = self.instance.atendimento_id
            self.initial["atendimento_busca"] = f"#{self.instance.atendimento_id} • {self.instance.atendimento.paciente_nome}"

    def clean(self):
        cleaned = super().clean()

        atendimento_id = cleaned.get("atendimento_id")
        atendimento_busca = (cleaned.get("atendimento_busca") or "").strip()

        atendimento = None
        if atendimento_id:
            atendimento = self._atendimentos_qs.filter(pk=atendimento_id).first()
            if not atendimento:
                self.add_error("atendimento_busca", "Atendimento inválido.")
        elif atendimento_busca:
            self.add_error("atendimento_busca", "Selecione um atendimento válido nas sugestões.")
        else:
            self.add_error("atendimento_busca", "Selecione um atendimento para continuar.")

        cleaned["atendimento_obj"] = atendimento
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.atendimento = self.cleaned_data.get("atendimento_obj")
        if commit:
            obj.save()
        return obj


class VacinacaoSaudeForm(forms.ModelForm):
    atendimento_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    atendimento_busca = forms.CharField(
        required=False,
        label="Atendimento",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar atendimento por paciente, CPF ou número…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = VacinacaoSaude
        fields = [
            "atendimento_id",
            "atendimento_busca",
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

        self._atendimentos_qs = AtendimentoSaude.objects.all()
        if unidades_qs is not None:
            self.fields["unidade_aplicadora"].queryset = unidades_qs
            self._atendimentos_qs = self._atendimentos_qs.filter(
                unidade_id__in=unidades_qs.values_list("id", flat=True)
            )
        if profissionais_qs is not None:
            self.fields["aplicador"].queryset = profissionais_qs

        _configure_autocomplete_field(
            self.fields["atendimento_busca"],
            url=reverse("saude:api_atendimentos_suggest"),
            fill_target="#id_atendimento_id",
            min_chars=2,
            max_items=10,
        )

        if getattr(self.instance, "atendimento_id", None):
            self.initial["atendimento_id"] = self.instance.atendimento_id
            self.initial["atendimento_busca"] = f"#{self.instance.atendimento_id} • {self.instance.atendimento.paciente_nome}"

    def clean(self):
        cleaned = super().clean()

        atendimento_id = cleaned.get("atendimento_id")
        atendimento_busca = (cleaned.get("atendimento_busca") or "").strip()

        atendimento = None
        if atendimento_id:
            atendimento = self._atendimentos_qs.filter(pk=atendimento_id).first()
            if not atendimento:
                self.add_error("atendimento_busca", "Atendimento inválido.")
        elif atendimento_busca:
            self.add_error("atendimento_busca", "Selecione um atendimento válido nas sugestões.")
        else:
            self.add_error("atendimento_busca", "Selecione um atendimento para continuar.")

        cleaned["atendimento_obj"] = atendimento
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.atendimento = self.cleaned_data.get("atendimento_obj")
        if commit:
            obj.save()
        return obj


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
    aluno_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    aluno_busca = forms.CharField(
        required=False,
        label="Aluno (Educação)",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Digite nome, CPF ou NIS do aluno…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = PacienteSaude
        fields = [
            "unidade_referencia",
            "aluno_id",
            "aluno_busca",
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

        _configure_autocomplete_field(
            self.fields["aluno_busca"],
            url=reverse("saude:api_alunos_suggest"),
            fill_target="#id_aluno_id",
            min_chars=2,
            max_items=8,
        )

        if getattr(self.instance, "aluno_id", None):
            self.initial["aluno_id"] = self.instance.aluno_id
            self.initial["aluno_busca"] = getattr(self.instance.aluno, "nome", "")

    def clean(self):
        cleaned = super().clean()

        aluno_id = cleaned.get("aluno_id")
        aluno_busca = (cleaned.get("aluno_busca") or "").strip()

        aluno = None
        if aluno_id:
            aluno = Aluno.objects.filter(pk=aluno_id).first()
            if not aluno:
                self.add_error("aluno_busca", "Aluno inválido.")
        elif aluno_busca:
            self.add_error("aluno_busca", "Selecione um aluno válido nas sugestões.")

        cleaned["aluno_obj"] = aluno

        if aluno and not cleaned.get("nome"):
            cleaned["nome"] = aluno.nome

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.aluno = self.cleaned_data.get("aluno_obj")
        if commit:
            obj.save()
        return obj


class CheckInSaudeForm(forms.ModelForm):
    agendamento_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    agendamento_busca = forms.CharField(
        required=False,
        label="Agendamento",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar agendamento por paciente, CPF ou número…",
                "autocomplete": "off",
            }
        ),
    )
    atendimento_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    atendimento_busca = forms.CharField(
        required=False,
        label="Atendimento",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar atendimento por paciente, CPF ou número…",
                "autocomplete": "off",
            }
        ),
    )
    paciente_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    paciente_busca = forms.CharField(
        required=False,
        label="Paciente",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar paciente por nome, CPF ou Cartão SUS…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = CheckInSaude
        fields = [
            "unidade",
            "agendamento_id",
            "agendamento_busca",
            "atendimento_id",
            "atendimento_busca",
            "paciente_id",
            "paciente_busca",
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
        self._pacientes_qs = PacienteSaude.objects.none()
        self._atendimentos_qs = AtendimentoSaude.objects.none()
        self._agendamentos_qs = AgendamentoSaude.objects.none()

        if unidades_qs is not None:
            scoped_ids = unidades_qs.values_list("id", flat=True)
            self.fields["unidade"].queryset = unidades_qs
            self._pacientes_qs = PacienteSaude.objects.filter(
                unidade_referencia_id__in=scoped_ids
            ).order_by("nome")
            self._atendimentos_qs = AtendimentoSaude.objects.filter(
                unidade_id__in=scoped_ids
            ).order_by("-data", "-id")
            self._agendamentos_qs = AgendamentoSaude.objects.filter(
                unidade_id__in=scoped_ids
            ).order_by("-inicio", "-id")

        _configure_autocomplete_field(
            self.fields["paciente_busca"],
            url=reverse("saude:api_pacientes_suggest"),
            fill_target="#id_paciente_id",
            min_chars=2,
            max_items=10,
        )
        _configure_autocomplete_field(
            self.fields["atendimento_busca"],
            url=reverse("saude:api_atendimentos_suggest"),
            fill_target="#id_atendimento_id",
            min_chars=2,
            max_items=10,
        )
        _configure_autocomplete_field(
            self.fields["agendamento_busca"],
            url=reverse("saude:api_agendamentos_suggest"),
            fill_target="#id_agendamento_id",
            min_chars=2,
            max_items=10,
        )

        if getattr(self.instance, "paciente_id", None):
            self.initial["paciente_id"] = self.instance.paciente_id
            self.initial["paciente_busca"] = getattr(self.instance.paciente, "nome", "")
        if getattr(self.instance, "atendimento_id", None):
            self.initial["atendimento_id"] = self.instance.atendimento_id
            self.initial["atendimento_busca"] = f"#{self.instance.atendimento_id} • {self.instance.atendimento.paciente_nome}"
        if getattr(self.instance, "agendamento_id", None):
            self.initial["agendamento_id"] = self.instance.agendamento_id
            self.initial["agendamento_busca"] = f"#{self.instance.agendamento_id} • {self.instance.agendamento.paciente_nome}"

    def clean(self):
        cleaned = super().clean()

        paciente_id = cleaned.get("paciente_id")
        paciente_busca = (cleaned.get("paciente_busca") or "").strip()
        atendimento_id = cleaned.get("atendimento_id")
        atendimento_busca = (cleaned.get("atendimento_busca") or "").strip()
        agendamento_id = cleaned.get("agendamento_id")
        agendamento_busca = (cleaned.get("agendamento_busca") or "").strip()

        paciente = None
        atendimento = None
        agendamento = None

        if paciente_id:
            paciente = self._pacientes_qs.filter(pk=paciente_id).first()
            if not paciente:
                self.add_error("paciente_busca", "Paciente inválido.")
        elif paciente_busca:
            self.add_error("paciente_busca", "Selecione um paciente válido nas sugestões.")

        if atendimento_id:
            atendimento = self._atendimentos_qs.filter(pk=atendimento_id).first()
            if not atendimento:
                self.add_error("atendimento_busca", "Atendimento inválido.")
        elif atendimento_busca:
            self.add_error("atendimento_busca", "Selecione um atendimento válido nas sugestões.")

        if agendamento_id:
            agendamento = self._agendamentos_qs.filter(pk=agendamento_id).first()
            if not agendamento:
                self.add_error("agendamento_busca", "Agendamento inválido.")
        elif agendamento_busca:
            self.add_error("agendamento_busca", "Selecione um agendamento válido nas sugestões.")

        cleaned["paciente_obj"] = paciente
        cleaned["atendimento_obj"] = atendimento
        cleaned["agendamento_obj"] = agendamento

        if paciente and not cleaned.get("paciente_nome"):
            cleaned["paciente_nome"] = paciente.nome
        elif atendimento and not cleaned.get("paciente_nome"):
            cleaned["paciente_nome"] = atendimento.paciente_nome
        elif agendamento and not cleaned.get("paciente_nome"):
            cleaned["paciente_nome"] = agendamento.paciente_nome

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.paciente = self.cleaned_data.get("paciente_obj")
        obj.atendimento = self.cleaned_data.get("atendimento_obj")
        obj.agendamento = self.cleaned_data.get("agendamento_obj")
        if commit:
            obj.save()
        return obj


class MedicamentoUsoContinuoSaudeForm(forms.ModelForm):
    paciente_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    paciente_busca = forms.CharField(
        required=False,
        label="Paciente",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar paciente por nome, CPF ou Cartão SUS…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = MedicamentoUsoContinuoSaude
        fields = [
            "paciente_id",
            "paciente_busca",
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
        self._pacientes_qs = PacienteSaude.objects.none()
        if unidades_qs is not None:
            self._pacientes_qs = PacienteSaude.objects.filter(
                unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)
            ).order_by("nome")

        _configure_autocomplete_field(
            self.fields["paciente_busca"],
            url=reverse("saude:api_pacientes_suggest"),
            fill_target="#id_paciente_id",
            min_chars=2,
            max_items=10,
        )

        if getattr(self.instance, "paciente_id", None):
            self.initial["paciente_id"] = self.instance.paciente_id
            self.initial["paciente_busca"] = getattr(self.instance.paciente, "nome", "")

    def clean(self):
        cleaned = super().clean()

        paciente_id = cleaned.get("paciente_id")
        paciente_busca = (cleaned.get("paciente_busca") or "").strip()

        paciente = None
        if paciente_id:
            paciente = self._pacientes_qs.filter(pk=paciente_id).first()
            if not paciente:
                self.add_error("paciente_busca", "Paciente inválido.")
        elif paciente_busca:
            self.add_error("paciente_busca", "Selecione um paciente válido nas sugestões.")
        else:
            self.add_error("paciente_busca", "Selecione um paciente para continuar.")

        cleaned["paciente_obj"] = paciente
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.paciente = self.cleaned_data.get("paciente_obj")
        if commit:
            obj.save()
        return obj


class DispensacaoSaudeForm(forms.ModelForm):
    atendimento_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    atendimento_busca = forms.CharField(
        required=False,
        label="Atendimento",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar atendimento por paciente, CPF ou número…",
                "autocomplete": "off",
            }
        ),
    )
    paciente_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    paciente_busca = forms.CharField(
        required=False,
        label="Paciente",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar paciente por nome, CPF ou Cartão SUS…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = DispensacaoSaude
        fields = [
            "unidade",
            "atendimento_id",
            "atendimento_busca",
            "paciente_id",
            "paciente_busca",
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
        self._pacientes_qs = PacienteSaude.objects.none()
        self._atendimentos_qs = AtendimentoSaude.objects.none()
        if unidades_qs is not None:
            scoped_ids = unidades_qs.values_list("id", flat=True)
            self.fields["unidade"].queryset = unidades_qs
            self._pacientes_qs = PacienteSaude.objects.filter(
                unidade_referencia_id__in=scoped_ids
            ).order_by("nome")
            self._atendimentos_qs = AtendimentoSaude.objects.filter(
                unidade_id__in=scoped_ids
            ).order_by("-data", "-id")

        _configure_autocomplete_field(
            self.fields["paciente_busca"],
            url=reverse("saude:api_pacientes_suggest"),
            fill_target="#id_paciente_id",
            min_chars=2,
            max_items=10,
        )
        _configure_autocomplete_field(
            self.fields["atendimento_busca"],
            url=reverse("saude:api_atendimentos_suggest"),
            fill_target="#id_atendimento_id",
            min_chars=2,
            max_items=10,
        )

        if getattr(self.instance, "paciente_id", None):
            self.initial["paciente_id"] = self.instance.paciente_id
            self.initial["paciente_busca"] = getattr(self.instance.paciente, "nome", "")
        if getattr(self.instance, "atendimento_id", None):
            self.initial["atendimento_id"] = self.instance.atendimento_id
            self.initial["atendimento_busca"] = f"#{self.instance.atendimento_id} • {self.instance.atendimento.paciente_nome}"

    def clean(self):
        cleaned = super().clean()

        paciente_id = cleaned.get("paciente_id")
        paciente_busca = (cleaned.get("paciente_busca") or "").strip()
        atendimento_id = cleaned.get("atendimento_id")
        atendimento_busca = (cleaned.get("atendimento_busca") or "").strip()

        paciente = None
        atendimento = None

        if paciente_id:
            paciente = self._pacientes_qs.filter(pk=paciente_id).first()
            if not paciente:
                self.add_error("paciente_busca", "Paciente inválido.")
        elif paciente_busca:
            self.add_error("paciente_busca", "Selecione um paciente válido nas sugestões.")
        else:
            self.add_error("paciente_busca", "Selecione um paciente para continuar.")

        if atendimento_id:
            atendimento = self._atendimentos_qs.filter(pk=atendimento_id).first()
            if not atendimento:
                self.add_error("atendimento_busca", "Atendimento inválido.")
        elif atendimento_busca:
            self.add_error("atendimento_busca", "Selecione um atendimento válido nas sugestões.")

        cleaned["paciente_obj"] = paciente
        cleaned["atendimento_obj"] = atendimento
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.paciente = self.cleaned_data.get("paciente_obj")
        obj.atendimento = self.cleaned_data.get("atendimento_obj")
        if commit:
            obj.save()
        return obj


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
    paciente_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    paciente_busca = forms.CharField(
        required=False,
        label="Paciente",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Buscar paciente por nome, CPF ou Cartão SUS…",
                "autocomplete": "off",
            }
        ),
    )

    class Meta:
        model = InternacaoSaude
        fields = [
            "unidade",
            "paciente_id",
            "paciente_busca",
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
        self._pacientes_qs = PacienteSaude.objects.none()
        if unidades_qs is not None:
            self.fields["unidade"].queryset = unidades_qs
            self._pacientes_qs = PacienteSaude.objects.filter(
                unidade_referencia_id__in=unidades_qs.values_list("id", flat=True)
            ).order_by("nome")
        if profissionais_qs is not None:
            self.fields["profissional_responsavel"].queryset = profissionais_qs

        _configure_autocomplete_field(
            self.fields["paciente_busca"],
            url=reverse("saude:api_pacientes_suggest"),
            fill_target="#id_paciente_id",
            min_chars=2,
            max_items=10,
        )

        if getattr(self.instance, "paciente_id", None):
            self.initial["paciente_id"] = self.instance.paciente_id
            self.initial["paciente_busca"] = getattr(self.instance.paciente, "nome", "")

    def clean(self):
        cleaned = super().clean()

        paciente_id = cleaned.get("paciente_id")
        paciente_busca = (cleaned.get("paciente_busca") or "").strip()

        paciente = None
        if paciente_id:
            paciente = self._pacientes_qs.filter(pk=paciente_id).first()
            if not paciente:
                self.add_error("paciente_busca", "Paciente inválido.")
        elif paciente_busca:
            self.add_error("paciente_busca", "Selecione um paciente válido nas sugestões.")
        else:
            self.add_error("paciente_busca", "Selecione um paciente para continuar.")

        cleaned["paciente_obj"] = paciente
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.paciente = self.cleaned_data.get("paciente_obj")
        if commit:
            obj.save()
        return obj


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
