"""Loader vague 2 — référentiels unifiés."""

from __future__ import annotations

from typing import Any

from app.models.referentiel import Cause, Nature, Siege, Signalisation, TypeEnd

from scripts.migration.hfsql_odbc import load_table_rows
from scripts.migration.loaders.base import BaseLoader
from scripts.migration.transforms.codes import slug_code, text_key
from scripts.migration.transforms.rows import row_get


class ReferentielLoader(BaseLoader):
    entity_name = "referentiel"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._codes_seen: dict[str, int] = {}

    def run(self) -> dict[str, Any]:
        self._load_causes()
        self._load_sieges()
        self._load_signalisations()
        self._load_natures()
        self._load_types_end()
        for entity in (
            "causes",
            "causes_by_text",
            "sieges",
            "sieges_by_text",
            "signalisations",
            "signalisations_by_text",
            "natures",
            "natures_by_text",
            "types_end",
        ):
            self.id_maps.save(entity)
        return self.summary()

    def _load_causes(self) -> None:
        specs = [
            ("Causes", "distribution", "IDCauses"),
            ("CausesTransport", "transport", "IDCausesTrans"),
        ]
        for table, type_reseau, id_field in specs:
            for row in load_table_rows(table):
                legacy_id = row.get(id_field)
                libelle = str(row.get("cause") or "").strip()
                if not libelle:
                    self.log_reject(legacy_id, "cause_vide", row)
                    continue
                code = slug_code(libelle, prefix="D" if type_reseau == "distribution" else "T")
                composite = f"{type_reseau}:{text_key(libelle)}"
                code_key = f"{type_reseau}:{code}"
                if self.id_maps.get("causes", legacy_id):
                    self.stats["skipped"] += 1
                    continue
                if code_key in self._codes_seen:
                    new_id = self._codes_seen[code_key]
                elif self.dry_run:
                    new_id = len(self.id_maps.load("causes")) + 1
                else:
                    obj = Cause(
                        code=code,
                        libelle=libelle[:200],
                        type_reseau=type_reseau,
                        is_active=True,
                    )
                    self.session.add(obj)
                    self.session.flush()
                    new_id = obj.id
                    self._codes_seen[code_key] = new_id
                if code_key not in self._codes_seen:
                    self._codes_seen[code_key] = new_id
                self.id_maps.put("causes", legacy_id, new_id)
                self.id_maps.put("causes_by_text", composite, new_id)
                self.stats["inserted"] += 1

    def _load_sieges(self) -> None:
        specs = [
            ("Sieges", "distribution", "IDSieges", "Sieges"),
            ("SiegesTransport", "transport", "IDSieges", "Sieges"),
        ]
        for table, type_reseau, id_field, lib_field in specs:
            for row in load_table_rows(table):
                legacy_id = row.get(id_field)
                libelle = str(row.get(lib_field) or row.get("sigles") or "").strip()
                if not libelle:
                    self.log_reject(legacy_id, "siege_vide", row)
                    continue
                code = slug_code(str(row.get("sigles") or libelle), prefix="D" if type_reseau == "distribution" else "T")
                composite = f"{type_reseau}:{text_key(libelle)}"
                code_key = f"{type_reseau}:{code}"
                if self.id_maps.get("sieges", legacy_id):
                    self.stats["skipped"] += 1
                    continue
                if code_key in self._codes_seen:
                    new_id = self._codes_seen[code_key]
                elif self.dry_run:
                    new_id = len(self.id_maps.load("sieges")) + 1
                else:
                    obj = Siege(
                        code=code,
                        libelle=libelle[:200],
                        type_reseau=type_reseau,
                        is_active=True,
                    )
                    self.session.add(obj)
                    self.session.flush()
                    new_id = obj.id
                    self._codes_seen[code_key] = new_id
                if code_key not in self._codes_seen:
                    self._codes_seen[code_key] = new_id
                self.id_maps.put("sieges", legacy_id, new_id)
                self.id_maps.put("sieges_by_text", composite, new_id)
                self.stats["inserted"] += 1

    def _load_signalisations(self) -> None:
        specs = [
            ("Signalisations", "distribution", "IDSignalisation"),
            ("SignalisationsTransport", "transport", "IDSignalisation"),
        ]
        for table, type_reseau, id_field in specs:
            for row in load_table_rows(table):
                legacy_id = row.get(id_field)
                libelle = str(
                    row.get("Signalisation") or row.get("signalisation") or legacy_id or ""
                ).strip()
                if not libelle:
                    self.log_reject(legacy_id, "signalisation_vide", row)
                    continue
                code = slug_code(str(libelle), prefix="D" if type_reseau == "distribution" else "T")
                composite = f"{type_reseau}:{text_key(libelle)}"
                code_key = f"{type_reseau}:{code}"
                if self.id_maps.get("signalisations", legacy_id):
                    self.stats["skipped"] += 1
                    continue
                if code_key in self._codes_seen:
                    new_id = self._codes_seen[code_key]
                elif self.dry_run:
                    new_id = len(self.id_maps.load("signalisations")) + 1
                else:
                    obj = Signalisation(
                        code=code,
                        libelle=libelle[:200],
                        type_reseau=type_reseau,
                        is_active=True,
                    )
                    self.session.add(obj)
                    self.session.flush()
                    new_id = obj.id
                    self._codes_seen[code_key] = new_id
                if code_key not in self._codes_seen:
                    self._codes_seen[code_key] = new_id
                self.id_maps.put("signalisations", legacy_id, new_id)
                self.id_maps.put("signalisations_by_text", composite, new_id)
                self.stats["inserted"] += 1

    def _load_natures(self) -> None:
        for row in load_table_rows("Natures"):
            legacy_id = row_get(row, "IDNature", "idnature")
            libelle = str(
                row_get(row, "Nature", "naturepresumee", "NaturePresumee") or ""
            ).strip()
            if not libelle:
                self.log_reject(legacy_id, "nature_vide", row)
                continue
            code = slug_code(libelle)
            if self.id_maps.get("natures", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("natures")) + 1
            else:
                obj = Nature(code=code, libelle=libelle[:200], is_active=True)
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("natures", legacy_id, new_id)
            key = text_key(libelle)
            if key:
                self.id_maps.put("natures_by_text", key, new_id)
            self.stats["inserted"] += 1

    def _load_types_end(self) -> None:
        for row in load_table_rows("TypesEND"):
            legacy_id = row.get("IDTypeEND")
            libelle = str(row.get("TypeEND") or row.get("Type_END") or "").strip()
            if not libelle:
                self.log_reject(legacy_id, "type_end_vide", row)
                continue
            code = slug_code(libelle)
            if self.id_maps.get("types_end", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("types_end")) + 1
            else:
                obj = TypeEnd(code=code, libelle=libelle[:200], is_active=True)
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("types_end", legacy_id, new_id)
            self.stats["inserted"] += 1
