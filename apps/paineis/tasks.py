from __future__ import annotations

from celery import shared_task

from .services.processing import process_dataset_version


@shared_task(name="paineis.process_dataset_version")
def process_dataset_version_task(version_id: int, google_sheet_url: str = "", actor_id: int | None = None):
    process_dataset_version(
        version_id,
        google_sheet_url=google_sheet_url,
        actor_id=actor_id,
    )
