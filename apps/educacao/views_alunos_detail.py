from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from apps.core.decorators import require_perm
from apps.core.rbac import can

from .models import Aluno, Matricula


@method_decorator(login_required, name="dispatch")
@method_decorator(require_perm("educacao.view"), name="dispatch")
class AlunoDetailView(View):
    template_name = "educacao/aluno_detail.html"

    def get(self, request, pk: int):
        aluno = get_object_or_404(Aluno, pk=pk)

        # Matrículas do aluno (correto: Aluno -> Matricula -> Turma)
        matriculas = (
            Matricula.objects
            .select_related("turma", "turma__unidade", "turma__unidade__secretaria", "turma__unidade__secretaria__municipio")
            .filter(aluno=aluno)
            .order_by("-id")
        )

        # Actions SUAP-like
        actions = [
            {"label": "Voltar", "url": reverse("educacao:aluno_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]
        if can(request.user, "educacao.manage"):
            actions.append({"label": "Editar", "url": reverse("educacao:aluno_update", args=[aluno.pk]), "icon": "fa-solid fa-pen", "variant": "btn--ghost"})
            actions.append({"label": "Matricular", "url": reverse("educacao:matricula_create") + f"?aluno={aluno.pk}", "icon": "fa-solid fa-id-card", "variant": "btn--ghost"})

        # Detail summary (component core)
        fields = [
            ("CPF", aluno.cpf or "—"),
            ("NIS", aluno.nis or "—"),
            ("Data nascimento", aluno.data_nascimento.strftime("%d/%m/%Y") if aluno.data_nascimento else "—"),
            ("Telefone", aluno.telefone or "—"),
            ("E-mail", aluno.email or "—"),
            ("Ativo", "Sim" if aluno.ativo else "Não"),
        ]

        pills = [
            ("Matrículas", matriculas.count()),
        ]

        # Tabela matrículas
        headers_matriculas = [
            {"label": "Turma"},
            {"label": "Ano", "width": "120px"},
            {"label": "Turno", "width": "140px"},
            {"label": "Unidade"},
            {"label": "Situação", "width": "160px"},
        ]

        rows_matriculas = []
        for m in matriculas:
            turma = m.turma
            unidade = getattr(turma, "unidade", None)
            unidade_nome = getattr(unidade, "nome", "—")

            rows_matriculas.append({
                "cells": [
                    {"text": turma.nome, "url": reverse("educacao:turma_detail", args=[turma.pk])},
                    {"text": str(turma.ano_letivo)},
                    {"text": turma.turno},
                    {"text": unidade_nome},
                    {"text": m.get_situacao_display() if hasattr(m, "get_situacao_display") else m.situacao},
                ],
                "can_edit": False,
                "edit_url": "",
            })

        context = {
            "aluno": aluno,
            "actions": actions,
            "fields": fields,
            "pills": pills,
            "headers_matriculas": headers_matriculas,
            "rows_matriculas": rows_matriculas,
        }
        return render(request, self.template_name, context)