from __future__ import annotations

from django import forms

from .models_diario import Aula, MaterialAulaProfessor, PlanoEnsinoProfessor
from .models_informatica import (
    InformaticaAulaDiario,
    InformaticaAvaliacao,
    InformaticaPlanoEnsinoProfessor,
)


class PlanoEnsinoProfessorForm(forms.ModelForm):
    class Meta:
        model = PlanoEnsinoProfessor
        fields = [
            "titulo",
            "ementa",
            "objetivos",
            "metodologia",
            "criterios_avaliacao",
            "cronograma",
            "referencias",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "gp-input", "maxlength": 180}),
            "ementa": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "objetivos": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "metodologia": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "criterios_avaliacao": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "cronograma": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "referencias": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
        }


class InformaticaPlanoEnsinoProfessorForm(forms.ModelForm):
    class Meta:
        model = InformaticaPlanoEnsinoProfessor
        fields = [
            "titulo",
            "ementa",
            "objetivos",
            "metodologia",
            "criterios_avaliacao",
            "cronograma",
            "referencias",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "gp-input", "maxlength": 180}),
            "ementa": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "objetivos": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "metodologia": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "criterios_avaliacao": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "cronograma": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "referencias": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
        }


class InformaticaAvaliacaoForm(forms.ModelForm):
    class Meta:
        model = InformaticaAvaliacao
        fields = [
            "titulo",
            "peso",
            "nota_maxima",
            "data",
            "ativo",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "gp-input", "maxlength": 180}),
            "peso": forms.NumberInput(attrs={"class": "gp-input", "step": "0.01", "min": "0"}),
            "nota_maxima": forms.NumberInput(attrs={"class": "gp-input", "step": "0.01", "min": "0"}),
            "data": forms.DateInput(attrs={"class": "gp-input", "type": "date"}),
        }


class MaterialAulaProfessorForm(forms.ModelForm):
    class Meta:
        model = MaterialAulaProfessor
        fields = [
            "titulo",
            "descricao",
            "diario",
            "aula",
            "turma_informatica",
            "aula_informatica",
            "arquivo",
            "link_externo",
            "publico_alunos",
            "ativo",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "gp-input", "maxlength": 180}),
            "descricao": forms.Textarea(attrs={"class": "gp-textarea", "rows": 4}),
            "diario": forms.Select(attrs={"class": "gp-select"}),
            "aula": forms.Select(attrs={"class": "gp-select"}),
            "turma_informatica": forms.Select(attrs={"class": "gp-select"}),
            "aula_informatica": forms.Select(attrs={"class": "gp-select"}),
            "link_externo": forms.URLInput(attrs={"class": "gp-input", "placeholder": "https://"}),
        }

    def __init__(self, *args, diarios_qs=None, turmas_informatica_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if diarios_qs is not None:
            self.fields["diario"].queryset = diarios_qs
        if turmas_informatica_qs is not None:
            self.fields["turma_informatica"].queryset = turmas_informatica_qs

        diario_id = None
        turma_informatica_id = None
        if self.data.get("diario"):
            diario_id = self.data.get("diario")
        elif self.instance and self.instance.pk and self.instance.diario_id:
            diario_id = self.instance.diario_id
        elif self.initial.get("diario"):
            diario_id = self.initial.get("diario")

        if self.data.get("turma_informatica"):
            turma_informatica_id = self.data.get("turma_informatica")
        elif self.instance and self.instance.pk and self.instance.turma_informatica_id:
            turma_informatica_id = self.instance.turma_informatica_id
        elif self.initial.get("turma_informatica"):
            turma_informatica_id = self.initial.get("turma_informatica")

        self.fields["aula"].queryset = Aula.objects.none()
        self.fields["aula_informatica"].queryset = InformaticaAulaDiario.objects.none()
        if diario_id and str(diario_id).isdigit():
            self.fields["aula"].queryset = Aula.objects.filter(diario_id=int(diario_id)).order_by("-data", "-id")
        if turma_informatica_id and str(turma_informatica_id).isdigit():
            self.fields["aula_informatica"].queryset = InformaticaAulaDiario.objects.filter(
                turma_id=int(turma_informatica_id)
            ).order_by("-data_aula", "-id")

    def clean(self):
        cleaned = super().clean()
        diario = cleaned.get("diario")
        aula = cleaned.get("aula")
        turma_informatica = cleaned.get("turma_informatica")
        aula_informatica = cleaned.get("aula_informatica")
        arquivo = cleaned.get("arquivo")
        link_externo = (cleaned.get("link_externo") or "").strip()

        if not arquivo and not link_externo:
            self.add_error("arquivo", "Informe um arquivo ou link externo.")

        if (diario or aula) and (turma_informatica or aula_informatica):
            self.add_error("diario", "Escolha vínculo regular ou de informática, não ambos no mesmo material.")

        if aula and diario and aula.diario_id != diario.id:
            self.add_error("aula", "A aula selecionada não pertence ao diário informado.")
        if aula and not diario:
            cleaned["diario"] = aula.diario

        if aula_informatica and turma_informatica and aula_informatica.turma_id != turma_informatica.id:
            self.add_error("aula_informatica", "A aula de informática selecionada não pertence à turma informada.")
        if aula_informatica and not turma_informatica:
            cleaned["turma_informatica"] = aula_informatica.turma

        return cleaned
