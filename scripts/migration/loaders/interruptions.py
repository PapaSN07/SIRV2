"""Loader vague 5 — interruptions unifiées."""

from __future__ import annotations

from typing import Any

from app.models.indicateurs import EnergieNd
from app.models.interruptions import (
    Interruption,
    InterruptionDistribution,
    InterruptionTransport,
    PosteInterruption,
)

from scripts.migration.config import get_settings
from scripts.migration.interruption_filter import interruption_date_window, should_include_interruption
from scripts.migration.hfsql_odbc import (
    export_is_pre_filtered,
    fetch_poste_interruptions_live,
    iter_table_rows,
    load_table_rows,
)
from scripts.migration.loaders.base import BaseLoader
from scripts.migration.transforms.dates import (
    duree_minutes_interruption,
    resolve_interruption_date_apparition,
    resolve_interruption_date_remise,
)
from scripts.migration.transforms.fk_resolver import FkResolver
from scripts.migration.transforms.rows import row_get
from scripts.migration.transforms.statut import map_statut

INTERRUPTION_SOURCES: list[tuple[str, str, bool]] = [
    ("Interruptions", "distribution", False),
    ("Interruptions_Histo", "distribution", True),
    ("InterruptionsTransport", "transport", False),
    ("Interruptions_OMVG", "omvg", False),
]

CLOSED_STATUTS = {"cloture", "valide", "archive"}
_MAX_INT = 2_147_483_647
_FK_FIELDS = (
    "service_id",
    "feeder_id",
    "sous_feeder_id",
    "poste_source_id",
    "cause_id",
    "nature_id",
    "siege_id",
    "signalisation_id",
)
_FK_TABLE_BY_FIELD: dict[str, str] = {
    "service_id": "services",
    "feeder_id": "feeders",
    "sous_feeder_id": "sous_feeders",
    "poste_source_id": "postes_sources",
    "cause_id": "causes",
    "nature_id": "natures",
    "siege_id": "sieges",
    "signalisation_id": "signalisations",
}


def _safe_numero_interruption(row: dict, legacy_id: Any) -> int:
    for field in ("NumeroInterruption", "Num", "num", "numerointerruption"):
        raw = row_get(row, field)
        if raw is not None and raw != "":
            try:
                n = int(raw)
                if 0 < n <= _MAX_INT:
                    return n
            except (TypeError, ValueError):
                continue
    try:
        lid = int(legacy_id)
        if 0 < lid <= _MAX_INT:
            return lid
    except (TypeError, ValueError):
        pass
    return abs(hash(str(legacy_id))) % 2_000_000_000 or 1


