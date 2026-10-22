"""Scoring risque panne / travaux — phase P0 (règles + statistiques)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_ml import MlFeatureSnapshot, MlPrediction
from app.repositories import assistant_ml_repository as repo

MODEL_VERSION = "p0-rules-v1"
DEFAULT_HORIZON_DAYS = 90


def _risk_level(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def compute_p0_score(stats: dict[str, Any], *, horizon_days: int) -> tuple[float, list[dict[str, Any]], str]:
    """Calcule un score 0–100 + facteurs explicatifs à partir d'agrégats feeder."""
    nb = int(stats.get("nb_interruptions") or 0)
    nb_perm = int(stats.get("nb_permanentes") or 0)
    duree = float(stats.get("duree_moyenne_minutes") or 0.0)
    clients = int(stats.get("clients_touches_total") or 0)

    # Normalisations empiriques (P0) — recalibrables SAQS
    freq_score = min(40.0, nb * (40.0 / max(horizon_days / 15.0, 1.0)))
    perm_ratio = (nb_perm / nb) if nb else 0.0
    perm_score = min(25.0, perm_ratio * 25.0)
    duree_score = min(20.0, (duree / 180.0) * 20.0) if duree else 0.0
    clients_score = min(15.0, (clients / 5000.0) * 15.0) if clients else 0.0

    score = round(freq_score + perm_score + duree_score + clients_score, 2)
    factors = [
        {
            "code": "frequence",
            "label": f"{nb} interruption(s) sur {horizon_days} j",
            "weight": round(freq_score, 2),
        },
        {
            "code": "permanentes",
            "label": f"{nb_perm} à caractère permanent/semi-permanent ({perm_ratio:.0%})",
            "weight": round(perm_score, 2),
        },
        {
            "code": "duree",
            "label": f"Durée moyenne {duree:.0f} min",
            "weight": round(duree_score, 2),
        },
        {
            "code": "clients",
            "label": f"{clients} clients touchés (cumul)",
            "weight": round(clients_score, 2),
        },
    ]

    level = _risk_level(score)
    if level in {"critical", "high"}:
        reco = (
            "Prioriser une inspection / travaux préventifs sur ce départ "
            "(tronçonnement SIG + postes impactés fréquents)."
        )
    elif level == "medium":
        reco = "Surveiller le feeder et planifier une visite si tendance haussière."
    else:
        reco = "Risque faible sur la fenêtre — maintenir le suivi habituel."
    return score, factors, reco


async def score_feeders(
    db: AsyncSession,
    *,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    service_ids: list[int] | None = None,
) -> dict[str, int | str]:
    """Recalcule les prédictions actives feeder (P0) et persiste snapshots."""
    now = datetime.utcnow()
    since = now - timedelta(days=horizon_days)
    stats_rows = await repo.list_feeder_incident_stats(
        db, since=since, service_ids=service_ids
    )

    await repo.deactivate_predictions(
        db,
        entity_type="feeder",
        horizon_days=horizon_days,
        model_version=MODEL_VERSION,
    )

    scored = 0
    for row in stats_rows:
        feeder_id = int(row["feeder_id"])
        score, factors, reco = compute_p0_score(row, horizon_days=horizon_days)
        snapshot = MlFeatureSnapshot(
            entity_type="feeder",
            entity_id=feeder_id,
            horizon_days=horizon_days,
            window_start=since,
            window_end=now,
            nb_interruptions=int(row.get("nb_interruptions") or 0),
            nb_permanentes=int(row.get("nb_permanentes") or 0),
            duree_moyenne_minutes=row.get("duree_moyenne_minutes"),
            clients_touches_total=int(row.get("clients_touches_total") or 0),
            service_id=row.get("service_id"),
            feeder_id=feeder_id,
            features_json=json.dumps(row, default=str)[:4000],
        )
        await repo.add_feature_snapshot(db, snapshot)

        libelle = row.get("feeder_libelle") or row.get("feeder_code") or f"Feeder #{feeder_id}"
        prediction = MlPrediction(
            entity_type="feeder",
            entity_id=feeder_id,
            entity_libelle=str(libelle)[:255],
            horizon_days=horizon_days,
            risk_score=score,
            risk_level=_risk_level(score),
            model_version=MODEL_VERSION,
            factors_json=json.dumps(factors, ensure_ascii=False)[:4000],
            recommendation=reco[:1000],
            service_id=row.get("service_id"),
            feeder_id=feeder_id,
            feature_snapshot_id=snapshot.id,
            calculated_at=now,
            is_active=True,
        )
        await repo.add_prediction(db, prediction)
        scored += 1

    await db.commit()
    return {
        "status": "calculated",
        "feeders_scored": scored,
        "model_version": MODEL_VERSION,
        "horizon_days": horizon_days,
    }
