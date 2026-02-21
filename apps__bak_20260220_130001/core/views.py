from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils import timezone
from django.urls import reverse
import json

from apps.accounts.models import Profile
from apps.core.rbac import can, get_profile, is_admin

from apps.org.models import Municipio, Secretaria, Unidade, Setor
from apps.educacao.models import Turma, Aluno, Matricula

from apps.core.rbac import (
    scope_filter_secretarias,
    scope_filter_unidades,
    scope_filter_turmas,
    scope_filter_alunos,
    scope_filter_matriculas,
)

from .forms import AlunoAvisoForm, AlunoArquivoForm
from .models import AlunoAviso, AlunoArquivo


# =========================================================
# ATALHOS POR CÓDIGO (NOVO)
# =========================================================
# Regras:
# - code: string do código digitado (ex: "201")
# - label: aparece em mensagens/ajuda
# - url_name: nome da URL (reverse)
# - perm: (opcional) permissão RBAC exigida para redirecionar
# - args/kwargs: (opcional) para reverse
CODE_ROUTES = {
    # Core
    "101": {"label": "Dashboard", "url_name": "core:dashboard"},

    # Organização
    "201": {"label": "Municípios", "url_name": "org:municipio_list", "perm": "org.view"},
    "202": {"label": "Secretarias", "url_name": "org:secretaria_list", "perm": "org.view"},
    "203": {"label": "Unidades", "url_name": "org:unidade_list", "perm": "org.view"},
    "204": {"label": "Setores", "url_name": "org:setor_list", "perm": "org.view"},

    # Educação
    "301": {"label": "Alunos", "url_name": "educacao:aluno_list", "perm": "educacao.view"},
    "302": {"label": "Turmas", "url_name": "educacao:turma_list", "perm": "educacao.view"},
    "303": {"label": "Nova Matrícula", "url_name": "educacao:matricula_create", "perm": "educacao.manage"},

    # NEE
    "501": {"label": "NEE • Tipos", "url_name": "nee:tipo_list", "perm": "nee.view"},
    "502": {"label": "NEE • Relatórios", "url_name": "nee:relatorios_index", "perm": "nee.view"},

    # ✅ EXEMPLO (quando você souber o nome real da URL):
    # "401": {"label": "Alterar senha", "url_name": "accounts:alterar_senha", "perm": "accounts.view"},
}


def _resolve_code_to_url(user, code: str):
    """
    Retorna URL (str) se o código existir e o usuário puder acessar.
    Caso contrário, retorna None.
    """
    if not code:
        return None

    code = (code or "").strip().upper()
    # aceita "401", "#401", "COD401" etc. — você pode padronizar como quiser
    if code.startswith("#"):
        code = code[1:]
    if code.startswith("COD"):
        code = code[3:].strip()

    entry = CODE_ROUTES.get(code)
    if not entry:
        return None

    perm = entry.get("perm")
    if perm and not (can(user, perm) or is_admin(user) or getattr(user, "is_superuser", False) or getattr(user, "is_staff", False)):
        return None

    try:
        return reverse(entry["url_name"], args=entry.get("args", None), kwargs=entry.get("kwargs", None))
    except Exception:
        return None


@login_required
def go_code(request, codigo: str = ""):
    """
    Recebe o código via:
    - /go/<codigo>/
    - /go/?c=<codigo>
    Redireciona para a tela.
    """
    code = (codigo or request.GET.get("c") or request.POST.get("c") or "").strip()
    url = _resolve_code_to_url(request.user, code)

    if url:
        return redirect(url)

    # fallback: mostra erro e lista códigos disponíveis (sem template novo)
    messages.error(request, "Código inválido ou sem permissão para acessar.")
    # Opcional: se quiser, volta para o referer
    back = request.META.get("HTTP_REFERER")
    return redirect(back or "core:dashboard")


# =========================================================
# SEU CÓDIGO ATUAL (dashboard_view, aviso_create, arquivo_create)
# =========================================================
def _portal_manage_allowed(user) -> bool:
    return bool(
        can(user, "educacao.manage")
        or can(user, "org.manage_unidade")
        or can(user, "org.manage_secretaria")
        or can(user, "org.manage_municipio")
        or (get_profile(user) and get_profile(user).role == "PROFESSOR")
        or is_admin(user)
        or getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
    )

