from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db.models import Avg, Count
from django.utils import timezone

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import can, is_admin
from apps.core.services_auditoria import registrar_auditoria
from apps.org.models import Municipio

from .forms import ConversionJobForm
from .models import ConversionJob, ConversionJobInput
from .services import process_conversion_job_with_audit
from .tasks import process_conversion_job_task


DOWNLOAD_TOKEN_SALT = "conversor.download.token"
DOWNLOAD_TOKEN_MAX_AGE = 15 * 60


def _resolve_municipio(request, *, require_selected: bool = False):
    user = request.user
    if is_admin(user):
        profile = getattr(user, "profile", None)
        if profile and profile.municipio_id:
            municipio = Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
            if municipio:
                return municipio

        municipio_id = (request.POST.get("municipio") or "").strip()
        if municipio_id.isdigit():
            return Municipio.objects.filter(pk=int(municipio_id), ativo=True).first()
        if require_selected:
            return None
        return Municipio.objects.filter(ativo=True).order_by("nome").first()

    profile = getattr(user, "profile", None)
    if profile and profile.municipio_id:
        return Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
    return None


def _jobs_queryset(request):
    qs = ConversionJob.objects.select_related("municipio", "criado_por")
    if is_admin(request.user):
        return qs

    profile = getattr(request.user, "profile", None)
    if not profile or not profile.municipio_id:
        return qs.none()
    return qs.filter(municipio_id=profile.municipio_id)


def _make_download_token(job: ConversionJob, user_id: int) -> str:
    payload = f"{job.pk}:{job.atualizado_em.timestamp():.6f}:{user_id}"
    return signing.dumps(payload, salt=DOWNLOAD_TOKEN_SALT)


