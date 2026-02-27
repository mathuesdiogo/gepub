from __future__ import annotations

from django import forms

from apps.core.rbac import scope_filter_turmas
from apps.educacao.models import Turma

from .models import AvaliacaoProva, QuestaoProva


def option_letters(total: int) -> list[str]:
    safe = max(2, min(int(total or 0), 5))
    return [chr(ord("A") + idx) for idx in range(safe)]


class AvaliacaoProvaForm(forms.ModelForm):
    class Meta:
        model = AvaliacaoProva
        fields = [
            "turma",
            "titulo",
            "disciplina",
            "data_aplicacao",
            "peso",
            "nota_maxima",
            "tipo",
            "opcoes",
            "qtd_questoes",
            "tem_versoes",
            "secretaria",
            "unidade",
            "setor",
        ]
        widgets = {
            "data_aplicacao": forms.DateInput(attrs={"type": "date"}),
            "qtd_questoes": forms.NumberInput(attrs={"min": 1, "max": 200}),
            "opcoes": forms.NumberInput(attrs={"min": 4, "max": 5}),
        }

    def __init__(self, *args, municipio=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.municipio = municipio
        self.user = user

        turma_qs = Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio")
        if municipio is not None:
            turma_qs = turma_qs.filter(unidade__secretaria__municipio=municipio)
            self.fields["secretaria"].queryset = self.fields["secretaria"].queryset.filter(municipio=municipio)
            self.fields["unidade"].queryset = self.fields["unidade"].queryset.filter(secretaria__municipio=municipio)
            self.fields["setor"].queryset = self.fields["setor"].queryset.filter(unidade__secretaria__municipio=municipio)

        if user is not None:
            turma_qs = scope_filter_turmas(user, turma_qs)

        self.fields["turma"].queryset = turma_qs.order_by("-ano_letivo", "nome")

    def clean(self):
        cleaned = super().clean()

        turma = cleaned.get("turma")
        if turma is None:
            return cleaned

        unidade = getattr(turma, "unidade", None)
        secretaria_turma = getattr(unidade, "secretaria", None) if unidade else None
        municipio_turma = getattr(secretaria_turma, "municipio", None) if secretaria_turma else None

        if self.municipio and municipio_turma and municipio_turma.pk != self.municipio.pk:
            self.add_error("turma", "A turma selecionada não pertence ao município escolhido.")

        secretaria = cleaned.get("secretaria")
        unidade_sel = cleaned.get("unidade")
        setor = cleaned.get("setor")

        if secretaria and municipio_turma and secretaria.municipio_id != municipio_turma.pk:
            self.add_error("secretaria", "Secretaria fora do escopo da turma.")

        if unidade_sel and secretaria_turma and unidade_sel.secretaria_id != secretaria_turma.pk:
            self.add_error("unidade", "Unidade fora do escopo da turma.")

        if setor and unidade_sel and setor.unidade_id != unidade_sel.pk:
            self.add_error("setor", "Setor incompatível com a unidade selecionada.")

        qtd_questoes = int(cleaned.get("qtd_questoes") or 0)
        if qtd_questoes < 1 or qtd_questoes > 200:
            self.add_error("qtd_questoes", "Informe entre 1 e 200 questões.")

        opcoes = int(cleaned.get("opcoes") or 0)
        if opcoes not in {4, 5}:
            self.add_error("opcoes", "Quantidade de opções deve ser 4 ou 5.")

        return cleaned


class QuestaoProvaForm(forms.ModelForm):
    alt_a = forms.CharField(label="Alternativa A", required=False)
    alt_b = forms.CharField(label="Alternativa B", required=False)
    alt_c = forms.CharField(label="Alternativa C", required=False)
    alt_d = forms.CharField(label="Alternativa D", required=False)
    alt_e = forms.CharField(label="Alternativa E", required=False)

    class Meta:
        model = QuestaoProva
        fields = ["numero", "enunciado", "tipo", "peso"]
        widgets = {
            "numero": forms.NumberInput(attrs={"min": 1}),
            "enunciado": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, avaliacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.avaliacao = avaliacao

        if self.instance and self.instance.pk:
            alternativas = self.instance.alternativas or {}
            for letra in ["A", "B", "C", "D", "E"]:
                self.fields[f"alt_{letra.lower()}"].initial = alternativas.get(letra, "")

        if avaliacao and avaliacao.opcoes < 5:
            self.fields["alt_e"].widget = forms.HiddenInput()
            self.fields["alt_e"].required = False

    def clean_numero(self):
        numero = int(self.cleaned_data.get("numero") or 0)
        if numero < 1:
            raise forms.ValidationError("Número da questão inválido.")
        if self.avaliacao and numero > self.avaliacao.qtd_questoes:
            raise forms.ValidationError("Número excede a quantidade de questões da avaliação.")
        return numero

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        if tipo == QuestaoProva.Tipo.OBJETIVA:
            letras = option_letters(self.avaliacao.opcoes if self.avaliacao else 5)
            preenchidas = [str(cleaned.get(f"alt_{letra.lower()}") or "").strip() for letra in letras]
            if not all(preenchidas):
                raise forms.ValidationError("Preencha todas as alternativas para questão objetiva.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        letras = option_letters(self.avaliacao.opcoes if self.avaliacao else 5)
        alternativas: dict[str, str] = {}
        for letra in letras:
            texto = (self.cleaned_data.get(f"alt_{letra.lower()}") or "").strip()
            if texto:
                alternativas[letra] = texto
        instance.alternativas = alternativas
        if self.avaliacao:
            instance.avaliacao = self.avaliacao
        if commit:
            instance.save()
        return instance


class RespostasObjetivasForm(forms.Form):
    def __init__(self, *args, qtd_questoes: int, opcoes: int, initial_respostas: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.qtd_questoes = max(1, int(qtd_questoes or 1))
        self.letras = option_letters(opcoes)
        initial_respostas = initial_respostas or {}

        options = [("", "—")]
        options.extend([(letra, letra) for letra in self.letras])

        for idx in range(1, self.qtd_questoes + 1):
            key = str(idx)
            field_name = f"q_{idx}"
            self.fields[field_name] = forms.ChoiceField(
                label=f"Questão {idx}",
                choices=options,
                required=False,
                initial=str(initial_respostas.get(key, "") or "").strip().upper(),
                widget=forms.Select(attrs={"class": "input"}),
            )

    def respostas_dict(self) -> dict[str, str]:
        respostas: dict[str, str] = {}
        for idx in range(1, self.qtd_questoes + 1):
            val = str(self.cleaned_data.get(f"q_{idx}") or "").strip().upper()
            if val and val in self.letras:
                respostas[str(idx)] = val
        return respostas


class CorrecaoFolhaForm(RespostasObjetivasForm):
    imagem_original = forms.FileField(
        required=False,
        label="Imagem/PDF da folha",
        help_text="Opcional: anexe scan/foto para auditoria.",
    )
    usar_omr = forms.BooleanField(
        required=False,
        label="Executar leitura OMR (beta)",
        help_text="Sugere respostas automaticamente para revisão manual.",
    )


class TokenLookupForm(forms.Form):
    token = forms.UUIDField(
        label="Token da folha",
        help_text="Cole o token lido no QR Code.",
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "UUID da folha",
                "style": "min-width:260px;",
            }
        ),
    )
