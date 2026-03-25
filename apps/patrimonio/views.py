from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import is_admin, scope_filter_locais_estruturais, scope_filter_secretarias, scope_filter_unidades
from apps.core.services_auditoria import registrar_auditoria
from apps.core.services_transparencia import publicar_evento_transparencia
from apps.org.models import LocalEstrutural, Municipio, Secretaria, Unidade

from .forms import PatrimonioCadastroForm, PatrimonioInventarioForm, PatrimonioMovimentacaoForm
from .models import (
    BemPatrimonial,
    InventarioItem,
    MovimentacaoPatrimonial,
    PatrimonioCadastro,
    PatrimonioInventario,
    PatrimonioMovimentacao,
)


def _resolve_municipio(request, *, require_selected: bool = False):
    user = request.user
    if is_admin(user):
        municipio_id = (request.GET.get("municipio") or request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            return Municipio.objects.filter(pk=int(municipio_id), ativo=True).first()
        if require_selected:
            return None
        return Municipio.objects.filter(ativo=True).order_by("nome").first()

    profile = getattr(user, "profile", None)
    if profile and profile.municipio_id:
        return Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
    return None


def _municipios_admin(request):
    if not is_admin(request.user):
        return Municipio.objects.none()
    return Municipio.objects.filter(ativo=True).order_by("nome")


def _q_municipio(municipio: Municipio) -> str:
    return f"?municipio={municipio.pk}"


def _q_scope(request) -> str:
    parts: list[str] = []
    for key in ("secretaria", "unidade", "local"):
        value = (request.GET.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value}")
    return ("&" + "&".join(parts)) if parts else ""


def _scope_context(request, municipio: Municipio):
    secretaria_id = (request.GET.get("secretaria") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()
    local_id = (request.GET.get("local") or "").strip()

    secretarias = scope_filter_secretarias(
        request.user,
        Secretaria.objects.filter(municipio=municipio, ativo=True).order_by("nome"),
    )
    unidades = scope_filter_unidades(
        request.user,
        Unidade.objects.filter(secretaria__municipio=municipio, ativo=True).select_related("secretaria").order_by("nome"),
    )
    locais = scope_filter_locais_estruturais(
        request.user,
        LocalEstrutural.objects.filter(municipio=municipio, status=LocalEstrutural.Status.ATIVO)
        .select_related("unidade", "secretaria")
        .order_by("nome"),
    )

    if secretaria_id.isdigit():
        unidades = unidades.filter(secretaria_id=int(secretaria_id))
        locais = locais.filter(secretaria_id=int(secretaria_id))
    if unidade_id.isdigit():
        locais = locais.filter(unidade_id=int(unidade_id))

    return {
        "secretarias": secretarias,
        "unidades": unidades,
        "locais": locais,
        "secretaria_id": secretaria_id,
        "unidade_id": unidade_id,
        "local_id": local_id,
    }


def _parse_date(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _apply_scope_filters(
    request,
    qs,
    *,
    secretaria_field: str | None,
    unidade_field: str | None,
    setor_field: str | None = None,
    local_field: str | None = None,
):
    profile = getattr(request.user, "profile", None)

    if not is_admin(request.user) and profile:
        if secretaria_field and getattr(profile, "secretaria_id", None):
            qs = qs.filter(**{f"{secretaria_field}_id": profile.secretaria_id})
        if unidade_field and getattr(profile, "unidade_id", None):
            qs = qs.filter(**{f"{unidade_field}_id": profile.unidade_id})
        if setor_field and getattr(profile, "setor_id", None):
            qs = qs.filter(**{f"{setor_field}_id": profile.setor_id})
        if local_field and getattr(profile, "local_estrutural_id", None):
            qs = qs.filter(**{f"{local_field}_id": profile.local_estrutural_id})

    secretaria_id = (request.GET.get("secretaria") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()
    setor_id = (request.GET.get("setor") or "").strip()
    local_id = (request.GET.get("local") or "").strip()

    if secretaria_field and secretaria_id.isdigit():
        qs = qs.filter(**{f"{secretaria_field}_id": int(secretaria_id)})
    if unidade_field and unidade_id.isdigit():
        qs = qs.filter(**{f"{unidade_field}_id": int(unidade_id)})
    if setor_field and setor_id.isdigit():
        qs = qs.filter(**{f"{setor_field}_id": int(setor_id)})
    if local_field and local_id.isdigit():
        qs = qs.filter(**{f"{local_field}_id": int(local_id)})
    return qs


@login_required
@require_perm("patrimonio.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)

    bens = _apply_scope_filters(
        request,
        PatrimonioCadastro.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        setor_field="setor",
        local_field="local_estrutural",
    )
    movs = _apply_scope_filters(
        request,
        PatrimonioMovimentacao.objects.filter(municipio=municipio),
        secretaria_field="bem__secretaria",
        unidade_field="bem__unidade",
        setor_field="bem__setor",
        local_field="bem__local_estrutural",
    )
    invs = _apply_scope_filters(
        request,
        PatrimonioInventario.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        local_field="local_estrutural",
    )
    return render(
        request,
        "patrimonio/index.html",
        {
            "title": "Patrimônio",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "cards": [
                {"label": "Bens ativos", "value": bens.filter(status=PatrimonioCadastro.Status.ATIVO).count()},
                {"label": "Em manutenção", "value": bens.filter(situacao=PatrimonioCadastro.Situacao.MANUTENCAO).count()},
                {"label": "Movimentações mês", "value": movs.filter(data_movimento__month=timezone.localdate().month).count()},
                {"label": "Inventários abertos", "value": invs.filter(status=PatrimonioInventario.Status.ABERTO).count()},
                {"label": "Secretarias no escopo", "value": bens.exclude(secretaria_id=None).values("secretaria_id").distinct().count()},
                {"label": "Unidades no escopo", "value": bens.exclude(unidade_id=None).values("unidade_id").distinct().count()},
                {"label": "Locais no escopo", "value": bens.exclude(local_estrutural_id=None).values("local_estrutural_id").distinct().count()},
            ],
            "latest_movs": movs.select_related("bem", "bem__secretaria", "bem__unidade", "bem__local_estrutural").order_by("-data_movimento", "-id")[:10],
            "latest_invs": invs.order_by("-criado_em")[:8],
            "actions": [
                {
                    "label": "Novo bem",
                    "url": reverse("patrimonio:bem_create") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Movimentações",
                    "url": reverse("patrimonio:movimentacao_list") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-right-left",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Inventários",
                    "url": reverse("patrimonio:inventario_list") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-clipboard-check",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Relatórios",
                    "url": reverse("patrimonio:relatorios") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-chart-column",
                    "variant": "gp-button--ghost",
                },
            ],
            **scope_ctx,
        },
    )


@login_required
@require_perm("patrimonio.view")
def bem_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)
    q = (request.GET.get("q") or "").strip()
    situacao = (request.GET.get("situacao") or "").strip()
    qs = _apply_scope_filters(
        request,
        PatrimonioCadastro.objects.filter(municipio=municipio).select_related("secretaria", "unidade", "setor", "local_estrutural"),
        secretaria_field="secretaria",
        unidade_field="unidade",
        setor_field="setor",
        local_field="local_estrutural",
    )
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(tombo__icontains=q) | Q(nome__icontains=q))
    if situacao:
        qs = qs.filter(situacao=situacao)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("nome"):
            rows.append(
                [
                    item.codigo,
                    item.tombo,
                    item.nome,
                    item.get_situacao_display(),
                    item.get_status_display(),
                    item.secretaria.nome if item.secretaria else "",
                    item.unidade.nome if item.unidade else "",
                    item.local_estrutural.nome if item.local_estrutural else (item.setor.nome if item.setor else ""),
                ]
            )
        headers = ["Codigo", "Tombo", "Nome", "Situacao", "Status", "Secretaria", "Unidade", "Local"]
        if export == "csv":
            return export_csv("patrimonio_bens.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="patrimonio_bens.pdf",
            title="Bens patrimoniais",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Situacao={situacao or '-'}",
        )
    return render(
        request,
        "patrimonio/bem_list.html",
        {
            "title": "Bens patrimoniais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("nome"),
            "q": q,
            "situacao": situacao,
            "situacao_choices": PatrimonioCadastro.Situacao.choices,
            "actions": [
                {
                    "label": "Novo bem",
                    "url": reverse("patrimonio:bem_create") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&q={q}&situacao={situacao}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&q={q}&situacao={situacao}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Relatórios",
                    "url": reverse("patrimonio:relatorios") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-chart-column",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Painel patrimônio",
                    "url": reverse("patrimonio:index") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
            **scope_ctx,
        },
    )


@login_required
@require_perm("patrimonio.manage")
def bem_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para adicionar bem.")
        return redirect("patrimonio:bem_list")
    form = PatrimonioCadastroForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Bem patrimonial cadastrado.")
        return redirect(reverse("patrimonio:bem_list") + _q_municipio(municipio) + _q_scope(request))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo bem patrimonial",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("patrimonio:bem_list") + _q_municipio(municipio) + _q_scope(request),
            "submit_label": "Salvar bem",
        },
    )


@login_required
@require_perm("patrimonio.manage")
def bem_update(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(PatrimonioCadastro, pk=pk, municipio=municipio)
    form = PatrimonioCadastroForm(request.POST or None, instance=obj, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bem atualizado.")
        return redirect(reverse("patrimonio:bem_list") + _q_municipio(municipio) + _q_scope(request))
    return render(
        request,
        "core/form_base.html",
        {
            "title": f"Editar bem {obj.codigo}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("patrimonio:bem_list") + _q_municipio(municipio) + _q_scope(request),
            "submit_label": "Salvar alterações",
        },
    )


@login_required
@require_perm("patrimonio.view")
def movimentacao_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)
    tipo = (request.GET.get("tipo") or "").strip()
    q = (request.GET.get("q") or "").strip()
    qs = _apply_scope_filters(
        request,
        PatrimonioMovimentacao.objects.filter(municipio=municipio).select_related(
            "bem",
            "bem__secretaria",
            "bem__unidade",
            "bem__setor",
            "bem__local_estrutural",
            "local_origem",
            "local_destino",
            "unidade_origem",
            "unidade_destino",
        ),
        secretaria_field="bem__secretaria",
        unidade_field="bem__unidade",
        setor_field="bem__setor",
        local_field="bem__local_estrutural",
    )
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(Q(bem__nome__icontains=q) | Q(observacao__icontains=q))

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("-data_movimento", "-id"):
            rows.append(
                [
                    str(item.data_movimento),
                    item.bem.codigo,
                    item.bem.nome,
                    item.get_tipo_display(),
                    item.bem.secretaria.nome if item.bem.secretaria else "",
                    item.unidade_origem.nome if item.unidade_origem else "",
                    item.unidade_destino.nome if item.unidade_destino else "",
                    item.local_destino.nome if item.local_destino else (item.bem.local_estrutural.nome if item.bem.local_estrutural else ""),
                ]
            )
        headers = ["Data", "Bem codigo", "Bem", "Tipo", "Secretaria", "Origem", "Destino", "Local destino"]
        if export == "csv":
            return export_csv("patrimonio_movimentacoes.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="patrimonio_movimentacoes.pdf",
            title="Movimentacoes patrimoniais",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Tipo={tipo or '-'}",
        )
    return render(
        request,
        "patrimonio/movimentacao_list.html",
        {
            "title": "Movimentações patrimoniais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-data_movimento", "-id"),
            "tipo": tipo,
            "q": q,
            "tipo_choices": PatrimonioMovimentacao.Tipo.choices,
            "actions": [
                {
                    "label": "Nova movimentação",
                    "url": reverse("patrimonio:movimentacao_create") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&q={q}&tipo={tipo}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&q={q}&tipo={tipo}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Relatórios",
                    "url": reverse("patrimonio:relatorios") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-chart-column",
                    "variant": "gp-button--ghost",
                },
            ],
            **scope_ctx,
        },
    )


@login_required
@require_perm("patrimonio.manage")
def movimentacao_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar movimentação.")
        return redirect("patrimonio:movimentacao_list")
    form = PatrimonioMovimentacaoForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()

        bem = obj.bem
        if obj.tipo == PatrimonioMovimentacao.Tipo.BAIXA:
            bem.situacao = PatrimonioCadastro.Situacao.BAIXADO
            bem.status = PatrimonioCadastro.Status.INATIVO
            bem.save(update_fields=["situacao", "status", "atualizado_em"])
        elif obj.tipo == PatrimonioMovimentacao.Tipo.MANUTENCAO:
            bem.situacao = PatrimonioCadastro.Situacao.MANUTENCAO
            bem.save(update_fields=["situacao", "atualizado_em"])
        elif obj.tipo == PatrimonioMovimentacao.Tipo.TRANSFERENCIA and obj.unidade_destino_id:
            bem.unidade_id = obj.unidade_destino_id
            bem.situacao = PatrimonioCadastro.Situacao.EM_USO
            bem.save(update_fields=["unidade", "situacao", "atualizado_em"])

        registrar_auditoria(
            municipio=municipio,
            modulo="PATRIMONIO",
            evento="MOVIMENTACAO_REGISTRADA",
            entidade="PatrimonioMovimentacao",
            entidade_id=obj.pk,
            usuario=request.user,
            depois={"tipo": obj.tipo, "bem": obj.bem.codigo},
        )
        messages.success(request, "Movimentação patrimonial registrada.")
        return redirect(reverse("patrimonio:movimentacao_list") + _q_municipio(municipio) + _q_scope(request))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Nova movimentação patrimonial",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("patrimonio:movimentacao_list") + _q_municipio(municipio) + _q_scope(request),
            "submit_label": "Salvar movimentação",
        },
    )


@login_required
@require_perm("patrimonio.view")
def inventario_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)
    status = (request.GET.get("status") or "").strip()
    qs = _apply_scope_filters(
        request,
        PatrimonioInventario.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        local_field="local_estrutural",
    )
    if status:
        qs = qs.filter(status=status)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        rows = []
        for item in qs.order_by("-criado_em"):
            rows.append(
                [
                    item.codigo,
                    item.get_status_display(),
                    str(item.total_bens),
                    str(item.total_bens_ativos),
                    str(item.criado_em),
                    str(item.concluido_em or ""),
                ]
            )
        headers = ["Codigo", "Status", "Total bens", "Ativos", "Criado em", "Concluido em"]
        if export == "csv":
            return export_csv("patrimonio_inventarios.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="patrimonio_inventarios.pdf",
            title="Inventarios patrimoniais",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Status={status or '-'}",
        )
    return render(
        request,
        "patrimonio/inventario_list.html",
        {
            "title": "Inventários patrimoniais",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": qs.order_by("-criado_em"),
            "status": status,
            "status_choices": PatrimonioInventario.Status.choices,
            "actions": [
                {
                    "label": "Novo inventário",
                    "url": reverse("patrimonio:inventario_create") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&status={status}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&status={status}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Relatórios",
                    "url": reverse("patrimonio:relatorios") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-chart-column",
                    "variant": "gp-button--ghost",
                },
            ],
            **scope_ctx,
        },
    )


