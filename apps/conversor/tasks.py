from __future__ import annotations

from celery import shared_task

from .services import process_conversion_job_with_audit


@shared_task(name="conversor.process_job")
def process_conversion_job_task(job_id: int, actor_id: int | None = None):
    process_conversion_job_with_audit(job_id, actor_id=actor_id)
