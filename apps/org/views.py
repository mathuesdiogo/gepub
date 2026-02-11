from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Profile
from core.decorators import require_perm
from core.rbac import get_profile, is_admin, scope_filter_municipios
from org.models import Municipio, Secretaria, Unidade, Setor
from educacao.models import Turma, Matricula  # Matricula é usada em dashboards/contagens futuras

from .forms import MunicipioForm, SecretariaForm, UnidadeForm, SetorForm, MunicipioContatoForm


# =============================
# Helpers
# =============================

def _profile_has_field(field_name: str) -> bool:
    """Evita quebrar se o Profile não tiver unidade/setor."""
    try:
        return any(getattr(f, "name", None) == field_name for f in Profile._meta.get_fields())
    except Exception:
        return False


def _ensure_in_scope_or_403(user, municipio_id: int | None):
    """Bloqueio simples por município para detalhes (URL direta)."""
    if is_admin(user):
        return None
    p = get_profile(user)
    if p and p.municipio_id and municipio_id and int(p.municipio_id) != int(municipio_id):
        return HttpResponseForbidden("403 — Fora do seu município.")
    return None


# =============================
# Index
# =============================

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

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "org/municipio_list.html",
        {"q": q, "page_obj": page_obj},
    )


@login_required
def municipio_detail(request, pk: int):
    municipio = get_object_or_404(Municipio, pk=pk)

    # Bloqueio por escopo (URL direta)
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
    # ✅ já estava: municipal não edita municipio
    if not is_admin(request.user):
        return HttpResponseForbidden("403 — Apenas administrador pode editar município.")

    municipio = get_object_or_404(Municipio, pk=pk)

    FormClass = MunicipioForm if is_admin(request.user) else MunicipioContatoForm

    if request.method == "POST":
        form = FormClass(request.POST, instance=municipio)
        if form.is_valid():
            obj = form.save(commit=False)

            # municipal nunca altera campos sensíveis (defensivo)
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

    return render(
        request,
        "org/municipio_form.html",
        {"form": form, "mode": "update", "municipio": municipio},
    )


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
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(sigla__icontains=q)
            | Q(municipio__nome__icontains=q)
        )

    municipios = scope_filter_municipios(
        request.user,
        Municipio.objects.filter(ativo=True).order_by("nome")
    )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "org/secretaria_list.html",
        {
            "q": q,
            "municipio_id": municipio_id,
            "page_obj": page_obj,
            "municipios": municipios,
        },
    )


@login_required

def secretaria_detail(request, pk: int):
    secretaria = get_object_or_404(
        Secretaria.objects.select_related("municipio"),
        pk=pk
    )

    # ✅ Bloqueio por escopo municipal (URL direta)
    block = _ensure_in_scope_or_403(request.user, secretaria.municipio_id)
    if block:
        return block

    from core.rbac import scope_filter_unidades

    unidades_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria").filter(secretaria_id=secretaria.id)
    ).order_by("nome")

    unidade_ids = list(unidades_qs.values_list("id", flat=True))

    # Turmas por unidade
    turmas_map = {
        row["unidade_id"]: row["total"]
        for row in Turma.objects
            .filter(unidade_id__in=unidade_ids)
            .values("unidade_id")
            .annotate(total=Count("id"))
    }

    # ✅ Setores por unidade + total de setores na secretaria
    setores_map = {
        row["unidade_id"]: row["total"]
        for row in Setor.objects
            .filter(unidade_id__in=unidade_ids)
            .values("unidade_id")
            .annotate(total=Count("id"))
    }
    setores_total = sum(setores_map.values()) if setores_map else 0

    # Usuários por unidade (se Profile tiver unidade)
    users_map = {}
    prof_map = {}
    aux_map = {}

    if unidade_ids and _profile_has_field("unidade"):
        qs_profiles = Profile.objects.filter(unidade_id__in=unidade_ids)
        users_map = {
            row["unidade_id"]: row["total"]
            for row in qs_profiles.values("unidade_id").annotate(total=Count("id"))
        }
        prof_map = {
            row["unidade_id"]: row["total"]
            for row in qs_profiles.filter(role="PROFESSOR").values("unidade_id").annotate(total=Count("id"))
        }
        aux_map = {
            row["unidade_id"]: row["total"]
            for row in qs_profiles.filter(role__icontains="AUX").values("unidade_id").annotate(total=Count("id"))
        }

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

        # KPIs
        "unidades_total": len(unidades_view),
        "setores_total": setores_total,
        "turmas_total": sum(x["turmas_total"] for x in unidades_view),
        "usuarios_total": sum(x["usuarios_total"] for x in unidades_view),

        # Lista
        "unidades": unidades_view,
    }
    return render(request, "org/secretaria_detail.html", ctx)


