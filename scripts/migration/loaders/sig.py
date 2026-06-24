"""Loader — topologie SIG (Noeud_SIG, Troncon_SIG)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.models.sig import NoeudSig, TronconSig

from scripts.migration.hfsql_odbc import iter_table_rows
from scripts.migration.loaders.base import BaseLoader
from scripts.migration.transforms.codes import text_key
from scripts.migration.transforms.dates import parse_datetime
from scripts.migration.transforms.rows import row_get

TRONCON_SIG_BATCH_SIZE = 50_000


class SigLoader(BaseLoader):
    entity_name = "sig"

    def _resolve_feeder_id(self, nom_feeder: str | None) -> int | None:
        if not nom_feeder:
            return None
        key = text_key(nom_feeder)
        if not key:
            return None
        feeder_id = self.id_maps.lookup_text("feeders_by_text", key)
        if feeder_id is not None:
            return int(feeder_id)
        return None

    def load_noeuds_sig(self) -> None:
        existing_legacy: set[int] = set()
        if not self.dry_run:
            existing_legacy = set(
                self.session.execute(select(NoeudSig.legacy_id)).scalars().all()
            )
        batch: list[tuple[int, NoeudSig]] = []

        def _flush_noeud_batch() -> None:
            if not batch or self.dry_run:
                batch.clear()
                return
            self.session.flush()
            for legacy_id, entity in batch:
                self.id_maps.put("noeuds_sig", legacy_id, entity.id)
            self.session.commit()
            batch.clear()

        for row in iter_table_rows("Noeud_SIG", allow_live=True):
            legacy_id = row_get(row, "IDNoeud_SIG", "idnoeud_sig")
            legacy_fid = row_get(row, "FID", "fid")
            if legacy_id is None or legacy_fid is None:
                continue
            lid = int(legacy_id)
            nom_feeder = row_get(row, "NOMFEEDER", "nomfeeder")
            entity = NoeudSig(
                legacy_id=lid,
                legacy_fid=int(legacy_fid),
                nom=row_get(row, "NOM", "nom"),
                nom_feeder=nom_feeder,
                feeder_id=self._resolve_feeder_id(str(nom_feeder) if nom_feeder else None),
                station=row_get(row, "SSTATION", "sstation"),
                coord_x=_float_or_none(row_get(row, "CORX", "corx")),
                coord_y=_float_or_none(row_get(row, "CORY", "cory")),
                categorie=row_get(row, "CATEGORIE", "categorie"),
            )
            if self.dry_run:
                self.stats["noeuds_sig"] = self.stats.get("noeuds_sig", 0) + 1
                continue
            if lid in existing_legacy:
                continue
            self.session.add(entity)
            batch.append((lid, entity))
            existing_legacy.add(lid)
            self.stats["noeuds_sig"] = self.stats.get("noeuds_sig", 0) + 1
            self.stats["inserted"] += 1
            if len(batch) >= TRONCON_SIG_BATCH_SIZE:
                _flush_noeud_batch()

        _flush_noeud_batch()
        if not self.dry_run and self.stats.get("noeuds_sig"):
            print(f"  … noeuds_sig terminé ({self.stats.get('noeuds_sig', 0)} lignes)", flush=True)

    def load_troncons_sig(self) -> None:
        latest_by_legacy: dict[int, tuple[datetime | None, dict[str, Any]]] = {}
        for row in iter_table_rows("Troncon_SIG", allow_live=True):
            legacy_id = row_get(row, "ID_Troncon_SIG", "id_troncon_sig")
            if legacy_id is None:
                continue
            lid = int(legacy_id)
            date_chargement = parse_datetime(row_get(row, "Date_Chargement", "date_chargement"))
            prev = latest_by_legacy.get(lid)
            if prev is not None:
                prev_dt = prev[0]
                if prev_dt is not None and date_chargement is not None and date_chargement <= prev_dt:
                    continue
            latest_by_legacy[lid] = (date_chargement, row)

        total = len(latest_by_legacy)
        batch: list[tuple[int, TronconSig]] = []
        existing_legacy: set[int] = set()
        if not self.dry_run:
            existing_legacy = set(
                self.session.execute(select(TronconSig.legacy_id)).scalars().all()
            )
            print(
                f"  … troncons_sig : {total} à traiter, {len(existing_legacy)} déjà en base",
                flush=True,
            )

        def _flush_troncon_batch() -> None:
            if not batch or self.dry_run:
                batch.clear()
                return
            self.session.flush()
            for legacy_id, entity in batch:
                self.id_maps.put("troncons_sig", legacy_id, entity.id)
            self.session.commit()
            batch.clear()

        for idx, (lid, (_, row)) in enumerate(latest_by_legacy.items(), start=1):
            nom_feeder = row_get(row, "NOMFEEDER", "nomfeeder")
            entity = TronconSig(
                legacy_id=lid,
                legacy_fid=_int_or_none(row_get(row, "FID", "fid")),
                nom_feeder=nom_feeder,
                feeder_id=self._resolve_feeder_id(str(nom_feeder) if nom_feeder else None),
                nom_troncon=row_get(row, "NomTroncon", "nomtroncon"),
                nom_noeud_amont=row_get(row, "NOMNAMONT", "nomnamont"),
                code_noeud_amont=row_get(row, "CODAMONT", "codamont"),
                nom_noeud_aval=row_get(row, "NOMNAVAL", "nomnaval"),
                code_noeud_aval=row_get(row, "CODAVAL", "codaval"),
                tension_kv=_float_or_none(row_get(row, "NTENSION", "ntension")),
                longueur_m=_float_or_none(row_get(row, "Shape_Leng", "shape_leng")),
                date_chargement=parse_datetime(row_get(row, "Date_Chargement", "date_chargement")),
            )
            if self.dry_run:
                self.stats["troncons_sig"] = self.stats.get("troncons_sig", 0) + 1
                continue
            if lid in existing_legacy:
                continue
            self.session.add(entity)
            batch.append((lid, entity))
            existing_legacy.add(lid)
            self.stats["troncons_sig"] = self.stats.get("troncons_sig", 0) + 1
            self.stats["inserted"] += 1

            if len(batch) >= TRONCON_SIG_BATCH_SIZE:
                _flush_troncon_batch()
                print(f"  … troncons_sig {idx}/{total} lignes traitées", flush=True)

        _flush_troncon_batch()
        if not self.dry_run and total:
            print(f"  … troncons_sig terminé ({total} legacy uniques)", flush=True)

    def run(self) -> None:
        self.load_noeuds_sig()
        self.load_troncons_sig()


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        iv = int(value)
        return iv if iv > 0 else None
    except (TypeError, ValueError):
        return None
