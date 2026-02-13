from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from accounts.models import Profile
from core.decorators import require_perm
from core.rbac import get_profile, is_admin, scope_filter_municipios
from org.models import Municipio, Secretaria, Unidade, Setor
from educacao.models import Turma  # usado em contagens
from django.http import JsonResponse


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

@login_required
def municipio_list(request):
    q = (request.GET.get("q") or "").strip()

    qs = scope_filter_municipios(request.user, Municipio.objects.all())

    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(uf__icontains=q))

    paginator = Paginator(qs.order_by("nome"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ✅ actions do PageHead (município geralmente é admin)
    actions = []
    if is_admin(request.user):
        actions.append({
            "label": "Novo município",
            "url": reverse("org:municipio_create"),
            "icon": "fa-solid fa-plus",
            "variant": "btn-primary",
        })

    # ✅ tabela (TableShell)
    headers = [
        {"label": "Município"},
        {"label": "UF", "width": "90px"},
        {"label": "Ativo", "width": "90px"},
    ]

    rows = []
    for m in page_obj:
        rows.append({
            "obj": m,
            "cells": [
                {"text": m.nome, "url": reverse("org:municipio_detail", args=[m.pk])},
                {"text": m.uf or "—", "url": ""},
                {"text": "Sim" if m.ativo else "Não", "url": ""},
            ],
            "can_edit": bool(is_admin(request.user)),
            "edit_url": reverse("org:municipio_update", args=[m.pk]) if is_admin(request.user) else "",
        })

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

        },
    )



@login_required
def municipio_detail(request, pk: int):
    municipio = get_object_or_404(Municipio, pk=pk)
    block = _ensure_in_scope_or_403(request.user, municipio.id)
    if block:
        return block
    return render(request, "org/municipio_detail.html", {"municipio": municipio})


@login_required
@require_perm("org.manage_municipio")
def municipio_create(request):
    if request.method == "POST":
        form = MunicipioForm(request.POST)
        if form.is_valid():
            municipio = form.save()
            messages.success(request, "Município criado com sucesso.")
            return redirect("org:municipio_detail", pk=municipio.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = MunicipioForm()

    return render(request, "org/municipio_form.html", {"form": form, "mode": "create"})


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

    return render(request, "org/municipio_form.html", {"form": form, "mode": "update", "municipio": municipio})


# =============================
# Secretarias (CRUD)
# =============================

@login_required
def secretaria_list(request):
    q = (request.GET.get("q") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()

    p = get_profile(request.user)
    if not is_admin(request.user) and p and p.municipio_id:
        municipio_id = str(p.municipio_id)

    qs = Secretaria.objects.select_related("municipio").all()

    if municipio_id.isdigit():
        qs = qs.filter(municipio_id=int(municipio_id))

    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(sigla__icontains=q) | Q(municipio__nome__icontains=q))

    municipios = scope_filter_municipios(
        request.user,
        Municipio.objects.filter(ativo=True).order_by("nome"),
    )

    from core.exports import export_csv, export_pdf_table
    export = (request.GET.get("export") or "").strip().lower()

    if export in ("csv", "pdf"):
        items = list(qs.order_by("nome").values_list("nome", "sigla", "municipio__nome"))

        headers = ["Nome", "Sigla", "Município"]
        rows = [[nome or "", sigla or "", municipio or ""] for (nome, sigla, municipio) in items]

        if export == "csv":
            return export_csv("secretarias.csv", headers, rows)

        filtros = f"Município={municipio_id or '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="secretarias.pdf",
            title="Relatório — Secretarias",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "org/secretaria_list.html", {"q": q, "municipio_id": municipio_id, "page_obj": page_obj, "municipios": municipios})


