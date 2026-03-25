from __future__ import annotations

from django import forms
from django.utils import timezone

from apps.core.rbac import scope_filter_alunos, scope_filter_unidades
from apps.org.models import Unidade

from .models_biblioteca import (
    BibliotecaBloqueio,
    BibliotecaEscolar,
    BibliotecaExemplar,
    BibliotecaLivro,
    BibliotecaReserva,
    MatriculaInstitucional,
)
from .models import Aluno
from .services_biblioteca import LibraryLoanService


def _bibliotecas_scope(user):
    unidades_ids = scope_filter_unidades(
        user,
        Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
    ).values_list("id", flat=True)
    return BibliotecaEscolar.objects.select_related("unidade").filter(unidade_id__in=unidades_ids)


class BibliotecaEscolarForm(forms.ModelForm):
    class Meta:
        model = BibliotecaEscolar
        fields = [
            "unidade",
            "nome",
            "codigo",
            "tipo",
            "status",
            "responsavel",
            "limite_emprestimos_ativos",
            "dias_prazo_emprestimo",
            "permitir_emprestimo_com_atraso",
            "observacoes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["unidade"].queryset = scope_filter_unidades(
                user,
                Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
            )


class BibliotecaLivroForm(forms.ModelForm):
    class Meta:
        model = BibliotecaLivro
        fields = [
            "biblioteca",
            "titulo",
            "subtitulo",
            "autor",
            "editora",
            "edicao",
            "ano_publicacao",
            "isbn",
            "categoria",
            "assunto",
            "idioma",
            "descricao",
            "capa",
            "status",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["biblioteca"].queryset = _bibliotecas_scope(user).order_by("nome")


class BibliotecaExemplarForm(forms.ModelForm):
    class Meta:
        model = BibliotecaExemplar
        fields = [
            "livro",
            "codigo_exemplar",
            "tombo",
            "localizacao_estante",
            "status",
            "condicao_fisica",
            "data_aquisicao",
            "observacoes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["livro"].queryset = BibliotecaLivro.objects.filter(biblioteca__in=_bibliotecas_scope(user))


class BibliotecaBloqueioForm(forms.ModelForm):
    class Meta:
        model = BibliotecaBloqueio
        fields = [
            "biblioteca",
            "aluno",
            "matricula_institucional",
            "motivo",
            "data_inicio",
            "data_fim",
            "status",
            "observacoes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            bibliotecas_qs = _bibliotecas_scope(user).order_by("nome")
            self.fields["biblioteca"].queryset = bibliotecas_qs
            self.fields["aluno"].queryset = scope_filter_alunos(user, Aluno.objects.filter(ativo=True)).order_by("nome")
            self.fields["matricula_institucional"].queryset = MatriculaInstitucional.objects.filter(
                aluno__in=self.fields["aluno"].queryset
            ).select_related("aluno")


class BibliotecaEmprestimoCreateForm(forms.Form):
    biblioteca = forms.ModelChoiceField(queryset=BibliotecaEscolar.objects.none(), label="Biblioteca")
    identificador_aluno = forms.CharField(
        max_length=120,
        label="Aluno (matrícula / código de acesso / nome)",
        help_text="Você pode buscar por matrícula institucional, código de acesso ou nome.",
    )
    exemplar = forms.ModelChoiceField(queryset=BibliotecaExemplar.objects.none(), label="Exemplar")
    data_emprestimo = forms.DateField(initial=timezone.localdate, required=False)
    data_prevista_devolucao = forms.DateField(required=False)
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.aluno = None
        bibliotecas_qs = _bibliotecas_scope(user).order_by("nome") if user else BibliotecaEscolar.objects.none()
        self.fields["biblioteca"].queryset = bibliotecas_qs
        self.fields["exemplar"].queryset = (
            BibliotecaExemplar.objects.select_related("livro", "livro__biblioteca")
            .filter(
                livro__biblioteca__in=bibliotecas_qs,
                status=BibliotecaExemplar.Status.DISPONIVEL,
            )
            .order_by("livro__titulo", "codigo_exemplar")
        )

    def clean(self):
        cleaned = super().clean()
        biblioteca = cleaned.get("biblioteca")
        exemplar = cleaned.get("exemplar")
        token = (cleaned.get("identificador_aluno") or "").strip()
        if not token:
            self.add_error("identificador_aluno", "Informe um identificador de aluno.")
            return cleaned

        aluno = LibraryLoanService.find_student_by_identifier(token)
        if aluno is None:
            self.add_error("identificador_aluno", "Aluno não encontrado para o identificador informado.")
            return cleaned
        self.aluno = aluno

        if biblioteca and exemplar and exemplar.livro.biblioteca_id != biblioteca.id:
            self.add_error("exemplar", "O exemplar selecionado não pertence à biblioteca informada.")

        return cleaned


class BibliotecaReservaCreateForm(forms.Form):
    biblioteca = forms.ModelChoiceField(queryset=BibliotecaEscolar.objects.none(), label="Biblioteca")
    identificador_aluno = forms.CharField(
        max_length=120,
        label="Aluno (matrícula / código de acesso / nome)",
        help_text="Você pode buscar por matrícula institucional, código de acesso ou nome.",
    )
    livro = forms.ModelChoiceField(queryset=BibliotecaLivro.objects.none(), label="Livro")
    exemplar = forms.ModelChoiceField(queryset=BibliotecaExemplar.objects.none(), required=False, label="Exemplar (opcional)")
    dias_validade = forms.IntegerField(initial=3, min_value=1, max_value=30)
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.aluno = None
        bibliotecas_qs = _bibliotecas_scope(user).order_by("nome") if user else BibliotecaEscolar.objects.none()
        self.fields["biblioteca"].queryset = bibliotecas_qs
        self.fields["livro"].queryset = (
            BibliotecaLivro.objects.select_related("biblioteca")
            .filter(biblioteca__in=bibliotecas_qs, status=BibliotecaLivro.Status.ATIVO)
            .order_by("titulo")
        )
        self.fields["exemplar"].queryset = (
            BibliotecaExemplar.objects.select_related("livro", "livro__biblioteca")
            .filter(livro__biblioteca__in=bibliotecas_qs)
            .exclude(status__in=[BibliotecaExemplar.Status.BAIXADO, BibliotecaExemplar.Status.PERDIDO])
            .order_by("livro__titulo", "codigo_exemplar")
        )

    def clean(self):
        cleaned = super().clean()
        biblioteca = cleaned.get("biblioteca")
        livro = cleaned.get("livro")
        exemplar = cleaned.get("exemplar")
        token = (cleaned.get("identificador_aluno") or "").strip()

        if not token:
            self.add_error("identificador_aluno", "Informe um identificador de aluno.")
            return cleaned
        aluno = LibraryLoanService.find_student_by_identifier(token)
        if aluno is None:
            self.add_error("identificador_aluno", "Aluno não encontrado para o identificador informado.")
            return cleaned
        self.aluno = aluno

        if biblioteca and livro and livro.biblioteca_id != biblioteca.id:
            self.add_error("livro", "O livro selecionado não pertence à biblioteca informada.")
        if exemplar and livro and exemplar.livro_id != livro.id:
            self.add_error("exemplar", "O exemplar informado não pertence ao livro selecionado.")
        if exemplar and biblioteca and exemplar.livro.biblioteca_id != biblioteca.id:
            self.add_error("exemplar", "O exemplar selecionado não pertence à biblioteca informada.")

        return cleaned


class BibliotecaDevolucaoForm(forms.Form):
    data_devolucao = forms.DateField(initial=timezone.localdate)
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class BibliotecaRenovacaoForm(forms.Form):
    dias_adicionais = forms.IntegerField(initial=7, min_value=1, max_value=60)
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class BibliotecaReservaCancelForm(forms.Form):
    motivo = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
