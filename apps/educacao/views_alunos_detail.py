from __future__ import annotations

from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, scope_filter_turmas

from .models import Aluno, Matricula, MatriculaMovimentacao, Turma
from .services_matricula import registrar_movimentacao

from apps.nee.models import AlunoNecessidade, TipoNecessidade, ApoioMatricula

try:
    from apps.saude.models import AtendimentoSaude
except Exception:  # pragma: no cover
    AtendimentoSaude = None  # type: ignore


def _matricula_form_fields():
    names = {f.name for f in Matricula._meta.fields}
    fields = ["turma"]
    # se existir (em alguns projetos você usa situacao)
    if "situacao" in names:
        fields.append("situacao")
    if "ativo" in names:
        fields.append("ativo")
    return fields


class MatriculaInlineForm(forms.ModelForm):
    class Meta:
        model = Matricula
        fields = _matricula_form_fields()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Turmas ativas primeiro (se existir campo ativo)
        qs = Turma.objects.all().order_by("-ano_letivo", "nome")
        if "ativo" in {f.name for f in Turma._meta.fields}:
            qs = Turma.objects.filter(ativo=True).order_by("-ano_letivo", "nome")
        if "turma" in self.fields:
            self.fields["turma"].queryset = qs


class NeeInlineForm(forms.ModelForm):
    class Meta:
        model = AlunoNecessidade
        fields = ["tipo", "observacao"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tipo"].queryset = TipoNecessidade.objects.filter(ativo=True).order_by("nome")


class ApoioInlineForm(forms.ModelForm):
    class Meta:
        model = ApoioMatricula
        fields = ["matricula", "descricao", "observacao", "ativo"]

    def __init__(self, aluno: Aluno, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["matricula"].queryset = Matricula.objects.select_related("turma", "turma__unidade").filter(aluno=aluno).order_by("-id")


class MatriculaMovimentacaoForm(forms.Form):
    matricula = forms.ModelChoiceField(queryset=Matricula.objects.none(), label="Matrícula")
    tipo = forms.ChoiceField(
        label="Tipo de movimentação",
        choices=[
            (MatriculaMovimentacao.Tipo.REMANEJAMENTO, "Remanejamento de turma"),
            (MatriculaMovimentacao.Tipo.TRANSFERENCIA, "Transferência"),
            (MatriculaMovimentacao.Tipo.CANCELAMENTO, "Cancelamento"),
            (MatriculaMovimentacao.Tipo.REATIVACAO, "Reativação"),
        ],
    )
    turma_destino = forms.ModelChoiceField(
        queryset=Turma.objects.none(),
        label="Turma de destino",
        required=False,
    )
    motivo = forms.CharField(
        label="Motivo",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, aluno: Aluno, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aluno = aluno
        self.user = user

        self.fields["matricula"].queryset = (
            Matricula.objects.select_related("turma", "turma__unidade")
            .filter(aluno=aluno)
            .order_by("-id")
        )

        turma_qs = scope_filter_turmas(
            user,
            Turma.objects.select_related("unidade", "unidade__secretaria").filter(ativo=True),
        ).order_by("-ano_letivo", "nome")
        self.fields["turma_destino"].queryset = turma_qs

    def clean(self):
        cleaned = super().clean()
        matricula = cleaned.get("matricula")
        tipo = cleaned.get("tipo")
        turma_destino = cleaned.get("turma_destino")

        if not matricula:
            return cleaned

        if tipo in {
            MatriculaMovimentacao.Tipo.REMANEJAMENTO,
            MatriculaMovimentacao.Tipo.TRANSFERENCIA,
        }:
            if not turma_destino:
                self.add_error("turma_destino", "Selecione a turma de destino.")
            elif turma_destino == matricula.turma:
                self.add_error("turma_destino", "A turma de destino deve ser diferente da turma atual.")

        return cleaned


@method_decorator(login_required, name="dispatch")
@method_decorator(require_perm("educacao.view"), name="dispatch")
class AlunoDetailView(View):
    template_name = "educacao/aluno_detail.html"

    def _build_context(self, request, aluno: Aluno, form_matricula=None, form_nee=None, form_apoio=None, form_movimentacao=None):
        matriculas = (
            Matricula.objects
            .select_related("turma", "turma__unidade", "turma__unidade__secretaria", "turma__unidade__secretaria__municipio")
            .filter(aluno=aluno)
            .order_by("-id")
        )

        headers_matriculas = [
            {"label": "Turma"},
            {"label": "Ano", "width": "120px"},
            {"label": "Turno", "width": "140px"},
            {"label": "Unidade"},
            {"label": "Situação", "width": "160px"},
            {"label": "Código", "width": "90px"},
        ]

        rows_matriculas = []
        for m in matriculas:
            turma = m.turma
            unidade = getattr(turma, "unidade", None)
            unidade_nome = getattr(unidade, "nome", "—")
            situacao = getattr(m, "get_situacao_display", None)
            situacao_txt = situacao() if callable(situacao) else getattr(m, "situacao", "—")
            rows_matriculas.append({
                "cells": [
                    {"text": turma.nome, "url": reverse("educacao:turma_detail", args=[turma.pk])},
                    {"text": str(getattr(turma, "ano_letivo", "") or "—")},
                    {"text": getattr(turma, "get_turno_display", lambda: getattr(turma, "turno", "—"))()},
                    {"text": unidade_nome},
                    {"text": situacao_txt},
                    {"text": str(m.pk)},
                ],
                "can_edit": False,
                "edit_url": "",
            })

        fields = [
            ("CPF", getattr(aluno, "cpf", "") or "—"),
            ("NIS", getattr(aluno, "nis", "") or "—"),
            ("Data nascimento", aluno.data_nascimento.strftime("%d/%m/%Y") if getattr(aluno, "data_nascimento", None) else "—"),
            ("Telefone", getattr(aluno, "telefone", "") or "—"),
            ("E-mail", getattr(aluno, "email", "") or "—"),
            ("Ativo", "Sim" if getattr(aluno, "ativo", True) else "Não"),
        ]
        pills = [("Matrículas", matriculas.count())]

        necessidades = AlunoNecessidade.objects.select_related("tipo").filter(aluno=aluno).order_by("-id")
        apoios = ApoioMatricula.objects.select_related("matricula", "matricula__turma", "matricula__turma__unidade").filter(matricula__aluno=aluno).order_by("-id")
        movimentacoes = (
            MatriculaMovimentacao.objects.select_related("usuario", "turma_origem", "turma_destino", "matricula")
            .filter(aluno=aluno)
            .order_by("-criado_em", "-id")[:50]
        )

        headers_movimentacoes = [
            {"label": "Data/Hora", "width": "160px"},
            {"label": "Tipo", "width": "150px"},
            {"label": "Matrícula", "width": "90px"},
            {"label": "Origem"},
            {"label": "Destino"},
            {"label": "Situação"},
            {"label": "Usuário", "width": "180px"},
            {"label": "Motivo"},
        ]
        rows_movimentacoes = []
        for mov in movimentacoes:
            origem = getattr(mov.turma_origem, "nome", "—")
            destino = getattr(mov.turma_destino, "nome", "—")
            sit_ant = mov.situacao_anterior or "—"
            sit_nova = mov.situacao_nova or "—"
            usuario = getattr(getattr(mov, "usuario", None), "username", "—")
            rows_movimentacoes.append(
                {
                    "cells": [
                        {"text": mov.criado_em.strftime("%d/%m/%Y %H:%M")},
                        {"text": mov.get_tipo_display()},
                        {"text": str(mov.matricula_id)},
                        {"text": origem},
                        {"text": destino},
                        {"text": f"{sit_ant} → {sit_nova}"},
                        {"text": usuario},
                        {"text": mov.motivo or "—"},
                    ],
                    "can_edit": False,
                    "edit_url": "",
                }
            )

        can_edu_manage = can(request.user, "educacao.manage") or can(request.user, "nee.manage")

        return {
            "aluno": aluno,
            "fields": fields,
            "pills": pills,
            "headers_matriculas": headers_matriculas,
            "rows_matriculas": rows_matriculas,
            "can_edu_manage": can_edu_manage,
            "necessidades": necessidades,
            "apoios": apoios,
            "headers_movimentacoes": headers_movimentacoes,
            "rows_movimentacoes": rows_movimentacoes,
            "form_matricula": form_matricula or MatriculaInlineForm(),
            "form_nee": form_nee or NeeInlineForm(),
            "form_apoio": form_apoio or ApoioInlineForm(aluno),
            "form_movimentacao": form_movimentacao or MatriculaMovimentacaoForm(aluno, request.user),
        }

    def get(self, request, pk: int):
        aluno = get_object_or_404(Aluno, pk=pk)
        return render(request, self.template_name, self._build_context(request, aluno))

    def post(self, request, pk: int):
        aluno = get_object_or_404(Aluno, pk=pk)
        action = (request.POST.get("_action") or "").strip()

        if not (can(request.user, "educacao.manage") or can(request.user, "nee.manage")):
            return redirect("educacao:aluno_detail", pk=aluno.pk)

        # default forms
        form_matricula = MatriculaInlineForm(request.POST or None)
        form_nee = NeeInlineForm(request.POST or None)
        form_apoio = ApoioInlineForm(aluno, request.POST or None)
        form_movimentacao = MatriculaMovimentacaoForm(aluno, request.user, request.POST or None)

        if action == "add_matricula":
            if form_matricula.is_valid():
                obj = form_matricula.save(commit=False)
                obj.aluno = aluno
                obj.save()
                registrar_movimentacao(
                    matricula=obj,
                    tipo=MatriculaMovimentacao.Tipo.CRIACAO,
                    usuario=request.user,
                    turma_destino=obj.turma,
                    situacao_nova=obj.situacao,
                    motivo="Matrícula criada pelo detalhe do aluno.",
                )
                messages.success(request, "Matrícula adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

        elif action == "add_nee":
            if form_nee.is_valid():
                obj = form_nee.save(commit=False)
                obj.aluno = aluno
                obj.save()
                messages.success(request, "Necessidade adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

        elif action == "add_apoio":
            if form_apoio.is_valid():
                form_apoio.save()
                messages.success(request, "Apoio registrado com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

        elif action == "mov_matricula":
            if form_movimentacao.is_valid():
                matricula = form_movimentacao.cleaned_data["matricula"]
                tipo = form_movimentacao.cleaned_data["tipo"]
                turma_destino = form_movimentacao.cleaned_data.get("turma_destino")
                motivo = form_movimentacao.cleaned_data.get("motivo") or ""

                situacao_anterior = matricula.situacao
                turma_origem = matricula.turma

                if tipo == MatriculaMovimentacao.Tipo.REMANEJAMENTO:
                    if Matricula.objects.filter(aluno=aluno, turma=turma_destino).exclude(pk=matricula.pk).exists():
                        form_movimentacao.add_error("turma_destino", "Já existe matrícula deste aluno na turma de destino.")
                    else:
                        matricula.turma = turma_destino
                        matricula.situacao = Matricula.Situacao.ATIVA
                        matricula.save(update_fields=["turma", "situacao"])
                        registrar_movimentacao(
                            matricula=matricula,
                            tipo=tipo,
                            usuario=request.user,
                            turma_origem=turma_origem,
                            turma_destino=turma_destino,
                            situacao_anterior=situacao_anterior,
                            situacao_nova=matricula.situacao,
                            motivo=motivo,
                        )
                        messages.success(request, "Remanejamento realizado com sucesso.")
                        return redirect("educacao:aluno_detail", pk=aluno.pk)

                elif tipo == MatriculaMovimentacao.Tipo.TRANSFERENCIA:
                    if Matricula.objects.filter(aluno=aluno, turma=turma_destino).exists():
                        form_movimentacao.add_error("turma_destino", "Já existe matrícula deste aluno na turma de destino.")
                    else:
                        matricula.situacao = Matricula.Situacao.TRANSFERIDO
                        matricula.save(update_fields=["situacao"])
                        registrar_movimentacao(
                            matricula=matricula,
                            tipo=tipo,
                            usuario=request.user,
                            turma_origem=turma_origem,
                            turma_destino=turma_destino,
                            situacao_anterior=situacao_anterior,
                            situacao_nova=Matricula.Situacao.TRANSFERIDO,
                            motivo=motivo,
                        )
                        nova_matricula = Matricula.objects.create(
                            aluno=aluno,
                            turma=turma_destino,
                            data_matricula=date.today(),
                            situacao=Matricula.Situacao.ATIVA,
                            observacao=(f"Transferência da matrícula #{matricula.pk}. {motivo}".strip()),
                        )
                        registrar_movimentacao(
                            matricula=nova_matricula,
                            tipo=MatriculaMovimentacao.Tipo.CRIACAO,
                            usuario=request.user,
                            turma_origem=turma_origem,
                            turma_destino=turma_destino,
                            situacao_nova=nova_matricula.situacao,
                            motivo="Matrícula de destino criada automaticamente por transferência.",
                        )
                        messages.success(request, "Transferência realizada com sucesso.")
                        return redirect("educacao:aluno_detail", pk=aluno.pk)

                elif tipo == MatriculaMovimentacao.Tipo.CANCELAMENTO:
                    matricula.situacao = Matricula.Situacao.CANCELADO
                    matricula.save(update_fields=["situacao"])
                    registrar_movimentacao(
                        matricula=matricula,
                        tipo=tipo,
                        usuario=request.user,
                        turma_origem=turma_origem,
                        turma_destino=turma_origem,
                        situacao_anterior=situacao_anterior,
                        situacao_nova=matricula.situacao,
                        motivo=motivo,
                    )
                    messages.success(request, "Matrícula cancelada com sucesso.")
                    return redirect("educacao:aluno_detail", pk=aluno.pk)

                elif tipo == MatriculaMovimentacao.Tipo.REATIVACAO:
                    matricula.situacao = Matricula.Situacao.ATIVA
                    matricula.save(update_fields=["situacao"])
                    registrar_movimentacao(
                        matricula=matricula,
                        tipo=tipo,
                        usuario=request.user,
                        turma_origem=turma_origem,
                        turma_destino=turma_origem,
                        situacao_anterior=situacao_anterior,
                        situacao_nova=matricula.situacao,
                        motivo=motivo,
                    )
                    messages.success(request, "Matrícula reativada com sucesso.")
                    return redirect("educacao:aluno_detail", pk=aluno.pk)

                messages.error(request, "Não foi possível concluir a movimentação informada.")

        else:
            messages.error(request, "Ação inválida.")

        # se falhar validação, renderiza de volta com erros
        ctx = self._build_context(
            request,
            aluno,
            form_matricula=form_matricula,
            form_nee=form_nee,
            form_apoio=form_apoio,
            form_movimentacao=form_movimentacao,
        )
        return render(request, self.template_name, ctx)
