"""Loader vague 1 — géographie."""

from __future__ import annotations

from typing import Any

from app.models.geo import Agence, Delegation, Region, Service

from scripts.migration.hfsql_odbc import load_table_rows
from scripts.migration.loaders.base import BaseLoader
from scripts.migration.transforms.codes import slug_code, text_key
from scripts.migration.transforms.rows import row_get


class GeoLoader(BaseLoader):
    entity_name = "geo"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._region_agence: dict[int, int] = {}

    def run(self) -> dict[str, Any]:
        self._load_regions()
        self._load_delegations()
        self._load_agences()
        self._cache_agence_by_region()
        self._load_services()
        for entity in ("regions", "delegations", "agences", "services", "services_by_text"):
            self.id_maps.save(entity)
        return self.summary()

    def _load_regions(self) -> None:
        rows = load_table_rows("Regions")
        for row in rows:
            legacy_id = row_get(row, "IDRegions", "idregions")
            libelle = str(row_get(row, "Region", "region") or "").strip()
            if not libelle:
                self.log_reject(legacy_id, "region_vide", row)
                continue
            code = slug_code(libelle)
            if self.id_maps.get("regions", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("regions")) + 1
            else:
                obj = Region(code=code, libelle=libelle[:100], is_active=True)
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("regions", legacy_id, new_id)
            self.id_maps.put("regions_by_text", text_key(libelle) or code, new_id)
            self.stats["inserted"] += 1

    def _default_region_id(self) -> int | None:
        mapping = self.id_maps.load("regions")
        return next(iter(mapping.values()), None) if mapping else None

    def _load_delegations(self) -> None:
        rows = load_table_rows("Delegation")
        default_region = self._default_region_id()
        for row in rows:
            legacy_id = row_get(row, "IDDelegation", "iddelegation")
            libelle = str(
                row_get(row, "LibelleDelegation", "libelledelegation", "AbregeDelegation", "abregedelegation")
                or ""
            ).strip()
            if not libelle:
                self.log_reject(legacy_id, "delegation_vide", row)
                continue
            region_id = self.id_maps.get("regions", row_get(row, "IDRegions", "idregions")) or default_region
            if region_id is None:
                self.log_reject(legacy_id, "region_introuvable", row)
                continue
            abrege = row_get(row, "AbregeDelegation", "abregedelegation", "CodeDelegation", "codedelegation")
            code = slug_code(str(abrege or libelle), prefix="DEL")
            if self.id_maps.get("delegations", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("delegations")) + 1
            else:
                obj = Delegation(
                    region_id=region_id,
                    code=code,
                    libelle=libelle[:100],
                    is_active=True,
                )
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("delegations", legacy_id, new_id)
            self.stats["inserted"] += 1
        self._ensure_default_delegations()

    def _ensure_default_delegations(self) -> None:
        for region_legacy, region_id in self.id_maps.load("regions").items():
            key = f"DEFAULT_{region_legacy}"
            if self.id_maps.get("delegations", key):
                continue
            code = slug_code(f"DEFAULT_{region_legacy}", prefix="DEL")
            if self.dry_run:
                new_id = len(self.id_maps.load("delegations")) + 10000
            else:
                from sqlalchemy import select

                existing = self.session.execute(
                    select(Delegation).where(Delegation.code == code)
                ).scalar_one_or_none()
                if existing:
                    new_id = existing.id
                else:
                    obj = Delegation(
                        region_id=region_id,
                        code=code,
                        libelle="DEFAULT",
                        is_active=True,
                    )
                    self.session.add(obj)
                    self.session.flush()
                    new_id = obj.id
            self.id_maps.put("delegations", key, new_id)

    def _default_delegation_id(self) -> int | None:
        mapping = self.id_maps.load("delegations")
        return next(iter(mapping.values()), None) if mapping else None

    def _load_agences(self) -> None:
        rows = load_table_rows("Agences")
        default_del = self._default_delegation_id()
        for row in rows:
            legacy_id = row_get(row, "IDAgence", "idagence")
            libelle = str(row_get(row, "Agence", "agence") or "").strip()
            if not libelle:
                self.log_reject(legacy_id, "agence_vide", row)
                continue
            delegation_id = self.id_maps.get("delegations", row_get(row, "IDDelegation", "iddelegation")) or default_del
            if delegation_id is None:
                self.log_reject(legacy_id, "delegation_introuvable", row)
                continue
            code = slug_code(str(row_get(row, "Codeagence", "codeagence") or libelle), prefix="AG")
            if self.id_maps.get("agences", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("agences")) + 1
            else:
                obj = Agence(
                    delegation_id=delegation_id,
                    code=code,
                    libelle=libelle[:100],
                    is_active=True,
                )
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("agences", legacy_id, new_id)
            self.stats["inserted"] += 1

    def _default_agence_id(self) -> int | None:
        mapping = self.id_maps.load("agences")
        return next(iter(mapping.values()), None) if mapping else None

    def _cache_agence_by_region(self) -> None:
        """Première agence par région — rattachement Services.Region."""
        if self.dry_run:
            return
        from sqlalchemy import select

        rows = self.session.execute(
            select(Agence.id, Delegation.region_id)
            .join(Delegation, Agence.delegation_id == Delegation.id)
            .order_by(Agence.id)
        ).all()
        for agence_id, region_id in rows:
            if region_id not in self._region_agence:
                self._region_agence[int(region_id)] = int(agence_id)

    def _resolve_agence_id(self, row: dict) -> int | None:
        region_text = str(row_get(row, "Region", "region") or "").strip()
        if region_text:
            region_id = self.id_maps.lookup_text("regions_by_text", text_key(region_text))
            if region_id is not None:
                agence_id = self._region_agence.get(int(region_id))
                if agence_id is not None:
                    return agence_id
        delegation_legacy = row_get(row, "IDDelegation", "iddelegation")
        agence_id = self.id_maps.get("agences", delegation_legacy)
        if agence_id is not None:
            return agence_id
        return self._default_agence_id()

    def _load_services(self) -> None:
        rows = load_table_rows("Services")
        for row in rows:
            legacy_id = row_get(row, "IDAUTO", "idauto")
            libelle = str(row_get(row, "Service", "service") or "").strip()
            if not libelle:
                self.log_reject(legacy_id, "service_vide", row)
                continue
            agence_id = self._resolve_agence_id(row)
            if agence_id is None:
                self.log_reject(legacy_id, "agence_introuvable", row)
                continue
            code = slug_code(libelle)
            if self.id_maps.get("services", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("services")) + 1
            else:
                obj = Service(
                    agence_id=agence_id,
                    code=code,
                    libelle=libelle[:100],
                    is_active=True,
                )
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("services", legacy_id, new_id)
            key = text_key(libelle)
            if key:
                self.id_maps.put("services_by_text", key, new_id)
            self.stats["inserted"] += 1
