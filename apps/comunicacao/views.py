from __future__ import annotations

import json
import re
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.http import HttpRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.core.decorators import require_perm
from apps.core.exports import export_csv, export_pdf_table
from apps.core.rbac import can, is_admin
from apps.org.models import Municipio, Secretaria, Unidade

from .forms import NotificationChannelConfigForm, NotificationTemplateForm
from .models import NotificationChannelConfig, NotificationJob, NotificationLog, NotificationTemplate
from .services import (
    process_pending_notification_jobs,
    queue_event_notifications,
    validate_template_payload,
)
from .tasks import process_notification_job_task

EVENT_KEY_RE = re.compile(r"^[a-z0-9_.:-]{3,80}$")
DEFAULT_MAX_API_JSON_BODY = 256 * 1024

EVENTS_CATALOG = [
    {
        "key": "educacao.fechamento.periodo",
        "module": "EDUCACAO",
        "label": "Fechamento de período letivo",
        "description": "Notifica responsáveis e equipe após fechamento de notas/frequências.",
        "variables": ["nome", "turma", "periodo", "unidade", "link_portal"],
    },
    {
        "key": "educacao.frequencia.alerta",
        "module": "EDUCACAO",
        "label": "Frequência baixa",
        "description": "Alerta responsável sobre risco de faltas elevadas.",
        "variables": ["nome", "percentual_frequencia", "turma", "unidade"],
    },
    {
        "key": "nee.laudo.vencendo",
        "module": "NEE",
        "label": "Laudo NEE vencendo",
        "description": "Lembra equipe e família sobre renovação de laudo.",
        "variables": ["nome", "aluno", "data_validade", "unidade"],
    },
    {
        "key": "nee.evolucao.pendente",
        "module": "NEE",
        "label": "Evolução pendente",
        "description": "Avisa sobre ausência de evolução no plano clínico.",
        "variables": ["nome", "aluno", "dias_sem_evolucao", "responsavel"],
    },
    {
        "key": "saude.consulta.lembrete",
        "module": "SAUDE",
        "label": "Lembrete de consulta",
        "description": "Lembrete pré-consulta para reduzir absenteísmo.",
        "variables": ["nome", "data", "hora", "unidade", "profissional"],
    },
    {
        "key": "saude.agendamento.remarcado",
        "module": "SAUDE",
        "label": "Consulta remarcada",
        "description": "Comunica remarcação automática ou manual.",
        "variables": ["nome", "data", "hora", "unidade", "profissional"],
    },
    {
        "key": "processos.prazo.estourando",
        "module": "PROCESSOS",
        "label": "Prazo processual estourando",
        "description": "Avisa responsáveis sobre SLA em risco.",
        "variables": ["nome", "numero_processo", "prazo", "setor"],
    },
]


def _resolve_municipio(request: HttpRequest, *, require_selected: bool = False):
    user = request.user
    if is_admin(user):
        profile = getattr(user, "profile", None)
        if profile and profile.municipio_id:
            municipio = Municipio.objects.filter(pk=profile.municipio_id, ativo=True).first()
            if municipio:
                return municipio

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


def _request_data(request: HttpRequest) -> dict[str, Any]:
    if request.content_type and "application/json" in request.content_type:
        max_bytes = int(getattr(settings, "COMUNICACAO_API_MAX_JSON_BODY_BYTES", DEFAULT_MAX_API_JSON_BODY))
        raw_body = request.body or b""
        if len(raw_body) > max_bytes:
            return {"__error__": "payload_too_large"}
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
            if isinstance(payload, dict):
                return payload
            return {"__error__": "invalid_json_object"}
        except Exception:
            return {"__error__": "invalid_json"}
    return request.POST.dict()


