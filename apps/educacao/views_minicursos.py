from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.rbac import can, is_admin, scope_filter_alunos, scope_filter_turmas, scope_filter_unidades
from apps.org.models import Unidade

from .models import Aluno, AlunoCertificado, Curso, MatriculaCurso, Turma


def _minicurso_cursos_scope(user):
    base = Curso.objects.filter(
        modalidade_oferta__in=[Curso.ModalidadeOferta.FIC, Curso.ModalidadeOferta.LIVRE]
    ).order_by("nome")
    if is_admin(user):
        return base

    turmas_scope = scope_filter_turmas(
        user,
        Turma.objects.filter(
            modalidade=Turma.Modalidade.ATIVIDADE_COMPLEMENTAR,
            curso__isnull=False,
            curso__modalidade_oferta__in=[Curso.ModalidadeOferta.FIC, Curso.ModalidadeOferta.LIVRE],
        ),
    )
    return base.filter(turmas__in=turmas_scope).distinct()


def _minicurso_turmas_scope(user):
    return scope_filter_turmas(
        user,
        Turma.objects.select_related("curso", "unidade", "unidade__secretaria")
        .filter(
            modalidade=Turma.Modalidade.ATIVIDADE_COMPLEMENTAR,
            curso__isnull=False,
            curso__modalidade_oferta__in=[Curso.ModalidadeOferta.FIC, Curso.ModalidadeOferta.LIVRE],
        )
        .order_by("-ano_letivo", "nome"),
    )


class MinicursoCursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            "nome",
            "codigo",
            "modalidade_oferta",
            "eixo_tecnologico",
            "carga_horaria",
            "ativo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modalidade_oferta"].choices = [
            (Curso.ModalidadeOferta.FIC, dict(Curso.ModalidadeOferta.choices)[Curso.ModalidadeOferta.FIC]),
            (Curso.ModalidadeOferta.LIVRE, dict(Curso.ModalidadeOferta.choices)[Curso.ModalidadeOferta.LIVRE]),
        ]
        self.fields["modalidade_oferta"].initial = Curso.ModalidadeOferta.FIC
        self.fields["codigo"].help_text = "Ex.: MINI-INFO-2026"


