from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.decorators import require_perm
from apps.core.rbac import can, is_admin
from apps.core.services_auditoria import registrar_auditoria
from apps.org.models import Municipio

from .forms import ConversionJobForm
from .models import ConversionJob, ConversionJobInput
from .services import process_conversion_job_with_audit
from .tasks import process_conversion_job_task


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


def _jobs_queryset(request):
    qs = ConversionJob.objects.select_related("municipio", "secretaria", "unidade", "setor", "criado_por")
    if is_admin(request.user):
        return qs

    profile = getattr(request.user, "profile", None)
    if not profile or not profile.municipio_id:
        return qs.none()
    return qs.filter(municipio_id=profile.municipio_id)


@login_required
@require_perm("conversor.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        messages.error(request, "Selecione um município para acessar o Conversor.")
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    tipo = (request.GET.get("tipo") or "").strip()

    jobs_qs = _jobs_queryset(request).filter(municipio=municipio)
    if q:
        jobs_qs = jobs_qs.filter(logs__icontains=q)
    if status:
        jobs_qs = jobs_qs.filter(status=status)
    if tipo:
        jobs_qs = jobs_qs.filter(tipo=tipo)

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

            return redirect(reverse("conversor:index") + f"?municipio={municipio.pk}")

    return render(
        request,
        "conversor/index.html",
        {
            "title": "Conversor de Arquivos",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items": jobs_qs.order_by("-criado_em")[:120],
            "q": q,
            "status": status,
            "tipo": tipo,
            "status_choices": ConversionJob.Status.choices,
            "tipo_choices": ConversionJob.Tipo.choices,
            "form": form,
            "actions": [
                {
                    "label": "Portal",
                    "url": reverse("portal"),
                    "icon": "fa-solid fa-arrow-left",
                    "variant": "btn--ghost",
                }
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
