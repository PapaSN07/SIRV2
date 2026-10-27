"""Repository — datamart ML + prédictions + conversations Assistant."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, text, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_ml import AssistantConversation, MlFeatureSnapshot, MlPrediction
from app.models.reseau import Feeder
from app.models.utilisateurs import Utilisateur


async def list_feeder_incident_stats(
    db: AsyncSession,
    *,
    since: datetime,
    service_ids: list[int] | None = None,
    feeder_id: int | None = None,
) -> list[dict[str, Any]]:
    """Agrège les incidents distribution par feeder depuis `since` (datamart runtime)."""
    sql = """
        SELECT
            i.feeder_id AS feeder_id,
            f.code AS feeder_code,
            f.libelle AS feeder_libelle,
            i.service_id AS service_id,
            COUNT(*) AS nb_interruptions,
            SUM(
                CASE
                    WHEN n.code IN (N'PERMANENT', N'SEMI_PERMANENT', N'permanent', N'semi-permanent')
                      OR LOWER(COALESCE(n.libelle, N'')) LIKE N'%permanent%'
                    THEN 1 ELSE 0
                END
            ) AS nb_permanentes,
            AVG(CAST(i.duree_minutes AS FLOAT)) AS duree_moyenne_minutes,
            SUM(COALESCE(i.nombre_clients_touches, 0)) AS clients_touches_total
        FROM dbo.interruptions i
        LEFT JOIN dbo.feeders f ON f.id = i.feeder_id
        LEFT JOIN dbo.natures n ON n.id = i.nature_id
        WHERE i.type_direction = N'distribution'
          AND i.feeder_id IS NOT NULL
          AND i.date_apparition >= :since
    """
    params: dict[str, Any] = {"since": since}
    if feeder_id is not None:
        sql += " AND i.feeder_id = :feeder_id"
        params["feeder_id"] = feeder_id
    if service_ids:
        placeholders = ", ".join(f":sid{i}" for i in range(len(service_ids)))
        sql += f" AND i.service_id IN ({placeholders})"
        for i, sid in enumerate(service_ids):
            params[f"sid{i}"] = sid
    sql += """
        GROUP BY i.feeder_id, f.code, f.libelle, i.service_id
        ORDER BY COUNT(*) DESC
    """
    result = await db.execute(text(sql), params)
    return [dict(row) for row in result.mappings().all()]


async def list_datamart_feeder_mois(
    db: AsyncSession,
    *,
    service_ids: list[int] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 500))
    sql = f"""
        SELECT TOP ({safe_limit})
            feeder_id, feeder_code, feeder_libelle, service_id,
            annee, mois, nb_interruptions, nb_force_majeure,
            duree_moyenne_minutes, clients_touches_total
        FROM dbo.v_ml_incidents_feeder_mois
        WHERE 1 = 1
    """
    params: dict[str, Any] = {}
    if service_ids:
        placeholders = ", ".join(f":sid{i}" for i in range(len(service_ids)))
        sql += f" AND service_id IN ({placeholders})"
        for i, sid in enumerate(service_ids):
            params[f"sid{i}"] = sid
    sql += " ORDER BY annee DESC, mois DESC, nb_interruptions DESC"
    result = await db.execute(text(sql), params)
    return [dict(row) for row in result.mappings().all()]


async def list_datamart_troncon_sig(
    db: AsyncSession,
    *,
    service_ids: list[int] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 500))
    sql = f"""
        SELECT TOP ({safe_limit})
            troncon_sig_id, troncon_sig_libelle, feeder_id, service_id,
            nb_interruptions, duree_moyenne_minutes, derniere_apparition
        FROM dbo.v_ml_incidents_troncon_sig
        WHERE 1 = 1
    """
    params: dict[str, Any] = {}
    if service_ids:
        placeholders = ", ".join(f":sid{i}" for i in range(len(service_ids)))
        sql += f" AND service_id IN ({placeholders})"
        for i, sid in enumerate(service_ids):
            params[f"sid{i}"] = sid
    sql += " ORDER BY nb_interruptions DESC"
    result = await db.execute(text(sql), params)
    return [dict(row) for row in result.mappings().all()]


async def list_datamart_poste(
    db: AsyncSession,
    *,
    service_ids: list[int] | None = None,
    feeder_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 500))
    sql = f"""
        SELECT TOP ({safe_limit})
            poste_id, poste_code, poste_libelle, feeder_id, service_id,
            nb_impactes, clients_touches_total, derniere_apparition
        FROM dbo.v_ml_incidents_poste
        WHERE 1 = 1
    """
    params: dict[str, Any] = {}
    if feeder_id is not None:
        sql += " AND feeder_id = :feeder_id"
        params["feeder_id"] = feeder_id
    if service_ids:
        placeholders = ", ".join(f":sid{i}" for i in range(len(service_ids)))
        sql += f" AND service_id IN ({placeholders})"
        for i, sid in enumerate(service_ids):
            params[f"sid{i}"] = sid
    sql += " ORDER BY nb_impactes DESC"
    result = await db.execute(text(sql), params)
    return [dict(row) for row in result.mappings().all()]


async def get_feeder(db: AsyncSession, feeder_id: int) -> Feeder | None:
    result = await db.execute(select(Feeder).where(Feeder.id == feeder_id))
    return result.scalar_one_or_none()


async def deactivate_predictions(
    db: AsyncSession,
    *,
    entity_type: str,
    horizon_days: int,
    model_version: str,
) -> None:
    await db.execute(
        update(MlPrediction)
        .where(
            MlPrediction.entity_type == entity_type,
            MlPrediction.horizon_days == horizon_days,
            MlPrediction.model_version == model_version,
            MlPrediction.is_active == true(),
        )
        .values(is_active=False)
    )


async def add_feature_snapshot(db: AsyncSession, snapshot: MlFeatureSnapshot) -> MlFeatureSnapshot:
    db.add(snapshot)
    await db.flush()
    return snapshot


async def add_prediction(db: AsyncSession, prediction: MlPrediction) -> MlPrediction:
    db.add(prediction)
    await db.flush()
    return prediction


async def list_active_predictions(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    feeder_id: int | None = None,
    service_ids: list[int] | None = None,
    risk_level: str | None = None,
    limit: int = 50,
) -> list[MlPrediction]:
    stmt = (
        select(MlPrediction)
        .where(MlPrediction.is_active == true())
        .order_by(MlPrediction.risk_score.desc(), MlPrediction.calculated_at.desc())
        .offset(0)
        .limit(limit)
    )
    if entity_type:
        stmt = stmt.where(MlPrediction.entity_type == entity_type)
    if feeder_id is not None:
        stmt = stmt.where(
            (MlPrediction.feeder_id == feeder_id)
            | (
                (MlPrediction.entity_type == "feeder")
                & (MlPrediction.entity_id == feeder_id)
            )
        )
    if risk_level:
        stmt = stmt.where(MlPrediction.risk_level == risk_level)
    if service_ids:
        stmt = stmt.where(MlPrediction.service_id.in_(service_ids))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_latest_feeder_prediction(
    db: AsyncSession,
    feeder_id: int,
    *,
    service_ids: list[int] | None = None,
) -> MlPrediction | None:
    stmt = (
        select(MlPrediction)
        .where(
            MlPrediction.is_active == true(),
            MlPrediction.entity_type == "feeder",
            MlPrediction.entity_id == feeder_id,
        )
        .order_by(MlPrediction.calculated_at.desc())
        .offset(0)
        .limit(1)
    )
    if service_ids:
        stmt = stmt.where(MlPrediction.service_id.in_(service_ids))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def add_conversation(
    db: AsyncSession,
    *,
    user: Utilisateur,
    question: str,
    answer: str,
    context_json: str | None,
    feeder_id: int | None,
    interruption_id: int | None,
) -> AssistantConversation:
    row = AssistantConversation(
        user_id=user.id,
        question=question,
        answer=answer,
        context_json=context_json,
        feeder_id=feeder_id,
        interruption_id=interruption_id,
    )
    db.add(row)
    await db.flush()
    return row


async def set_conversation_feedback(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
    accepted: bool,
) -> AssistantConversation | None:
    result = await db.execute(
        select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    row.accepted = accepted
    await db.flush()
    return row
