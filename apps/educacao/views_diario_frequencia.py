from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.exports import export_pdf_table
from apps.core.rbac import scope_filter_turmas

from .models import Turma, Matricula
from .models_diario import Aula, Frequencia
from .views_diario_permissions import can_edit_diario, can_view_diario


def aula_frequencia_impl(request, pk: int, aula_id: int):
    aula = get_object_or_404(
        Aula.objects.select_related(
            "diario",
            "diario__turma",
            "diario__professor",
            "diario__turma__unidade",
        ),
        pk=aula_id,
        diario_id=pk,
    )
    diario = aula.diario

    if not can_view_diario(request.user, diario):
        return HttpResponseForbidden("403 — Você não tem permissão para acessar esta aula.")

    can_edit = can_edit_diario(request.user, diario)
    q = (request.GET.get("q") or "").strip()

    alunos_qs = (
        Matricula.objects.filter(turma=diario.turma, situacao="ATIVA")
        .select_related("aluno")
        .order_by("aluno__nome")
    )

    if q:
        alunos_qs = alunos_qs.filter(
            Q(aluno__nome__icontains=q)
            | Q(aluno__cpf__icontains=q)
            | Q(aluno__nis__icontains=q)
        )

    freq_map = {f.aluno_id: f.status for f in aula.frequencias.all()}

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("403 — Somente o professor responsável pode lançar frequência.")

        for m in alunos_qs:
            status = (request.POST.get(f"aluno_{m.aluno_id}") or "P").strip()
            Frequencia.objects.update_or_create(
                aula=aula,
                aluno=m.aluno,
                defaults={"status": status},
            )

        messages.success(request, "Frequência salva com sucesso.")
        base = reverse("educacao:aula_frequencia", args=[diario.pk, aula.pk])
        return redirect(f"{base}?q={q}" if q else base)

    export = (request.GET.get("export") or "").strip().lower()
    if export == "pdf":
        headers = ["Aluno", "Status"]
        rows = []
        for m in alunos_qs:
            st = freq_map.get(m.aluno_id, "P")
            label = dict(Frequencia.Status.choices).get(st, "Presente")
            rows.append([m.aluno.nome, label])

        filtros = f"Turma={diario.turma.nome} | Data={aula.data.strftime('%d/%m/%Y') if aula.data else '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="frequencia_aula.pdf",
            title="Frequência — Aula",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("educacao:diario_detail", args=[diario.pk]),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        },
        {
            "label": "Imprimir PDF",
            "url": (reverse("educacao:aula_frequencia", args=[diario.pk, aula.pk]) + ("?q=" + q + "&" if q else "?") + "export=pdf"),
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
    ]
    if can_edit:
        actions.append(
            {
                "label": "Salvar Frequência",
                "url": "#freq-form",
                "icon": "fa-solid fa-check",
                "variant": "btn-primary",
            }
        )

    alunos_render = []
    for m in alunos_qs:
        alunos_render.append(
            {
                "id": m.aluno_id,
                "nome": m.aluno.nome,
                "status": freq_map.get(m.aluno_id, "P"),
            }
        )

    base_url = reverse("educacao:aula_frequencia", args=[diario.pk, aula.pk])

    return render(
        request,
        "educacao/aula_frequencia.html",
        {
            "aula": aula,
            "diario": diario,
            "alunos_render": alunos_render,
            "can_edit": can_edit,
            "actions": actions,
            "q": q,
            "action_url": base_url,
            "clear_url": base_url,
            "has_filters": bool(q),
            "autocomplete_url": reverse("educacao:api_alunos_turma_suggest", args=[diario.turma.pk]),
            "autocomplete_href": base_url + "?q={q}",
        },
    )


def api_alunos_turma_suggest_impl(request, pk: int):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    turma_qs = scope_filter_turmas(request.user, Turma.objects.all())
    turma = get_object_or_404(turma_qs, pk=pk)

    alunos_qs = (
        Matricula.objects.filter(turma=turma, situacao="ATIVA")
        .select_related("aluno")
        .filter(
            Q(aluno__nome__icontains=q)
            | Q(aluno__cpf__icontains=q)
            | Q(aluno__nis__icontains=q)
        )
        .order_by("aluno__nome")[:10]
    )

    results = []
    for m in alunos_qs:
        a = m.aluno
        results.append({
            "id": a.id,
            "text": a.nome,
            "meta": (a.cpf or a.nis or ""),
        })

    return JsonResponse({"results": results})