@login_required
def guia_telas(request):
    q = (request.GET.get("q") or "").strip()

    # ---------- Actions (PageHead) ----------
    actions = [
        {
            "label": "Voltar",
            "url": reverse("core:dashboard"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    # ---------- TableShell ----------
    headers = [
        {"label": "Código", "width": "120px"},
        {"label": "Tela"},
        {"label": "Módulo", "width": "160px"},
    ]

    rows = []
    # ordena por número quando possível
    def _sort_key(item):
        code = item[0]
        try:
            return int(code)
        except Exception:
            return 999999

    for code, entry in sorted(CODE_ROUTES.items(), key=_sort_key):
        url = _resolve_code_to_url(request.user, code)
        if not url:
            continue  # sem permissão ou inválido

        label = entry.get("label") or "—"
        url_name = entry.get("url_name") or ""
        modulo = (url_name.split(":")[0] if ":" in url_name else "core").upper()

        # filtro de busca (por código, label ou módulo)
        if q:
            hay = f"{code} {label} {modulo} {url_name}".lower()
            if q.lower() not in hay:
                continue

        rows.append({
            "cells": [
                {"text": code, "url": url},
                {"text": label, "url": url},
                {"text": modulo, "url": url},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    action_url = reverse("core:guia_telas")
    clear_url = reverse("core:guia_telas")
    has_filters = bool(q)

    return render(request, "core/guia_telas.html", {
        "actions": actions,
        "q": q,
        "action_url": action_url,
        "clear_url": clear_url,
        "has_filters": has_filters,
        "headers": headers,
        "rows": rows,
    })


@login_required
def dashboard_view(request):
    user = request.user
    p = get_profile(user)

    base_ctx = {
        "page_title": "Dashboard",
        "page_subtitle": "Visão geral",
    }

    # =========================
    # ADMIN
    # =========================
    if is_admin(user) or getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        kpis = {
            "municipios": Municipio.objects.count(),
            "usuarios": User.objects.count(),
            "secretarias": Secretaria.objects.count(),
            "unidades": Unidade.objects.count(),
            "setores": Setor.objects.count(),
            "turmas": Turma.objects.count(),
            "alunos": Aluno.objects.count(),
            "matriculas": Matricula.objects.count(),
        }

        roles_qs = Profile.objects.values("role").annotate(total=Count("id")).order_by("-total")
        role_labels = [r["role"] or "SEM_ROLE" for r in roles_qs]
        role_values = [r["total"] for r in roles_qs]
        chart_roles = {"labels": json.dumps(role_labels), "values": json.dumps(role_values)}

        unidades_por_municipio = list(
            Unidade.objects.values("secretaria__municipio_id", "secretaria__municipio__nome")
            .annotate(unidades=Count("id"))
            .order_by("-unidades")[:10]
        )

        secretarias_por_municipio = list(
            Secretaria.objects.values("municipio_id", "municipio__nome")
            .annotate(secretarias=Count("id"))
        )
        sec_map = {r["municipio_id"]: r["secretarias"] for r in secretarias_por_municipio}

        top_municipios = []
        for r in unidades_por_municipio:
            mid = r["secretaria__municipio_id"]
            top_municipios.append({
                "id": mid,
                "nome": r["secretaria__municipio__nome"] or "—",
                "secretarias": sec_map.get(mid, 0),
                "unidades": r["unidades"],
            })

        top_unidades_raw = list(
            Turma.objects.values("unidade_id", "unidade__nome")
            .annotate(turmas=Count("id"))
            .order_by("-turmas", "unidade__nome")[:10]
        )
        top_unidades = [{"id": r["unidade_id"], "nome": r["unidade__nome"] or "—", "turmas": r["turmas"]} for r in top_unidades_raw]

        chart_municipios = {
            "labels": json.dumps([m["nome"] for m in top_municipios]),
            "values": json.dumps([m["unidades"] for m in top_municipios]),
        }

        ctx = {
            **base_ctx,
            "page_subtitle": "Visão geral do sistema",
            "dash_template": "core/dashboards/partials/admin.html",
            "kpis": kpis,
            "chart_roles": chart_roles,
            "chart_municipios": chart_municipios,
            "top_municipios": top_municipios,
            "top_unidades": top_unidades,
            "can_nee": True,
            "can_users": True,
            "ultimos_municipios": Municipio.objects.order_by("-id")[:5],
        }
        return render(request, "core/dashboard.html", ctx)

    # Sem profile ou inativo
    if not p or not getattr(p, "ativo", True):
        return render(request, "core/dashboard.html", {**base_ctx, "dash_template": "core/dashboards/partials/default.html"})

    role = (p.role or "").upper()

    # =========================
    # ALUNO
    # =========================
    if role == "ALUNO":
        if not getattr(p, "aluno_id", None):
            return render(request, "core/dashboard.html", {
                **base_ctx,
                "page_subtitle": "Meu painel",
                "dash_template": "core/dashboards/partials/aluno.html",
                "sem_vinculo": True,
                "avisos": [],
                "arquivos": [],
            })

        aluno_id = p.aluno_id

        matriculas = Matricula.objects.select_related(
            "turma",
            "turma__unidade",
            "turma__unidade__secretaria",
            "turma__unidade__secretaria__municipio",
        ).filter(aluno_id=aluno_id)

        turma_ids = list(matriculas.values_list("turma_id", flat=True))
        unidade_ids = list(matriculas.values_list("turma__unidade_id", flat=True))
        secretaria_ids = list(matriculas.values_list("turma__unidade__secretaria_id", flat=True))
        municipio_ids = list(matriculas.values_list("turma__unidade__secretaria__municipio_id", flat=True))

        avisos = (
            AlunoAviso.objects.filter(ativo=True)
            .filter(
                Q(aluno_id=aluno_id)
                | Q(turma_id__in=turma_ids)
                | Q(unidade_id__in=unidade_ids)
                | Q(secretaria_id__in=secretaria_ids)
                | Q(municipio_id__in=municipio_ids)
            )
            .select_related("autor")
            .order_by("-criado_em")[:20]
        )

        arquivos = (
            AlunoArquivo.objects.filter(ativo=True)
            .filter(
                Q(aluno_id=aluno_id)
                | Q(turma_id__in=turma_ids)
                | Q(unidade_id__in=unidade_ids)
                | Q(secretaria_id__in=secretaria_ids)
                | Q(municipio_id__in=municipio_ids)
            )
            .select_related("autor")
            .order_by("-criado_em")[:20]
        )

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Meu painel",
            "dash_template": "core/dashboards/partials/aluno.html",
            "sem_vinculo": False,
            "avisos": avisos,
            "arquivos": arquivos,
        })

    # =========================
    # PROFESSOR
    # =========================
    if role == "PROFESSOR":
        ano_atual = timezone.now().date().year
        turmas_qs = scope_filter_turmas(user, Turma.objects.all()).select_related("unidade").order_by("-ano_letivo", "nome")
        alunos_total = Matricula.objects.filter(turma__in=turmas_qs).values("aluno_id").distinct().count()

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Minhas turmas e alunos",
            "dash_template": "core/dashboards/partials/professor.html",
            "turmas": turmas_qs.filter(ano_letivo=ano_atual)[:8],
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_total,
            "ano_atual": ano_atual,
        })

    # =========================
    # MUNICIPAL
    # =========================
    if role == "MUNICIPAL":
        secretarias_qs = scope_filter_secretarias(user, Secretaria.objects.all()).select_related("municipio")
        unidades_qs = scope_filter_unidades(user, Unidade.objects.all()).select_related("secretaria", "secretaria__municipio")

        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        matriculas_qs = scope_filter_matriculas(user, Matricula.objects.all())
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())

        graf_unidades_por_secretaria = list(
            Unidade.objects.filter(secretaria__in=secretarias_qs)
            .values("secretaria__nome").annotate(total=Count("id")).order_by("-total")[:8]
        )
        graf_alunos_por_secretaria = list(
            Matricula.objects.filter(turma__unidade__secretaria__in=secretarias_qs)
            .values("turma__unidade__secretaria__nome")
            .annotate(total=Count("aluno", distinct=True))
            .order_by("-total")[:8]
        )

        ctx = {
            **base_ctx,
            "page_subtitle": "Visão municipal",
            "dash_template": "core/dashboards/partials/municipal.html",
            "municipio_nome": getattr(p.municipio, "nome", "—") if getattr(p, "municipio_id", None) else "—",
            "secretarias_total": secretarias_qs.count(),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),
            "ultimas_secretarias": secretarias_qs.order_by("-id")[:5],
            "ultimos_alunos": alunos_qs.prefetch_related("matriculas__turma__unidade").order_by("-id")[:5],
            "chart1_labels": [i["secretaria__nome"] for i in graf_unidades_por_secretaria],
            "chart1_values": [i["total"] for i in graf_unidades_por_secretaria],
            "chart2_labels": [i["turma__unidade__secretaria__nome"] for i in graf_alunos_por_secretaria],
            "chart2_values": [i["total"] for i in graf_alunos_por_secretaria],
        }
        return render(request, "core/dashboard.html", ctx)

    # =========================
    # SECRETARIA
    # =========================
    if role == "SECRETARIA":
        unidades_qs = scope_filter_unidades(user, Unidade.objects.all()).select_related("secretaria")
        turmas_qs = scope_filter_turmas(user, Turma.objects.all())
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())

        graf_turmas_por_unidade = list(
            turmas_qs.values("unidade__nome").annotate(total=Count("id")).order_by("-total")[:8]
        )

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Visão da secretaria",
            "dash_template": "core/dashboards/partials/secretaria.html",
            "secretaria_nome": getattr(getattr(p, "secretaria", None), "nome", "—"),
            "unidades_total": unidades_qs.count(),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "unidades": unidades_qs.order_by("nome")[:10],
            "graf_turmas_por_unidade": graf_turmas_por_unidade,
        })

    # =========================
    # UNIDADE
    # =========================
    if role == "UNIDADE":
        turmas_qs = scope_filter_turmas(user, Turma.objects.all()).select_related("unidade")
        alunos_qs = scope_filter_alunos(user, Aluno.objects.all())
        matriculas_qs = scope_filter_matriculas(user, Matricula.objects.all()).select_related("turma")

        graf_matriculas_por_turma = list(
            matriculas_qs.values("turma__nome").annotate(total=Count("id")).order_by("-total")[:10]
        )

        return render(request, "core/dashboard.html", {
            **base_ctx,
            "page_subtitle": "Visão da unidade",
            "dash_template": "core/dashboards/partials/unidade.html",
            "unidade_nome": getattr(getattr(p, "unidade", None), "nome", "—"),
            "turmas_total": turmas_qs.count(),
            "alunos_total": alunos_qs.count(),
            "matriculas_total": matriculas_qs.count(),
            "turmas": turmas_qs.order_by("-ano_letivo", "nome")[:10],
            "graf_matriculas_por_turma": graf_matriculas_por_turma,
        })

    return render(request, "core/dashboard.html", {**base_ctx, "dash_template": "core/dashboards/partials/default.html"})