def _safe_int(value: Any, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = int(default)
    if minimum is not None and parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _input_error(data: dict[str, Any]) -> str:
    return str(data.get("__error__") or "").strip()


def _normalize_event_key(raw_value: Any, *, required: bool = False, default: str = "") -> str | None:
    value = str(raw_value or default).strip().lower()
    if not value:
        return None if required else default
    if not EVENT_KEY_RE.match(value):
        return None
    return value


def _normalize_priority(raw_value: Any) -> str:
    value = str(raw_value or NotificationJob.Priority.NORMAL).strip().upper()
    valid = {choice for choice, _label in NotificationJob.Priority.choices}
    if value not in valid:
        return NotificationJob.Priority.NORMAL
    return value


def _bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    return raw in {"1", "true", "t", "yes", "sim", "on"}


def _secretaria_unidade_from_data(data: dict[str, Any], municipio: Municipio) -> tuple[Secretaria | None, Unidade | None]:
    secretaria = None
    unidade = None
    secretaria_id = str(data.get("secretaria_id") or data.get("secretaria") or "").strip()
    unidade_id = str(data.get("unidade_id") or data.get("unidade") or "").strip()
    if secretaria_id.isdigit():
        secretaria = Secretaria.objects.filter(pk=int(secretaria_id), municipio=municipio).first()
    if unidade_id.isdigit():
        unidade = Unidade.objects.filter(pk=int(unidade_id), secretaria__municipio=municipio).first()
        if unidade and not secretaria:
            secretaria = unidade.secretaria
    return secretaria, unidade


def _parse_recipients(data: dict[str, Any]) -> list[dict[str, Any]]:
    recipients = data.get("recipients")
    if isinstance(recipients, list):
        return [item for item in recipients if isinstance(item, dict)]

    single = {
        "nome": data.get("nome") or data.get("to_name") or "",
        "email": data.get("email") or data.get("to_email") or "",
        "telefone": data.get("telefone") or data.get("phone") or data.get("to_phone") or "",
        "whatsapp": data.get("whatsapp") or data.get("to_whatsapp") or "",
    }
    if any(single.values()):
        return [single]
    return []


@login_required
@require_perm("comunicacao.view")
def index(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip().upper()
    channel = (request.GET.get("channel") or "").strip().upper()
    event_key = (request.GET.get("event_key") or "").strip()

    jobs_qs = NotificationJob.objects.filter(municipio=municipio).select_related("secretaria", "unidade")
    logs_qs = NotificationLog.objects.filter(job__municipio=municipio).select_related("job")
    templates_qs = NotificationTemplate.objects.filter(municipio=municipio)
    channels_qs = NotificationChannelConfig.objects.filter(municipio=municipio)
    dead_letter_qs = jobs_qs.filter(
        status=NotificationJob.Status.FALHA,
        attempts__gte=F("max_attempts"),
    )

    if q:
        jobs_qs = jobs_qs.filter(Q(destination__icontains=q) | Q(event_key__icontains=q))
        templates_qs = templates_qs.filter(Q(nome__icontains=q) | Q(event_key__icontains=q))
        channels_qs = channels_qs.filter(Q(sender_identifier__icontains=q) | Q(sender_name__icontains=q))
    if status:
        jobs_qs = jobs_qs.filter(status=status)
    if channel:
        jobs_qs = jobs_qs.filter(channel=channel)
        templates_qs = templates_qs.filter(channel=channel)
        channels_qs = channels_qs.filter(channel=channel)
    if event_key:
        jobs_qs = jobs_qs.filter(event_key__icontains=event_key)
        templates_qs = templates_qs.filter(event_key__icontains=event_key)

    export = (request.GET.get("export") or "").strip().lower()
    export_scope = (request.GET.get("scope") or "jobs").strip().lower()
    if export in {"csv", "pdf"}:
        if export_scope == "logs":
            headers = ["Data", "Evento", "Canal", "Destino", "Status", "Erro"]
            rows = []
            for item in logs_qs.order_by("-created_at", "-id")[:2000]:
                rows.append(
                    [
                        str(item.created_at),
                        item.job.event_key,
                        item.get_channel_display(),
                        item.destination,
                        item.get_status_display(),
                        item.error_message or "",
                    ]
                )
            if export == "csv":
                return export_csv("comunicacao_logs.csv", headers, rows)
            return export_pdf_table(
                request,
                filename="comunicacao_logs.pdf",
                title="Logs de comunicacao",
                subtitle=f"{municipio.nome}/{municipio.uf}",
                headers=headers,
                rows=rows,
                filtros=f"Busca={q or '-'} | Canal={channel or '-'} | Status={status or '-'} | Event={event_key or '-'}",
            )

        if export_scope == "templates":
            headers = ["Evento", "Canal", "Nome", "Escopo", "Ativo", "NEE Safe"]
            rows = []
            for item in templates_qs.order_by("event_key", "channel", "nome")[:2000]:
                rows.append(
                    [
                        item.event_key,
                        item.get_channel_display(),
                        item.nome,
                        item.get_scope_display(),
                        "SIM" if item.is_active else "NAO",
                        "SIM" if item.nee_safe else "NAO",
                    ]
                )
            if export == "csv":
                return export_csv("comunicacao_templates.csv", headers, rows)
            return export_pdf_table(
                request,
                filename="comunicacao_templates.pdf",
                title="Templates de comunicacao",
                subtitle=f"{municipio.nome}/{municipio.uf}",
                headers=headers,
                rows=rows,
                filtros=f"Busca={q or '-'} | Canal={channel or '-'} | Event={event_key or '-'}",
            )

        if export_scope == "channels":
            headers = ["Canal", "Provedor", "Remetente", "Escopo", "Ativo", "Prioridade"]
            rows = []
            for item in channels_qs.order_by("channel", "prioridade", "id")[:2000]:
                scope = item.unidade.nome if item.unidade else item.secretaria.nome if item.secretaria else municipio.nome
                rows.append(
                    [
                        item.get_channel_display(),
                        item.get_provider_display(),
                        item.sender_identifier or "",
                        scope,
                        "SIM" if item.is_active else "NAO",
                        str(item.prioridade),
                    ]
                )
            if export == "csv":
                return export_csv("comunicacao_canais.csv", headers, rows)
            return export_pdf_table(
                request,
                filename="comunicacao_canais.pdf",
                title="Canais de comunicacao",
                subtitle=f"{municipio.nome}/{municipio.uf}",
                headers=headers,
                rows=rows,
                filtros=f"Busca={q or '-'} | Canal={channel or '-'}",
            )

        headers = ["Data", "Evento", "Canal", "Destino", "Status", "Tentativas", "Escopo"]
        rows = []
        for item in jobs_qs.order_by("-created_at", "-id")[:2000]:
            scope = item.unidade.nome if item.unidade else item.secretaria.nome if item.secretaria else municipio.nome
            rows.append(
                [
                    str(item.created_at),
                    item.event_key,
                    item.get_channel_display(),
                    item.destination,
                    item.get_status_display(),
                    f"{item.attempts}/{item.max_attempts}",
                    scope,
                ]
            )
        if export == "csv":
            return export_csv("comunicacao_jobs.csv", headers, rows)
        return export_pdf_table(
            request,
            filename="comunicacao_jobs.pdf",
            title="Jobs de comunicacao",
            subtitle=f"{municipio.nome}/{municipio.uf}",
            headers=headers,
            rows=rows,
            filtros=f"Busca={q or '-'} | Canal={channel or '-'} | Status={status or '-'} | Event={event_key or '-'}",
        )

    return render(
        request,
        "comunicacao/index.html",
        {
            "title": "Comunicação Automática",
            "subtitle": f"{municipio.nome}/{municipio.uf}",
            "municipio": municipio,
            "municipios": _municipios_admin(request),
            "items_jobs": jobs_qs.order_by("-created_at")[:100],
            "items_logs": logs_qs.order_by("-created_at")[:120],
            "items_templates": templates_qs.order_by("event_key", "channel", "nome")[:120],
            "items_channels": channels_qs.order_by("channel", "prioridade", "id"),
            "items_dead_letter": dead_letter_qs.order_by("-updated_at", "-id")[:50],
            "q": q,
            "status": status,
            "channel": channel,
            "event_key": event_key,
            "status_choices": NotificationJob.Status.choices,
            "channel_choices": NotificationChannelConfig.Channel.choices,
            "counts": {
                "pendente": NotificationJob.objects.filter(
                    municipio=municipio, status=NotificationJob.Status.PENDENTE
                ).count(),
                "entregue": NotificationJob.objects.filter(
                    municipio=municipio, status=NotificationJob.Status.ENTREGUE
                ).count(),
                "falha": NotificationJob.objects.filter(
                    municipio=municipio, status=NotificationJob.Status.FALHA
                ).count(),
                "dead_letter": NotificationJob.objects.filter(
                    municipio=municipio,
                    status=NotificationJob.Status.FALHA,
                    attempts__gte=F("max_attempts"),
                ).count(),
                "templates": NotificationTemplate.objects.filter(municipio=municipio, is_active=True).count(),
                "canais": NotificationChannelConfig.objects.filter(municipio=municipio, is_active=True).count(),
                "eventos_catalogo": len(EVENTS_CATALOG),
            },
            "actions": [
                {
                    "label": "Templates (API)",
                    "url": reverse("comunicacao:templates_api") + _q_municipio(municipio),
                    "icon": "fa-solid fa-file-lines",
                    "variant": "btn-primary",
                },
                {
                    "label": "Config canais (API)",
                    "url": reverse("comunicacao:channels_config_api") + _q_municipio(municipio),
                    "icon": "fa-solid fa-gears",
                    "variant": "btn--ghost",
                },
                {
                    "label": "Catálogo eventos (API)",
                    "url": reverse("comunicacao:events_catalog_api") + _q_municipio(municipio),
                    "icon": "fa-solid fa-list-check",
                    "variant": "btn--ghost",
                },
                {
                    "label": "CSV jobs",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&channel={channel}&status={status}&event_key={event_key}&scope=jobs&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "btn--ghost",
                },
                {
                    "label": "CSV logs",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&channel={channel}&status={status}&event_key={event_key}&scope=logs&export=csv",
                    "icon": "fa-solid fa-file-csv",
                    "variant": "btn--ghost",
                },
                {
                    "label": "PDF jobs",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&channel={channel}&status={status}&event_key={event_key}&scope=jobs&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "btn--ghost",
                },
                {
                    "label": "PDF logs",
                    "url": request.path + f"?municipio={municipio.pk}&q={q}&channel={channel}&status={status}&event_key={event_key}&scope=logs&export=pdf",
                    "icon": "fa-solid fa-file-pdf",
                    "variant": "btn--ghost",
                },
            ],
            "can_manage": can(request.user, "comunicacao.manage"),
            "can_send": can(request.user, "comunicacao.send"),
            "can_audit": can(request.user, "comunicacao.audit"),
            "can_admin": can(request.user, "comunicacao.admin"),
            "event_catalog_preview": EVENTS_CATALOG[:8],
        },
    )


@login_required
@require_perm("comunicacao.manage")
@require_POST
def processar_fila(request):
    municipio = _resolve_municipio(request) or _resolve_municipio(request, require_selected=False)
    if not municipio:
        return redirect("core:dashboard")
    limit = _safe_int(request.POST.get("limit"), default=100, minimum=1, maximum=500)
    stats = process_pending_notification_jobs(limit=limit)
    messages.success(
        request,
        f"Fila processada: {stats['processed']} jobs, {stats['delivered']} entregues, {stats['failed']} falhas.",
    )
    return redirect(reverse("comunicacao:index") + _q_municipio(municipio))


@login_required
@require_perm("comunicacao.manage")
@require_POST
def requeue_failed_jobs(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return redirect("core:dashboard")

    limit = _safe_int(request.POST.get("limit"), default=100, minimum=1, maximum=500)
    qs = NotificationJob.objects.filter(
        municipio=municipio,
        status=NotificationJob.Status.FALHA,
    ).order_by("-updated_at", "-id")[:limit]
    ids = list(qs.values_list("id", flat=True))
    if ids:
        NotificationJob.objects.filter(id__in=ids).update(
            status=NotificationJob.Status.PENDENTE,
            attempts=0,
            fallback_index=0,
            error_message="",
        )
    messages.success(request, f"{len(ids)} jobs com falha foram reenfileirados.")
    return redirect(reverse("comunicacao:index") + _q_municipio(municipio))


@login_required
@require_perm("comunicacao.send")
@require_POST
def notifications_send(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return JsonResponse({"ok": False, "error": "Município não selecionado."}, status=400)

    data = _request_data(request)
    parse_error = _input_error(data)
    if parse_error:
        return JsonResponse({"ok": False, "error": "Payload JSON inválido ou acima do limite permitido."}, status=400)

    recipients = _parse_recipients(data)
    if not recipients:
        return JsonResponse({"ok": False, "error": "Informe ao menos um destinatário."}, status=400)

    secretaria, unidade = _secretaria_unidade_from_data(data, municipio)
    event_key = _normalize_event_key(data.get("event_key"), default="manual.campanha")
    if not event_key:
        return JsonResponse({"ok": False, "error": "event_key inválido. Use letras minúsculas, números, ponto, sublinhado, dois-pontos ou hífen."}, status=400)
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    priority = _normalize_priority(data.get("priority"))
    urgent = _bool_value(data.get("urgent"), default=(priority == NotificationJob.Priority.URGENTE))
    subject = str(data.get("subject") or "").strip()[:220]
    body = str(data.get("body") or "").strip()[:10000]

    jobs = queue_event_notifications(
        municipio=municipio,
        secretaria=secretaria,
        unidade=unidade,
        event_key=event_key,
        payload=payload,
        recipients=recipients,
        actor=request.user,
        priority=priority,
        urgent=urgent,
        subject_override=subject,
        body_override=body,
        entity_module=str(data.get("entity_module") or ""),
        entity_type=str(data.get("entity_type") or ""),
        entity_id=str(data.get("entity_id") or ""),
    )
    for job in jobs:
        try:
            process_notification_job_task.delay(job.pk)
        except Exception:
            pass

    return JsonResponse({"ok": True, "queued": len(jobs), "job_ids": [j.pk for j in jobs]})


@login_required
@require_perm("comunicacao.manage")
@require_POST
def notifications_trigger(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return JsonResponse({"ok": False, "error": "Município não selecionado."}, status=400)

    data = _request_data(request)
    parse_error = _input_error(data)
    if parse_error:
        return JsonResponse({"ok": False, "error": "Payload JSON inválido ou acima do limite permitido."}, status=400)
    recipients = _parse_recipients(data)
    if not recipients:
        return JsonResponse({"ok": False, "error": "Destinatários não informados."}, status=400)

    secretaria, unidade = _secretaria_unidade_from_data(data, municipio)
    event_key = _normalize_event_key(data.get("event_key"), required=True)
    if not event_key:
        return JsonResponse({"ok": False, "error": "event_key é obrigatório."}, status=400)

    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    priority = _normalize_priority(data.get("priority"))
    urgent = _bool_value(data.get("urgent"), default=(priority == NotificationJob.Priority.URGENTE))

    jobs = queue_event_notifications(
        municipio=municipio,
        secretaria=secretaria,
        unidade=unidade,
        event_key=event_key,
        payload=payload,
        recipients=recipients,
        actor=request.user,
        priority=priority,
        urgent=urgent,
        entity_module=str(data.get("entity_module") or ""),
        entity_type=str(data.get("entity_type") or ""),
        entity_id=str(data.get("entity_id") or ""),
    )
    for job in jobs:
        try:
            process_notification_job_task.delay(job.pk)
        except Exception:
            pass

    return JsonResponse({"ok": True, "queued": len(jobs), "job_ids": [j.pk for j in jobs]})


@login_required
@require_perm("comunicacao.view")
@require_GET
def notifications_logs(request):
    if not (can(request.user, "comunicacao.audit") or can(request.user, "comunicacao.manage") or is_admin(request.user)):
        return HttpResponseForbidden("403 — Sem permissão para visualizar logs de comunicação.")

    municipio = _resolve_municipio(request)
    if not municipio:
        return JsonResponse({"ok": False, "error": "Município não selecionado."}, status=400)

    event_key = (request.GET.get("event_key") or "").strip()
    channel = (request.GET.get("channel") or "").strip().upper()
    status = (request.GET.get("status") or "").strip().upper()
    q = (request.GET.get("q") or "").strip()
    limit = _safe_int(request.GET.get("limit"), default=100, minimum=1, maximum=500)

    qs = NotificationLog.objects.select_related("job").filter(job__municipio=municipio)
    if event_key:
        qs = qs.filter(job__event_key__icontains=event_key)
    if channel:
        qs = qs.filter(channel=channel)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(destination__icontains=q) | Q(error_message__icontains=q))

    data = [
        {
            "id": item.id,
            "job_id": item.job_id,
            "event_key": item.job.event_key,
            "status": item.status,
            "channel": item.channel,
            "provider": item.provider,
            "destination": item.destination,
            "attempt": item.attempt,
            "created_at": item.created_at.isoformat(),
            "error_message": item.error_message or "",
        }
        for item in qs.order_by("-created_at", "-id")[:limit]
    ]
    return JsonResponse({"ok": True, "count": len(data), "items": data})


@login_required
@require_perm("comunicacao.view")
@require_GET
def events_catalog_api(request):
    municipio = _resolve_municipio(request)
    if not municipio:
        return JsonResponse({"ok": False, "error": "Município não selecionado."}, status=400)

    template_keys = set(
        NotificationTemplate.objects.filter(municipio=municipio, is_active=True).values_list("event_key", flat=True)
    )
    items = []
    for event in EVENTS_CATALOG:
        key = str(event.get("key") or "")
        items.append(
            {
                **event,
                "template_active": key in template_keys,
            }
        )
    return JsonResponse({"ok": True, "count": len(items), "items": items})


@login_required
@require_perm("comunicacao.manage")
@require_POST
def template_preview_api(request):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return JsonResponse({"ok": False, "error": "Município não selecionado."}, status=400)

    data = _request_data(request)
    parse_error = _input_error(data)
    if parse_error:
        return JsonResponse({"ok": False, "error": "Payload JSON inválido ou acima do limite permitido."}, status=400)

    subject = str(data.get("subject") or "")
    body = str(data.get("body") or "")
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}

    template_id_raw = str(data.get("template_id") or "").strip()
    if template_id_raw.isdigit():
        obj = NotificationTemplate.objects.filter(pk=int(template_id_raw), municipio=municipio).first()
        if obj:
            if not subject:
                subject = obj.subject or ""
            if not body:
                body = obj.body or ""

    if not subject and not body:
        event_key = _normalize_event_key(data.get("event_key"), required=False)
        channel = str(data.get("channel") or NotificationChannelConfig.Channel.EMAIL).strip().upper()
        if event_key and channel:
            obj = (
                NotificationTemplate.objects.filter(
                    municipio=municipio,
                    event_key=event_key,
                    channel=channel,
                    is_active=True,
                )
                .order_by("-id")
                .first()
            )
            if obj:
                subject = obj.subject or ""
                body = obj.body or ""

    validation = validate_template_payload(subject=subject, body=body, payload=payload)
    return JsonResponse(
        {
            "ok": True,
            "subject": subject,
            "body": body,
            "placeholders": validation["placeholders"],
            "missing": validation["missing"],
            "rendered_subject": validation["rendered_subject"],
            "rendered_body": validation["rendered_body"],
        }
    )


@login_required
@require_perm("comunicacao.view")
@require_http_methods(["GET", "POST"])
def templates_api(request):
    municipio = _resolve_municipio(request, require_selected=(request.method == "POST"))
    if not municipio:
        return JsonResponse({"ok": False, "error": "Município não selecionado."}, status=400)

    if request.method == "GET":
        qs = NotificationTemplate.objects.filter(municipio=municipio).order_by("event_key", "channel", "nome")
        data = [
            {
                "id": item.id,
                "scope": item.scope,
                "event_key": item.event_key,
                "channel": item.channel,
                "nome": item.nome,
                "subject": item.subject,
                "body": item.body,
                "is_active": item.is_active,
                "nee_safe": item.nee_safe,
                "secretaria_id": item.secretaria_id,
                "unidade_id": item.unidade_id,
            }
            for item in qs[:500]
        ]
        return JsonResponse({"ok": True, "count": len(data), "items": data})

    if not can(request.user, "comunicacao.manage"):
        return HttpResponseForbidden("403 — Sem permissão para criar templates.")

    data = _request_data(request)
    parse_error = _input_error(data)
    if parse_error:
        return JsonResponse({"ok": False, "error": "Payload JSON inválido ou acima do limite permitido."}, status=400)
    form = NotificationTemplateForm(data, municipio=municipio)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.municipio = municipio
        obj.atualizado_por = request.user
        obj.save()
        return JsonResponse({"ok": True, "id": obj.id})
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


@login_required
@require_perm("comunicacao.manage")
@require_http_methods(["PUT", "POST"])
def template_update_api(request, pk: int):
    municipio = _resolve_municipio(request, require_selected=True)
    if not municipio:
        return JsonResponse({"ok": False, "error": "Município não selecionado."}, status=400)

    obj = get_object_or_404(NotificationTemplate, pk=pk, municipio=municipio)
    data = _request_data(request)
    parse_error = _input_error(data)
    if parse_error:
        return JsonResponse({"ok": False, "error": "Payload JSON inválido ou acima do limite permitido."}, status=400)
    form = NotificationTemplateForm(data, instance=obj, municipio=municipio)
    if form.is_valid():
        saved = form.save(commit=False)
        saved.atualizado_por = request.user
        saved.save()
        return JsonResponse({"ok": True, "id": saved.id})
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


@login_required
@require_perm("comunicacao.view")
@require_http_methods(["GET", "POST"])
def channels_config_api(request):
    municipio = _resolve_municipio(request, require_selected=(request.method == "POST"))
    if not municipio:
        return JsonResponse({"ok": False, "error": "Município não selecionado."}, status=400)

    if request.method == "GET":
        qs = NotificationChannelConfig.objects.filter(municipio=municipio).order_by("channel", "prioridade", "id")
        data = [
            {
                "id": item.id,
                "channel": item.channel,
                "provider": item.provider,
                "is_active": item.is_active,
                "sender_name": item.sender_name,
                "sender_identifier": item.sender_identifier,
                "prioridade": item.prioridade,
                "secretaria_id": item.secretaria_id,
                "unidade_id": item.unidade_id,
            }
            for item in qs[:200]
        ]
        return JsonResponse({"ok": True, "count": len(data), "items": data})

    if not can(request.user, "comunicacao.admin"):
        return HttpResponseForbidden("403 — Somente admin pode configurar canais.")

    data = _request_data(request)
    parse_error = _input_error(data)
    if parse_error:
        return JsonResponse({"ok": False, "error": "Payload JSON inválido ou acima do limite permitido."}, status=400)
    obj = None
    obj_id = str(data.get("id") or "").strip()
    if obj_id.isdigit():
        obj = NotificationChannelConfig.objects.filter(pk=int(obj_id), municipio=municipio).first()

    form = NotificationChannelConfigForm(data, instance=obj, municipio=municipio)
    if form.is_valid():
        saved = form.save(commit=False)
        saved.municipio = municipio
        saved.atualizado_por = request.user
        saved.save()
        return JsonResponse({"ok": True, "id": saved.id})
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)
