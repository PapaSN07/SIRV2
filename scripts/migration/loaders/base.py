"""Classe de base pour les loaders ETL."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from scripts.migration.config import get_settings
from scripts.migration.id_maps import IdMapStore

logger = logging.getLogger(__name__)


class BaseLoader:
    entity_name: str = "base"

    def __init__(
        self,
        session: Session,
        id_maps: IdMapStore,
        dry_run: bool = True,
        batch_size: int | None = None,
    ) -> None:
        self.session = session
        self.id_maps = id_maps
        self.dry_run = dry_run
        self.batch_size = batch_size or get_settings().migration_batch_size
        self.stats: dict[str, int] = {"inserted": 0, "skipped": 0, "rejected": 0}
        self._reject_reasons: dict[str, int] = {}
        self._log_path = get_settings().logs_dir / f"etl_{datetime.now():%Y%m%d}.jsonl"

    def log_reject(self, legacy_id: Any, reason: str, row: dict | None = None) -> None:
        self.stats["rejected"] += 1
        self._reject_reasons[reason] = self._reject_reasons.get(reason, 0) + 1
        if self._reject_reasons[reason] <= 5:
            logger.warning("Rejet %s/%s: %s", self.entity_name, legacy_id, reason)
        entry = {
            "entity": self.entity_name,
            "legacy_id": legacy_id,
            "reason": reason,
            "at": datetime.now().isoformat(),
        }
        if row:
            safe = {k: v for k, v in row.items() if k.lower() not in ("mdp", "password", "motpasse")}
            entry["row_preview"] = {k: safe[k] for k in list(safe)[:8]}
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def flush_batch(self) -> None:
        if self.dry_run:
            self.session.rollback()
        else:
            self.session.commit()

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {"entity": self.entity_name, "dry_run": self.dry_run, **self.stats}
        if self._reject_reasons:
            out["reject_reasons"] = dict(
                sorted(self._reject_reasons.items(), key=lambda x: -x[1])[:15]
            )
        return out