def unidade_detail(request, pk: int):
    from core.rbac import scope_filter_unidades

    unidade_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria", "secretaria__municipio")
    )
    unidade = get_object_or_404(unidade_qs, pk=pk)

    # ✅ Turmas clicáveis + alunos por turma (via matrícula)
    turmas = (
        Turma.objects
        .filter(unidade_id=unidade.id)
        .annotate(alunos_total=Count("matriculas__aluno", distinct=True))
        .order_by("-ano_letivo", "nome")
    )

    usuarios_total = professores_total = auxiliares_total = 0
    usuarios_por_role = []

    if _profile_has_field("unidade"):
        qs_profiles = Profile.objects.filter(unidade_id=unidade.id)
        usuarios_total = qs_profiles.count()
        professores_total = qs_profiles.filter(role="PROFESSOR").count()
        auxiliares_total = qs_profiles.filter(role__icontains="AUX").count()
        usuarios_por_role = list(
            qs_profiles.values("role")
                      .annotate(total=Count("id"))
                      .order_by("-total", "role")
        )

    ctx = {
        "unidade": unidade,

        # KPIs
        "turmas_total": turmas.count(),
        "usuarios_total": usuarios_total,
        "professores_total": professores_total,
        "auxiliares_total": auxiliares_total,

        # Lista
        "turmas": turmas,
        "usuarios_por_role": usuarios_por_role,
    }
    return render(request, "org/unidade_detail.html", ctx)



@login_required
@require_perm("org.manage_secretaria")
def secretaria_create(request):
    p_me = get_profile(request.user)

    if request.method == "POST":
        form = SecretariaForm(request.POST, user=request.user)
        if form.is_valid():
            secretaria = form.save(commit=False)

            # MUNICIPAL: município sempre o dele
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

    # MUNICIPAL: não edita secretaria de outro município
    if (not is_admin(request.user)) and p_me and p_me.municipio_id:
        if secretaria.municipio_id != p_me.municipio_id:
            return HttpResponseForbidden("403 — Fora do seu município.")

    if request.method == "POST":
        form = SecretariaForm(request.POST, instance=secretaria, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)

            # MUNICIPAL: NÃO pode trocar município
            if (not is_admin(request.user)) and p_me and p_me.municipio_id:
                obj.municipio_id = p_me.municipio_id

            obj.save()
            messages.success(request, "Secretaria atualizada com sucesso.")
            return redirect("org:secretaria_detail", pk=obj.pk)

        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = SecretariaForm(instance=secretaria, user=request.user)

    return render(
        request,
        "org/secretaria_form.html",
        {"form": form, "mode": "update", "secretaria": secretaria},
    )


# =============================
# Unidades (CRUD)
# =============================