def _validate_download_token(job: ConversionJob, user_id: int, token: str) -> bool:
    if not token:
        return False
    try:
        raw = signing.loads(token, salt=DOWNLOAD_TOKEN_SALT, max_age=DOWNLOAD_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    parts = str(raw).split(":")
    if len(parts) != 3:
        return False
    job_id, ts_str, token_user_id = parts
    if str(job.pk) != job_id:
        return False
    if str(user_id) != token_user_id:
        return False
    try:
        expected_ts = f"{job.atualizado_em.timestamp():.6f}"
    except Exception:
        return False
    return expected_ts == ts_str


@login_required
@require_perm("conversor.view")
def index(request):
    municipio = _resolve_municipio(request, require_selected=False)
    if not municipio:
        messages.error(request, "Nenhum município ativo encontrado para usar o Conversor.")
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()

    jobs_qs = _jobs_queryset(request)
    if not is_admin(request.user):
        jobs_qs = jobs_qs.filter(municipio=municipio)
    if q:
        jobs_qs = jobs_qs.filter(logs__icontains=q)
    if status:
        jobs_qs = jobs_qs.filter(status=status)
    if tipo:
        jobs_qs = jobs_qs.filter(tipo=tipo)

    export = (request.GET.get("export") or "").strip().lower()
    if export in {"csv", "pdf"}:
        headers = ["Job", "Tipo", "Status", "Tamanho entrada", "Duracao ms", "Criado em", "Concluido em"]
        rows = []
        for item in jobs_qs.order_by("-criado_em", "-id")[:3000]:
            rows.append(
                [
                    str(item.pk),
                    item.get_tipo_display(),
                    item.get_status_display(),
                    str(item.tamanho_entrada),
                    str(item.duracao_ms),
                    str(item.criado_em),
                    str(item.concluido_em or ""),
                ]
            )
        if export == "csv":
            return export_csv("conversor_jobs.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="conversor_jobs.pdf",
            title="Historico de conversoes",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Tipo={tipo or '-'} | Status={status or '-'}",
        )

    form = ConversionJobForm(
        request.POST or None,
        request.FILES or None,
        municipio=municipio,
        user=request.user,
    )

    if request.method == "POST":
        if not can(request.user, "conversor.manage"):
            return HttpResponseForbidden("403 — Sem permissão para executar conversões.")

        if form.is_valid():
            job = form.save(commit=False)
            job.municipio = municipio
            job.criado_por = request.user
            job.status = ConversionJob.Status.PENDENTE
            job.parametros_json = form.cleaned_data.get("parametros_json") or {}
            job.tamanho_entrada = int(form.cleaned_data.get("total_size") or 0)
            job.save()
            request.session["conversor_last_job_id"] = job.pk

            extras = form.cleaned_data.get("arquivos_adicionais_list") or []
            for idx, fobj in enumerate(extras, start=1):
                ConversionJobInput.objects.create(job=job, arquivo=fobj, ordem=idx)

            queued = False
            try:
                process_conversion_job_task.delay(job.pk, actor_id=request.user.pk)
                queued = True
            except Exception:
                process_conversion_job_with_audit(job.pk, actor=request.user)

            job.refresh_from_db()
            if job.status == ConversionJob.Status.CONCLUIDO:
                messages.success(request, "Conversão concluída com sucesso.")
            elif job.status == ConversionJob.Status.ERRO:
                messages.error(request, f"Falha na conversão: {job.logs}")
            elif queued:
                messages.info(request, "Job enviado para processamento assíncrono.")
            else:
                messages.warning(request, "Fila assíncrona indisponível. Conversão executada localmente.")

            return redirect("conversor:index")

    status_count = {
        row["status"]: row["total"]
        for row in jobs_qs.values("status").annotate(total=Count("id"))
    }
    avg_duration_ms = {
        row["tipo"]: int(row["avg_ms"] or 0)
        for row in jobs_qs.filter(status=ConversionJob.Status.CONCLUIDO)
        .values("tipo")
        .annotate(avg_ms=Avg("duracao_ms"))
    }
    latest_job_id = request.session.get("conversor_last_job_id")
    latest_job = jobs_qs.filter(pk=latest_job_id).first() if latest_job_id else None
    latest_job_download_url = ""
    if latest_job and latest_job.output_file:
        token = _make_download_token(latest_job, request.user.id)
        latest_job_download_url = reverse("conversor:download", args=[latest_job.pk]) + f"?token={token}"

    items = list(jobs_qs.order_by("-criado_em")[:120])
    for item in items:
        item.download_url = ""
        if item.output_file:
            token = _make_download_token(item, request.user.id)
            item.download_url = reverse("conversor:download", args=[item.pk]) + f"?token={token}"

    return render(
        request,
        "conversor/index.html",
        {
            "title": "Conversor de Arquivos",
            "subtitle": "Ferramenta de conversão e organização de arquivos",
            "municipio": municipio,
            "items": items,
            "q": q,
            "status": status,
            "tipo": tipo,
            "status_choices": ConversionJob.Status.choices,
            "tipo_choices": ConversionJob.Tipo.choices,
            "form": form,
            "latest_job": latest_job,
            "latest_job_download_url": latest_job_download_url,
            "avg_duration_ms": avg_duration_ms,
            "counts": {
                "total": jobs_qs.count(),
                "pendente": status_count.get(ConversionJob.Status.PENDENTE, 0),
                "processando": status_count.get(ConversionJob.Status.PROCESSANDO, 0),
                "concluido": status_count.get(ConversionJob.Status.CONCLUIDO, 0),
                "erro": status_count.get(ConversionJob.Status.ERRO, 0),
            },
            "tool_cards": _tool_cards(),
            "actions": [
                {
                    "label": "Portal",
                    "url": reverse("portal"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                },
                {
                    "label": "CSV",
                    "url": request.path + f"?q={q}&status={status}&tipo={tipo}&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "btn--ghost",
                },
                {
                    "label": "PDF",
                    "url": request.path + f"?q={q}&status={status}&tipo={tipo}&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "btn--ghost",
                },
            ],
        },
    )


@login_required
@require_perm("conversor.view")
def download(request, pk: int):
    job = get_object_or_404(_jobs_queryset(request), pk=pk)
    if not job.output_file:
        messages.error(request, "Arquivo de saída ainda indisponível.")
        return redirect("conversor:index")

    token = (request.GET.get("token") or "").strip()
    if not token or not _validate_download_token(job, request.user.id, token):
        messages.error(request, "Link de download expirado ou inválido.")
        return redirect("conversor:index")

    with job.output_file.open("rb") as fobj:
        data = fobj.read()

    registrar_auditoria(
        municipio=job.municipio,
        modulo="CONVERSOR",
        evento="CONVERSAO_DOWNLOAD",
        entidade="ConversionJob",
        entidade_id=job.pk,
        usuario=request.user,
        depois={"tipo": job.tipo, "arquivo": job.output_file.name},
    )

    filename = job.output_file.name.split("/")[-1]
    response = HttpResponse(data, content_type="application/octet-stream")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_perm("conversor.view")
def job_status(request, pk: int):
    job = get_object_or_404(_jobs_queryset(request), pk=pk)
    has_output = bool(job.output_file)
    progress_map = {
        ConversionJob.Status.PENDENTE: 10,
        ConversionJob.Status.PROCESSANDO: 60,
        ConversionJob.Status.CONCLUIDO: 100,
        ConversionJob.Status.ERRO: 100,
    }
    progress = progress_map.get(job.status, 0)
    eta_seconds = None
    if job.status in {ConversionJob.Status.PENDENTE, ConversionJob.Status.PROCESSANDO}:
        avg_ms = (
            ConversionJob.objects.filter(
                municipio=job.municipio,
                tipo=job.tipo,
                status=ConversionJob.Status.CONCLUIDO,
                duracao_ms__gt=0,
            )
            .aggregate(v=Avg("duracao_ms"))
            .get("v")
            or 0
        )
        if avg_ms:
            elapsed = max(int((timezone.now() - job.criado_em).total_seconds()), 0)
            eta_seconds = max(int((avg_ms / 1000) - elapsed), 0)

    download_url = ""
    if has_output:
        token = _make_download_token(job, request.user.id)
        download_url = reverse("conversor:download", args=[job.pk]) + f"?token={token}"
    return JsonResponse(
        {
            "ok": True,
            "id": job.pk,
            "status": job.status,
            "status_label": job.get_status_display(),
            "progress_percent": progress,
            "eta_seconds": eta_seconds,
            "has_output": has_output,
            "download_url": download_url,
            "logs": (job.logs or "")[:400],
            "link_expires_in_seconds": DOWNLOAD_TOKEN_MAX_AGE if has_output else 0,
        }
    )


def _tool_cards() -> list[dict]:
    return [
        {
            "tipo": ConversionJob.Tipo.DOCX_TO_PDF,
            "titulo": "Word para PDF",
            "descricao": "Converte arquivos DOC e DOCX em PDF.",
            "icon": "fa-solid fa-file-word",
            "tone": "word",
            "ext": ".docx / .doc",
        },
        {
            "tipo": ConversionJob.Tipo.XLSX_TO_PDF,
            "titulo": "Excel para PDF",
            "descricao": "Converte planilhas XLS e XLSX em PDF.",
            "icon": "fa-solid fa-file-excel",
            "tone": "excel",
            "ext": ".xlsx / .xls",
        },
        {
            "tipo": ConversionJob.Tipo.IMG_TO_PDF,
            "titulo": "Imagem para PDF",
            "descricao": "Junta imagens em um único arquivo PDF no padrão A4.",
            "icon": "fa-solid fa-file-image",
            "tone": "image",
            "ext": ".png / .jpg / .webp",
        },
        {
            "tipo": ConversionJob.Tipo.PDF_MERGE,
            "titulo": "Unir PDFs",
            "descricao": "Consolida múltiplos PDFs em um só documento.",
            "icon": "fa-solid fa-file-pdf",
            "tone": "pdf",
            "ext": "2+ arquivos PDF",
        },
        {
            "tipo": ConversionJob.Tipo.PDF_SPLIT,
            "titulo": "Separar PDF",
            "descricao": "Extrai páginas específicas em arquivos individuais.",
            "icon": "fa-regular fa-file-pdf",
            "tone": "pdf",
            "ext": "PDF + faixas",
        },
        {
            "tipo": ConversionJob.Tipo.PDF_TO_IMAGES,
            "titulo": "PDF para Imagens",
            "descricao": "Exporta páginas do PDF como imagens em ZIP.",
            "icon": "fa-solid fa-images",
            "tone": "image",
            "ext": "PDF -> PNG",
        },
        {
            "tipo": ConversionJob.Tipo.PDF_TO_TEXT,
            "titulo": "PDF para Texto",
            "descricao": "Extrai o texto do PDF para arquivo TXT.",
            "icon": "fa-solid fa-file-lines",
            "tone": "txt",
            "ext": "PDF -> TXT",
        },
    ]
