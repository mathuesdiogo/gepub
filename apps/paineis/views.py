from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Max, Q
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_template
from apps.core.rbac import is_admin, role_scope_base
from apps.core.services_auditoria import registrar_auditoria
from apps.org.models import Municipio

from .forms import DatasetCreateForm
from .models import Dataset, DatasetColumn, DatasetVersion, ExportJob
from .services import (
    build_dashboard_payload,
    build_dataset_package,
    load_rows_from_csv_bytes,
    process_dataset_version,
)
from .tasks import process_dataset_version_task


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


def _scoped_queryset(request):
    qs = Dataset.objects.select_related("municipio", "secretaria", "unidade", "setor")
    user = request.user

    if is_admin(user):
        return qs

    profile = getattr(user, "profile", None)
    if not profile or not profile.municipio_id:
        return qs.none()

    qs = qs.filter(municipio_id=profile.municipio_id)

    role = (getattr(profile, "role", "") or "").upper()
    role_base = role_scope_base(role)
    if role_base == "SECRETARIA" and profile.secretaria_id:
        qs = qs.filter(Q(secretaria_id=profile.secretaria_id) | Q(secretaria__isnull=True))
    if role_base == "UNIDADE" and profile.unidade_id:
        qs = qs.filter(Q(unidade_id=profile.unidade_id) | Q(unidade__isnull=True))

    return qs


def _latest_version(dataset: Dataset) -> DatasetVersion | None:
    return dataset.versoes.order_by("-numero").first()


def _dataset_status_counts(qs):
    return {
        "total": qs.count(),
        "rascunho": qs.filter(status=Dataset.Status.RASCUNHO).count(),
        "validado": qs.filter(status=Dataset.Status.VALIDADO).count(),
        "publicado": qs.filter(status=Dataset.Status.PUBLICADO).count(),
        "arquivado": qs.filter(status=Dataset.Status.ARQUIVADO).count(),
    }


def _build_dashboard_summary(payload: dict, filters: dict) -> str:
    kpis = payload.get("kpis") or {}
    ranking = payload.get("ranking") or {}
    line = payload.get("line") or {}

    linhas = int(kpis.get("linhas_filtradas") or 0)
    total = int(kpis.get("linhas_total") or 0)
    valor_col = str(kpis.get("coluna_valor") or "-")
    soma = str(kpis.get("soma_principal") or "-")

    top_label = ""
    top_value = ""
    labels = ranking.get("labels") or []
    values = ranking.get("values") or []
    if labels and values:
        top_label = str(labels[0])
        try:
            top_value = f"{float(values[0]):.2f}"
        except Exception:
            top_value = str(values[0])

    trend = ""
    line_values = line.get("values") or []
    line_labels = line.get("labels") or []
    if len(line_values) >= 2:
        prev_val = float(line_values[-2] or 0)
        curr_val = float(line_values[-1] or 0)
        if prev_val:
            delta = ((curr_val - prev_val) / prev_val) * 100
            sinal = "crescimento" if delta >= 0 else "redução"
            trend = f"Último período ({line_labels[-1]}): {sinal} de {abs(delta):.1f}% frente ao período anterior."

    filtros_ativos = []
    for key, label in [
        ("date_start", "data inicial"),
        ("date_end", "data final"),
        ("secretaria", "secretaria"),
        ("unidade", "unidade"),
        ("categoria", "categoria"),
    ]:
        if filters.get(key):
            filtros_ativos.append(f"{label}: {filters[key]}")

    base = (
        f"Foram analisadas {linhas} linhas de um total de {total}. "
        f"A métrica principal ({valor_col}) soma {soma}."
    )
    if top_label:
        base += f" Maior concentração atual em {top_label} ({top_value})."
    if trend:
        base += f" {trend}"
    if filtros_ativos:
        base += " Filtros ativos: " + "; ".join(filtros_ativos) + "."
    return base


