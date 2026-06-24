"""Persistance des correspondances legacy_id → sir_v2_id."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.migration.config import get_settings


class IdMapStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or get_settings().id_maps_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, int]] = {}

    def _path(self, entity: str) -> Path:
        return self.base_dir / f"{entity}.json"

    def load(self, entity: str) -> dict[str, int]:
        if entity in self._cache:
            return self._cache[entity]
        path = self._path(entity)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self._cache[entity] = {str(k): int(v) for k, v in data.items()}
        else:
            self._cache[entity] = {}
        return self._cache[entity]

    def save(self, entity: str) -> None:
        path = self._path(entity)
        path.write_text(
            json.dumps(self._cache.get(entity, {}), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def put(self, entity: str, legacy_key: str | int, new_id: int) -> None:
        mapping = self.load(entity)
        mapping[str(legacy_key)] = new_id
        self._cache[entity] = mapping

    def get(self, entity: str, legacy_key: str | int | None) -> int | None:
        if legacy_key is None:
            return None
        return self.load(entity).get(str(legacy_key))

    def lookup_text(self, entity: str, text_key: str) -> int | None:
        """Lookup par clé texte normalisée (feeders, services…)."""
        return self.get(entity, text_key.strip().upper() if text_key else None)
