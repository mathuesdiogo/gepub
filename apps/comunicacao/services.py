from __future__ import annotations

import base64
import json
import re
from urllib import parse, request
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from apps.core.services_auditoria import registrar_auditoria

from .models import NotificationChannelConfig, NotificationJob, NotificationLog, NotificationTemplate


PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def render_placeholders(text: str, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    raw = text or ""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        val = payload.get(key, "")
        if val is None:
            return ""
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False)
        return str(val)

    return PLACEHOLDER_RE.sub(repl, raw)


def list_placeholders(text: str) -> list[str]:
    found: list[str] = []
    for match in PLACEHOLDER_RE.finditer(text or ""):
        key = (match.group(1) or "").strip()
        if key and key not in found:
            found.append(key)
    return found


def validate_template_payload(*, subject: str, body: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    placeholders_subject = list_placeholders(subject)
    placeholders_body = list_placeholders(body)
    placeholders = []
    for key in placeholders_subject + placeholders_body:
        if key not in placeholders:
            placeholders.append(key)
    missing = [key for key in placeholders if key not in payload]
    return {
        "placeholders": placeholders,
        "missing": missing,
        "rendered_subject": render_placeholders(subject, payload),
        "rendered_body": render_placeholders(body, payload),
    }


def _retry_delay_minutes(attempt_number: int) -> int:
    base = int(getattr(settings, "COMUNICACAO_RETRY_BASE_MINUTES", 2) or 2)
    max_delay = int(getattr(settings, "COMUNICACAO_RETRY_MAX_MINUTES", 60) or 60)
    safe_attempt = max(1, int(attempt_number or 1))
    delay = base * (2 ** (safe_attempt - 1))
    return max(1, min(max_delay, delay))


def _priority_order_expr():
    return Case(
        When(priority=NotificationJob.Priority.URGENTE, then=Value(0)),
        When(priority=NotificationJob.Priority.ALTA, then=Value(1)),
        When(priority=NotificationJob.Priority.NORMAL, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "t", "yes", "sim", "on"}


def _to_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return int(default)


def _credentials_value(config: NotificationChannelConfig, *keys: str, default: str = "") -> str:
    data = config.get_credentials()
    for key in keys:
        value = str(data.get(key) or "").strip()
        if value:
            return value
    return default


def _resolve_channel_config(
    *,
    municipio,
    channel: str,
    secretaria=None,
    unidade=None,
) -> NotificationChannelConfig | None:
    base_qs = NotificationChannelConfig.objects.filter(
        municipio=municipio,
        channel=channel,
        is_active=True,
    ).order_by("prioridade", "-id")

    if unidade is not None:
        item = base_qs.filter(unidade=unidade).first()
        if item:
            return item

    if secretaria is not None:
        item = base_qs.filter(secretaria=secretaria, unidade__isnull=True).first()
        if item:
            return item

    return base_qs.filter(secretaria__isnull=True, unidade__isnull=True).first()


def _resolve_template(
    *,
    municipio,
    event_key: str,
    channel: str,
    secretaria=None,
    unidade=None,
) -> NotificationTemplate | None:
    base_qs = NotificationTemplate.objects.filter(
        municipio=municipio,
        event_key=event_key,
        channel=channel,
        is_active=True,
    ).order_by("-id")

    if unidade is not None:
        item = base_qs.filter(unidade=unidade).first()
        if item:
            return item

    if secretaria is not None:
        item = base_qs.filter(secretaria=secretaria, unidade__isnull=True).first()
        if item:
            return item

    return base_qs.filter(secretaria__isnull=True, unidade__isnull=True).first()


def _normalize_channels(channels: list[str] | None, *, urgent: bool) -> list[str]:
    base_order = (
        [
            NotificationChannelConfig.Channel.WHATSAPP,
            NotificationChannelConfig.Channel.SMS,
            NotificationChannelConfig.Channel.EMAIL,
        ]
        if urgent
        else [
            NotificationChannelConfig.Channel.EMAIL,
            NotificationChannelConfig.Channel.WHATSAPP,
            NotificationChannelConfig.Channel.SMS,
        ]
    )
    if not channels:
        return base_order

    normalized = [str(item).strip().upper() for item in channels]
    filtered = [
        item
        for item in normalized
        if item
        in {
            NotificationChannelConfig.Channel.EMAIL,
            NotificationChannelConfig.Channel.SMS,
            NotificationChannelConfig.Channel.WHATSAPP,
        }
    ]
    if not filtered:
        return base_order

    ordered = [item for item in base_order if item in filtered]
    for item in filtered:
        if item not in ordered:
            ordered.append(item)
    return ordered


def _destination_for_channel(channel: str, recipient: dict[str, Any]) -> str:
    if channel == NotificationChannelConfig.Channel.EMAIL:
        return (recipient.get("email") or recipient.get("to_email") or "").strip()
    if channel == NotificationChannelConfig.Channel.SMS:
        return (recipient.get("telefone") or recipient.get("phone") or recipient.get("sms") or "").strip()
    if channel == NotificationChannelConfig.Channel.WHATSAPP:
        return (recipient.get("whatsapp") or recipient.get("telefone") or recipient.get("phone") or "").strip()
    return ""


def _channels_from_preferences(channels: list[str], recipient: dict[str, Any]) -> list[str]:
    if recipient.get("opt_out"):
        return []

    allowed = set(channels)
    if recipient.get("allow_email") is False and NotificationChannelConfig.Channel.EMAIL in allowed:
        allowed.remove(NotificationChannelConfig.Channel.EMAIL)
    if recipient.get("allow_sms") is False and NotificationChannelConfig.Channel.SMS in allowed:
        allowed.remove(NotificationChannelConfig.Channel.SMS)
    if recipient.get("allow_whatsapp") is False and NotificationChannelConfig.Channel.WHATSAPP in allowed:
        allowed.remove(NotificationChannelConfig.Channel.WHATSAPP)
    return [ch for ch in channels if ch in allowed]


def queue_event_notifications(
    *,
    municipio,
    event_key: str,
    payload: dict[str, Any] | None,
    recipients: list[dict[str, Any]],
    actor=None,
    secretaria=None,
    unidade=None,
    priority: str = NotificationJob.Priority.NORMAL,
    urgent: bool = False,
    subject_override: str = "",
    body_override: str = "",
    message_kind: str = NotificationJob.MessageKind.TRANSACIONAL,
    correlation_key: str = "",
    entity_module: str = "",
    entity_type: str = "",
    entity_id: str = "",
) -> list[NotificationJob]:
    payload = payload or {}
    created_jobs: list[NotificationJob] = []

    for recipient in recipients:
        preferred = recipient.get("channels")
        channels = _normalize_channels(preferred if isinstance(preferred, list) else None, urgent=urgent)
        channels = _channels_from_preferences(channels, recipient)
        if not channels:
            continue

        first_channel = None
        destination = ""
        for ch in channels:
            destination = _destination_for_channel(ch, recipient)
            if destination:
                first_channel = ch
                break
        if not first_channel or not destination:
            continue

        merged_payload = {
            **payload,
            "nome": recipient.get("nome") or recipient.get("name") or payload.get("nome") or "",
            "email": recipient.get("email") or "",
            "telefone": recipient.get("telefone") or recipient.get("phone") or "",
            "whatsapp": recipient.get("whatsapp") or "",
        }

        template = None
        if not body_override:
            template = _resolve_template(
                municipio=municipio,
                event_key=event_key,
                channel=first_channel,
                secretaria=secretaria,
                unidade=unidade,
            )

        subject_text = subject_override
        body_text = body_override
        if template:
            if not subject_text:
                subject_text = template.subject or ""
            if not body_text:
                body_text = template.body or ""

        subject_rendered = render_placeholders(subject_text, merged_payload)
        body_rendered = render_placeholders(body_text, merged_payload)

        if merged_payload.get("nee_sensitive"):
            body_rendered = "Há uma atualização no acompanhamento educacional. Acesse o portal para visualizar."
            if first_channel == NotificationChannelConfig.Channel.EMAIL and not subject_rendered:
                subject_rendered = "Atualização de acompanhamento educacional"

        created_jobs.append(
            NotificationJob.objects.create(
                municipio=municipio,
                secretaria=secretaria,
                unidade=unidade,
                event_key=event_key,
                channel=first_channel,
                destination=destination,
                to_name=merged_payload.get("nome", ""),
                payload_json=merged_payload,
                subject_rendered=subject_rendered,
                body_rendered=body_rendered,
                status=NotificationJob.Status.PENDENTE,
                priority=priority,
                message_kind=message_kind,
                correlation_key=(correlation_key or "")[:120],
                fallback_channels=channels,
                fallback_index=channels.index(first_channel),
                entity_module=(entity_module or "")[:40],
                entity_type=(entity_type or "")[:80],
                entity_id=(entity_id or "")[:60],
                created_by=actor,
            )
        )

    return created_jobs


def _create_log(job: NotificationJob, *, status: str, response: dict[str, Any] | None = None, error: str = ""):
    NotificationLog.objects.create(
        job=job,
        status=status,
        attempt=max(1, int(job.attempts or 1)),
        channel=job.channel,
        provider=job.provider or "",
        destination=job.destination or "",
        subject=job.subject_rendered or "",
        body=job.body_rendered or "",
        provider_response=response or {},
        error_message=error or "",
    )


def _schedule_fallback(job: NotificationJob) -> NotificationJob | None:
    chain = list(job.fallback_channels or [])
    next_index = int(job.fallback_index or 0) + 1
    while next_index < len(chain):
        next_channel = chain[next_index]
        destination = _destination_for_channel(next_channel, job.payload_json or {})
        if destination:
            return NotificationJob.objects.create(
                municipio=job.municipio,
                secretaria=job.secretaria,
                unidade=job.unidade,
                event_key=job.event_key,
                channel=next_channel,
                destination=destination,
                to_name=job.to_name or "",
                payload_json=job.payload_json or {},
                subject_rendered=job.subject_rendered or "",
                body_rendered=job.body_rendered or "",
                status=NotificationJob.Status.PENDENTE,
                priority=job.priority,
                message_kind=job.message_kind,
                correlation_key=job.correlation_key,
                attempts=0,
                max_attempts=job.max_attempts,
                fallback_channels=chain,
                fallback_index=next_index,
                entity_module=job.entity_module or "",
                entity_type=job.entity_type or "",
                entity_id=job.entity_id or "",
                created_by=job.created_by,
            )
        next_index += 1
    return None


def _send_email(job: NotificationJob, config: NotificationChannelConfig) -> dict[str, Any]:
    from_email = (
        config.sender_identifier
        or _credentials_value(config, "from_email", "sender")
        or getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@gepub.local")
    )
    subject = job.subject_rendered or f"Notificação GEPUB • {job.event_key}"
    message = job.body_rendered or "Você possui uma atualização no GEPUB."
    smtp_host = _credentials_value(config, "host", "smtp_host")
    smtp_port = _to_int(_credentials_value(config, "port", "smtp_port", default="587"), 587)
    smtp_user = _credentials_value(config, "username", "user", "smtp_user")
    smtp_password = _credentials_value(config, "password", "pass", "smtp_password")
    use_tls = _to_bool(config.get_credentials().get("use_tls"), default=True)
    use_ssl = _to_bool(config.get_credentials().get("use_ssl"), default=False)
    timeout = _to_int(config.get_credentials().get("timeout"), 20)
    if smtp_host:
        connection = get_connection(
            host=smtp_host,
            port=smtp_port,
            username=smtp_user or None,
            password=smtp_password or None,
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=timeout,
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[job.destination],
            fail_silently=False,
            connection=connection,
        )
    else:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[job.destination],
            fail_silently=False,
        )
    return {"provider": config.provider, "result": "accepted", "to": job.destination, "channel": "email"}


def _twilio_send_message(*, account_sid: str, auth_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    base_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    encoded = parse.urlencode(payload).encode("utf-8")
    auth_raw = f"{account_sid}:{auth_token}".encode("utf-8")
    auth_header = base64.b64encode(auth_raw).decode("utf-8")
    req = request.Request(base_url, data=encoded, method="POST")
    req.add_header("Authorization", f"Basic {auth_header}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _meta_send_message(*, access_token: str, phone_number_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=raw, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _send_whatsapp(job: NotificationJob, config: NotificationChannelConfig) -> dict[str, Any]:
    credentials = config.get_credentials()
    dry_run = _to_bool((config.options_json or {}).get("dry_run"), default=True)
    text_body = job.body_rendered or f"Atualização GEPUB: {job.event_key}"
    destination = (job.destination or "").strip()
    if not destination:
        raise ValueError("Destino de WhatsApp não informado.")

    if config.provider == NotificationChannelConfig.Provider.TWILIO:
        account_sid = _credentials_value(config, "account_sid", "sid")
        auth_token = _credentials_value(config, "auth_token", "token")
        from_number = _credentials_value(config, "from_number", "whatsapp_from")
        if not (account_sid and auth_token and from_number):
            raise ValueError("Credenciais Twilio incompletas (account_sid, auth_token, from_number).")
        payload = {
            "From": f"whatsapp:{from_number}",
            "To": f"whatsapp:{destination}",
            "Body": text_body,
        }
        if dry_run:
            return {
                "provider": config.provider,
                "result": "dry_run",
                "channel": "whatsapp",
                "to": destination,
                "payload": payload,
            }
        response = _twilio_send_message(account_sid=account_sid, auth_token=auth_token, payload=payload)
        return {
            "provider": config.provider,
            "result": "accepted",
            "channel": "whatsapp",
            "to": destination,
            "message_id": str(response.get("sid") or ""),
            "response": response,
        }

    if config.provider == NotificationChannelConfig.Provider.META:
        access_token = _credentials_value(config, "access_token", "token")
        phone_number_id = _credentials_value(config, "phone_number_id")
        if not (access_token and phone_number_id):
            raise ValueError("Credenciais Meta incompletas (access_token, phone_number_id).")
        payload = {
            "messaging_product": "whatsapp",
            "to": destination,
            "type": "text",
            "text": {"body": text_body},
        }
        if dry_run:
            return {
                "provider": config.provider,
                "result": "dry_run",
                "channel": "whatsapp",
                "to": destination,
                "payload": payload,
            }
        response = _meta_send_message(access_token=access_token, phone_number_id=phone_number_id, payload=payload)
        message_id = ""
        try:
            message_id = str(((response.get("messages") or [{}])[0]).get("id") or "")
        except Exception:
            message_id = ""
        return {
            "provider": config.provider,
            "result": "accepted",
            "channel": "whatsapp",
            "to": destination,
            "message_id": message_id,
            "response": response,
        }

    if config.provider in {NotificationChannelConfig.Provider.MOCK, NotificationChannelConfig.Provider.OUTRO}:
        return _send_mock(job, config)

    raise ValueError(f"Provedor {config.provider} ainda não suportado para WhatsApp.")


def _send_sms(job: NotificationJob, config: NotificationChannelConfig) -> dict[str, Any]:
    if config.provider == NotificationChannelConfig.Provider.TWILIO:
        account_sid = _credentials_value(config, "account_sid", "sid")
        auth_token = _credentials_value(config, "auth_token", "token")
        from_number = _credentials_value(config, "from_number", "sms_from")
        text_body = job.body_rendered or f"Atualização GEPUB: {job.event_key}"
        if not (account_sid and auth_token and from_number):
            raise ValueError("Credenciais Twilio SMS incompletas.")
        payload = {
            "From": from_number,
            "To": (job.destination or "").strip(),
            "Body": text_body,
        }
        dry_run = _to_bool((config.options_json or {}).get("dry_run"), default=True)
        if dry_run:
            return {
                "provider": config.provider,
                "result": "dry_run",
                "channel": "sms",
                "to": job.destination,
                "payload": payload,
            }
        response = _twilio_send_message(account_sid=account_sid, auth_token=auth_token, payload=payload)
        return {
            "provider": config.provider,
            "result": "accepted",
            "channel": "sms",
            "to": job.destination,
            "message_id": str(response.get("sid") or ""),
            "response": response,
        }
    return _send_mock(job, config)


def _send_mock(job: NotificationJob, config: NotificationChannelConfig) -> dict[str, Any]:
    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    return {
        "provider": config.provider,
        "result": "mock_sent",
        "message_id": f"mock-{job.channel.lower()}-{job.pk}-{timestamp}",
        "to": job.destination,
    }


def send_notification_job(job: NotificationJob) -> NotificationJob:
    if job.status in {NotificationJob.Status.ENTREGUE, NotificationJob.Status.CANCELADO}:
        return job

    now = timezone.now()
    job.status = NotificationJob.Status.PROCESSANDO
    job.attempts = int(job.attempts or 0) + 1
    job.save(update_fields=["status", "attempts", "updated_at"])

    config = _resolve_channel_config(
        municipio=job.municipio,
        channel=job.channel,
        secretaria=job.secretaria,
        unidade=job.unidade,
    )
    if not config:
        error = f"Canal {job.get_channel_display()} sem configuração ativa no escopo."
        if job.attempts < job.max_attempts:
            job.status = NotificationJob.Status.PENDENTE
            job.scheduled_at = now + timedelta(minutes=_retry_delay_minutes(job.attempts))
        else:
            job.status = NotificationJob.Status.FALHA
        job.error_message = error
        job.save(update_fields=["status", "scheduled_at", "error_message", "updated_at"])
        _create_log(job, status=job.status, error=error)
        if job.status == NotificationJob.Status.FALHA:
            _schedule_fallback(job)
        return job

    try:
        response: dict[str, Any]
        job.provider = config.provider

        if job.channel == NotificationChannelConfig.Channel.EMAIL:
            response = _send_email(job, config)
        elif job.channel == NotificationChannelConfig.Channel.WHATSAPP:
            response = _send_whatsapp(job, config)
        elif job.channel == NotificationChannelConfig.Channel.SMS:
            response = _send_sms(job, config)
        else:
            response = _send_mock(job, config)

        job.status = NotificationJob.Status.ENTREGUE
        job.sent_at = now
        job.delivered_at = now
        job.provider_message_id = str(response.get("message_id") or "")
        job.error_message = ""
        job.save(
            update_fields=[
                "provider",
                "status",
                "sent_at",
                "delivered_at",
                "provider_message_id",
                "error_message",
                "updated_at",
            ]
        )
        _create_log(job, status=job.status, response=response)
        registrar_auditoria(
            municipio=job.municipio,
            modulo="COMUNICACAO",
            evento="NOTIFICACAO_ENTREGUE",
            entidade="NotificationJob",
            entidade_id=job.pk,
            usuario=job.created_by,
            depois={
                "event_key": job.event_key,
                "channel": job.channel,
                "destination": job.destination,
                "provider": job.provider,
                "status": job.status,
            },
        )
        return job
    except Exception as exc:
        error = str(exc)
        if job.attempts < job.max_attempts:
            job.status = NotificationJob.Status.PENDENTE
            job.scheduled_at = now + timedelta(minutes=_retry_delay_minutes(job.attempts))
        else:
            job.status = NotificationJob.Status.FALHA
        job.error_message = error
        job.save(update_fields=["provider", "status", "scheduled_at", "error_message", "updated_at"])
        _create_log(job, status=job.status, error=error)
        registrar_auditoria(
            municipio=job.municipio,
            modulo="COMUNICACAO",
            evento="NOTIFICACAO_FALHOU",
            entidade="NotificationJob",
            entidade_id=job.pk,
            usuario=job.created_by,
            depois={
                "event_key": job.event_key,
                "channel": job.channel,
                "destination": job.destination,
                "status": job.status,
                "erro": error[:280],
            },
        )
        if job.status == NotificationJob.Status.FALHA:
            _schedule_fallback(job)
        return job


def run_channel_connection_test(
    *,
    config: NotificationChannelConfig,
    destination: str | None = None,
    actor=None,
) -> dict[str, Any]:
    target = (destination or "").strip() or (config.sender_identifier or "").strip()
    if not target:
        raise ValueError("Informe um destino de teste (e-mail/telefone).")

    test_job = NotificationJob(
        municipio=config.municipio,
        secretaria=config.secretaria,
        unidade=config.unidade,
        event_key="comunicacao.configuracao.teste",
        channel=config.channel,
        destination=target,
        to_name="Teste de canal",
        payload_json={"nome": "Teste", "tenant": config.municipio.nome},
        subject_rendered="Teste de configuração GEPUB",
        body_rendered="Mensagem de teste enviada pela central de comunicação.",
        status=NotificationJob.Status.PENDENTE,
        priority=NotificationJob.Priority.NORMAL,
        message_kind=NotificationJob.MessageKind.INTERNA,
        created_by=actor,
    )

    now = timezone.now()
    try:
        if config.channel == NotificationChannelConfig.Channel.EMAIL:
            response = _send_email(test_job, config)
        elif config.channel == NotificationChannelConfig.Channel.WHATSAPP:
            response = _send_whatsapp(test_job, config)
        elif config.channel == NotificationChannelConfig.Channel.SMS:
            response = _send_sms(test_job, config)
        else:
            response = _send_mock(test_job, config)
        config.last_test_status = NotificationChannelConfig.TestStatus.SUCESSO
        config.last_test_message = "Conexão validada com sucesso."
        config.last_tested_at = now
        config.save(update_fields=["last_test_status", "last_test_message", "last_tested_at", "atualizado_em"])
        return {"ok": True, "channel": config.channel, "provider": config.provider, "response": response}
    except Exception as exc:
        config.last_test_status = NotificationChannelConfig.TestStatus.FALHA
        config.last_test_message = str(exc)[:1000]
        config.last_tested_at = now
        config.save(update_fields=["last_test_status", "last_test_message", "last_tested_at", "atualizado_em"])
        raise


def process_pending_notification_jobs(*, limit: int = 100) -> dict[str, int]:
    now = timezone.now()
    qs = (
        NotificationJob.objects.select_related("municipio", "secretaria", "unidade", "created_by")
        .filter(status=NotificationJob.Status.PENDENTE, scheduled_at__lte=now)
        .annotate(priority_order=_priority_order_expr())
        .order_by("priority_order", "scheduled_at", "id")
    )
    processed = 0
    delivered = 0
    failed = 0
    for job in qs[: max(1, int(limit or 100))]:
        processed += 1
        send_notification_job(job)
        if job.status == NotificationJob.Status.ENTREGUE:
            delivered += 1
        elif job.status == NotificationJob.Status.FALHA:
            failed += 1
    return {"processed": processed, "delivered": delivered, "failed": failed}