@login_required
@require_perm("patrimonio.view")
def relatorios(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    scope_ctx = _scope_context(request, municipio)
    scope_qs = _q_scope(request)
    date_from_raw = (request.GET.get("data_inicio") or "").strip()
    date_to_raw = (request.GET.get("data_fim") or "").strip()
    date_from = _parse_date(date_from_raw)
    date_to = _parse_date(date_to_raw)

    bens_qs = _apply_scope_filters(
        request,
        PatrimonioCadastro.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        setor_field="setor",
        local_field="local_estrutural",
    )
    movs_qs = _apply_scope_filters(
        request,
        PatrimonioMovimentacao.objects.filter(municipio=municipio),
        secretaria_field="bem__secretaria",
        unidade_field="bem__unidade",
        setor_field="bem__setor",
        local_field="bem__local_estrutural",
    )
    inventarios_qs = _apply_scope_filters(
        request,
        PatrimonioInventario.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        local_field="local_estrutural",
    )
    bens_novo_qs = _apply_scope_filters(
        request,
        BemPatrimonial.objects.filter(municipio=municipio),
        secretaria_field="secretaria",
        unidade_field="unidade",
        local_field="local_estrutural",
    )
    movs_novo_qs = _apply_scope_filters(
        request,
        MovimentacaoPatrimonial.objects.filter(bem__municipio=municipio),
        secretaria_field="bem__secretaria",
        unidade_field="bem__unidade",
        local_field="bem__local_estrutural",
    )
    inventario_itens_qs = _apply_scope_filters(
        request,
        InventarioItem.objects.filter(inventario__municipio=municipio),
        secretaria_field="inventario__secretaria",
        unidade_field="inventario__unidade",
        local_field="bem__local_estrutural",
    )

    if date_from:
        movs_qs = movs_qs.filter(data_movimento__gte=date_from)
        movs_novo_qs = movs_novo_qs.filter(data_movimentacao__date__gte=date_from)
        inventarios_qs = inventarios_qs.filter(criado_em__date__gte=date_from)
    if date_to:
        movs_qs = movs_qs.filter(data_movimento__lte=date_to)
        movs_novo_qs = movs_novo_qs.filter(data_movimentacao__date__lte=date_to)
        inventarios_qs = inventarios_qs.filter(criado_em__date__lte=date_to)

    bens_por_secretaria = list(
        bens_qs.values("secretaria__nome")
        .annotate(
            total=Count("id"),
            ativos=Count("id", filter=Q(status=PatrimonioCadastro.Status.ATIVO)),
            manutencao=Count("id", filter=Q(situacao=PatrimonioCadastro.Situacao.MANUTENCAO)),
            baixados=Count("id", filter=Q(situacao=PatrimonioCadastro.Situacao.BAIXADO)),
        )
        .order_by("secretaria__nome")
    )
    bens_por_unidade = list(
        bens_qs.values("unidade__nome")
        .annotate(
            total=Count("id"),
            ativos=Count("id", filter=Q(status=PatrimonioCadastro.Status.ATIVO)),
            valor_total=Coalesce(
                Sum("valor_aquisicao"),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
        )
        .order_by("unidade__nome")
    )
    bens_por_local = list(
        bens_qs.annotate(local_nome=Coalesce("local_estrutural__nome", "setor__nome", Value("Sem local")))
        .values("local_nome")
        .annotate(
            total=Count("id"),
            valor_total=Coalesce(
                Sum("valor_aquisicao"),
                Value(0, output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
        )
        .order_by("local_nome")
    )
    movs_por_tipo = list(
        movs_qs.values("tipo").annotate(total=Count("id")).order_by("tipo")
    )

    inventario_divergencias = inventario_itens_qs.filter(
        status_conferencia__in={
            InventarioItem.StatusConferencia.DIVERGENTE,
            InventarioItem.StatusConferencia.NAO_LOCALIZADO,
            InventarioItem.StatusConferencia.DANIFICADO,
        }
    ).count()
    transferencias_novo_modelo = movs_novo_qs.filter(
        tipo_movimentacao__in={
            MovimentacaoPatrimonial.TipoMovimentacao.TRANSFERENCIA_INTERNA,
            MovimentacaoPatrimonial.TipoMovimentacao.TRANSFERENCIA_UNIDADE,
            MovimentacaoPatrimonial.TipoMovimentacao.TRANSFERENCIA_SECRETARIA,
        }
    ).count()

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = ["Tipo", "Agrupador", "Quantidade", "Valor"]
        rows: list[list[str]] = []

        for row in bens_por_secretaria:
            rows.append(
                [
                    "Bens por secretaria",
                    row.get("secretaria__nome") or "Sem secretaria",
                    str(row.get("total") or 0),
                    "0",
                ]
            )
        for row in bens_por_unidade:
            rows.append(
                [
                    "Bens por unidade",
                    row.get("unidade__nome") or "Sem unidade",
                    str(row.get("total") or 0),
                    str(row.get("valor_total") or 0),
                ]
            )
        for row in bens_por_local:
            rows.append(
                [
                    "Bens por local",
                    row.get("local_nome") or "Sem local",
                    str(row.get("total") or 0),
                    str(row.get("valor_total") or 0),
                ]
            )
        tipo_labels = dict(PatrimonioMovimentacao.Tipo.choices)
        for row in movs_por_tipo:
            rows.append(
                [
                    "Movimentações por tipo",
                    tipo_labels.get(row.get("tipo"), row.get("tipo") or "N/A"),
                    str(row.get("total") or 0),
                    "0",
                ]
            )

        rows.append(["Indicador", "Bens sem responsável (novo modelo)", str(bens_novo_qs.filter(responsavel_atual__isnull=True, ativo=True).count()), "0"])
        rows.append(["Indicador", "Transferências (novo modelo)", str(transferencias_novo_modelo), "0"])
        rows.append(["Indicador", "Inventário com divergência (novo modelo)", str(inventario_divergencias), "0"])

        if export == "csv":
            return export_csv("patrimonio_relatorios.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="patrimonio_relatorios.pdf",
            title="Relatórios de patrimônio",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Data início={date_from_raw or '-'} | Data fim={date_to_raw or '-'}",
        )

    return render(
        request,
        "patrimonio/relatorios.html",
        {
            "title": "Relatórios de Patrimônio",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "data_inicio": date_from_raw,
            "data_fim": date_to_raw,
            "bens_por_secretaria": bens_por_secretaria,
            "bens_por_unidade": bens_por_unidade,
            "bens_por_local": bens_por_local,
            "movs_por_tipo": [
                {"tipo_label": dict(PatrimonioMovimentacao.Tipo.choices).get(row["tipo"], row["tipo"]), "total": row["total"]}
                for row in movs_por_tipo
            ],
            "movimentos_recentes": movs_qs.select_related("bem", "bem__secretaria", "bem__unidade", "bem__local_estrutural").order_by("-data_movimento", "-id")[:20],
            "cards": [
                {"label": "Bens ativos", "value": bens_qs.filter(status=PatrimonioCadastro.Status.ATIVO).count()},
                {"label": "Bens em manutenção", "value": bens_qs.filter(situacao=PatrimonioCadastro.Situacao.MANUTENCAO).count()},
                {"label": "Bens baixados", "value": bens_qs.filter(situacao=PatrimonioCadastro.Situacao.BAIXADO).count()},
                {"label": "Bens sem responsável (novo modelo)", "value": bens_novo_qs.filter(responsavel_atual__isnull=True, ativo=True).count()},
                {"label": "Inventários abertos", "value": inventarios_qs.filter(status=PatrimonioInventario.Status.ABERTO).count()},
                {"label": "Movimentações no período", "value": movs_qs.count() + movs_novo_qs.count()},
                {"label": "Transferências (novo modelo)", "value": transferencias_novo_modelo},
                {"label": "Inventário com divergência (novo modelo)", "value": inventario_divergencias},
            ],
            "actions": [
                {
                    "label": "Voltar ao painel",
                    "url": reverse("patrimonio:index") + _q_municipio(municipio) + scope_qs,
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&data_inicio={date_from_raw}&data_fim={date_to_raw}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}{scope_qs}&data_inicio={date_from_raw}&data_fim={date_to_raw}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
            ],
            **scope_ctx,
        },
    )


@login_required
@require_perm("patrimonio.manage")
def inventario_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para iniciar inventário.")
        return redirect("patrimonio:inventario_list")
    form = PatrimonioInventarioForm(request.POST or None, municipio=municipio)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.criado_por = request.user
        obj.save()
        messages.success(request, "Inventário aberto com sucesso.")
        return redirect(reverse("patrimonio:inventario_list") + _q_municipio(municipio) + _q_scope(request))
    return render(
        request,
        "core/form_base.html",
        {
            "title": "Novo inventário patrimonial",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [],
            "form": form,
            "cancel_url": reverse("patrimonio:inventario_list") + _q_municipio(municipio) + _q_scope(request),
            "submit_label": "Salvar inventário",
        },
    )


@login_required
@require_perm("patrimonio.manage")
@require_POST
def inventario_concluir(request, pk: int):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")
    obj = get_object_or_404(PatrimonioInventario, pk=pk, municipio=municipio)
    qs_bens = PatrimonioCadastro.objects.filter(municipio=municipio)
    if obj.unidade_id:
        qs_bens = qs_bens.filter(unidade_id=obj.unidade_id)
    if obj.local_estrutural_id:
        qs_bens = qs_bens.filter(local_estrutural_id=obj.local_estrutural_id)
    obj.total_bens = qs_bens.count()
    obj.total_bens_ativos = qs_bens.filter(status=PatrimonioCadastro.Status.ATIVO).count()
    obj.status = PatrimonioInventario.Status.CONCLUIDO
    obj.concluido_em = timezone.now()
    obj.concluido_por = request.user
    obj.save(
        update_fields=[
            "total_bens",
            "total_bens_ativos",
            "status",
            "concluido_em",
            "concluido_por",
            "atualizado_em",
        ]
    )
    publicar_evento_transparencia(
        municipio=municipio,
        modulo="PATRIMONIO",
        tipo_evento="INVENTARIO_CONCLUIDO",
        titulo=f"Inventário {obj.codigo} concluído",
        referencia=obj.codigo,
        dados={"total_bens": obj.total_bens, "total_bens_ativos": obj.total_bens_ativos},
        publico=False,
    )
    messages.success(request, "Inventário concluído.")
    return redirect(reverse("patrimonio:inventario_list") + _q_municipio(municipio) + _q_scope(request))


# compatibilidade com rota antiga
create = bem_create
