"""Résolution FK legacy ID et texte → id via IdMapStore."""

from __future__ import annotations

from typing import Any

from scripts.migration.id_maps import IdMapStore
from scripts.migration.transforms.codes import text_key
from scripts.migration.transforms.rows import row_get


def _positive_legacy(legacy_id: Any) -> int | None:
    if legacy_id is None or legacy_id == "":
        return None
    try:
        value = int(legacy_id)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


class FkResolver:
    def __init__(self, id_maps: IdMapStore) -> None:
        self.id_maps = id_maps

    def service_id(self, service_text: str | None) -> int | None:
        key = text_key(service_text)
        return self.id_maps.lookup_text("services_by_text", key) if key else None

    def service_id_by_legacy(self, legacy_id: Any) -> int | None:
        lid = _positive_legacy(legacy_id)
        return self.id_maps.get("services", lid) if lid is not None else None

    def feeder_id(self, feeder_text: str | None) -> int | None:
        key = text_key(feeder_text)
        return self.id_maps.lookup_text("feeders_by_text", key) if key else None

    def feeder_id_by_legacy(self, legacy_id: Any) -> int | None:
        lid = _positive_legacy(legacy_id)
        if lid is not None:
            mapped = self.id_maps.get("feeders", lid)
            if mapped is not None:
                return mapped
        return None

    def cause_id(self, cause_text: str | None, type_reseau: str = "distribution") -> int | None:
        key = text_key(cause_text)
        if not key:
            return None
        composite = f"{type_reseau}:{key}"
        return self.id_maps.get("causes_by_text", composite)

    def cause_id_by_legacy(self, legacy_id: Any, type_reseau: str = "distribution") -> int | None:
        lid = _positive_legacy(legacy_id)
        if lid is None:
            return None
        mapped = self.id_maps.get("causes", lid)
        if mapped is not None:
            return mapped
        if type_reseau == "transport":
            return self.id_maps.get("causes", f"trans_{lid}")
        return None

    def siege_id(self, siege_text: str | None, type_reseau: str = "distribution") -> int | None:
        key = text_key(siege_text)
        if not key:
            return None
        composite = f"{type_reseau}:{key}"
        return self.id_maps.get("sieges_by_text", composite)

    def siege_id_by_legacy(self, legacy_id: Any) -> int | None:
        lid = _positive_legacy(legacy_id)
        return self.id_maps.get("sieges", lid) if lid is not None else None

    def signalisation_id(
        self, sig_text: str | None, type_reseau: str = "distribution"
    ) -> int | None:
        key = text_key(sig_text)
        if not key:
            return None
        composite = f"{type_reseau}:{key}"
        return self.id_maps.get("signalisations_by_text", composite)

    def signalisation_id_by_legacy(self, legacy_id: Any) -> int | None:
        lid = _positive_legacy(legacy_id)
        return self.id_maps.get("signalisations", lid) if lid is not None else None

    def nature_id(self, nature_text: str | None) -> int | None:
        key = text_key(nature_text)
        return self.id_maps.lookup_text("natures_by_text", key) if key else None

    def nature_id_by_legacy(self, legacy_id: Any) -> int | None:
        lid = _positive_legacy(legacy_id)
        return self.id_maps.get("natures", lid) if lid is not None else None

    def poste_source_id(self, ps_text: str | None) -> int | None:
        key = text_key(ps_text)
        return self.id_maps.lookup_text("postes_sources_by_text", key) if key else None

    def poste_id(self, poste_text: str | None) -> int | None:
        key = text_key(poste_text)
        return self.id_maps.lookup_text("postes_by_text", key) if key else None

    def poste_id_by_legacy(self, legacy_id: Any) -> int | None:
        lid = _positive_legacy(legacy_id)
        return self.id_maps.get("postes", lid) if lid is not None else None

    def sous_feeder_id_by_legacy(self, legacy_id: Any) -> int | None:
        lid = _positive_legacy(legacy_id)
        return self.id_maps.get("sous_feeders", lid) if lid is not None else None

    def utilisateur_id(self, login: str | None) -> int | None:
        if not login:
            return None
        return self.id_maps.get("utilisateurs", login.strip().lower())

    def interruption_id(self, legacy_id: int | str | None) -> int | None:
        return self.id_maps.get("interruptions", legacy_id)

    def resolve_service_id(self, row: dict[str, Any]) -> int | None:
        resolved = self.service_id_by_legacy(
            row_get(row, "idservice", "IDService", "id_service")
        )
        if resolved is not None:
            return resolved
        return self.service_id(str(row_get(row, "Service", "service") or ""))

    def resolve_feeder_id(self, row: dict[str, Any]) -> int | None:
        resolved = self.feeder_id_by_legacy(
            row_get(row, "idfeeder", "IDFeeder", "id_feeder")
        )
        if resolved is not None:
            return resolved
        for field in ("Feeder", "Feeder1", "feeder", "feeder1", "feeder2"):
            text = str(row_get(row, field) or "").strip()
            if text:
                found = self.feeder_id(text)
                if found is not None:
                    return found
        return None

    def resolve_cause_id(
        self, row: dict[str, Any], type_reseau: str = "distribution"
    ) -> int | None:
        resolved = self.cause_id_by_legacy(
            row_get(row, "idcauses", "IDCauses", "id_causes"), type_reseau
        )
        if resolved is not None:
            return resolved
        for field in ("Cause", "cause", "causeeffective", "causepresumees"):
            text = str(row_get(row, field) or "").strip()
            if text:
                found = self.cause_id(text, type_reseau)
                if found is not None:
                    return found
        return None

    def resolve_siege_id(
        self, row: dict[str, Any], type_reseau: str = "distribution"
    ) -> int | None:
        resolved = self.siege_id_by_legacy(row_get(row, "idsieges", "IDSieges", "id_sieges"))
        if resolved is not None:
            return resolved
        return self.siege_id(str(row_get(row, "Sieges", "sieges") or ""), type_reseau)

    def resolve_signalisation_id(
        self, row: dict[str, Any], type_reseau: str = "distribution"
    ) -> int | None:
        resolved = self.signalisation_id_by_legacy(
            row_get(row, "idsignalisation", "IDSignalisation", "id_signalisation")
        )
        if resolved is not None:
            return resolved
        return self.signalisation_id(
            str(row_get(row, "Signalisation", "signalisation") or ""), type_reseau
        )

    def resolve_nature_id(self, row: dict[str, Any]) -> int | None:
        resolved = self.nature_id_by_legacy(row_get(row, "idnature", "IDNature", "id_nature"))
        if resolved is not None:
            return resolved
        for field in ("Nature", "nature", "naturepresumee", "NaturePresumee"):
            text = str(row_get(row, field) or "").strip()
            if text:
                found = self.nature_id(text)
                if found is not None:
                    return found
        return None
