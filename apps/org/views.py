from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from apps.accounts.models import Profile
from apps.core.decorators import require_perm
from apps.core.rbac import get_profile, is_admin, scope_filter_municipios
from apps.core.rbac import can
from apps.org.models import Municipio, Secretaria, Unidade, Setor
from apps.educacao.models import Turma, Matricula  # usado em contagens
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import redirect, render

from .forms import MunicipioForm, SecretariaForm, UnidadeForm, SetorForm, MunicipioContatoForm


def _profile_has_field(field_name: str) -> bool:
    try:
        return any(getattr(f, "name", None) == field_name for f in Profile._meta.get_fields())
    except Exception:
        return False


def _ensure_in_scope_or_403(user, municipio_id: int | None):
    if is_admin(user):
        return None
    p = get_profile(user)
    if p and p.municipio_id and municipio_id and int(p.municipio_id) != int(municipio_id):
        return HttpResponseForbidden("403 — Fora do seu município.")
    return None


@login_required
def index(request):
    return render(request, "org/index.html")


# =============================
# Municípios (CRUD)
# =============================

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

# assume que você já tem:
# - scope_filter_municipios(user, qs)
# - is_admin(user)

@login_required
def municipio_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = scope_filter_municipios(request.user, Municipio.objects.all())

    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(uf__icontains=q))

    paginator = Paginator(qs.order_by("nome"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    actions = []
    if is_admin(request.user):
        actions.append({
            "label": "Novo município",
            "url": reverse("org:municipio_create"),
            "icon": "fa-solid fa-plus",
            "variant": "btn-primary",
        })

    headers = [
        {"label": "Município"},
        {"label": "UF", "width": "90px"},
        {"label": "Ativo", "width": "90px"},
    ]

    rows = []
    can_edit = bool(is_admin(request.user))

    for m in page_obj:
        ativo_html = (
            f'<span class="status {"success" if m.ativo else "danger"}">'
            f'{"Sim" if m.ativo else "Não"}'
            f"</span>"
        )

        rows.append({
            "obj": m,
            "cells": [
                {"text": m.nome, "url": reverse("org:municipio_detail", args=[m.pk])},
                {"text": m.uf or "—", "url": ""},
                {"html": ativo_html, "safe": True},
            ],
            "can_edit": can_edit,
            "edit_url": reverse("org:municipio_update", args=[m.pk]) if can_edit else "",
        })

    breadcrumbs = [
        {"label": "Início", "url": reverse("core:dashboard")},
        {"label": "Organização", "url": reverse("org:index")},
        {"label": "Municípios", "url": None},
    ]

    return render(
        request,
        "org/municipio_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "actions": actions,
            "headers": headers,
            "rows": rows,
            "action_url": reverse("org:municipio_list"),
            "clear_url": reverse("org:municipio_list"),
            "has_filters": bool(q),
            "autocomplete_url": reverse("org:municipio_autocomplete"),
            "autocomplete_href": reverse("org:municipio_list") + "?q={q}",
            "breadcrumbs": breadcrumbs,
        },
    )





@login_required
def municipio_detail(request, pk: int):
    municipio = get_object_or_404(Municipio, pk=pk)
    block = _ensure_in_scope_or_403(request.user, municipio.id)
    if block:
        return block

    secretarias_qs = Secretaria.objects.filter(municipio_id=municipio.id)
    unidades_qs = Unidade.objects.filter(secretaria__municipio_id=municipio.id)
    setores_qs = Setor.objects.filter(unidade__secretaria__municipio_id=municipio.id)

    summary_items = [
        {"label": "Secretarias", "value": secretarias_qs.count(), "href": reverse("org:secretaria_list") + f"?municipio={municipio.id}", "meta": "Ver todas"},
        {"label": "Unidades", "value": unidades_qs.count(), "href": reverse("org:unidade_list") + f"?municipio={municipio.id}", "meta": "Ver todas"},
        {"label": "Setores", "value": setores_qs.count(), "href": reverse("org:setor_list") + f"?municipio={municipio.id}", "meta": "Ver todos"},
    ]

    actions = [
        {"label": "Voltar", "url": reverse("org:municipio_list"), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]
    if is_admin(request.user):
        actions.append({
            "label": "Editar",
            "url": reverse("org:municipio_update", args=[municipio.pk]),
            "icon": "fa-solid fa-pen",
            "variant": "btn-primary",
        })

    breadcrumbs = [
        {"label": "Início", "url": reverse("core:dashboard")},
        {"label": "Organização", "url": reverse("org:index")},
        {"label": "Municípios", "url": reverse("org:municipio_list")},
        {"label": municipio.nome, "url": None},
    ]

    return render(
        request,
        "org/municipio_detail.html",
        {
            "municipio": municipio,
            "actions": actions,
            "summary_items": summary_items,
            "breadcrumbs": breadcrumbs,
        },
    )





@login_required
def municipio_create(request):
    if not is_admin(request.user):
        return HttpResponseForbidden("403 — Apenas administrador pode criar município.")

    if request.method == "POST":
        form = MunicipioForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Município criado com sucesso.")
            return redirect("org:municipio_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = MunicipioForm()

    breadcrumbs = [
        {"label": "Início", "url": reverse("core:dashboard")},
        {"label": "Organização", "url": reverse("org:index")},
        {"label": "Municípios", "url": reverse("org:municipio_list")},
        {"label": "Novo", "url": None},
    ]

    return render(
        request,
        "org/municipio_form.html",
        {
            "form": form,
            "mode": "create",
            "breadcrumbs": breadcrumbs,
            "cancel_url": reverse("org:municipio_list"),
            "submit_label": "Salvar município",
        },
    )





@login_required
def municipio_update(request, pk: int):
    if not is_admin(request.user):
        return HttpResponseForbidden("403 — Apenas administrador pode editar município.")

    municipio = get_object_or_404(Municipio, pk=pk)

    FormClass = MunicipioForm if is_admin(request.user) else MunicipioContatoForm

    if request.method == "POST":
        form = FormClass(request.POST, instance=municipio)
        if form.is_valid():
            obj = form.save(commit=False)
            if not is_admin(request.user):
                obj.cnpj_prefeitura = municipio.cnpj_prefeitura
                obj.razao_social_prefeitura = municipio.razao_social_prefeitura
                obj.nome_fantasia_prefeitura = municipio.nome_fantasia_prefeitura
            obj.save()
            messages.success(request, "Município atualizado com sucesso.")
            return redirect("org:municipio_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = FormClass(instance=municipio)

    breadcrumbs = [
        {"label": "Início", "url": reverse("core:dashboard")},
        {"label": "Organização", "url": reverse("org:index")},
        {"label": "Municípios", "url": reverse("org:municipio_list")},
        {"label": municipio.nome, "url": reverse("org:municipio_detail", args=[municipio.pk])},
        {"label": "Editar", "url": None},
    ]

    return render(
        request,
        "org/municipio_form.html",
        {
            "form": form,
            "mode": "update",
            "municipio": municipio,
            "breadcrumbs": breadcrumbs,
            "cancel_url": reverse("org:municipio_detail", args=[municipio.pk]),
            "submit_label": "Salvar alterações",
        },
    )



# =============================
# Secretarias (CRUD)
# =============================

@login_required
def secretaria_list(request):
    q = (request.GET.get("q") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()

    p = get_profile(request.user)
    if not is_admin(request.user) and p and getattr(p, "municipio_id", None):
        municipio_id = str(p.municipio_id)

    qs = Secretaria.objects.select_related("municipio").all()

    if municipio_id.isdigit():
        qs = qs.filter(municipio_id=int(municipio_id))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(sigla__icontains=q)
            | Q(municipio__nome__icontains=q)
        )

    paginator = Paginator(qs.order_by("nome"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    actions = []
    if is_admin(request.user):
        actions.append({
            "label": "Nova Secretaria",
            "url": reverse("org:secretaria_create"),
            "icon": "fa-solid fa-plus",
            "variant": "btn-primary",
        })

    headers = [
        {"label": "Nome"},
        {"label": "Sigla", "width": "120px"},
        {"label": "Município"},
        {"label": "Ativo", "width": "90px"},
    ]

    rows = []
    can_edit = bool(is_admin(request.user))

    for s in page_obj:
        ativo_html = (
            f'<span class="status {"success" if getattr(s, "ativo", False) else "danger"}">'
            f'{"Sim" if getattr(s, "ativo", False) else "Não"}'
            f"</span>"
        )

        rows.append({
            "cells": [
                {"text": s.nome, "url": reverse("org:secretaria_detail", args=[s.pk])},
                {"text": s.sigla or "—", "url": ""},
                {"text": getattr(s.municipio, "nome", "—") or "—", "url": ""},
                {"html": ativo_html, "safe": True},
            ],
            "can_edit": can_edit,
            "edit_url": reverse("org:secretaria_update", args=[s.pk]) if can_edit else "",
        })

    breadcrumbs = [
        {"label": "Início", "url": reverse("core:dashboard")},
        {"label": "Organização", "url": reverse("org:index")},
        {"label": "Secretarias", "url": None},
    ]

    return render(request, "org/secretaria_list.html", {
        "q": q,
        "municipio_id": municipio_id,
        "page_obj": page_obj,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "action_url": reverse("org:secretaria_list"),
        "clear_url": reverse("org:secretaria_list"),
        "has_filters": bool(q or municipio_id),
        "autocomplete_url": reverse("org:secretaria_autocomplete"),
        "autocomplete_href": reverse("org:secretaria_list") + "?q={q}",
        "breadcrumbs": breadcrumbs,
})





@login_required
def secretaria_detail(request, pk: int):
    secretaria = get_object_or_404(
        Secretaria.objects.select_related("municipio"),
        pk=pk
    )

    block = _ensure_in_scope_or_403(request.user, secretaria.municipio_id)
    if block:
        return block

    from apps.core.rbac import scope_filter_unidades

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria")
        .filter(secretaria_id=secretaria.id)
    ).order_by("nome")

    unidade_ids = list(unidades_qs.values_list("id", flat=True))

    turmas_map = {
        row["unidade_id"]: row["total"]
        for row in Turma.objects
        .filter(unidade_id__in=unidade_ids)
        .values("unidade_id")
        .annotate(total=Count("id"))
    }

    setores_map = {
        row["unidade_id"]: row["total"]
        for row in Setor.objects
        .filter(unidade_id__in=unidade_ids)
        .values("unidade_id")
        .annotate(total=Count("id"))
    }

    users_map = {}
    prof_map = {}
    aux_map = {}

    if unidade_ids and _profile_has_field("unidade"):
        qs_profiles = Profile.objects.filter(unidade_id__in=unidade_ids)

        users_map = {
            row["unidade_id"]: row["total"]
            for row in qs_profiles
            .values("unidade_id")
            .annotate(total=Count("id"))
        }

        prof_map = {
            row["unidade_id"]: row["total"]
            for row in qs_profiles
            .filter(role="PROFESSOR")
            .values("unidade_id")
            .annotate(total=Count("id"))
        }

        aux_map = {
            row["unidade_id"]: row["total"]
            for row in qs_profiles
            .filter(role__icontains="AUX")
            .values("unidade_id")
            .annotate(total=Count("id"))
        }

    # 🔹 TABLE_SHELL HEADERS
    headers = [
        {"label": "Unidade"},
        {"label": "Tipo", "width": "140px"},
        {"label": "Turmas", "width": "100px"},
        {"label": "Setores", "width": "100px"},
        {"label": "Usuários", "width": "100px"},
        {"label": "Ativa", "width": "100px"},
    ]

    # 🔹 TABLE_SHELL ROWS
    rows = []

    for u in unidades_qs:
        uid = u.id

        rows.append({
            "cells": [
                {
                    "text": u.nome,
                    "url": reverse("org:unidade_detail", args=[uid]),
                },
                {
                    "text": getattr(u, "get_tipo_display", lambda: getattr(u, "tipo", "—"))(),
                    "url": "",
                },
                {
                    "text": str(turmas_map.get(uid, 0)),
                    "url": "",
                },
                {
                    "text": str(setores_map.get(uid, 0)),
                    "url": "",
                },
                {
                    "text": str(users_map.get(uid, 0)),
                    "url": "",
                },
                {
                    "text": "Sim" if getattr(u, "ativo", True) else "Não",
                    "url": "",
                },
            ],
            "can_edit": False,
            "edit_url": "",
        })
        breadcrumbs = [
    {"label": "Início", "url": reverse("core:dashboard")},
    {"label": "Organização", "url": reverse("org:index")},
    {"label": "Secretarias", "url": reverse("org:secretaria_list")},
    {"label": secretaria.nome, "url": None},
]


    # 🔹 ACTIONS (PageHead)
    actions = []

    if can(request.user, "org.manage"):
        actions.append({
            "label": "Editar",
            "url": reverse("org:secretaria_update", args=[secretaria.pk]),
            "icon": "fa-solid fa-pen",
            "variant": "btn-primary",
        })

    ctx = {
        "secretaria": secretaria,
        "unidades_total": unidades_qs.count(),
        "turmas_total": sum(turmas_map.values()) if turmas_map else 0,
        "setores_total": sum(setores_map.values()) if setores_map else 0,
        "usuarios_total": sum(users_map.values()) if users_map else 0,
        "headers": headers,
        "rows": rows,
        "actions": actions,
        "breadcrumbs": breadcrumbs,

    }

    return render(request, "org/secretaria_detail.html", ctx)



@login_required
@require_perm("org.manage_secretaria")
def secretaria_create(request):
    p_me = get_profile(request.user)

    if request.method == "POST":
        form = SecretariaForm(request.POST, user=request.user)
        if form.is_valid():
            secretaria = form.save(commit=False)
            if (not is_admin(request.user)) and p_me and p_me.municipio_id:
                secretaria.municipio_id = p_me.municipio_id
            secretaria.save()
            messages.success(request, "Secretaria criada com sucesso.")
            return redirect("org:secretaria_detail", pk=secretaria.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = SecretariaForm(user=request.user)

    breadcrumbs = [
        {"label": "Início", "url": reverse("core:dashboard")},
        {"label": "Organização", "url": reverse("org:index")},
        {"label": "Secretarias", "url": reverse("org:secretaria_list")},
        {"label": "Nova", "url": None},
    ]

    return render(request, "org/secretaria_form.html", {
        "form": form,
        "mode": "create",
        "breadcrumbs": breadcrumbs,
        "cancel_url": reverse("org:secretaria_list"),
        "submit_label": "Salvar secretaria",
    })



@login_required
@require_perm("org.manage_secretaria")
def secretaria_update(request, pk: int):
    secretaria = get_object_or_404(Secretaria, pk=pk)
    p_me = get_profile(request.user)

    if (not is_admin(request.user)) and p_me and p_me.municipio_id:
        if secretaria.municipio_id != p_me.municipio_id:
            return HttpResponseForbidden("403 — Fora do seu município.")

    if request.method == "POST":
        form = SecretariaForm(request.POST, instance=secretaria, user=request.user)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Secretaria atualizada com sucesso.")
            return redirect("org:secretaria_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = SecretariaForm(instance=secretaria, user=request.user)

    breadcrumbs = [
        {"label": "Início", "url": reverse("core:dashboard")},
        {"label": "Organização", "url": reverse("org:index")},
        {"label": "Secretarias", "url": reverse("org:secretaria_list")},
        {"label": secretaria.nome, "url": reverse("org:secretaria_detail", args=[secretaria.pk])},
        {"label": "Editar", "url": None},
    ]

    return render(request, "org/secretaria_form.html", {
        "form": form,
        "mode": "update",
        "secretaria": secretaria,
        "breadcrumbs": breadcrumbs,
        "cancel_url": reverse("org:secretaria_detail", args=[secretaria.pk]),
        "submit_label": "Salvar alterações",
    })



# =============================
# Unidades (CRUD)
# =============================

@login_required
def unidade_list(request):
    q = (request.GET.get("q") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    secretaria_id = (request.GET.get("secretaria") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()

    # trava município do perfil (não-admin)
    p = get_profile(request.user)
    if not is_admin(request.user) and p and p.municipio_id:
        municipio_id = str(p.municipio_id)

    from apps.core.rbac import scope_filter_unidades

    qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria", "secretaria__municipio").all()
    )

    if municipio_id.isdigit():
        qs = qs.filter(secretaria__municipio_id=int(municipio_id))
    if secretaria_id.isdigit():
        qs = qs.filter(secretaria_id=int(secretaria_id))
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(codigo_inep__icontains=q)
            | Q(cnpj__icontains=q)
            | Q(secretaria__nome__icontains=q)
            | Q(secretaria__municipio__nome__icontains=q)
        )

    # =============================
    # BASE DE FILTROS (selects)
    # =============================
    municipios = scope_filter_municipios(
        request.user,
        Municipio.objects.filter(ativo=True).order_by("nome"),
    )

    secretarias_qs = Secretaria.objects.select_related("municipio").filter(
        ativo=True,
        municipio__in=municipios
    )
    if municipio_id.isdigit():
        secretarias_qs = secretarias_qs.filter(municipio_id=int(municipio_id))
    secretarias = secretarias_qs.order_by("nome")

    # =============================
    # EXPORTAÇÃO
    # =============================
    from apps.core.exports import export_csv, export_pdf_table
    export = (request.GET.get("export") or "").strip().lower()

    if export in ("csv", "pdf"):
        items = list(
            qs.order_by("nome").values_list(
                "nome",
                "tipo",
                "codigo_inep",
                "cnpj",
                "secretaria__nome",
                "secretaria__municipio__nome",
                "secretaria__municipio__uf",
                "ativo",
            )
        )

        headers_export = ["Unidade", "Tipo", "INEP", "CNPJ", "Secretaria", "Município", "UF", "Ativo"]
        rows_export = [
            [
                nome or "",
                str(tipo_val or ""),
                inep or "",
                cnpj or "",
                secretaria_nome or "",
                municipio_nome or "",
                uf or "",
                "Sim" if ativo else "Não",
            ]
            for (nome, tipo_val, inep, cnpj, secretaria_nome, municipio_nome, uf, ativo) in items
        ]

        if export == "csv":
            return export_csv("unidades.csv", headers_export, rows_export)

        filtros = f"Município={municipio_id or '-'} | Secretaria={secretaria_id or '-'} | Tipo={tipo or '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="unidades.pdf",
            title="Relatório — Unidades",
            headers=headers_export,
            rows=rows_export,
            filtros=filtros,
        )

    # =============================
    # PAGINAÇÃO
    # =============================
    paginator = Paginator(qs.order_by("nome"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # =============================
    # ACTIONS (PageHead)
    # =============================
    qs_query = []
    if q:
        qs_query.append(f"q={q}")
    if municipio_id:
        qs_query.append(f"municipio={municipio_id}")
    if secretaria_id:
        qs_query.append(f"secretaria={secretaria_id}")
    if tipo:
        qs_query.append(f"tipo={tipo}")
    base_query = "&".join(qs_query)

    def qjoin(extra: str) -> str:
        return f"?{base_query + ('&' if base_query else '')}{extra}"

    actions = [
        {"label": "Exportar CSV", "url": qjoin("export=csv"), "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": qjoin("export=pdf"), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        {"label": "Nova Unidade", "url": reverse("org:unidade_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
    ]

    # =============================
    # TABLE (TableShell)
    # =============================
    headers = [
        {"label": "Unidade"},
        {"label": "Tipo", "width": "140px"},
        {"label": "INEP", "width": "140px"},
        {"label": "CNPJ", "width": "170px"},
        {"label": "Secretaria"},
        {"label": "Município"},
        {"label": "Ativo", "width": "90px"},
    ]

    rows = []
    for u in page_obj:
        municipio_nome = getattr(getattr(getattr(u, "secretaria", None), "municipio", None), "nome", "—") or "—"
        municipio_uf = getattr(getattr(getattr(u, "secretaria", None), "municipio", None), "uf", "") or ""
        rows.append({
            "cells": [
                {"text": u.nome, "url": reverse("org:unidade_detail", args=[u.pk])},
                {"text": u.get_tipo_display() if hasattr(u, "get_tipo_display") else (u.tipo or "—"), "url": ""},
                {"text": u.codigo_inep or "—", "url": ""},
                {"text": u.cnpj or "—", "url": ""},
                {"text": getattr(getattr(u, "secretaria", None), "nome", "—") or "—", "url": ""},
                {"text": (f"{municipio_nome} / {municipio_uf}" if municipio_uf else municipio_nome), "url": ""},
                {"text": "Sim" if getattr(u, "ativo", False) else "Não", "url": ""},
            ],
            "can_edit": True,
            "edit_url": reverse("org:unidade_update", args=[u.pk]) if u.pk else "",
        })

    # =============================
    # EXTRA FILTERS (3 selects)
    # =============================
    options_municipios = [{"value": str(m.id), "label": f"{m.nome} / {m.uf}"} for m in municipios]
    options_secretarias = [{"value": str(s.id), "label": f"{s.nome} ({s.municipio.uf})"} for s in secretarias]
    options_tipos = [{"value": str(value), "label": str(label)} for (value, label) in Unidade.Tipo.choices]

    extra_filters = ""
    extra_filters += render_to_string(
        "core/partials/filter_select.html",
        {"name": "municipio", "label": "Município", "value": municipio_id, "empty_label": "Todos", "options": options_municipios},
        request=request,
    )
    extra_filters += render_to_string(
        "core/partials/filter_select.html",
        {"name": "secretaria", "label": "Secretaria", "value": secretaria_id, "empty_label": "Todas", "options": options_secretarias},
        request=request,
    )
    extra_filters += render_to_string(
        "core/partials/filter_select.html",
        {"name": "tipo", "label": "Tipo", "value": tipo, "empty_label": "Todos", "options": options_tipos},
        request=request,
    )

    # ✅ autocomplete do buscar
    autocomplete_url = reverse("org:unidade_autocomplete")
    autocomplete_href = reverse("org:unidade_list") + "?q={q}"

    # ✅ RENDER CORRETO (LISTA)
    return render(request, "org/unidade_list.html", {
        "q": q,
        "municipio_id": municipio_id,
        "secretaria_id": secretaria_id,
        "tipo": tipo,
        "page_obj": page_obj,
        "actions": actions,
        "headers": headers,
        "rows": rows,
        "action_url": reverse("org:unidade_list"),
        "clear_url": reverse("org:unidade_list"),
        "has_filters": bool(municipio_id or secretaria_id or tipo),
        "extra_filters": extra_filters,
        "autocomplete_url": autocomplete_url,
        "autocomplete_href": autocomplete_href,
    })





# =============================
# Setores (CRUD)
# =============================

@login_required
def setor_list(request):
    q = (request.GET.get("q") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()

    # escopo de unidades do usuário
    from apps.core.rbac import scope_filter_unidades
    unidades_scope = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria", "secretaria__municipio").all()
    )

    qs = Setor.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
    ).filter(unidade_id__in=unidades_scope.values_list("id", flat=True))

    # filtros
    if unidade_id.isdigit():
        qs = qs.filter(unidade_id=int(unidade_id))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
            | Q(unidade__secretaria__municipio__nome__icontains=q)
        )

    # =============================
    # EXPORTAÇÃO CSV / PDF
    # =============================
    from apps.core.exports import export_csv, export_pdf_table
    export = (request.GET.get("export") or "").strip().lower()

    if export in ("csv", "pdf"):
        items = list(
            qs.order_by("nome").values_list(
                "nome",
                "unidade__nome",
                "unidade__secretaria__nome",
                "unidade__secretaria__municipio__nome",
                "unidade__secretaria__municipio__uf",
                "ativo",
            )
        )

        headers_export = ["Setor", "Unidade", "Secretaria", "Município", "UF", "Ativo"]
        rows_export = [
            [
                setor or "",
                unidade or "",
                secretaria or "",
                municipio or "",
                uf or "",
                "Sim" if ativo else "Não",
            ]
            for (setor, unidade, secretaria, municipio, uf, ativo) in items
        ]

        if export == "csv":
            return export_csv("setores.csv", headers_export, rows_export)

        filtros = f"Unidade={unidade_id or '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="setores.pdf",
            title="Relatório — Setores",
            headers=headers_export,
            rows=rows_export,
            filtros=filtros,
        )

    # =============================
    # PAGINAÇÃO
    # =============================
    paginator = Paginator(qs.order_by("nome"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # =============================
    # ACTIONS (PageHead)
    # =============================
    qs_query = []
    if q:
        qs_query.append(f"q={q}")
    if unidade_id:
        qs_query.append(f"unidade={unidade_id}")
    base_query = "&".join(qs_query)

    def qjoin(extra: str) -> str:
        return f"?{base_query + ('&' if base_query else '')}{extra}"

    actions = [
        {"label": "Exportar CSV", "url": qjoin("export=csv"), "icon": "fa-solid fa-file-csv", "variant": "btn--ghost"},
        {"label": "Exportar PDF", "url": qjoin("export=pdf"), "icon": "fa-solid fa-file-pdf", "variant": "btn--ghost"},
        {"label": "Novo Setor", "url": reverse("org:setor_create"), "icon": "fa-solid fa-plus", "variant": "btn-primary"},
    ]

    # =============================
    # TABLE (TableShell)
    # =============================
    headers = [
        {"label": "Setor"},
        {"label": "Unidade"},
        {"label": "Secretaria"},
        {"label": "Município"},
        {"label": "Ativo", "width": "90px"},
    ]

    rows = []
    for s in page_obj:
        unidade_nome = getattr(getattr(s, "unidade", None), "nome", "—") or "—"
        secretaria_nome = getattr(getattr(getattr(s, "unidade", None), "secretaria", None), "nome", "—") or "—"
        mun = getattr(getattr(getattr(s, "unidade", None), "secretaria", None), "municipio", None)
        mun_nome = getattr(mun, "nome", "—") or "—"
        mun_uf = getattr(mun, "uf", "") or ""

        rows.append({
            "cells": [
                {"text": s.nome, "url": reverse("org:setor_detail", args=[s.pk])},
                {"text": unidade_nome, "url": ""},
                {"text": secretaria_nome, "url": ""},
                {"text": (f"{mun_nome} / {mun_uf}" if mun_uf else mun_nome), "url": ""},
                {"text": "Sim" if getattr(s, "ativo", False) else "Não", "url": ""},
            ],
            "can_edit": True,
            "edit_url": reverse("org:setor_update", args=[s.pk]) if s.pk else "",
        })

    # =============================
    # EXTRA FILTERS (Select Unidade) usando filter_select genérico
    # =============================
    options_unidades = []
    for u in unidades_scope.order_by("nome"):
        mun = getattr(getattr(u, "secretaria", None), "municipio", None)
        mun_uf = getattr(mun, "uf", "") or ""
        options_unidades.append({
            "value": str(u.id),
            "label": f"{u.nome} ({mun_uf})" if mun_uf else u.nome,
        })

    extra_filters = render_to_string(
        "core/partials/filter_select.html",
        {
            "name": "unidade",
            "label": "Unidade",
            "value": unidade_id,
            "empty_label": "Todas",
            "options": options_unidades,
        },
        request=request,
    )

    return render(request, "org/setor_list.html", {
    "q": q,
    "unidade_id": unidade_id,
    "page_obj": page_obj,
    "actions": actions,
    "headers": headers,
    "rows": rows,
    "action_url": reverse("org:setor_list"),
    "clear_url": reverse("org:setor_list"),
    "has_filters": bool(unidade_id),
    "extra_filters": extra_filters,
    "autocomplete_url": reverse("org:setor_autocomplete"),
    "autocomplete_href": reverse("org:setor_list") + "?q={q}",
})



@login_required
def unidade_detail(request, pk: int):
    from apps.core.rbac import scope_filter_unidades

    unidade = get_object_or_404(
        scope_filter_unidades(
            request.user,
            Unidade.objects.select_related("secretaria", "secretaria__municipio"),
        ),
        pk=pk,
    )

    can_org_manage = (
        can(request.user, "org.manage")
        or can(request.user, "org.manage_unidade")
        or request.user.is_staff
        or request.user.is_superuser
    )

    # ---------- Actions (PageHead) ----------
    actions = [
        {
            "label": "Voltar",
            "url": reverse("org:unidade_list"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]
    if can_org_manage:
        actions.append(
            {
                "label": "Editar",
                "url": reverse("org:unidade_update", args=[unidade.pk]),
                "icon": "fa-solid fa-pen",
                "variant": "btn-primary",
            }
        )

    # ---------- KPIs (sem template legacy) ----------
    turmas_qs = Turma.objects.filter(unidade_id=unidade.id).order_by("-ano_letivo", "nome")
    turmas_total = turmas_qs.count()

    usuarios_total = 0
    professores_total = 0
    auxiliares_total = 0
    roles_rows = []

    # usuários por role (se existir Profile.unidade)
    try:
        if any(getattr(f, "name", None) == "unidade" for f in Profile._meta.get_fields()):
            profiles = Profile.objects.filter(unidade_id=unidade.id)
            usuarios_total = profiles.count()
            professores_total = profiles.filter(role="PROFESSOR").count()
            auxiliares_total = profiles.filter(role__icontains="AUX").count()

            roles_agg = list(
                profiles.values("role")
                .annotate(total=Count("id"))
                .order_by("role")
            )
            for r in roles_agg:
                roles_rows.append({
                    "cells": [
                        {"text": (r.get("role") or "—"), "url": ""},
                        {"text": str(r.get("total") or 0), "url": ""},
                    ],
                    "can_edit": False,
                    "edit_url": "",
                })
    except Exception:
        roles_rows = []

    # ---------- TableShell: Turmas ----------
    headers_turmas = [
        {"label": "Turma"},
        {"label": "Ano letivo", "width": "140px"},
        {"label": "Alunos", "width": "140px"},
        {"label": "Ativa", "width": "110px"},
    ]

    rows_turmas = []
    for t in turmas_qs:
        rows_turmas.append({
            "cells": [
                {"text": t.nome, "url": reverse("educacao:turma_detail", args=[t.pk])},
                {"text": str(getattr(t, "ano_letivo", "") or "—"), "url": ""},
                {"text": str(getattr(t, "alunos_total", 0) or 0), "url": ""},
                {"text": "Sim" if getattr(t, "ativo", False) else "Não", "url": ""},
            ],
            "can_edit": False,
            "edit_url": "",
        })

    # ---------- TableShell: Usuários por perfil ----------
    headers_roles = [
        {"label": "Perfil"},
        {"label": "Total", "width": "120px"},
    ]

    # ---------- Dados do topo ----------
    unidade_tipo = (
        unidade.get_tipo_display()
        if hasattr(unidade, "get_tipo_display")
        else (getattr(unidade, "tipo", "") or "—")
    )
    secretaria_nome = getattr(getattr(unidade, "secretaria", None), "nome", "—") or "—"
    secretaria_id = getattr(unidade, "secretaria_id", None)

    return render(request, "org/unidade_detail.html", {
        "actions": actions,

        # dados simples para o resumo do topo (sem HTML complexo)
        "page_title": unidade.nome,
        "page_subtitle": "Detalhes da unidade e visão geral",
        "unidade_tipo": unidade_tipo,
        "unidade_ativo": bool(getattr(unidade, "ativo", False)),
        "secretaria_nome": secretaria_nome,
        "secretaria_id": secretaria_id,

        "turmas_total": turmas_total,
        "usuarios_total": usuarios_total,
        "professores_total": professores_total,
        "auxiliares_total": auxiliares_total,

        # tables
        "headers_turmas": headers_turmas,
        "rows_turmas": rows_turmas,
        "headers_roles": headers_roles,
        "rows_roles": roles_rows,
        "has_roles": bool(roles_rows),
    })



@login_required
def setor_autocomplete(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    from apps.core.rbac import scope_filter_unidades

    unidades_scope = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria", "secretaria__municipio").all()
    )

    qs = Setor.objects.select_related("unidade").filter(
        unidade_id__in=unidades_scope.values_list("id", flat=True)
    )

    qs = qs.filter(
        Q(nome__icontains=q) | Q(unidade__nome__icontains=q)
    ).order_by("nome")[:10]

    return JsonResponse({
        "results": [
            {"id": s.id, "text": s.nome, "meta": (s.unidade.nome if s.unidade_id else "")}
            for s in qs
        ]
    })


# from .forms import UnidadeForm   # (já deve estar importado no seu arquivo)

@login_required
def unidade_create(request):
    # ✅ bloqueio direto (sem depender de _deny_manage_org)
    if not (can(request.user, "org.manage") or can(request.user, "org.manage_unidade") or request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Você não tem permissão para cadastrar unidades.")
        return redirect("org:unidade_list")

    actions = [
        {
            "label": "Voltar",
            "url": reverse("org:unidade_list"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    if request.method == "POST":
        try:
            form = UnidadeForm(request.POST, user=request.user)
        except TypeError:
            form = UnidadeForm(request.POST)

        if form.is_valid():
            obj = form.save()
            messages.success(request, "Unidade criada com sucesso.")
            return redirect("org:unidade_detail", pk=obj.pk)

        messages.error(request, "Corrija os erros do formulário.")
    else:
        try:
            form = UnidadeForm(user=request.user)
        except TypeError:
            form = UnidadeForm()

    return render(
        request,
        "org/unidade_form.html",
        {
            "form": form,
            "mode": "create",
            "actions": actions,
            "cancel_url": reverse("org:unidade_list"),
            "action_url": reverse("org:unidade_create"),
        },
    )




@login_required
def unidade_update(request, pk: int):
    # Permissão: manter padrão do projeto (sem helper inexistente)
    can_manage = (
        can(request.user, "org.manage")
        or can(request.user, "org.manage_unidade")
        or request.user.is_staff
        or request.user.is_superuser
    )
    if not can_manage:
        messages.error(request, "Você não tem permissão para editar unidades.")
        return redirect("org:unidade_list")

    from apps.core.rbac import scope_filter_unidades

    obj = get_object_or_404(
        scope_filter_unidades(
            request.user,
            Unidade.objects.select_related("secretaria", "secretaria__municipio"),
        ),
        pk=pk,
    )

    if request.method == "POST":
        try:
            form = UnidadeForm(request.POST, instance=obj, user=request.user)
        except TypeError:
            form = UnidadeForm(request.POST, instance=obj)

        if form.is_valid():
            obj = form.save()
            messages.success(request, "Unidade atualizada com sucesso.")
            return redirect("org:unidade_detail", pk=obj.pk)

        messages.error(request, "Corrija os erros do formulário.")
    else:
        try:
            form = UnidadeForm(instance=obj, user=request.user)
        except TypeError:
            form = UnidadeForm(instance=obj)

    # --------- padrão componentizado (igual create) ----------
    page_title = "Editar unidade"
    page_subtitle = obj.nome
    actions = [
        {"label": "Voltar", "url": reverse("org:unidade_detail", args=[obj.pk]), "icon": "fa-solid fa-arrow-left", "variant": "btn--ghost"},
    ]

    return render(request, "org/unidade_form.html", {
        "form": form,
        "mode": "update",

        # padrão do template novo
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "actions": actions,
        "submit_label": "Salvar alterações",
        "cancel_url": reverse("org:unidade_detail", args=[obj.pk]),
        "action_url": reverse("org:unidade_update", args=[obj.pk]),
    })


@login_required
def setor_detail(request, pk: int):
    setor = get_object_or_404(
        Setor.objects.select_related(
            "unidade",
            "unidade__secretaria",
            "unidade__secretaria__municipio",
        ),
        pk=pk,
    )

    from apps.core.rbac import scope_filter_unidades

    unidade_ok = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(pk=setor.unidade_id),
    ).exists()

    if not unidade_ok:
        raise Http404

    can_manage = (
        can(request.user, "org.manage")
        or can(request.user, "org.manage_unidade")
        or request.user.is_staff
        or request.user.is_superuser
    )

    actions = [
        {
            "label": "Voltar",
            "url": reverse("org:setor_list"),
            "icon": "fa-solid fa-arrow-left",
            "variant": "btn--ghost",
        }
    ]

    if can_manage:
        actions.append({
            "label": "Editar",
            "url": reverse("org:setor_update", args=[setor.pk]),
            "icon": "fa-solid fa-pen",
            "variant": "btn-primary",
        })

    unidade = setor.unidade
    secretaria = unidade.secretaria
    municipio = secretaria.municipio

    fields = [
        {"label": "Unidade", "value": unidade.nome},
        {"label": "Secretaria", "value": secretaria.nome},
        {"label": "Município", "value": f"{municipio.nome}/{municipio.uf}"},
    ]

    pills = [
        {
            "label": "Ativo",
            "value": "Sim" if setor.ativo else "Não",
            "variant": "success" if setor.ativo else "danger",
        }
    ]

    return render(request, "org/setor_detail.html", {
        "page_title": setor.nome,
        "page_subtitle": "Detalhes do setor",
        "actions": actions,
        "fields": fields,
        "pills": pills,
    })


@login_required
def setor_create(request):
    # ✅ Permissão no mesmo padrão de unidade_create (sem _deny_manage_org)
    can_manage = (
        can(request.user, "org.manage")
        or can(request.user, "org.manage_unidade")
        or can(request.user, "org.manage_secretaria")
        or request.user.is_staff
        or request.user.is_superuser
    )
    if not can_manage:
        messages.error(request, "Você não tem permissão para cadastrar setores.")
        return redirect("org:setor_list")

    if request.method == "POST":
        try:
            form = SetorForm(request.POST, user=request.user)
        except TypeError:
            form = SetorForm(request.POST)

        if form.is_valid():
            obj = form.save(commit=False)

            # trava unidade no escopo
            from apps.core.rbac import scope_filter_unidades
            unidade_ok = scope_filter_unidades(
                request.user,
                Unidade.objects.filter(pk=obj.unidade_id),
            ).exists()
            if not unidade_ok:
                return HttpResponseForbidden("403 — Unidade fora do seu escopo.")

            obj.save()
            messages.success(request, "Setor criado com sucesso.")
            return redirect("org:setor_detail", pk=obj.pk)

        messages.error(request, "Corrija os erros do formulário.")
    else:
        try:
            form = SetorForm(user=request.user)
        except TypeError:
            form = SetorForm()

    return render(request, "org/setor_form.html", {"form": form, "mode": "create"})


@login_required
def setor_update(request, pk: int):
    # ✅ Permissão no mesmo padrão de unidade_update (sem _deny_manage_org)
    can_manage = (
        can(request.user, "org.manage")
        or can(request.user, "org.manage_unidade")
        or can(request.user, "org.manage_secretaria")
        or request.user.is_staff
        or request.user.is_superuser
    )
    if not can_manage:
        messages.error(request, "Você não tem permissão para editar setores.")
        return redirect("org:setor_list")

    setor = get_object_or_404(Setor, pk=pk)

    # Protege por escopo
    from apps.core.rbac import scope_filter_unidades
    unidade_ok = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(pk=setor.unidade_id),
    ).exists()
    if not unidade_ok:
        raise Http404

    if request.method == "POST":
        try:
            form = SetorForm(request.POST, instance=setor, user=request.user)
        except TypeError:
            form = SetorForm(request.POST, instance=setor)

        if form.is_valid():
            obj = form.save(commit=False)

            # se trocar unidade, valida escopo
            unidade_ok2 = scope_filter_unidades(
                request.user,
                Unidade.objects.filter(pk=obj.unidade_id),
            ).exists()
            if not unidade_ok2:
                return HttpResponseForbidden("403 — Unidade fora do seu escopo.")

            obj.save()
            messages.success(request, "Setor atualizado com sucesso.")
            return redirect("org:setor_detail", pk=obj.pk)

        messages.error(request, "Corrija os erros do formulário.")
    else:
        try:
            form = SetorForm(instance=setor, user=request.user)
        except TypeError:
            form = SetorForm(instance=setor)

    return render(request, "org/setor_form.html", {"form": form, "mode": "update", "setor": setor})

@login_required
def secretaria_autocomplete(request):
    q = request.GET.get("q", "").strip()

    qs = Secretaria.objects.all()
    if q:
        qs = qs.filter(nome__icontains=q)

    data = {
        "results": [
            {"id": s.id, "text": s.nome}
            for s in qs.order_by("nome")[:10]
        ]
    }
    return JsonResponse(data)


@login_required
def unidade_autocomplete(request):
    q = request.GET.get("q", "").strip()

    qs = Unidade.objects.select_related("secretaria")
    if q:
        qs = qs.filter(nome__icontains=q)

    data = {
        "results": [
            {"id": u.id, "text": f"{u.nome} — {u.secretaria.nome}"}
            for u in qs.order_by("nome")[:10]
        ]
    }
    return JsonResponse(data)



@login_required
def municipio_autocomplete(request):
    q = request.GET.get("q", "").strip()

    qs = Municipio.objects.all()
    if q:
        qs = qs.filter(nome__icontains=q)

    data = {
        "results": [
            {"id": m.id, "text": f"{m.nome}/{m.uf}"}
            for m in qs.order_by("nome")[:10]
        ]
    }
    return JsonResponse(data)
