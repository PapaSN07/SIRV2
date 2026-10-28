"""Loader vague 6 — indicateurs SAIFI/SAIDI et nombre clients."""

from __future__ import annotations

from typing import Any

from app.models.indicateurs import NombreClientMois, SaifiSaidi

from scripts.migration.hfsql_odbc import load_table_rows
from scripts.migration.loaders.base import BaseLoader
from scripts.migration.transforms.fk_resolver import FkResolver
from scripts.migration.transforms.rows import row_get


# Agrégats régionaux HFSQL (id_service toujours 0) → service représentatif
_REGION_SERVICE_LEGACY: dict[str, str] = {
    "15": "1",  # Dakar → DD
    "16": "4",  # Régions → BRC
}


class IndicateursLoader(BaseLoader):
    entity_name = "indicateurs"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fk = FkResolver(self.id_maps)

    def run(self) -> dict[str, Any]:
        self._load_saifi_saidi()
        self._load_nombre_client_mois()
        return self.summary()

    def _resolve_service_id(self, row: dict) -> int | None:
        legacy_svc = row_get(row, "id_service", "ID_Service", "IDAUTO")
        try:
            if legacy_svc is not None and int(legacy_svc) > 0:
                return self.id_maps.get("services", legacy_svc)
        except (TypeError, ValueError):
            pass
        region_legacy = row_get(row, "idregions", "IDRegions", "idregions")
        if region_legacy is not None:
            svc_legacy = _REGION_SERVICE_LEGACY.get(str(region_legacy))
            if svc_legacy:
                sid = self.id_maps.get("services", svc_legacy)
                if sid:
                    return sid
        return self.fk.service_id(str(row_get(row, "Service", "service") or ""))

    def _parse_mois(self, row: dict) -> int:
        # MoisNumerique d'abord : « Mois » peut être le libellé (« Janvier »)
        raw = row_get(row, "MoisNumerique", "MoisNum", "Mois")
        if raw is None:
            return 0
        try:
            return int(str(raw).strip())
        except ValueError:
            return 0

    def _load_saifi_saidi(self) -> None:
        for row in load_table_rows("SAIFISAIDI"):
            service_id = self._resolve_service_id(row)
            if service_id is None:
                self.log_reject(row_get(row, "IDSAIFISAIDI"), "service_introuvable", row)
                continue
            annee = int(row_get(row, "Annee", "annee") or 0)
            mois = self._parse_mois(row)
            if not annee or not (1 <= mois <= 12):
                self.log_reject(row_get(row, "IDSAIFISAIDI"), "periode_invalide", row)
                continue
            if self.dry_run:
                self.stats["inserted"] += 1
                continue
            obj = SaifiSaidi(
                service_id=service_id,
                annee=annee,
                mois=mois,
                saifi=float(row_get(row, "SAIFI", "saifi") or 0),
                saidi=float(row_get(row, "SAIDI", "saidi") or 0),
                nombre_interruptions=int(row_get(row, "NombreInterruptions", "nombreinterruptions") or 0),
                total_clients_reference=int(
                    row_get(row, "NombreClient", "nombreclient", "NbClient", "nbclient") or 0
                ),
            )
            self.session.add(obj)
            self.stats["inserted"] += 1

    def _load_nombre_client_mois(self) -> None:
        agg: dict[tuple[int, int, int], dict[str, float | int]] = {}
        for row in load_table_rows("NombreClientMois"):
            service_id = self._resolve_service_id(row)
            if service_id is None:
                self.log_reject(row_get(row, "IDNombreClientMois", "idclientannee"), "service_introuvable", row)
                continue
            annee = int(row_get(row, "Annee", "annee") or 0)
            mois = self._parse_mois(row)
            if not annee or not (1 <= mois <= 12):
                self.log_reject(row_get(row, "IDNombreClientMois", "idclientannee"), "periode_invalide", row)
                continue
            key = (service_id, annee, mois)
            bucket = agg.setdefault(
                key,
                {"nombre_clients": 0, "saifi": 0.0, "saidi": 0.0, "rows": 0},
            )
            nb = int(row_get(row, "NombreClient", "nombreclient") or 0)
            # Somme, comme la mesure Power BI SENELEC (SUM(NombreClientMois[Nombreclient]))
            bucket["nombre_clients"] = int(bucket["nombre_clients"]) + nb
            saifi = float(row_get(row, "SAIFI", "saifi") or 0)
            saidi = float(row_get(row, "SAIDI", "saidi") or 0)
            if saifi or saidi:
                bucket["saifi"] = float(bucket["saifi"]) + saifi
                bucket["saidi"] = float(bucket["saidi"]) + saidi
                bucket["rows"] = int(bucket["rows"]) + 1

        if self.dry_run:
            self.stats["inserted"] += len(agg) * 2
            return

        for (service_id, annee, mois), bucket in agg.items():
            self.session.add(
                NombreClientMois(
                    service_id=service_id,
                    annee=annee,
                    mois=mois,
                    nombre_clients=int(bucket["nombre_clients"]),
                )
            )
            self.stats["inserted"] += 1
            if bucket["saifi"] or bucket["saidi"]:
                rows_n = int(bucket["rows"]) or 1
                self.session.add(
                    SaifiSaidi(
                        service_id=service_id,
                        annee=annee,
                        mois=mois,
                        saifi=float(bucket["saifi"]) / rows_n,
                        saidi=float(bucket["saidi"]) / rows_n,
                        nombre_interruptions=0,
                        total_clients_reference=int(bucket["nombre_clients"]),
                    )
                )
                self.stats["inserted"] += 1
            elif int(bucket["nombre_clients"]) > 0:
                self.session.add(
                    SaifiSaidi(
                        service_id=service_id,
                        annee=annee,
                        mois=mois,
                        saifi=0.0,
                        saidi=0.0,
                        nombre_interruptions=0,
                        total_clients_reference=int(bucket["nombre_clients"]),
                    )
                )
                self.stats["inserted"] += 1
