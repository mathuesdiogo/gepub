from __future__ import annotations

from celery import shared_task

from .models import NotificationJob
from .services import process_pending_notification_jobs, send_notification_job


@shared_task(name="comunicacao.process_job")
def process_notification_job_task(job_id: int):
    job = NotificationJob.objects.filter(pk=job_id).first()
    if not job:
        return
    send_notification_job(job)


@shared_task(name="comunicacao.process_pending")
def process_pending_notification_jobs_task(limit: int = 100):
    return process_pending_notification_jobs(limit=limit)
