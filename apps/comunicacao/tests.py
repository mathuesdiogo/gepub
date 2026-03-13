from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Profile
from apps.org.models import Municipio

from .models import NotificationChannelConfig, NotificationJob, NotificationLog, NotificationTemplate
from .services import process_pending_notification_jobs


class ComunicacaoModuleTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="muni_com", password="123456")
        profile = getattr(self.user, "profile", None)
        if profile is None:
            profile = Profile.objects.create(user=self.user)

        self.municipio = Municipio.objects.create(nome="Cidade Comunicação", uf="MA", ativo=True)
        profile.role = Profile.Role.MUNICIPAL
        profile.municipio = self.municipio
        profile.must_change_password = False
        profile.ativo = True
        profile.save(update_fields=["role", "municipio", "must_change_password", "ativo"])
        self.client.force_login(self.user)

        NotificationChannelConfig.objects.create(
            municipio=self.municipio,
            channel=NotificationChannelConfig.Channel.WHATSAPP,
            provider=NotificationChannelConfig.Provider.MOCK,
            sender_name="GEPUB",
            sender_identifier="5511999999999",
            is_active=True,
            atualizado_por=self.user,
        )

    def test_notifications_send_and_process_queue(self):
        payload = {
            "event_key": "educacao.comunicado",
            "subject": "Comunicado",
            "body": "Olá {{nome}}, nova atualização no portal.",
            "recipients": [
                {
                    "nome": "Responsável Teste",
                    "whatsapp": "5598999999999",
                    "channels": ["WHATSAPP"],
                }
            ],
            "priority": "NORMAL",
        }
        resp = self.client.post(
            reverse("comunicacao:notifications_send") + f"?municipio={self.municipio.pk}",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("queued"), 1)

        job = NotificationJob.objects.first()
        self.assertIsNotNone(job)
        self.assertEqual(job.channel, NotificationChannelConfig.Channel.WHATSAPP)
        self.assertEqual(job.status, NotificationJob.Status.PENDENTE)

        resp_process = self.client.post(
            reverse("comunicacao:processar_fila") + f"?municipio={self.municipio.pk}",
            data={"limit": 10},
            follow=True,
        )
        self.assertEqual(resp_process.status_code, 200)

        job.refresh_from_db()
        self.assertEqual(job.status, NotificationJob.Status.ENTREGUE)
        self.assertTrue(NotificationLog.objects.filter(job=job).exists())

    def test_templates_api_create_and_list(self):
        create_payload = {
            "scope": "MUNICIPIO",
            "event_key": "protocol.updated",
            "channel": "EMAIL",
            "nome": "Atualização de protocolo",
            "subject": "Seu protocolo {{protocolo_numero}} foi atualizado",
            "body": "Olá {{nome}}, status: {{status}}",
            "is_active": "true",
            "nee_safe": "false",
        }
        resp_create = self.client.post(
            reverse("comunicacao:templates_api") + f"?municipio={self.municipio.pk}",
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        self.assertEqual(resp_create.status_code, 200)
        self.assertTrue(resp_create.json().get("ok"))
        template_id = resp_create.json().get("id")
        self.assertTrue(NotificationTemplate.objects.filter(pk=template_id).exists())

        resp_list = self.client.get(reverse("comunicacao:templates_api") + f"?municipio={self.municipio.pk}")
        self.assertEqual(resp_list.status_code, 200)
        self.assertTrue(resp_list.json().get("count", 0) >= 1)

    def test_logs_endpoint_requires_data_and_returns_json(self):
        job = NotificationJob.objects.create(
            municipio=self.municipio,
            event_key="processo.criado",
            channel=NotificationChannelConfig.Channel.WHATSAPP,
            destination="5598999990000",
            status=NotificationJob.Status.FALHA,
            priority=NotificationJob.Priority.NORMAL,
            body_rendered="Falha teste",
            created_by=self.user,
        )
        NotificationLog.objects.create(
            job=job,
            status=NotificationJob.Status.FALHA,
            attempt=1,
            channel=NotificationChannelConfig.Channel.WHATSAPP,
            provider=NotificationChannelConfig.Provider.MOCK,
            destination=job.destination,
            error_message="Erro de teste",
        )

        resp = self.client.get(reverse("comunicacao:notifications_logs") + f"?municipio={self.municipio.pk}&limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertGreaterEqual(data.get("count", 0), 1)

    def test_events_catalog_endpoint_returns_items(self):
        resp = self.client.get(reverse("comunicacao:events_catalog_api") + f"?municipio={self.municipio.pk}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertGreaterEqual(data.get("count", 0), 1)
        first = (data.get("items") or [{}])[0]
        self.assertIn("key", first)
        self.assertIn("variables", first)

    def test_template_preview_reports_missing_placeholders(self):
        payload = {
            "subject": "Aviso para {{nome}}",
            "body": "Consulta em {{data}} às {{hora}}",
            "payload": {"nome": "Maria", "data": "01/03/2026"},
        }
        resp = self.client.post(
            reverse("comunicacao:template_preview_api") + f"?municipio={self.municipio.pk}",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertIn("hora", data.get("missing", []))
        self.assertEqual(data.get("rendered_subject"), "Aviso para Maria")

    def test_retry_uses_exponential_backoff_without_channel_config(self):
        job = NotificationJob.objects.create(
            municipio=self.municipio,
            event_key="saude.consulta.lembrete",
            channel=NotificationChannelConfig.Channel.EMAIL,
            destination="responsavel@example.com",
            status=NotificationJob.Status.PENDENTE,
            priority=NotificationJob.Priority.NORMAL,
            max_attempts=3,
            created_by=self.user,
        )
        process_pending_notification_jobs(limit=10)
        job.refresh_from_db()
        self.assertEqual(job.status, NotificationJob.Status.PENDENTE)
        self.assertEqual(job.attempts, 1)
        delta_first = (job.scheduled_at - timezone.now()).total_seconds()
        self.assertGreaterEqual(delta_first, 60)

        job.scheduled_at = timezone.now() - timedelta(minutes=1)
        job.save(update_fields=["scheduled_at"])
        process_pending_notification_jobs(limit=10)
        job.refresh_from_db()
        self.assertEqual(job.status, NotificationJob.Status.PENDENTE)
        self.assertEqual(job.attempts, 2)
        delta_second = (job.scheduled_at - timezone.now()).total_seconds()
        self.assertGreaterEqual(delta_second, 180)
