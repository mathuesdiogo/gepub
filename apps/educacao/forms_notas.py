from django import forms
from .models_diario import Avaliacao
from .models_periodos import PeriodoLetivo


class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = [
            "tipo",
            "sigla",
            "titulo",
            "descricao",
            "periodo",
            "modo_registro",
            "peso",
            "nota_maxima",
            "data",
            "ativo",
        ]
        widgets = {
            "tipo": forms.Select(attrs={"class": "gp-select"}),
            "sigla": forms.TextInput(attrs={"class": "gp-input", "maxlength": 12, "placeholder": "Ex.: P1"}),
            "titulo": forms.TextInput(attrs={"class": "gp-input", "maxlength": 160}),
            "descricao": forms.Textarea(attrs={"class": "gp-textarea", "rows": 3}),
            "periodo": forms.Select(attrs={"class": "gp-select"}),
            "modo_registro": forms.Select(attrs={"class": "gp-select"}),
            "peso": forms.NumberInput(attrs={"class": "gp-input", "step": "0.01", "min": "0"}),
            "nota_maxima": forms.NumberInput(attrs={"class": "gp-input", "step": "0.01", "min": "0"}),
            "data": forms.DateInput(attrs={"type": "date", "class": "gp-input"}),
            "ativo": forms.CheckboxInput(attrs={"class": "gp-checkbox"}),
        }

    def __init__(self, *args, diario=None, **kwargs):
        self.diario = diario
        super().__init__(*args, **kwargs)
        self.fields["periodo"].required = False
        self.fields["descricao"].required = False
        self.fields["sigla"].required = False
        self.fields["tipo"].help_text = "Tipo do instrumento avaliativo."
        self.fields["sigla"].help_text = "Sigla curta exibida no cronograma do aluno."
        self.fields["descricao"].help_text = "Descrição detalhada para orientar o estudante."
        self.fields["modo_registro"].help_text = "Defina se o lançamento será por nota numérica ou conceito."
        self.fields["periodo"].help_text = "Etapa/bimestre ao qual a avaliação pertence."
        self.fields["nota_maxima"].help_text = "Usado somente para avaliações por nota."
        self.fields["ativo"].help_text = "Desative para ocultar sem apagar histórico."

        self.fields["periodo"].queryset = PeriodoLetivo.objects.none()
        if self.diario is None:
            return

        ano = getattr(self.diario, "ano_letivo", None)
        if not ano:
            return

        self.fields["periodo"].queryset = (
            PeriodoLetivo.objects.filter(ativo=True, ano_letivo=ano).order_by("tipo", "numero")
        )