@login_required
def unidade_list(request):
    q = (request.GET.get("q") or "").strip()
    municipio_id = (request.GET.get("municipio") or "").strip()
    p = get_profile(request.user)
    if not is_admin(request.user) and p and p.municipio_id:
        municipio_id = str(p.municipio_id)

    secretaria_id = (request.GET.get("secretaria") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()

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
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(codigo_inep__icontains=q)
            | Q(cnpj__icontains=q)
            | Q(secretaria__nome__icontains=q)
            | Q(secretaria__municipio__nome__icontains=q)
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    municipios = scope_filter_municipios(
        request.user,
        Municipio.objects.filter(ativo=True).order_by("nome")
    )

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


@login_required
def unidade_detail(request, pk: int):
    from core.rbac import scope_filter_unidades

    unidade_qs = scope_filter_unidades(
        request.user,
        Unidade.objects.select_related("secretaria", "secretaria__municipio")
    )
    unidade = get_object_or_404(unidade_qs, pk=pk)

    # ✅ KPIs + listas
    turmas = Turma.objects.filter(unidade_id=unidade.id).order_by("-ano_letivo", "nome")
    setores = Setor.objects.filter(unidade_id=unidade.id).order_by("nome")

    usuarios_total = professores_total = auxiliares_total = 0
    usuarios_por_role = []

    if _profile_has_field("unidade"):
        qs_profiles = Profile.objects.filter(unidade_id=unidade.id)
        usuarios_total = qs_profiles.count()
        professores_total = qs_profiles.filter(role="PROFESSOR").count()
        auxiliares_total = qs_profiles.filter(role__icontains="AUX").count()
        usuarios_por_role = list(
            qs_profiles.values("role")
                      .annotate(total=Count("id"))
                      .order_by("-total", "role")
        )

    ctx = {
        "unidade": unidade,

        # KPIs
        "turmas_total": turmas.count(),
        "usuarios_total": usuarios_total,
        "professores_total": professores_total,
        "auxiliares_total": auxiliares_total,

        # Listas
        "turmas": turmas,
        "setores": setores,
        "usuarios_por_role": usuarios_por_role,
    }
    return render(request, "org/unidade_detail.html", ctx)


@login_required
def unidade_create(request):
    if request.method == "POST":
        form = UnidadeForm(request.POST)
        if form.is_valid():
            unidade = form.save()
            messages.success(request, "Unidade criada com sucesso.")
            return redirect("org:unidade_detail", pk=unidade.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = UnidadeForm()

    return render(request, "org/unidade_form.html", {"form": form, "mode": "create"})


@login_required
def unidade_update(request, pk: int):
    unidade = get_object_or_404(Unidade, pk=pk)

    # (opcional) aqui dá pra aplicar escopo depois, se você quiser bloquear URL direta também

    if request.method == "POST":
        form = UnidadeForm(request.POST, instance=unidade)
        if form.is_valid():
            form.save()
            messages.success(request, "Unidade atualizada com sucesso.")
            return redirect("org:unidade_detail", pk=unidade.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = UnidadeForm(instance=unidade)

    return render(
        request,
        "org/unidade_form.html",
        {"form": form, "mode": "update", "unidade": unidade},
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

    if unidade_id.isdigit():
        qs = qs.filter(unidade_id=int(unidade_id))

    if q:
        qs = qs.filter(
            Q(nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__secretaria__nome__icontains=q)
        )

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    unidades = Unidade.objects.filter(ativo=True).order_by("nome")

    return render(
        request,
        "org/setor_list.html",
        {"q": q, "unidade_id": unidade_id, "page_obj": page_obj, "unidades": unidades},
    )


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

    # ✅ Bloqueio por escopo municipal (URL direta)
    block = _ensure_in_scope_or_403(request.user, setor.unidade.secretaria.municipio_id)
    if block:
        return block

    usuarios = []
    usuarios_total = 0
    if _profile_has_field("setor"):
        qs_profiles = Profile.objects.filter(setor_id=setor.id).select_related("user")
        usuarios_total = qs_profiles.count()
        usuarios = list(qs_profiles.order_by("user__username"))

    return render(
        request,
        "org/setor_detail.html",
        {"setor": setor, "usuarios_total": usuarios_total, "usuarios": usuarios},
    )


@login_required
def setor_create(request):
    if request.method == "POST":
        form = SetorForm(request.POST)
        if form.is_valid():
            setor = form.save()
            messages.success(request, "Setor criado com sucesso.")
            return redirect("org:setor_detail", pk=setor.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = SetorForm()

    return render(request, "org/setor_form.html", {"form": form, "mode": "create"})


@login_required
def setor_update(request, pk: int):
    setor = get_object_or_404(Setor, pk=pk)

    # (opcional) aqui também dá pra aplicar escopo depois, se você quiser bloquear URL direta

    if request.method == "POST":
        form = SetorForm(request.POST, instance=setor)
        if form.is_valid():
            form.save()
            messages.success(request, "Setor atualizado com sucesso.")
            return redirect("org:setor_detail", pk=setor.pk)
        messages.error(request, "Corrija os erros do formulário.")
    else:
        form = SetorForm(instance=setor)

    return render(
        request,
        "org/setor_form.html",
        {"form": form, "mode": "update", "setor": setor},
    )
