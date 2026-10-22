from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "sir",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.indicateurs",
        "app.workers.tasks.rapports",
        "app.workers.tasks.notifications",
        "app.workers.tasks.assistant_ml",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Dakar",
    enable_utc=True,
    task_track_started=True,
    result_expires=86400,  # 24h
)
