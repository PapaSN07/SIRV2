from celery import Celery
from celery.schedules import crontab

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
        "app.workers.tasks.alertes",
        "app.workers.tasks.rapports_planifies",
        "app.workers.tasks.base_clients",
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
    # Tâches planifiées : le worker est lancé avec -B (beat intégré, un seul worker)
    beat_schedule={
        "alertes-retard-24h": {"task": "alertes_retard_24h", "schedule": 3600.0},
        # Base clients SAIFI/SAIDI : BI_ODS est rechargée par SSIS vers 5 h 30 ; la photo du mois
        # est remplacée chaque jour, la dernière du mois fait foi (comme le fichier H2MC mensuel)
        "base-clients-bi-ods-7h": {
            "task": "synchroniser_contrats_ur",
            "schedule": crontab(hour=7, minute=0),
        },
        # Heure de Dakar (timezone ci-dessus) — décision SENELEC du 27/10/2026
        # Rapport hebdomadaire d'exploitation DD (samedi → vendredi) — décision du 29/10/2026
        "rapport-hebdo-dd-samedi-8h": {
            "task": "rapports_planifies",
            "schedule": crontab(hour=8, minute=0, day_of_week=6),
            "args": ("hebdo_dd",),
        },
        "rapport-mensuel-1er-8h": {
            "task": "rapports_planifies",
            "schedule": crontab(hour=8, minute=0, day_of_month=1),
            "args": ("mensuel_distribution",),
        },
    },
)
