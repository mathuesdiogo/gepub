from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from apps.core.decorators import require_perm
from apps.core.rbac import can

from .models import Turma, Matricula


@method_decorator(login_required, name="dispatch")
@method_decorator(require_perm("educacao.view"), name="dispatch")
class TurmaDetailView(View):
    template_name = "educacao/turma_detail.html"

    def get(self, request, pk: int):
        turma = get_object_or_404(
            Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio"),
            pk=pk,
        )

        # Actions
        actions = [
            {"label": "Voltar", "url": reverse("educacao:turma_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
        ]
        if can(request.user, "educacao.manage"):
            actions.append({"label": "Editar", "url": reverse("educacao:turma_update", args=[turma.pk]), "icon": "fa-solid fa-pen", "variant": "btn--ghost"})
            actions.append({"label": "Matricular", "url": reverse("educacao:matricula_create"), "icon": "fa-solid fa-id-card", "variant": "btn--ghost"})

        # Alunos via Matrícula (correto no seu models.py)
        matriculas = (
            Matricula.objects
            .select_related("aluno")
            .filter(turma=turma)
            .order_by("aluno__nome")
        )

        alunos_total = matriculas.count()
        alunos_ativos = matriculas.filter(aluno__ativo=True).count()
        alunos_inativos = matriculas.filter(aluno__ativo=False).count()

        # Professores (ManyToMany em Turma) – existe no seu models.py
        professores_qs = turma.professores.all().order_by("first_name", "last_name", "username")
        professores_total = professores_qs.count()

        # Gráfico de status (pela situacao da Matricula)
        status_aggs = matriculas.values("situacao").annotate(total=Count("id")).order_by("situacao")
        status_labels = [s["situacao"] for s in status_aggs]
        status_values = [s["total"] for s in status_aggs]

        # NEE / evolução (se não existir integração no momento, manda vazio sem quebrar)
        nee_labels, nee_values = [], []
        evol_labels, evol_values = [], []

        # Tabela alunos
        headers_alunos = [
            {"label": "Aluno"},
            {"label": "CPF", "width": "160px"},
            {"label": "NIS", "width": "160px"},
            {"label": "Ativo", "width": "110px"},
            {"label": "Situação", "width": "160px"},
        ]

        rows_alunos = []
        for m in matriculas:
            a = m.aluno
            rows_alunos.append({
                "cells": [
                    {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                    {"text": a.cpf or "—"},
                    {"text": a.nis or "—"},
                    {"text": "Sim" if a.ativo else "Não"},
                    {"text": m.get_situacao_display() if hasattr(m, "get_situacao_display") else m.situacao},
                ],
                "can_edit": False,
                "edit_url": "",
            })

        # Tabela professores
        headers_professores = [
            {"label": "Professor"},
            {"label": "Usuário", "width": "220px"},
        ]

        rows_professores = []
        for u in professores_qs:
            nome = (u.get_full_name() or "").strip() or getattr(u, "nome", "") or u.username
            rows_professores.append({
                "cells": [
                    {"text": nome},
                    {"text": u.username},
                ],
                "can_edit": False,
                "edit_url": "",
            })

        context = {
            "turma": turma,
            "actions": actions,

            "alunos_total": alunos_total,
            "alunos_ativos": alunos_ativos,
            "alunos_inativos": alunos_inativos,
            "professores_total": professores_total,

            "headers_alunos": headers_alunos,
            "rows_alunos": rows_alunos,
            "headers_professores": headers_professores,
            "rows_professores": rows_professores,

            "status_labels": status_labels,
            "status_values": status_values,
            "nee_labels": nee_labels,
            "nee_values": nee_values,
            "evol_labels": evol_labels,
            "evol_values": evol_values,
        }
        return render(request, self.template_name, context)