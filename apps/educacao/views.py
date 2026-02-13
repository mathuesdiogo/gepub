from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.http import HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.decorators import require_perm
from core.rbac import can, scope_filter_turmas, scope_filter_alunos, scope_filter_matriculas

from .forms import TurmaForm, AlunoForm, MatriculaForm, AlunoCreateComTurmaForm
from .models import Turma, Aluno, Matricula

from nee.forms import AlunoNecessidadeForm, ApoioMatriculaForm
from nee.models import AlunoNecessidade, ApoioMatricula
from django.http import JsonResponse
from accounts.models import Profile



@login_required
@require_perm("educacao.view")
def index(request):
    return render(request, "educacao/index.html")


# -----------------------------
# TURMAS (CRUD)
# -----------------------------

@login_required
@require_perm("educacao.view")
def turma_list(request):
    q = (request.GET.get("q") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    qs = Turma.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
    )

    if ano.isdigit():
        qs = qs.filter(ano_letivo=int(ano))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
            | Q(unidade__secretaria__municipio__nome__icontains=q)
        )

    qs = scope_filter_turmas(request.user, qs)

    # Export (mantém do jeito que já está no seu arquivo)
    from core.exports import export_csv, export_pdf_table
    export = (request.GET.get("export") or "").strip().lower()
    if export in ("csv", "pdf"):
        items = list(
            qs.order_by("-ano_letivo", "nome").values_list(
                "nome",
                "ano_letivo",
                "turno",
                "unidade__nome",
                "unidade__secretaria__nome",
                "unidade__secretaria__municipio__nome",
                "ativo",
            )
        )

        headers_export = ["Turma", "Ano", "Turno", "Unidade", "Secretaria", "Município", "Ativo"]
        rows = []
        for t in page_obj:
            rows.append({
                "cells": [
                    {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                    {"text": str(t.ano_letivo or "—")},
                    {"text": t.get_turno_display() if hasattr(t, "get_turno_display") else "—"},
                    {"text": getattr(getattr(t, "unidade", None), "nome", "—")},
                    {"text": getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "nome", "—")},
                ],
                "can_edit": bool(can_edu_manage and t.pk),
                "edit_url": reverse("educacao:turma_update", args=[t.pk]) if t.pk else "",
            })


        if export == "csv":
            return export_csv("turmas.csv", headers_export, rows_export)

        filtros = f"Ano={ano or '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="turmas.pdf",
            title="Relatório — Turmas",
            headers=headers_export,
            rows=rows_export,
            filtros=filtros,
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    can_edu_manage = can(request.user, "educacao.manage")

    # Actions do header
    # mantém filtros atuais na query (q + ano)
    qs_query = []
    if q:
        qs_query.append(f"q={q}")
    if ano:
        qs_query.append(f"ano={ano}")
    base_query = "&".join(qs_query)

    def qjoin(extra: str) -> str:
        return f"?{base_query + ('&' if base_query else '')}{extra}"

    actions = [
        {
            "label": "Exportar CSV",
            "url": qjoin("export=csv"),
            "icon": "fa-solid fa-file-csv",
            "variant": "btn--ghost",
        },
        {
            "label": "Exportar PDF",
            "url": qjoin("export=pdf"),
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
    ]
    if can_edu_manage:
        actions.append(
            {
                "label": "Nova Turma",
                "url": reverse("educacao:turma_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

        headers = [
        {"label": "Turma"},
        {"label": "Ano", "width": "110px"},
        {"label": "Turno", "width": "140px"},
        {"label": "Unidade"},
        {"label": "Secretaria"},
    ]

    rows = []
    for t in page_obj:
        rows.append({
            "cells": [
                {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                {"text": str(t.ano_letivo or "—")},
                {"text": t.get_turno_display() if hasattr(t, "get_turno_display") else "—"},
                {"text": getattr(getattr(t, "unidade", None), "nome", "—")},
                {"text": getattr(getattr(getattr(t, "unidade", None), "secretaria", None), "nome", "—")},
            ],
            "can_edit": bool(can_edu_manage and t.pk),
            "edit_url": reverse("educacao:turma_update", args=[t.pk]) if t.pk else "",
        })


    # Filtros extras (campo Ano) — HTML pronto e seguro
    extra_filters = f"""
      <div class="filter-bar__field" style="min-width:160px; flex:0 0 180px;">
        <label class="small">Ano letivo</label>
        <input name="ano" value="{ano}" placeholder="Ex.: 2026" />
      </div>
    """

    return render(
        request,
        "educacao/turma_list.html",
        {
            "q": q,
            "ano": ano,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("educacao:turma_list"),
            "clear_url": reverse("educacao:turma_list"),
            "has_filters": bool(ano),
            "extra_filters": extra_filters,
        },
    )
@login_required
@require_perm("educacao.view")
def matricula_create(request):
    if not can(request.user, "educacao.manage"):
        messages.error(request, "Você não tem permissão para realizar matrículas.")
        return redirect("educacao:index")

    q = (request.GET.get("q") or "").strip()
    aluno_id = (request.GET.get("aluno") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()

    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    turmas_base_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related("unidade", "unidade__secretaria", "unidade__secretaria__municipio")
    )

    # ---- busca de aluno (somente para selecionar) ----
    alunos_result = alunos_qs
    if q:
        alunos_result = alunos_result.filter(
            Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(nis__icontains=q) | Q(nome_mae__icontains=q)
        )
    alunos_result = alunos_result.order_by("nome")[:25]

    # ---- initial do form ----
    initial = {}
    if aluno_id.isdigit():
        initial["aluno"] = int(aluno_id)
    if unidade_id.isdigit():
        initial["unidade"] = int(unidade_id)

    form = MatriculaForm(request.POST or None, initial=initial)

    # limitar aluno ao escopo
    if "aluno" in form.fields:
        form.fields["aluno"].queryset = alunos_qs.order_by("nome")

    # ✅ Unidade (escola): filtra turmas
    # Se seu MatriculaForm NÃO tem o campo "unidade", você precisa adicionar no form (eu te passo já já).
    if "unidade" in form.fields:
        # opcional: restringir unidades via turmas_base_qs (somente unidades que aparecem no escopo)
        unidades_ids = turmas_base_qs.values_list("unidade_id", flat=True).distinct()
        form.fields["unidade"].queryset = form.fields["unidade"].queryset.filter(id__in=unidades_ids)

    turmas_qs = turmas_base_qs
    unidade_selecionada = None

    # pega unidade do POST primeiro (quando o usuário escolhe no form)
    unidade_sel = (request.POST.get("unidade") or unidade_id or "").strip()
    if unidade_sel.isdigit():
        unidade_selecionada = int(unidade_sel)
        turmas_qs = turmas_qs.filter(unidade_id=unidade_selecionada)

    if "turma" in form.fields:
        form.fields["turma"].queryset = turmas_qs.order_by("-ano_letivo", "nome")

    # ---- salvar ----
    if request.method == "POST":
        if form.is_valid():
            m = form.save(commit=False)

            if not alunos_qs.filter(pk=m.aluno_id).exists():
                messages.error(request, "Aluno fora do seu escopo.")
                return redirect("educacao:matricula_create")

            # proteção turma escopo (já filtrada, mas garante)
            if not turmas_base_qs.filter(pk=m.turma_id).exists():
                messages.error(request, "Turma fora do seu escopo.")
                return redirect("educacao:matricula_create")

            if Matricula.objects.filter(aluno=m.aluno, turma=m.turma).exists():
                messages.warning(request, "Esse aluno já possui matrícula nessa turma.")
            else:
                m.save()
                messages.success(request, "Matrícula realizada com sucesso.")
                return redirect(reverse("educacao:matricula_create") + f"?aluno={m.aluno_id}")

    # ---- lista de alunos (para selecionar) ----
    headers = [
        {"label": "Aluno"},
        {"label": "CPF", "width": "160px"},
        {"label": "NIS", "width": "160px"},
    ]

    rows = []
    for a in alunos_result:
        url = reverse("educacao:matricula_create") + f"?q={q}&aluno={a.pk}"
        if unidade_id:
            url += f"&unidade={unidade_id}"
        rows.append({
            "cells": [
                {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                {"text": a.cpf or "—", "url": ""},
                {"text": a.nis or "—", "url": ""},
            ],
            "can_edit": True,
            "edit_url": url,
        })

    actions = []

    return render(request, "educacao/matricula_create.html", {
        "q": q,
        "unidade": unidade_id,
        "alunos_result": alunos_result,
        "page_obj": None,
        "headers": headers,
        "rows": rows,
        "actions": actions,
        "action_url": reverse("educacao:matricula_create"),
        "clear_url": reverse("educacao:matricula_create"),
        "has_filters": bool(q),
        "form": form,
        "actions_partial": "educacao/partials/matricula_pick_action.html",
    })

    
    
    
@require_perm("educacao.view")
@login_required
def turma_detail(request, pk):
    turma_qs = scope_filter_turmas(
        request.user,
        Turma.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        )
    )
    turma = get_object_or_404(turma_qs, pk=pk)

    matriculas_qs = (
        Matricula.objects
        .filter(turma_id=turma.id)
        .select_related("aluno")
        .order_by("aluno__nome")
    )

    alunos = [m.aluno for m in matriculas_qs]
    alunos_total = len(alunos)

    alunos_ativos = (
        Matricula.objects
        .filter(turma_id=turma.id, aluno__ativo=True)
        .values("aluno_id").distinct().count()
    )
    alunos_inativos = (
        Matricula.objects
        .filter(turma_id=turma.id, aluno__ativo=False)
        .values("aluno_id").distinct().count()
    )

    professores = []
    professores_total = 0
    if any(getattr(f, "name", None) == "unidade" for f in Profile._meta.get_fields()):
        professores_qs = (
            Profile.objects
            .filter(unidade_id=turma.unidade_id, role="PROFESSOR")
            .select_related("user")
            .order_by("user__username")
        )
        professores = professores_qs
        professores_total = professores_qs.count()

    necessidades_rows = list(
        Matricula.objects
        .filter(
            turma_id=turma.id,
            aluno__necessidades__ativo=True,
            aluno__necessidades__tipo__ativo=True,
        )
        .values("aluno__necessidades__tipo__nome")
        .annotate(total=Count("aluno_id", distinct=True))
        .order_by("-total", "aluno__necessidades__tipo__nome")
    )

    nee_labels = [r["aluno__necessidades__tipo__nome"] for r in necessidades_rows]
    nee_values = [r["total"] for r in necessidades_rows]

    evol_rows = list(
        Turma.objects
        .filter(unidade_id=turma.unidade_id, nome=turma.nome)
        .values("ano_letivo")
        .annotate(total=Count("matriculas__aluno_id", distinct=True))
        .order_by("ano_letivo")
    )
    evol_labels = [str(r["ano_letivo"]) for r in evol_rows]
    evol_values = [r["total"] for r in evol_rows]

    ctx = {
        "turma": turma,
        "alunos_total": alunos_total,
        "professores_total": professores_total,
        "alunos_ativos": alunos_ativos,
        "alunos_inativos": alunos_inativos,
        "alunos": alunos,
        "professores": professores,
        "nee_labels": nee_labels,
        "nee_values": nee_values,
        "status_labels": ["Ativos", "Inativos"],
        "status_values": [alunos_ativos, alunos_inativos],
        "evol_labels": evol_labels,
        "evol_values": evol_values,
    }

    return render(request, "educacao/turma_detail.html", ctx)


@login_required
@require_perm("educacao.manage")
def turma_create(request):
    if request.method == "POST":
        form = TurmaForm(request.POST, user=request.user)
        if form.is_valid():
            turma = form.save()
            messages.success(request, "Turma criada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm(user=request.user)

    return render(request, "educacao/turma_form.html", {"form": form, "mode": "create"})


@login_required
@require_perm("educacao.manage")
def turma_update(request, pk: int):
    qs = Turma.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
    )
    qs = scope_filter_turmas(request.user, qs)
    turma = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = TurmaForm(request.POST, instance=turma, user=request.user)
        if form.is_valid():
            turma = form.save()
            messages.success(request, "Turma atualizada com sucesso.")
            return redirect("educacao:turma_detail", pk=turma.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = TurmaForm(instance=turma, user=request.user)

    return render(request, "educacao/turma_form.html", {"form": form, "mode": "update", "turma": turma})


# -----------------------------
# ALUNOS (CRUD)
# -----------------------------

@login_required
@require_perm("educacao.view")
def aluno_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = Aluno.objects.all()

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(nis__icontains=q)
            | Q(nome_mae__icontains=q)
        )

    qs = scope_filter_alunos(request.user, qs)

    # Export mantém igual (já está ótimo)
    from core.exports import export_csv, export_pdf_table
    export = (request.GET.get("export") or "").strip().lower()

    if export in ("csv", "pdf"):
        items = list(qs.order_by("nome").values_list("nome", "cpf", "nis", "ativo"))
        headers_export = ["Nome", "CPF", "NIS", "Ativo"]
        rows_export = [
            [nome or "", cpf or "", nis or "", "Sim" if ativo else "Não"]
            for (nome, cpf, nis, ativo) in items
        ]

        if export == "csv":
            return export_csv("alunos.csv", headers_export, rows_export)

        filtros = f"Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="alunos.pdf",
            title="Relatório — Alunos",
            headers=headers_export,
            rows=rows_export,
            filtros=filtros,
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # flags pro template (antes você usava can_edu_manage no template, mas não passava aqui)
    can_edu_manage = can(request.user, "educacao.manage")

    # actions do PageHead
    base_q = f"q={q}" if q else ""
    actions = [
        {
            "label": "Exportar CSV",
            "url": f"?{base_q + ('&' if base_q else '')}export=csv",
            "icon": "fa-solid fa-file-csv",
            "variant": "btn--ghost",
        },
        {
            "label": "Exportar PDF",
            "url": f"?{base_q + ('&' if base_q else '')}export=pdf",
            "icon": "fa-solid fa-file-pdf",
            "variant": "btn--ghost",
        },
    ]
    if can_edu_manage:
        actions.append(
            {
                "label": "Novo Aluno",
                "url": reverse("educacao:aluno_create"),
                "icon": "fa-solid fa-plus",
                "variant": "btn-primary",
            }
        )

    headers = [
        {"label": "Nome"},
        {"label": "CPF", "width": "160px"},
        {"label": "NIS", "width": "160px"},
        {"label": "Ativo", "width": "140px"},
    ]

    rows = []
    for a in page_obj:
        rows.append({
            "cells": [
                {"text": a.nome, "url": reverse("educacao:aluno_detail", args=[a.pk])},
                {"text": a.cpf or "—"},
                {"text": a.nis or "—"},
                {"text": "Sim" if a.ativo else "Não"},
            ],
            "can_edit": bool(can_edu_manage and a.pk),
            "edit_url": reverse("educacao:aluno_update", args=[a.pk]) if a.pk else "",
        })



    return render(
        request,
        "educacao/aluno_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("educacao:aluno_list"),
            "clear_url": reverse("educacao:aluno_list"),
        },
    )


@login_required
@require_perm("educacao.view")
def aluno_detail(request, pk: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    try:
        aluno = get_object_or_404(aluno_qs, pk=pk)
    except Http404:
        recent = request.session.get("recent_alunos", [])
        if pk in recent and can(request.user, "educacao.manage"):
            aluno = get_object_or_404(Aluno.objects.all(), pk=pk)
            if Matricula.objects.filter(aluno=aluno).exists():
                raise
        else:
            raise

    # ---------------------------
    # Permissões para o template
    # ---------------------------
    can_edu_manage = can(request.user, "educacao.manage")
    # Use a permissão que você já usa no seu RBAC para NEE.
    # Se no seu projeto a perm é "nee.manage", mantém assim.
    can_nee_manage = can(request.user, "nee.manage") or can_edu_manage

    matriculas_qs = (
        Matricula.objects.select_related(
            "aluno",
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        )
        .filter(aluno=aluno)
        .order_by("-id")
    )
    matriculas_qs = scope_filter_matriculas(request.user, matriculas_qs)
    matriculas = matriculas_qs

    necessidades = (
        AlunoNecessidade.objects.select_related("tipo")
        .filter(aluno=aluno)
        .order_by("-id")
    )

    apoios_qs = (
        ApoioMatricula.objects.select_related(
            "matricula",
            "matricula__turma",
            "matricula__turma__unidade",
            "matricula__turma__unidade__secretaria",
            "matricula__turma__unidade__secretaria__municipio",
        )
        .filter(matricula__aluno=aluno)
        .order_by("-id")
    )

    allowed_matriculas = scope_filter_matriculas(
        request.user, Matricula.objects.filter(aluno=aluno)
    ).values_list("id", flat=True)

    apoios = apoios_qs.filter(matricula_id__in=allowed_matriculas)

    if request.method == "POST":
        action = (request.POST.get("_action") or "").strip()

        if action in {"add_matricula", "add_nee", "add_apoio"} and not can_edu_manage:
            return HttpResponseForbidden("403 — Você não tem permissão para alterar dados de Educação.")

        if action == "add_matricula":
            form_matricula = MatriculaForm(request.POST, user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)

            if form_matricula.is_valid():
                m = form_matricula.save(commit=False)
                m.aluno = aluno

                turma_ok = scope_filter_turmas(
                    request.user, Turma.objects.filter(pk=m.turma_id)
                ).exists()
                if not turma_ok:
                    return HttpResponseForbidden("403 — Turma fora do seu escopo.")

                if not m.data_matricula:
                    m.data_matricula = timezone.localdate()
                m.save()

                recent = request.session.get("recent_alunos", [])
                if aluno.pk in recent:
                    recent.remove(aluno.pk)
                    request.session["recent_alunos"] = recent
                    request.session.modified = True

                messages.success(request, "Matrícula adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros da matrícula.")

        elif action == "add_nee":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)

            if form_nee.is_valid():
                nee = form_nee.save(commit=False)
                nee.aluno = aluno
                nee.save()
                messages.success(request, "Necessidade adicionada com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros da necessidade.")

        elif action == "add_apoio":
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(aluno=aluno)
            form_apoio = ApoioMatriculaForm(request.POST, aluno=aluno)

            if form_apoio.is_valid():
                apoio = form_apoio.save(commit=False)

                matricula_ok = scope_filter_matriculas(
                    request.user,
                    Matricula.objects.filter(pk=apoio.matricula_id, aluno=aluno),
                ).exists()
                if not matricula_ok:
                    return HttpResponseForbidden("403 — Matrícula fora do seu escopo.")

                apoio.save()
                messages.success(request, "Apoio adicionado com sucesso.")
                return redirect("educacao:aluno_detail", pk=aluno.pk)

            messages.error(request, "Corrija os erros do apoio.")

        else:
            form_matricula = MatriculaForm(user=request.user)
            form_nee = AlunoNecessidadeForm(request.POST, aluno=aluno)
            form_apoio = ApoioMatriculaForm(aluno=aluno)
            messages.error(request, "Ação inválida.")
    else:
        form_matricula = MatriculaForm(user=request.user)
        form_nee = AlunoNecessidadeForm(aluno=aluno)
        form_apoio = ApoioMatriculaForm(aluno=aluno)

    return render(
        request,
        "educacao/aluno_detail.html",
        {
            "aluno": aluno,
            "matriculas": matriculas,
            "form_matricula": form_matricula,

            # NEE
            "necessidades": necessidades,
            "form_nee": form_nee,

            # Apoios (acompanhamentos)
            "apoios": apoios,
            "acompanhamentos": apoios,  # ✅ alias pro template se ele usa esse nome
            "form_apoio": form_apoio,
            "allowed_matriculas": list(allowed_matriculas),

            # Flags de permissão pro template mostrar botões
            "can_edu_manage": can_edu_manage,
            "can_nee_manage": can_nee_manage,
        },
    )



@login_required
@require_perm("educacao.manage")
def aluno_create(request):
    if request.method == "POST":
        form = AlunoCreateComTurmaForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                turma = form.cleaned_data["turma"]
                aluno = form.save()

                Matricula.objects.create(
                    aluno=aluno,
                    turma=turma,
                    data_matricula=timezone.localdate(),
                    situacao=Matricula.Situacao.ATIVA,
                )

            messages.success(request, "Aluno criado e matriculado com sucesso.")
            return redirect("educacao:aluno_detail", pk=aluno.pk)

        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AlunoCreateComTurmaForm(user=request.user)

    return render(request, "educacao/aluno_form.html", {"form": form, "mode": "create"})


@login_required
@require_perm("educacao.manage")
def aluno_update(request, pk: int):
    aluno_qs = scope_filter_alunos(request.user, Aluno.objects.all())
    aluno = get_object_or_404(aluno_qs, pk=pk)

    if request.method == "POST":
        form = AlunoForm(request.POST, instance=aluno)
        if form.is_valid():
            form.save()
            messages.success(request, "Aluno atualizado com sucesso.")
            return redirect("educacao:aluno_detail", pk=aluno.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = AlunoForm(instance=aluno)

    return render(
        request,
        "educacao/aluno_form.html",
        {"form": form, "mode": "update", "aluno": aluno},
    )


@login_required
@require_perm("educacao.view")
def api_alunos_suggest(request):
    if not can(request.user, "educacao.manage"):
        return JsonResponse({"results": []})

    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    alunos_qs = scope_filter_alunos(request.user, Aluno.objects.all())

    qs = alunos_qs.filter(
        Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(nis__icontains=q)
    ).order_by("nome")[:10]

    results = []
    for a in qs:
        results.append({
            "id": a.id,
            "nome": a.nome,
            "cpf": a.cpf or "",
            "nis": a.nis or "",
        })

    return JsonResponse({"results": results})
