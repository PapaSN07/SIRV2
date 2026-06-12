import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

# Valid action values — matches ck_audit_action constraint
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
VALID_ACTIONS = {ACTION_CREATE, ACTION_UPDATE, ACTION_DELETE}


async def log_audit(
    db: AsyncSession,
    *,
    table_name: str,
    record_id: int,
    action: str,
    user_id: int,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist an audit log entry for a sensitive mutation.

    Must be called AFTER the mutation is staged (before commit).
    The caller's session commit will persist both the mutation and the log atomically.

    Args:
        db: Active async database session (same session as the mutation).
        table_name: Name of the table being mutated (e.g. "interruptions").
        record_id: Primary key of the mutated record.
        action: One of "create", "update", "delete".
        user_id: ID of the user performing the action.
        old_values: Previous field values (None for creates).
        new_values: New field values (None for deletes).

    Returns:
        The unsaved AuditLog instance (added to the session).

    Raises:
        ValueError: If action is not one of the valid values.

    Example:
        await log_audit(
            db,
            table_name="interruptions",
            record_id=interruption.id,
            action="update",
            user_id=current_user.id,
            old_values={"statut": "en_cours"},
            new_values={"statut": "valide"},
        )
    """
    if action not in VALID_ACTIONS:
        raise ValueError(
            f"Action '{action}' invalide. Valeurs acceptées : {sorted(VALID_ACTIONS)}"
        )

    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        user_id=user_id,
        old_values=json.dumps(old_values, ensure_ascii=False, default=str)
        if old_values is not None
        else None,
        new_values=json.dumps(new_values, ensure_ascii=False, default=str)
        if new_values is not None
        else None,
    )
    db.add(entry)
    return entry