class MinicursoTurmaForm(forms.ModelForm):
    class Meta:
        model = Turma
        fields = [
            "curso",
            "unidade",
            "nome",
            "ano_letivo",
            "turno",
            "professores",
            "ativo",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["ano_letivo"].initial = timezone.localdate().year
        self.fields["curso"].queryset = _minicurso_cursos_scope(user).filter(ativo=True)
        self.fields["unidade"].queryset = scope_filter_unidades(
            user,
            Unidade.objects.filter(ativo=True, tipo=Unidade.Tipo.EDUCACAO),
        ).order_by("nome")

        user_model = get_user_model()
        prof_qs = user_model.objects.filter(
            is_active=True,
            profile__ativo=True,
            profile__bloqueado=False,
        ).filter(Q(profile__role="PROFESSOR") | Q(profile__role="EDU_PROF"))
        if not is_admin(user):
            unidades_scope = scope_filter_unidades(
                user,
                Unidade.objects.filter(tipo=Unidade.Tipo.EDUCACAO),
            )
            unidade_ids = unidades_scope.values_list("id", flat=True).distinct()
            secretaria_ids = unidades_scope.values_list("secretaria_id", flat=True).distinct()
            prof_qs = prof_qs.filter(
                Q(profile__unidade_id__in=unidade_ids)
                | Q(profile__secretaria_id__in=secretaria_ids)
                | Q(profile__unidade__secretaria_id__in=secretaria_ids)
            )
        self.fields["professores"].queryset = prof_qs.distinct().order_by("first_name", "last_name", "username")
        self.fields["professores"].required = False

    def clean(self):
        cleaned = super().clean()
        curso = cleaned.get("curso")
        # Garante coerência do instance antes da validação do model (_post_clean).
        self.instance.modalidade = Turma.Modalidade.ATIVIDADE_COMPLEMENTAR
        self.instance.etapa = Turma.Etapa.FIC
        self.instance.serie_ano = Turma.SerieAno.NAO_APLICA
        self.instance.forma_oferta = Turma.FormaOferta.PRESENCIAL
        self.instance.matriz_curricular = None
        if curso is not None:
            self.instance.curso = curso

        if curso and curso.modalidade_oferta not in [Curso.ModalidadeOferta.FIC, Curso.ModalidadeOferta.LIVRE]:
            self.add_error("curso", "Selecione um curso com modalidade FIC ou Curso Livre.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.modalidade = Turma.Modalidade.ATIVIDADE_COMPLEMENTAR
        instance.etapa = Turma.Etapa.FIC
        instance.serie_ano = Turma.SerieAno.NAO_APLICA
        instance.forma_oferta = Turma.FormaOferta.PRESENCIAL
        instance.matriz_curricular = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class MinicursoMatriculaForm(forms.Form):
    aluno = forms.ModelChoiceField(label="Aluno", queryset=Aluno.objects.none(), required=True)
    curso = forms.ModelChoiceField(label="Minicurso", queryset=Curso.objects.none(), required=True)
    turma = forms.ModelChoiceField(label="Turma (opcional)", queryset=Turma.objects.none(), required=False)
    data_matricula = forms.DateField(label="Data da matrícula", widget=forms.DateInput(attrs={"type": "date"}))
    observacao = forms.CharField(label="Observação", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["data_matricula"].initial = timezone.localdate()
        self.fields["aluno"].queryset = scope_filter_alunos(user, Aluno.objects.filter(ativo=True)).order_by("nome")
        self.fields["curso"].queryset = _minicurso_cursos_scope(user).filter(ativo=True)
        turma_qs = _minicurso_turmas_scope(user).filter(ativo=True)

        curso_raw = ""
        if self.is_bound:
            curso_raw = (self.data.get(self.add_prefix("curso")) or "").strip()
        elif self.initial.get("curso"):
            curso_raw = str(self.initial.get("curso"))
        if curso_raw.isdigit():
            turma_qs = turma_qs.filter(curso_id=int(curso_raw))
        self.fields["turma"].queryset = turma_qs

    def clean(self):
        cleaned = super().clean()
        aluno = cleaned.get("aluno")
        curso = cleaned.get("curso")
        turma = cleaned.get("turma")
        if turma and curso and turma.curso_id != curso.id:
            self.add_error("turma", "A turma selecionada não pertence ao minicurso informado.")
        if aluno and curso:
            qs = MatriculaCurso.objects.filter(
                aluno=aluno,
                curso=curso,
                situacao__in=[MatriculaCurso.Situacao.MATRICULADO, MatriculaCurso.Situacao.EM_ANDAMENTO],
            )
            if turma:
                qs = qs.filter(turma=turma)
            if qs.exists():
                self.add_error("aluno", "Este aluno já possui matrícula ativa nesse minicurso/turma.")
        return cleaned

    def save(self, *, user):
        return MatriculaCurso.objects.create(
            aluno=self.cleaned_data["aluno"],
            curso=self.cleaned_data["curso"],
            turma=self.cleaned_data.get("turma"),
            data_matricula=self.cleaned_data["data_matricula"],
            situacao=MatriculaCurso.Situacao.MATRICULADO,
            observacao=self.cleaned_data.get("observacao") or "",
            cadastrado_por=user,
        )


class MinicursoCertificadoForm(forms.Form):
    matricula_curso = forms.ModelChoiceField(
        label="Matrícula de minicurso",
        queryset=MatriculaCurso.objects.none(),
        required=True,
    )
    data_emissao = forms.DateField(label="Data de emissão", widget=forms.DateInput(attrs={"type": "date"}))
    titulo = forms.CharField(label="Título do certificado", required=False, max_length=180)
    carga_horaria = forms.IntegerField(label="Carga horária (opcional)", required=False, min_value=0)
    resultado_final = forms.CharField(label="Resultado final", required=False, max_length=60)
    observacao = forms.CharField(label="Observação", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_emissao"].initial = timezone.localdate()
        turmas_scope = _minicurso_turmas_scope(user)
        qs = MatriculaCurso.objects.select_related("aluno", "curso", "turma").filter(
            curso__modalidade_oferta__in=[Curso.ModalidadeOferta.FIC, Curso.ModalidadeOferta.LIVRE],
        )
        if not is_admin(user):
            qs = qs.filter(Q(turma__in=turmas_scope) | Q(turma__isnull=True, curso__in=_minicurso_cursos_scope(user)))
        self.fields["matricula_curso"].queryset = qs.order_by("-data_matricula", "-id")
        self.fields["matricula_curso"].label_from_instance = (
            lambda mc: f"{mc.aluno.nome} • {mc.curso.nome} • {mc.get_situacao_display()}"
        )

    def save(self, *, user):
        mc: MatriculaCurso = self.cleaned_data["matricula_curso"]
        titulo = (self.cleaned_data.get("titulo") or "").strip() or f"Certificado de {mc.curso.nome}"
        carga = self.cleaned_data.get("carga_horaria")
        certificado = AlunoCertificado.objects.create(
            aluno=mc.aluno,
            curso=mc.curso,
            tipo=AlunoCertificado.Tipo.CERTIFICADO_CURSO,
            titulo=titulo,
            data_emissao=self.cleaned_data["data_emissao"],
            carga_horaria=carga if carga is not None else int(getattr(mc.curso, "carga_horaria", 0) or 0),
            resultado_final=(self.cleaned_data.get("resultado_final") or "").strip(),
            observacao=(
                (self.cleaned_data.get("observacao") or "").strip()
                or f"Certificado gerado a partir da matrícula de minicurso #{mc.id}."
            ),
            emitido_por=user,
        )
        return certificado


@login_required
@require_perm("educacao.manage")
def minicurso_dashboard(request):
    cursos_qs = _minicurso_cursos_scope(request.user)
    turmas_qs = _minicurso_turmas_scope(request.user)

    matriculas_qs = MatriculaCurso.objects.select_related("aluno", "curso", "turma").filter(
        curso__in=cursos_qs,
    )
    if not is_admin(request.user):
        matriculas_qs = matriculas_qs.filter(Q(turma__in=turmas_qs) | Q(turma__isnull=True))

    certificados_qs = AlunoCertificado.objects.select_related("aluno", "curso").filter(
        tipo=AlunoCertificado.Tipo.CERTIFICADO_CURSO,
        curso__in=cursos_qs,
    )

    return render(
        request,
        "educacao/minicurso_dashboard.html",
        {
            "stats": {
                "cursos": cursos_qs.count(),
                "turmas": turmas_qs.count(),
                "matriculas": matriculas_qs.count(),
                "certificados": certificados_qs.count(),
            },
            "recentes_cursos": cursos_qs.order_by("-id")[:8],
            "recentes_turmas": turmas_qs.order_by("-id")[:8],
            "recentes_matriculas": matriculas_qs.order_by("-id")[:10],
            "recentes_certificados": certificados_qs.order_by("-id")[:10],
            "actions": [
                {"label": "Novo minicurso", "url": reverse("educacao:minicurso_curso_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
                {"label": "Nova turma", "url": reverse("educacao:minicurso_turma_create"), "icon": "fa-solid fa-people-group", "variant": "btn--outline"},
                {"label": "Nova matrícula", "url": reverse("educacao:minicurso_matricula_create"), "icon": "fa-solid fa-user-plus", "variant": "btn--outline"},
                {"label": "Emitir certificado", "url": reverse("educacao:minicurso_certificado_emitir"), "icon": "fa-solid fa-certificate", "variant": "btn--outline"},
            ],
            "can_edu_manage": can(request.user, "educacao.manage"),
        },
    )


@login_required
@require_perm("educacao.manage")
def minicurso_curso_create(request):
    form = MinicursoCursoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        curso = form.save()
        messages.success(request, f"Minicurso criado com sucesso: {curso.nome}.")
        return redirect("educacao:minicurso_dashboard")
    return render(
        request,
        "educacao/minicurso_form.html",
        {
            "title": "Cadastro de Minicurso",
            "subtitle": "Crie o minicurso e defina modalidade, carga horária e eixo.",
            "form": form,
            "submit_label": "Salvar minicurso",
            "actions": [{"label": "Voltar", "url": reverse("educacao:minicurso_dashboard"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}],
        },
    )


@login_required
@require_perm("educacao.manage")
def minicurso_turma_create(request):
    form = MinicursoTurmaForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        turma = form.save()
        messages.success(request, f"Turma de minicurso criada com sucesso: {turma.nome}.")
        return redirect("educacao:minicurso_dashboard")
    return render(
        request,
        "educacao/minicurso_form.html",
        {
            "title": "Turmas de Minicurso",
            "subtitle": "Associe unidade, turno e professor para operação das turmas.",
            "form": form,
            "submit_label": "Salvar turma",
            "actions": [{"label": "Voltar", "url": reverse("educacao:minicurso_dashboard"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}],
        },
    )


@login_required
@require_perm("educacao.manage")
def minicurso_matricula_create(request):
    form = MinicursoMatriculaForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        matricula = form.save(user=request.user)
        messages.success(request, f"Matrícula criada com sucesso para {matricula.aluno.nome}.")
        return redirect("educacao:minicurso_dashboard")
    return render(
        request,
        "educacao/minicurso_form.html",
        {
            "title": "Matrículas de Minicurso",
            "subtitle": "Registre alunos em minicursos e turmas específicas.",
            "form": form,
            "submit_label": "Salvar matrícula",
            "actions": [{"label": "Voltar", "url": reverse("educacao:minicurso_dashboard"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}],
        },
    )


@login_required
@require_perm("educacao.manage")
def minicurso_certificado_emitir(request):
    form = MinicursoCertificadoForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        certificado = form.save(user=request.user)
        messages.success(
            request,
            f"Certificado emitido com sucesso. Código de validação: {certificado.codigo_verificacao}.",
        )
        return redirect("educacao:minicurso_dashboard")
    return render(
        request,
        "educacao/minicurso_form.html",
        {
            "title": "Certificados de Minicurso",
            "subtitle": "Emita certificados a partir das matrículas de minicurso.",
            "form": form,
            "submit_label": "Emitir certificado",
            "actions": [{"label": "Voltar", "url": reverse("educacao:minicurso_dashboard"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"}],
        },
    )