@login_required
def secretaria_detail(request, pk: int):
    secretaria = get_object_or_404(Secretaria.objects.select_related("municipio"), pk=pk)

    block = _ensure_in_scope_or_403(request.user, secretaria.municipio_id)
    if block:
        return block

    from core.rbac import scope_filter_unidades

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria").filter(secretaria_id=secretaria.id)
    ).order_by("nome")

    unidade_ids = list(unidades_qs.values_list("id", flat=True))

    turmas_map = {
        row["unidade_id"]: row["total"]
        for row in Turma.objects.filter(unidade_id__in=unidade_ids).values("unidade_id").annotate(total=Count("id"))
    }

    setores_map = {
        row["unidade_id"]: row["total"]
        for row in Setor.objects.filter(unidade_id__in=unidade_ids).values("unidade_id").annotate(total=Count("id"))
    }
    setores_total = sum(setores_map.values()) if setores_map else 0

    users_map = {}
    prof_map = {}
    aux_map = {}

    if unidade_ids and _profile_has_field("unidade"):
        qs_profiles = Profile.objects.filter(unidade_id__in=unidade_ids)
        users_map = {row["unidade_id"]: row["total"] for row in qs_profiles.values("unidade_id").annotate(total=Count("id"))}
        prof_map = {row["unidade_id"]: row["total"] for row in qs_profiles.filter(role="PROFESSOR").values("unidade_id").annotate(total=Count("id"))}
        aux_map = {row["unidade_id"]: row["total"] for row in qs_profiles.filter(role__icontains="AUX").values("unidade_id").annotate(total=Count("id"))}

    unidades_view = []
    for u in unidades_qs:
        uid = u.id
        unidades_view.append({
            "id": uid,
            "nome": u.nome,
            "tipo": getattr(u, "tipo", None),
            "ativo": getattr(u, "ativo", True),
            "turmas_total": turmas_map.get(uid, 0),
            "setores_total": setores_map.get(uid, 0),
            "usuarios_total": users_map.get(uid, 0),
            "professores_total": prof_map.get(uid, 0),
            "auxiliares_total": aux_map.get(uid, 0),
        })

    ctx = {
        "secretaria": secretaria,
        "unidades_total": len(unidades_view),
        "setores_total": setores_total,
        "turmas_total": sum(x["turmas_total"] for x in unidades_view),
        "usuarios_total": sum(x["usuarios_total"] for x in unidades_view),
        "unidades": unidades_view,
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

    return render(request, "org/secretaria_form.html", {"form": form, "mode": "create"})


@login_required
@require_perm("org.manage_secretaria")
def secretaria_update(request, pk: int):
    p_me = get_profile(request.user)
    secretaria = get_object_or_404(Secretaria, pk=pk)

    if (not is_admin(request.user)) and p_me and p_me.municipio_id:
        if secretaria.municipio_id != p_me.municipio_id:
            return HttpResponseForbidden("403 — Fora do seu município.")

    if request.method == "POST":
        form = SecretariaForm(request.POST, instance=secretaria, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            if (not is_admin(request.user)) and p_me and p_me.municipio_id:
                obj.municipio_id = p_me.municipio_id
            obj.save()
            messages.success(request, "Secretaria atualizada com sucesso.")
            return redirect("org:secretaria_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = SecretariaForm(instance=secretaria, user=request.user)

    return render(request, "org/secretaria_form.html", {"form": form, "mode": "update", "secretaria": secretaria})


# =============================
# Unidades (CRUD)
# =============================

@login_required
def unidade_list(request):
    q = (request.GET.get("q") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    secretaria_id = (request.GET.get("secretaria") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()

    p = get_profile(request.user)
    if not is_admin(request.user) and p and p.municipio_id:
        municipio_id = str(p.municipio_id)

    from core.rbac import scope_filter_unidades
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
        qs = qs.filter(Q(nome__icontains=q) | Q(secretaria__nome__icontains=q) | Q(secretaria__municipio__nome__icontains=q))

    from core.exports import export_csv, export_pdf_table
    export = (request.GET.get("export") or "").strip().lower()

    if export in ("csv", "pdf"):
        items = list(
            qs.order_by("nome").values_list(
                "nome", "tipo", "secretaria__nome", "secretaria__municipio__nome", "ativo"
            )
        )
        headers = ["Unidade", "Tipo", "Secretaria", "Município", "Ativo"]
        rows = [
            [n or "", t or "", s or "", m or "", "Sim" if a else "Não"]
            for (n, t, s, m, a) in items
        ]

        if export == "csv":
            return export_csv("unidades.csv", headers, rows)

        filtros = f"Município={municipio_id or '-'} | Secretaria={secretaria_id or '-'} | Tipo={tipo or '-'} | Busca={q or '-'}"
        return export_pdf_table(
            request,
            filename="unidades.pdf",
            title="Relatório — Unidades",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    municipios = scope_filter_municipios(request.user, Municipio.objects.filter(ativo=True).order_by("nome"))

    secretarias_qs = Secretaria.objects.select_related("municipio").filter(ativo=True)
    if municipio_id.isdigit():
        secretarias_qs = secretarias_qs.filter(municipio_id=int(municipio_id))
    secretarias = secretarias_qs.order_by("nome")

    return render(
        request,
        "org/unidade_list.html",
        {
            "q": q,
            "municipio_id": municipio_id,
            "secretaria_id": secretaria_id,
            "tipo": tipo,
            "page_obj": page_obj,
            "municipios": municipios,
            "secretarias": secretarias,
            "tipos": Unidade.Tipo.choices,
        },
    )


# =============================
# Setores (CRUD)
# =============================

@login_required
def setor_list(request):
    q = (request.GET.get("q") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()

    qs = Setor.objects.select_related(
        "unidade",
        "unidade__secretaria",
        "unidade__secretaria__municipio",
    )

    # Filtro por unidade
    if unidade_id.isdigit():
        qs = qs.filter(unidade_id=int(unidade_id))

    # Filtro busca
    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
        )

    # 🔐 Aplica escopo do usuário
    from core.rbac import scope_filter_unidades
    qs = qs.filter(
        unidade_id__in=scope_filter_unidades(
            request.user,
            Unidade.objects.all()
        ).values_list("id", flat=True)
    )

    # =============================
    # EXPORTAÇÃO CSV / PDF
    # =============================
    from core.exports import export_csv, export_pdf_table
    export = (request.GET.get("export") or "").strip().lower()

    if export in ("csv", "pdf"):
        items = list(
            qs.order_by("nome").values_list(
                "nome",
                "unidade__nome",
                "unidade__secretaria__nome",
                "unidade__secretaria__municipio__nome",
            )
        )

        headers = ["Setor", "Unidade", "Secretaria", "Município"]

        rows = [
            [
                nome or "",
                unidade or "",
                secretaria or "",
                municipio or "",
            ]
            for (nome, unidade, secretaria, municipio) in items
        ]

        if export == "csv":
            return export_csv("setores.csv", headers, rows)

        filtros = f"Unidade={unidade_id or '-'} | Busca={q or '-'}"

        return export_pdf_table(
            request,
            filename="setores.pdf",
            title="Relatório — Setores",
            headers=headers,
            rows=rows,
            filtros=filtros,
        )

    # =============================
    # Paginação normal
    # =============================
    paginator = Paginator(qs.order_by("nome"), 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    unidades = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(ativo=True)
    ).order_by("nome")

    return render(
        request,
        "org/setor_list.html",
        {
            "q": q,
            "unidade_id": unidade_id,
            "page_obj": page_obj,
            "unidades": unidades,
        },
    )


@login_required
def unidade_detail(request, pk: int):
    from core.rbac import scope_filter_unidades

    qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related(
            "secretaria",
            "secretaria__municipio",
        ),
    )
    unidade = get_object_or_404(qs, pk=pk)

    # Turmas da unidade (para exibir na página)
    turmas = (
        Turma.objects
        .filter(unidade_id=unidade.id)
        .order_by("-ano_letivo", "nome")
    )

    # Setores (se você estiver exibindo em algum lugar)
    setores = (
        Setor.objects
        .filter(unidade_id=unidade.id)
        .order_by("nome")
    )

    # Usuários por unidade (se Profile tiver unidade)
    usuarios_total = 0
    professores_total = 0
    auxiliares_total = 0

    try:
        if any(getattr(f, "name", None) == "unidade" for f in Profile._meta.get_fields()):
            profiles = Profile.objects.filter(unidade_id=unidade.id)
            usuarios_total = profiles.count()
            professores_total = profiles.filter(role="PROFESSOR").count()
            auxiliares_total = profiles.filter(role__icontains="AUX").count()
    except Exception:
        pass

    ctx = {
        "unidade": unidade,
        "turmas": turmas,
        "setores": setores,
        "turmas_total": turmas.count(),
        "setores_total": setores.count(),
        "usuarios_total": usuarios_total,
        "professores_total": professores_total,
        "auxiliares_total": auxiliares_total,
    }
    return render(request, "org/unidade_detail.html", ctx)


@login_required
def unidade_create(request):
    block = _deny_manage_org(request)
    if block:
        return block

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

    return render(request, "org/unidade_form.html", {"form": form, "mode": "create"})


@login_required
def unidade_update(request, pk: int):
    block = _deny_manage_org(request)
    if block:
        return block

    from core.rbac import scope_filter_unidades

    qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria", "secretaria__municipio"),
    )
    unidade = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        try:
            form = UnidadeForm(request.POST, instance=unidade, user=request.user)
        except TypeError:
            form = UnidadeForm(request.POST, instance=unidade)

        if form.is_valid():
            obj = form.save()
            messages.success(request, "Unidade atualizada com sucesso.")
            return redirect("org:unidade_detail", pk=obj.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        try:
            form = UnidadeForm(instance=unidade, user=request.user)
        except TypeError:
            form = UnidadeForm(instance=unidade)

    return render(request, "org/unidade_form.html", {"form": form, "mode": "update", "unidade": unidade})


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

    # Protege por escopo: se a unidade do setor não estiver no escopo do usuário, 404
    from core.rbac import scope_filter_unidades
    unidade_ok = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(pk=setor.unidade_id),
    ).exists()
    if not unidade_ok:
        raise Http404

    return render(request, "org/setor_detail.html", {"setor": setor})


@login_required
def setor_create(request):
    block = _deny_manage_org(request)
    if block:
        return block

    if request.method == "POST":
        try:
            form = SetorForm(request.POST, user=request.user)
        except TypeError:
            form = SetorForm(request.POST)

        if form.is_valid():
            obj = form.save(commit=False)

            # trava unidade no escopo
            from core.rbac import scope_filter_unidades
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
    block = _deny_manage_org(request)
    if block:
        return block

    setor = get_object_or_404(Setor, pk=pk)

    # Protege por escopo
    from core.rbac import scope_filter_unidades
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
def setor_autocomplete(request):
    q = request.GET.get("q", "").strip()

    qs = Setor.objects.select_related("unidade")
    if q:
        qs = qs.filter(nome__icontains=q)

    data = {
        "results": [
            {"id": s.id, "text": f"{s.nome} ({s.unidade.nome})"}
            for s in qs.order_by("nome")[:10]
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
