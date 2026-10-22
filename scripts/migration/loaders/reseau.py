"""Loader vague 3 — réseau."""

from __future__ import annotations

from typing import Any

from app.models.reseau import (
    EquipementTransport,
    Feeder,
    Poste,
    PosteLigne,
    PosteSource,
    SousFeeder,
    Troncon,
)

from sqlalchemy import select

from scripts.migration.hfsql_odbc import load_table_rows
from scripts.migration.loaders.base import BaseLoader
from scripts.migration.transforms.codes import slug_code, text_key
from scripts.migration.transforms.fk_resolver import FkResolver
from scripts.migration.transforms.rows import row_get


class ReseauLoader(BaseLoader):
    entity_name = "reseau"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fk = FkResolver(self.id_maps)
        self._eq_codes: dict[str, int] = {}
        self._ps_codes: dict[str, int] = {}
        self._feeder_codes: dict[str, int] = {}

    def _feeder_legacy_id(self, row: dict) -> str | None:
        libelle = str(row_get(row, "Feeder", "feeder") or "").strip()
        if not libelle:
            return None
        raw = row_get(row, "IDFeeder", "idfeeder")
        try:
            if raw is not None and int(raw) > 0:
                return str(raw)
        except (TypeError, ValueError):
            pass
        key = text_key(libelle)
        return f"T:{key}" if key else None

    def _valid_poste_source_id(self, ps_id: int | None) -> int | None:
        if ps_id is None:
            return None
        if self.dry_run:
            return ps_id
        ok = self.session.execute(
            select(PosteSource.id).where(PosteSource.id == ps_id)
        ).scalar_one_or_none()
        return ps_id if ok else None

    def _resolve_poste_source_id(self, row: dict, ps_text: str | None = None) -> int | None:
        ps_legacy = row_get(row, "IDPosteSource", "idpostesource")
        if ps_legacy is not None:
            try:
                if int(ps_legacy) > 0:
                    ps_id = self._valid_poste_source_id(
                        self.id_maps.get("postes_sources", ps_legacy)
                    )
                    if ps_id:
                        return ps_id
            except (TypeError, ValueError):
                pass
        ps_text = (ps_text or str(row_get(row, "PosteSource", "PosteSOurce", "postesource") or "")).strip()
        if not ps_text:
            return None
        ps_id = self._valid_poste_source_id(self.fk.poste_source_id(ps_text))
        if ps_id is not None:
            return ps_id
        code = slug_code(ps_text)
        if code in self._ps_codes:
            return self._ps_codes[code]
        if not self.dry_run:
            existing = self.session.execute(
                select(PosteSource.id).where(PosteSource.code == code)
            ).scalar_one_or_none()
            if existing:
                self._ps_codes[code] = existing
                key = text_key(ps_text)
                if key:
                    self.id_maps.put("postes_sources_by_text", key, existing)
                return existing
            obj = PosteSource(code=code, libelle=ps_text[:200], is_active=True)
            self.session.add(obj)
            self.session.flush()
            ps_id = obj.id
            self._ps_codes[code] = ps_id
            key = text_key(ps_text)
            if key:
                self.id_maps.put("postes_sources_by_text", key, ps_id)
            return ps_id
        return 1

    def run(self) -> dict[str, Any]:
        self._load_postes_sources()
        self._load_feeders()
        self._load_postes()
        self._load_troncons()
        self._load_sous_feeders()
        self._load_equipements_transport()
        self._load_postes_lignes()
        for entity in (
            "postes_sources",
            "postes_sources_by_text",
            "feeders",
            "feeders_by_text",
            "postes",
            "postes_by_text",
            "troncons",
            "sous_feeders",
            "equipements_transport",
            "postes_lignes",
        ):
            self.id_maps.save(entity)
        return self.summary()

    def _load_postes_sources(self) -> None:
        for row in load_table_rows("PostesSources"):
            legacy_id = row_get(row, "IDPosteSource", "IDPostesSources", "idpostesource")
            libelle = str(row_get(row, "PosteSource", "Poste", "postesource") or "").strip()
            if not libelle:
                self.log_reject(legacy_id, "poste_source_vide", row)
                continue
            code = slug_code(libelle)
            region_id = self.id_maps.get(
                "regions_by_text", text_key(str(row_get(row, "Region", "region") or ""))
            )
            if self.id_maps.get("postes_sources", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                self.stats["inserted"] += 1
                continue
            if code in self._ps_codes:
                new_id = self._ps_codes[code]
            else:
                existing = self.session.execute(
                    select(PosteSource.id).where(PosteSource.code == code)
                ).scalar_one_or_none()
                if existing:
                    new_id = existing
                else:
                    obj = PosteSource(
                        code=code,
                        libelle=libelle[:200],
                        region_id=region_id,
                        is_active=True,
                    )
                    self.session.add(obj)
                    self.session.flush()
                    new_id = obj.id
                self._ps_codes[code] = new_id
            self.id_maps.put("postes_sources", legacy_id, new_id)
            key = text_key(libelle)
            if key:
                self.id_maps.put("postes_sources_by_text", key, new_id)
            self.stats["inserted"] += 1

    def _load_feeders(self) -> None:
        if not self.dry_run and not self._feeder_codes:
            for row in self.session.execute(select(Feeder.id, Feeder.code)):
                self._feeder_codes[row.code] = row.id
        for row in load_table_rows("Feeders"):
            legacy_id = self._feeder_legacy_id(row)
            libelle = str(row_get(row, "Feeder", "feeder") or "").strip()
            if not legacy_id:
                self.log_reject(row_get(row, "IDFeeder", "idfeeder"), "feeder_vide", row)
                continue
            ps_id = self._resolve_poste_source_id(row)
            if ps_id is None:
                self.log_reject(legacy_id, "poste_source_introuvable", row)
                continue
            service_id = self.fk.service_id(str(row_get(row, "Service", "service") or ""))
            code = slug_code(libelle)
            if code in self._feeder_codes:
                new_id = self._feeder_codes[code]
                self.id_maps.put("feeders", legacy_id, new_id)
                key = text_key(libelle)
                if key:
                    self.id_maps.put("feeders_by_text", key, new_id)
                self.stats["skipped"] += 1
                continue
            if self.id_maps.get("feeders", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                self.stats["inserted"] += 1
                continue
            # Code unique en base — suffixe si collision libellé
            insert_code = code
            if self.session.execute(
                select(Feeder.id).where(Feeder.code == insert_code)
            ).scalar_one_or_none():
                insert_code = slug_code(f"{libelle}_{legacy_id}", max_len=20)
            obj = Feeder(
                poste_source_id=ps_id,
                service_id=service_id,
                code=insert_code,
                libelle=libelle[:200],
                tension_kv=row_get(row, "TensionPrimaire", "tensionprimaire"),
                is_active=True,
            )
            self.session.add(obj)
            self.session.flush()
            new_id = obj.id
            self._feeder_codes[code] = new_id
            self.id_maps.put("feeders", legacy_id, new_id)
            key = text_key(libelle)
            if key:
                self.id_maps.put("feeders_by_text", key, new_id)
            self.stats["inserted"] += 1

    def _load_postes(self) -> None:
        for row in load_table_rows("Postes"):
            legacy_id = row_get(row, "IDPostes", "idpostes")
            libelle = str(
                row_get(row, "Poste", "poste", "NomPoste", "nomposte") or ""
            ).strip()
            if not libelle:
                self.log_reject(legacy_id, "poste_vide", row)
                continue
            code = slug_code(str(legacy_id), prefix="P")
            if self.id_maps.get("postes", legacy_id):
                self.stats["skipped"] += 1
                continue
            feeder_id = self.fk.resolve_feeder_id(row)
            service_id = self.fk.service_id_by_legacy(
                row_get(row, "ID_Service", "id_service", "IDService", "idservice")
            )
            if service_id is None:
                service_id = self.fk.service_id(str(row_get(row, "Service", "service") or ""))
            puissance = row_get(row, "puissanceTransfo", "puissancetransfo")
            try:
                puissance_kva = float(puissance) if puissance not in (None, "") else None
            except (TypeError, ValueError):
                puissance_kva = None
            if self.dry_run:
                new_id = len(self.id_maps.load("postes")) + 1
            else:
                obj = Poste(
                    feeder_id=feeder_id,
                    service_id=service_id,
                    code=code,
                    libelle=libelle[:200],
                    puissance_kva=puissance_kva,
                    nombre_clients=None,
                    is_active=True,
                )
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("postes", legacy_id, new_id)
            key = text_key(libelle)
            if key:
                self.id_maps.put("postes_by_text", key, new_id)
            self.stats["inserted"] += 1

    def _load_troncons(self) -> None:
        for row in load_table_rows("Troncon"):
            legacy_id = row_get(row, "IDTroncon", "idtroncon")
            libelle = str(row_get(row, "Libelle_Troncon", "libelle_troncon") or legacy_id or "").strip()
            if not libelle:
                self.log_reject(legacy_id, "troncon_vide", row)
                continue
            feeder_id = self.fk.feeder_id_by_legacy(row_get(row, "IDFeeder", "idfeeder"))
            try:
                legacy_num = int(legacy_id)
                code = f"TR{legacy_num:05d}"[:20]
            except (TypeError, ValueError):
                code = slug_code(libelle, prefix="TR")
            if self.id_maps.get("troncons", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("troncons")) + 1
            else:
                obj = Troncon(
                    feeder_id=feeder_id,
                    code=code,
                    libelle=libelle[:200],
                    is_active=True,
                )
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("troncons", legacy_id, new_id)
            self.stats["inserted"] += 1

    def _load_sous_feeders(self) -> None:
        """Table HFSQL SousFeeder (Libelle_SousFeeder + IDFeeder)."""
        for row in load_table_rows("SousFeeder"):
            legacy_id = row_get(row, "IDSousFeeder", "idsousfeeder")
            libelle = str(
                row_get(
                    row,
                    "Libelle_SousFeeder",
                    "libelle_sousfeeder",
                    "SousFeeder",
                    "sousfeeder",
                )
                or ""
            ).strip()
            if not libelle:
                libelle = str(
                    row_get(row, "Libelle_Feeder_SousFeeder", "libelle_feeder_sousfeeder") or ""
                ).strip()
            if not libelle or legacy_id is None:
                self.log_reject(legacy_id, "sous_feeder_vide", row)
                continue
            code = f"SF{int(legacy_id)}"[:20]
            feeder_id = self.fk.feeder_id_by_legacy(
                row_get(row, "IDFeeder", "idfeeder", "id_feeder")
            )
            if feeder_id is None:
                feeder_id = self.fk.feeder_id(
                    str(row_get(row, "Libelle_Feeder_SousFeeder", "Feeder", "feeder") or "")
                )
            if feeder_id is None:
                self.log_reject(legacy_id, "feeder_introuvable", row)
                continue
            if self.id_maps.get("sous_feeders", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("sous_feeders")) + 1
            else:
                existing = self.session.execute(
                    select(SousFeeder.id).where(SousFeeder.code == code)
                ).scalar_one_or_none()
                if existing:
                    new_id = int(existing)
                    self.stats["skipped"] += 1
                    self.id_maps.put("sous_feeders", legacy_id, new_id)
                    continue
                obj = SousFeeder(
                    feeder_id=feeder_id,
                    code=code,
                    libelle=libelle[:200],
                    is_active=True,
                )
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("sous_feeders", legacy_id, new_id)
            self.stats["inserted"] += 1

    def _load_equipements_transport(self) -> None:
        for row in load_table_rows("EquipementsTransport"):
            legacy_id = row_get(
                row, "IDEquipementTransport", "idequipements", "idsourceequipement"
            )
            if legacy_id is None:
                self.log_reject(None, "equipement_sans_id", row)
                continue
            libelle = str(
                row_get(row, "Equipement", "nomequipement", "Ligne", "ligne") or legacy_id or ""
            ).strip()
            type_raw = row_get(row, "TypeEquipement", "idtypeequipement", "typeequipement")
            type_equipement = str(type_raw)[:50] if type_raw is not None else "LIGNE"
            code = slug_code(str(legacy_id), prefix="EQ")
            if self.id_maps.get("equipements_transport", legacy_id):
                self.stats["skipped"] += 1
                continue
            if code in self._eq_codes:
                new_id = self._eq_codes[code]
            elif self.dry_run:
                new_id = len(self.id_maps.load("equipements_transport")) + 1
            else:
                obj = EquipementTransport(
                    code=code,
                    libelle=libelle[:200],
                    type_equipement=type_equipement,
                    is_active=True,
                )
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
                self._eq_codes[code] = new_id
            if code not in self._eq_codes:
                self._eq_codes[code] = new_id
            self.id_maps.put("equipements_transport", legacy_id, new_id)
            self.stats["inserted"] += 1

    def _load_postes_lignes(self) -> None:
        for row in load_table_rows("PosteLigne"):
            ps_id = self.id_maps.get(
                "postes_sources", row_get(row, "IDPosteSource", "idpostesource")
            )
            eq_id = self.id_maps.get(
                "equipements_transport",
                row_get(row, "IDEquipementTransport", "idequipements", "idsourceequipement"),
            )
            if ps_id is None or eq_id is None:
                self.log_reject(row.get("IDPosteLigne"), "fk_poste_ligne", row)
                continue
            if self.dry_run:
                self.stats["inserted"] += 1
                continue
            obj = PosteLigne(
                poste_source_id=ps_id,
                equipement_transport_id=eq_id,
                is_active=True,
            )
            self.session.add(obj)
            self.stats["inserted"] += 1