@login_required
@require_perm("paineis.view")
def index(request):
    return redirect("paineis:dataset_list")


@login_required
@require_perm("paineis.view")
def dataset_list(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Selecione um município para acessar Painéis.")
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    categoria = (request.GET.get("categoria") or "").strip()

    base_qs = _scoped_queryset(request).filter(municipio=municipio)
    qs = base_qs
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(descricao__icontains=q) | Q(categoria__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if categoria:
        qs = qs.filter(categoria__icontains=categoria)

    items_qs = qs.order_by("-atualizado_em")
    status_counts = _dataset_status_counts(base_qs)
    item_ids = list(items_qs.values_list("id", flat=True)[:5000])
    version_status_map = {}
    for version in DatasetVersion.objects.filter(dataset_id__in=item_ids).order_by("dataset_id", "-numero", "-id"):
        if version.dataset_id not in version_status_map:
            version_status_map[version.dataset_id] = version.get_status_display()

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = [
            "Nome",
            "Categoria",
            "Fonte",
            "Visibilidade",
            "Status",
            "Municipio",
            "Secretaria",
            "Unidade",
            "Atualizado em",
        ]
        rows = []
        for item in items_qs[:5000]:
            rows.append(
                [
                    item.nome,
                    item.categoria or "",
                    item.get_fonte_display(),
                    item.get_visibilidade_display(),
                    item.get_status_display(),
                    item.municipio.nome,
                    item.secretaria.nome if item.secretaria else "",
                    item.unidade.nome if item.unidade else "",
                    str(item.atualizado_em),
                ]
            )
        if export == "csv":
            return export_csv("bi_datasets.csv", headers, rows)
        return export_pdf_template(
            request,
            filename="bi_datasets.pdf",
            title="Catalogo de Datasets BI",
            template_name="core/relatorios/pdf/table.html",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            filtros=f"Busca={q or '-'} | Status={status or '-'} | Categoria={categoria or '-'}",
            context={"headers": headers, "rows": rows},
        )

    items = list(items_qs)
    for item in items:
        item.version_status_label = version_status_map.get(item.id, "Sem versão")

    return render(
        request,
        "paineis/list.html",
        {
            "title": "Painéis BI",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": items,
            "q": q,
            "status": status,
            "categoria": categoria,
            "status_choices": Dataset.Status.choices,
            "counts": status_counts,
            "actions": [
                {
                    "label": "Novo dataset",
                    "url": reverse("paineis:dataset_create") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-plus",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&status={status}&categoria={categoria}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&status={status}&categoria={categoria}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Portal",
                    "url": reverse("portal"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("paineis.manage")
def dataset_create(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        messages.error(request, "Selecione um município para criar dataset.")
        return redirect("paineis:dataset_list")

    form = DatasetCreateForm(request.POST or None, request.FILES or None, municipio=municipio, user=request.user)

    if request.method == "POST" and form.is_valid():
        dataset = form.save(commit=False)
        dataset.municipio = municipio
        dataset.criado_por = request.user
        dataset.atualizado_por = request.user
        dataset.status = Dataset.Status.RASCUNHO
        dataset.save()

        versao_num = (dataset.versoes.aggregate(max_num=Max("numero")).get("max_num") or 0) + 1
        version = DatasetVersion.objects.create(
            dataset=dataset,
            numero=versao_num,
            fonte=dataset.fonte,
            status=DatasetVersion.Status.PENDENTE,
            criado_por=request.user,
            logs="Aguardando processamento.",
        )

        uploaded = form.cleaned_data.get("arquivo")
        if uploaded:
            raw_bytes = uploaded.read()
            version.arquivo_original.save(uploaded.name, ContentFile(raw_bytes), save=True)

        google_sheet_url = form.cleaned_data.get("google_sheet_url") or ""
        processing_error = ""
        queued = False
        try:
            process_dataset_version_task.delay(version.pk, google_sheet_url=google_sheet_url, actor_id=request.user.pk)
            queued = True
        except Exception as exc:
            processing_error = str(exc)
            process_dataset_version(
                version.pk,
                google_sheet_url=google_sheet_url,
                actor=request.user,
            )

        version.refresh_from_db()
        dataset.refresh_from_db()

        if version.status == DatasetVersion.Status.CONCLUIDO:
            if dataset.visibilidade == Dataset.Visibilidade.PUBLICO:
                has_sensitive = version.colunas.filter(sensivel=True).exists()
                if has_sensitive:
                    messages.warning(
                        request,
                        "Processamento concluído com colunas sensíveis. Revise antes de publicar no portal.",
                    )
            messages.success(request, "Dataset processado e validado com sucesso.")
        elif version.status == DatasetVersion.Status.ERRO:
            messages.error(request, f"Falha ao processar dataset: {version.logs}")
        elif queued:
            messages.info(request, "Dataset enviado para fila de processamento assíncrono.")
        else:
            messages.warning(
                request,
                "Fila assíncrona indisponível. Processamento executado localmente."
                if not processing_error
                else f"Fila assíncrona indisponível ({processing_error}). Processamento local aplicado.",
            )

        return redirect(reverse("paineis:dataset_detail", args=[dataset.pk]) + f"?municipio={municipio.pk}")

    return render(
        request,
        "paineis/create.html",
        {
            "title": "Novo dataset BI",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "actions": [
                {
                    "label": "Voltar",
                    "url": reverse("paineis:dataset_list") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                }
            ],
            "form": form,
            "cancel_url": reverse("paineis:dataset_list") + f"?municipio={municipio.pk}",
            "submit_label": "Ingerir e validar",
            "enctype": "multipart/form-data",
            "source_cards": [
                {
                    "tipo": Dataset.Fonte.CSV,
                    "titulo": "CSV",
                    "descricao": "Carga rápida para tabelas analíticas.",
                    "icon": "fa-solid fa-file-csv",
                    "tone": "csv",
                },
                {
                    "tipo": Dataset.Fonte.XLSX,
                    "titulo": "Excel",
                    "descricao": "Planilhas .xlsx com leitura automática de colunas.",
                    "icon": "fa-solid fa-file-excel",
                    "tone": "xlsx",
                },
                {
                    "tipo": Dataset.Fonte.GOOGLE_SHEETS,
                    "titulo": "Google Sheets",
                    "descricao": "Sincronização por URL pública CSV.",
                    "icon": "fa-brands fa-google-drive",
                    "tone": "sheet",
                },
            ],
        },
    )


@login_required
@require_perm("paineis.view")
def dataset_detail(request, pk: int):
    dataset = get_object_or_404(_scoped_queryset(request), pk=pk)
    municipio = dataset.municipio
    version = _latest_version(dataset)

    schema = []
    profile = {}
    preview = []
    preview_headers = []
    preview_rows = []
    columns = DatasetColumn.objects.none()
    if version:
        schema = (version.schema_json or {}).get("columns") or []
        profile = version.profile_json or {}
        preview = version.preview_json or []
        columns = version.colunas.order_by("ordem")
        preview_headers = [str(col.get("name", "")) for col in schema]
        preview_rows = [[row.get(header, "") for header in preview_headers] for row in preview]

    return render(
        request,
        "paineis/detail.html",
        {
            "title": f"Dataset • {dataset.nome}",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "dataset": dataset,
            "version": version,
            "schema": schema,
            "profile": profile,
            "preview_headers": preview_headers,
            "preview_rows": preview_rows,
            "columns": columns,
            "dashboards": dataset.dashboards.order_by("nome"),
            "actions": [
                {
                    "label": "Visualizar dashboard",
                    "url": reverse("paineis:dashboard", args=[dataset.pk]) + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-chart-line",
                    "variant": "gp-button--primary",
                },
                {
                    "label": "Baixar pacote",
                    "url": reverse("paineis:dataset_package", args=[dataset.pk]) + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-file-zipper",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Voltar",
                    "url": reverse("paineis:dataset_list") + f"?municipio={municipio.pk}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("paineis.manage")
def dataset_publish(request, pk: int):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    dataset = get_object_or_404(_scoped_queryset(request), pk=pk)
    version = _latest_version(dataset)
    if not version or version.status != DatasetVersion.Status.CONCLUIDO:
        messages.error(request, "Não há versão válida para publicação.")
        return redirect("paineis:dataset_detail", pk=dataset.pk)

    checklist_flags = {
        "check_quality": bool(request.POST.get("check_quality")),
        "check_lgpd": bool(request.POST.get("check_lgpd")),
        "check_publication_rules": bool(request.POST.get("check_publication_rules")),
    }
    if not all(checklist_flags.values()):
        messages.error(request, "Publicação bloqueada: conclua o checklist de qualidade e privacidade.")
        return redirect("paineis:dataset_detail", pk=dataset.pk)

    schema = (version.schema_json or {}).get("columns") or []
    has_sensitive = any(bool(col.get("sensitive")) for col in schema)
    if dataset.visibilidade == Dataset.Visibilidade.PUBLICO and has_sensitive:
        messages.error(request, "Publicação bloqueada: dataset possui colunas sensíveis.")
        return redirect("paineis:dataset_detail", pk=dataset.pk)

    dataset.status = Dataset.Status.PUBLICADO
    dataset.atualizado_por = request.user
    dataset.save(update_fields=["status", "atualizado_por", "atualizado_em"])

    registrar_auditoria(
        municipio=dataset.municipio,
        modulo="PAINEIS",
        evento="DATASET_PUBLICADO",
        entidade="Dataset",
        entidade_id=dataset.pk,
        usuario=request.user,
        depois={"status": dataset.status, "checklist": checklist_flags},
    )

    messages.success(request, "Dataset publicado com sucesso.")
    return redirect("paineis:dataset_detail", pk=dataset.pk)


@login_required
@require_perm("paineis.view")
def dashboard(request, dataset_pk: int):
    dataset = get_object_or_404(_scoped_queryset(request), pk=dataset_pk)
    version = _latest_version(dataset)
    if not version or version.status != DatasetVersion.Status.CONCLUIDO or not version.arquivo_tratado:
        messages.error(request, "Dataset sem versão tratada disponível.")
        return redirect("paineis:dataset_detail", pk=dataset.pk)

    with version.arquivo_tratado.open("rb") as fobj:
        headers, rows = load_rows_from_csv_bytes(fobj.read())

    schema = (version.schema_json or {}).get("columns") or [{"name": h, "type": "TEXTO"} for h in headers]

    filters = {
        "date_start": (request.GET.get("date_start") or "").strip(),
        "date_end": (request.GET.get("date_end") or "").strip(),
        "secretaria": (request.GET.get("secretaria") or "").strip(),
        "unidade": (request.GET.get("unidade") or "").strip(),
        "categoria": (request.GET.get("categoria") or "").strip(),
    }

    payload = build_dashboard_payload(rows, schema, filters)
    ranking_labels = payload.get("ranking", {}).get("labels") or []
    ranking_values = payload.get("ranking", {}).get("values") or []
    pie_items = [
        {"name": ranking_labels[idx], "value": ranking_values[idx]}
        for idx in range(min(len(ranking_labels), len(ranking_values), 6))
    ]
    payload["pie"] = pie_items
    summary_text = _build_dashboard_summary(payload, filters)
    table_rows = [[row.get(h, "") for h in payload["headers"]] for row in payload["rows"][:120]]

    export = (request.GET.get("export") or "").strip().lower()
    if export == "csv":
        rows_export = [[row.get(h, "") for h in payload["headers"]] for row in payload["rows"]]
        return export_csv(
            f"dataset_{dataset.pk}_filtrado.csv",
            payload["headers"],
            rows_export,
        )

    if export == "pdf":
        filtros_text = " • ".join(
            [
                f"Data: {filters['date_start']} a {filters['date_end']}" if filters["date_start"] or filters["date_end"] else "",
                f"Secretaria: {filters['secretaria']}" if filters["secretaria"] else "",
                f"Unidade: {filters['unidade']}" if filters["unidade"] else "",
                f"Categoria: {filters['categoria']}" if filters["categoria"] else "",
            ]
        ).strip(" •")

        sample_rows = [[row.get(h, "") for h in payload["headers"]] for row in payload["rows"][:100]]
        return export_pdf_template(
            request,
            filename=f"dashboard_dataset_{dataset.pk}.pdf",
            title=f"Dashboard BI • {dataset.nome}",
            template_name="paineis/pdf_dashboard.html",
            subtitle=f"{dataset.municipio.nome}/{dataset.municipio.uf}",
            filtros=filtros_text,
            hash_payload=str(filters),
            context={
                "dataset": dataset,
                "kpis": payload["kpis"],
                "headers": payload["headers"],
                "rows": sample_rows,
                "line": payload["line"],
                "ranking": payload["ranking"],
                "summary_text": summary_text,
            },
        )

    base_params = request.GET.copy()
    base_params.pop("export", None)
    qs = base_params.urlencode()
    path = request.path
    sep = "&" if qs else ""
    csv_url = f"{path}?{qs}{sep}export=csv" if (qs or sep) else f"{path}?export=csv"
    pdf_url = f"{path}?{qs}{sep}export=pdf" if (qs or sep) else f"{path}?export=pdf"

    return render(
        request,
        "paineis/dashboard.html",
        {
            "title": f"Dashboard • {dataset.nome}",
            "subtitle": f"{dataset.municipio.nome}/{dataset.municipio.uf}",
            "dataset": dataset,
            "version": version,
            "payload": payload,
            "summary_text": summary_text,
            "table_rows": table_rows,
            "filters": filters,
            "actions": [
                {
                    "label": "Exportar CSV",
                    "url": csv_url,
                    "icon": "fa-solid fa-file-csv",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Exportar PDF",
                    "url": pdf_url,
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "gp-button--ghost",
                },
                {
                    "label": "Voltar dataset",
                    "url": reverse("paineis:dataset_detail", args=[dataset.pk]) + f"?municipio={dataset.municipio_id}",
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "gp-button--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("paineis.view")
def dataset_package(request, pk: int):
    dataset = get_object_or_404(_scoped_queryset(request), pk=pk)
    version = _latest_version(dataset)

    if not version or version.status != DatasetVersion.Status.CONCLUIDO:
        messages.error(request, "Não há versão concluída para download.")
        return redirect("paineis:dataset_detail", pk=dataset.pk)

    schema = (version.schema_json or {}).get("columns") or []
    profile = version.profile_json or {}
    package_bytes = build_dataset_package(dataset, version, schema, profile)

    export_job = ExportJob.objects.create(
        dataset=dataset,
        formato=ExportJob.Formato.ZIP,
        status=ExportJob.Status.CONCLUIDO,
        filtros_json={},
        solicitado_por=request.user,
        concluido_em=timezone.now(),
    )
    export_job.arquivo.save(
        f"dataset_{dataset.pk}_pacote.zip",
        ContentFile(package_bytes),
        save=True,
    )

    registrar_auditoria(
        municipio=dataset.municipio,
        modulo="PAINEIS",
        evento="DATASET_PACOTE_DOWNLOAD",
        entidade="ExportJob",
        entidade_id=export_job.pk,
        usuario=request.user,
        depois={"dataset": dataset.nome, "formato": "ZIP"},
    )

    response = HttpResponse(package_bytes, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="dataset_{dataset.pk}_pacote.zip"'
    response["X-Content-Type-Options"] = "nosniff"
    return response