class InterruptionsLoader(BaseLoader):
    entity_name = "interruptions"

    def __init__(
        self,
        *args,
        system_user_id: int = 1,
        sync_existing: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fk = FkResolver(self.id_maps)
        self.system_user_id = system_user_id
        self.sync_existing = sync_existing
        settings = get_settings()
        self.date_from, self.date_to = interruption_date_window(settings)
        self._valid_fk_ids: dict[str, set[int]] | None = None
        if sync_existing:
            self.stats["updated"] = 0

    def _ensure_valid_fk_cache(self) -> None:
        if self._valid_fk_ids is not None:
            return
        from sqlalchemy import text

        valid: dict[str, set[int]] = {}
        for field, table in _FK_TABLE_BY_FIELD.items():
            rows = self.session.execute(text(f"SELECT id FROM dbo.{table}")).all()
            valid[field] = {int(r[0]) for r in rows}
        self._valid_fk_ids = valid

    def _sanitize_fk_fields(self, fields: dict[str, Any]) -> None:
        """Insert : annule les FK invalides (id_maps obsolètes)."""
        if self.dry_run:
            return
        self._ensure_valid_fk_cache()
        assert self._valid_fk_ids is not None
        for field in _FK_FIELDS:
            value = fields.get(field)
            if value is not None and int(value) not in self._valid_fk_ids[field]:
                fields[field] = None

    def _apply_field_updates(self, interruption: Interruption, fields: dict[str, Any]) -> None:
        """Applique les champs résolus ; conserve les FK existantes si résolution invalide."""
        self._ensure_valid_fk_cache()
        assert self._valid_fk_ids is not None
        scalar_keys = (
            "numero_interruption",
            "statut",
            "date_apparition",
            "date_remise",
            "duree_minutes",
            "is_force_majeure",
            "is_fugitive",
            "nombre_clients_touches",
            "puissance_coupee_mw",
            "localisation",
            "observations",
        )
        for key in scalar_keys:
            setattr(interruption, key, fields[key])
        for field in _FK_FIELDS:
            value = fields.get(field)
            if value is None:
                continue
            if int(value) in self._valid_fk_ids[field]:
                setattr(interruption, field, int(value))

    def run(self) -> dict[str, Any]:
        for table, type_direction, is_histo in INTERRUPTION_SOURCES:
            self._load_interruptions_table(table, type_direction, is_histo)
        if get_settings().migration_load_poste_interruptions:
            self._load_poste_interruptions()
        self._load_energie_nd()
        for entity in ("interruptions", "poste_interruptions", "energie_nd"):
            if not self.dry_run:
                self.id_maps.save(entity)
        return self.summary()

    def _include_row(self, row: dict, is_histo: bool) -> bool:
        return should_include_interruption(
            row, self.date_from, self.date_to, is_histo=is_histo
        )

    def _service_id_from_feeder(self, feeder_id: int) -> int | None:
        from sqlalchemy import select

        from app.models.reseau import Feeder

        return self.session.execute(
            select(Feeder.service_id).where(Feeder.id == feeder_id)
        ).scalar_one_or_none()

    def _resolve_row_fields(
        self, row: dict, *, type_direction: str, is_histo: bool, legacy_id: Any
    ) -> dict[str, Any] | None:
        date_app = resolve_interruption_date_apparition(row)
        if date_app is None:
            return None
        type_reseau = "transport" if type_direction in ("transport", "omvg") else "distribution"
        date_remise = resolve_interruption_date_remise(row)
        statut = map_statut(
            row_get(row, "EtatTraitement"),
            row_get(row, "Validation", "indicateurvalidation"),
            is_histo,
        )
        puissance = row_get(row, "PuissanceCoupee", "puissancecoupee")
        service_id = self.fk.resolve_service_id(row)
        feeder_id = self.fk.resolve_feeder_id(row)
        if service_id is None and feeder_id is not None:
            service_id = self._service_id_from_feeder(feeder_id)
        return {
            "numero_interruption": _safe_numero_interruption(row, legacy_id),
            "type_direction": type_direction,
            "statut": statut,
            "service_id": service_id,
            "feeder_id": feeder_id,
            "sous_feeder_id": self.fk.sous_feeder_id_by_legacy(
                row_get(row, "idsousfeeder", "IDSousFeeder", "id_sous_feeder")
            ),
            "poste_source_id": self.fk.poste_source_id(
                str(row_get(row, "PosteSource", "postesource") or "")
            ),
            "date_apparition": date_app,
            "date_remise": date_remise,
            "duree_minutes": duree_minutes_interruption(
                row_get(row, "dureeHeure", "dureeheure"), date_app, date_remise
            ),
            "cause_id": self.fk.resolve_cause_id(row, type_reseau),
            "siege_id": self.fk.resolve_siege_id(row, type_reseau),
            "signalisation_id": self.fk.resolve_signalisation_id(row, type_reseau),
            "nature_id": self.fk.resolve_nature_id(row),
            "is_force_majeure": bool(row_get(row, "casforcemajeur")),
            "is_fugitive": bool(row_get(row, "Fugitif", "fugitif")),
            "nombre_clients_touches": row_get(
                row, "Nombreclientimpacte", "nombreclientimpacte"
            ),
            "puissance_coupee_mw": float(puissance or 0) * 0.001
            if puissance is not None
            else None,
            "localisation": str(row_get(row, "NomTroncon", "nomtroncon") or "")[:500] or None,
            "observations": str(row_get(row, "Observation", "observation") or "")[:2000]
            or None,
            "distribution": {
                "tension_kv": row_get(row, "TensionPrimaire", "tensionprimaire"),
                "end_mwh": row_get(row, "ENDD", "endd"),
                "is_programme": bool(
                    row_get(row, "Délestage", "Delestage", "delestage", "délestage")
                ),
            },
            "transport": {
                "tension_kv": row_get(row, "TensionPrimaire", "tensionprimaire"),
                "energie_non_fournie_mwh": row_get(row, "ENDD", "endd"),
            },
        }

    def _update_interruption_from_row(
        self,
        sir_id: int,
        row: dict,
        *,
        type_direction: str,
        is_histo: bool,
        legacy_id: Any,
    ) -> bool:
        fields = self._resolve_row_fields(
            row, type_direction=type_direction, is_histo=is_histo, legacy_id=legacy_id
        )
        if fields is None:
            self.log_reject(legacy_id, "date_apparition_manquante", row)
            return False
        interruption = self.session.get(Interruption, sir_id)
        if interruption is None:
            self.log_reject(legacy_id, "sir_id_introuvable", row)
            return False
        if self.dry_run:
            self.stats["updated"] += 1
            return True
        self._apply_field_updates(interruption, fields)
        if type_direction == "distribution":
            dist = interruption.interruption_distribution
            if dist is None:
                dist = InterruptionDistribution(interruption_id=sir_id)
                self.session.add(dist)
            dist.tension_kv = fields["distribution"]["tension_kv"]
            dist.end_mwh = fields["distribution"]["end_mwh"]
            dist.is_programme = fields["distribution"]["is_programme"]
        else:
            transport = interruption.interruption_transport
            if transport is None:
                transport = InterruptionTransport(interruption_id=sir_id)
                self.session.add(transport)
            transport.tension_kv = fields["transport"]["tension_kv"]
            transport.energie_non_fournie_mwh = fields["transport"]["energie_non_fournie_mwh"]
        self.stats["updated"] += 1
        if self.stats["updated"] % self.batch_size == 0:
            self.flush_batch()
        return True

    def _load_interruptions_table(
        self, table: str, type_direction: str, is_histo: bool
    ) -> None:
        type_reseau = "transport" if type_direction in ("transport", "omvg") else "distribution"
        pre_filtered = export_is_pre_filtered(table)
        for row in iter_table_rows(table):
            legacy_id = row_get(row, "NInterruption", "ninterruption")
            if not pre_filtered and not self._include_row(row, is_histo):
                self.stats["skipped"] += 1
                continue
            existing_id = self.id_maps.get("interruptions", legacy_id)
            if existing_id is not None:
                if self.sync_existing:
                    self._update_interruption_from_row(
                        int(existing_id),
                        row,
                        type_direction=type_direction,
                        is_histo=is_histo,
                        legacy_id=legacy_id,
                    )
                else:
                    self.stats["skipped"] += 1
                continue
            fields = self._resolve_row_fields(
                row, type_direction=type_direction, is_histo=is_histo, legacy_id=legacy_id
            )
            if fields is None:
                self.log_reject(legacy_id, "date_apparition_manquante", row)
                continue
            self._sanitize_fk_fields(fields)
            created_by = (
                self.fk.utilisateur_id(str(row_get(row, "Login", "login") or ""))
                or self.system_user_id
            )
            if self.dry_run:
                self.stats["inserted"] += 1
                if self.stats["inserted"] % self.batch_size == 0:
                    self.flush_batch()
                continue
            interruption = Interruption(
                created_by_id=created_by,
                **{k: v for k, v in fields.items() if k not in ("distribution", "transport")},
            )
            self.session.add(interruption)
            self.session.flush()
            new_id = interruption.id
            if type_direction == "distribution":
                self.session.add(
                    InterruptionDistribution(
                        interruption_id=new_id,
                        **fields["distribution"],
                    )
                )
            else:
                self.session.add(
                    InterruptionTransport(
                        interruption_id=new_id,
                        **fields["transport"],
                    )
                )
            self.id_maps.put("interruptions", legacy_id, new_id)
            self.stats["inserted"] += 1
            if self.stats["inserted"] % self.batch_size == 0:
                self.flush_batch()

    def _load_poste_interruptions(self) -> None:
        legacy_ids = [
            int(k) for k in self.id_maps.load("interruptions").keys() if str(k).isdigit()
        ]
        if not legacy_ids:
            return
        for table in ("PosteInterruption", "PosteInterruption_Histo"):
            rows = fetch_poste_interruptions_live(table, legacy_ids)
            for row in rows:
                inter_id = self.fk.interruption_id(row_get(row, "NInterruption", "ninterruption"))
                poste_id = self.fk.poste_id_by_legacy(
                    row_get(row, "IDPostes", "idpostes", "IDPoste", "idposte")
                )
                if poste_id is None:
                    poste_id = self.fk.poste_id(
                        str(
                            row_get(
                                row,
                                "Poste",
                                "NomPoste",
                                "Posteconcerne",
                                "poste",
                                "nomposte",
                                "posteconcerne",
                            )
                            or ""
                        )
                    )
                if inter_id is None or poste_id is None:
                    self.log_reject(
                        row_get(row, "IDPosteInterruption"), "fk_poste_interruption", row
                    )
                    continue
                if self.dry_run:
                    self.stats["inserted"] += 1
                    continue
                inter = self.session.get(Interruption, inter_id)
                self.session.add(
                    PosteInterruption(
                        interruption_id=inter_id,
                        poste_id=poste_id,
                        nombre_clients_touches=row_get(
                            row, "Nombreclientimpacte", "nombreclientimpacte", "nombreclientposteestime"
                        ),
                        date_interruption=inter.date_apparition if inter else None,
                        feeder_id=inter.feeder_id if inter else None,
                        service_id=inter.service_id if inter else None,
                        poste_source_id=inter.poste_source_id if inter else None,
                    )
                )
                self.stats["inserted"] += 1

    def _load_energie_nd(self) -> None:
        for row in iter_table_rows("EnergieND"):
            inter_id = self.fk.interruption_id(row_get(row, "NInterruption", "ninterruption"))
            if inter_id is None:
                self.log_reject(row_get(row, "IDEnergieND"), "interruption_introuvable", row)
                continue
            end_val = float(row_get(row, "ENDD", "END", "endd", "end") or 0)
            if self.dry_run:
                self.stats["inserted"] += 1
                continue
            duree_inter = row_get(row, "DureeInterruption", "dureeinterruption")
            duree_heure = row_get(row, "dureeHeure", "dureeheure")
            self.session.add(
                EnergieNd(
                    interruption_id=inter_id,
                    type_end_id=self.id_maps.get("types_end", row_get(row, "IDTypeEND")),
                    valeur_mwh=end_val,
                    puissance_coupee_mw=float(row_get(row, "PuissanceCoupee", "puissancecoupee") or 0)
                    * 0.001,
                    duree_heures=float(duree_heure or 0) / 60
                    if duree_inter
                    else float(duree_heure or 1),
                    est_force_majeure=bool(row_get(row, "casforcemajeur")),
                )
            )
            self.stats["inserted"] += 1