@login_required
def dashboard_aluno(request):
    # Mantém por compatibilidade, mas agora tudo é pela dashboard única
    return redirect("core:dashboard")


@login_required
def aviso_create(request):
    if not _portal_manage_allowed(request.user):
        return HttpResponseForbidden("Você não tem permissão para acessar esta área.")

    form = AlunoAvisoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        aviso = form.save(commit=False)
        aviso.autor = request.user
        aviso.save()
        messages.success(request, "Aviso publicado.")
        return redirect("core:dashboard")

    return render(request, "core/aviso_form.html", {"form": form})


@login_required
def arquivo_create(request):
    if not _portal_manage_allowed(request.user):
        return HttpResponseForbidden("Você não tem permissão para acessar esta área.")

    form = AlunoArquivoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        arq = form.save(commit=False)
        arq.autor = request.user
        arq.save()
        messages.success(request, "Arquivo enviado.")
        return redirect("core:dashboard")

    return render(request, "core/arquivo_form.html", {"form": form})

@login_required
def portal(request):
    u = request.user
    modules = [
        {
            "key": "educacao",
            "title": "Educação",
            "desc": "Escolas, turmas, alunos, matrículas e relatórios.",
            "icon": "fa-solid fa-graduation-cap",
            "url": "educacao:index",
            "enabled": can(u, "educacao.view"),
            "color": "kpi-blue",
        },
        {
            "key": "nee",
            "title": "NEE",
            "desc": "Necessidades Educacionais Especiais e relatórios institucionais.",
            "icon": "fa-solid fa-wheelchair",
            "url": "nee:relatorios_index",
            "enabled": can(u, "nee.view"),
            "color": "kpi-purple",
        },
        {
            "key": "saude",
            "title": "Saúde",
            "desc": "Unidades, profissionais e atendimentos.",
            "icon": "fa-solid fa-heart-pulse",
            "url": "saude:index",
            "enabled": can(u, "saude.view"),
            "color": "kpi-green",
            },
    ]

    modules = [m for m in modules if m["enabled"]]
    return render(request, "core/portal.html", {"modules": modules})