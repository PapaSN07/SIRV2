"""Loader NAPT, consignations et destinataires."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.napt import Consignation, Napt
from app.models.notifications import Destinataire

from scripts.migration.hfsql_odbc import load_table_rows
from scripts.migration.loaders.base import BaseLoader
from scripts.migration.transforms.dates import merge_date_time, parse_datetime
from scripts.migration.transforms.fk_resolver import FkResolver


class NaptLoader(BaseLoader):
    entity_name = "napt"

    def __init__(self, *args, system_user_id: int = 1, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fk = FkResolver(self.id_maps)
        self.system_user_id = system_user_id

    def run(self) -> dict[str, Any]:
        self._load_napt()
        self._load_consignations()
        self._load_destinataires()
        self.id_maps.save("napt")
        return self.summary()

    def _load_napt(self) -> None:
        for row in load_table_rows("NAPT"):
            legacy_id = row.get("Num")
            numero = str(row.get("NAPT") or legacy_id or "").strip()
            if not numero:
                self.log_reject(legacy_id, "napt_vide", row)
                continue
            service_id = self.fk.service_id(str(row.get("exploitation") or row.get("Unite_demandeur") or ""))
            if service_id is None:
                self.log_reject(legacy_id, "service_introuvable", row)
                continue
            date_debut = merge_date_time(row.get("Debut_tvx"), row.get("Heure_debut"))
            date_fin = merge_date_time(row.get("Fin_napt"), row.get("Heure_fin"))
            if date_debut is None or date_fin is None:
                self.log_reject(legacy_id, "dates_napt_invalides", row)
                continue
            created_by = self.fk.utilisateur_id(str(row.get("SaisiePar") or "")) or self.system_user_id
            if self.id_maps.get("napt", legacy_id):
                self.stats["skipped"] += 1
                continue
            if self.dry_run:
                new_id = len(self.id_maps.load("napt")) + 1
            else:
                obj = Napt(
                    numero_napt=numero[:50],
                    service_id=service_id,
                    feeder_id=self.fk.feeder_id(str(row.get("Feeder") or row.get("Feeder_a_consigner") or "")),
                    statut="archive",
                    objet_travaux=str(row.get("Consistance_des_travaux") or "Migration")[:1000],
                    date_debut_prevue=date_debut,
                    date_fin_prevue=date_fin,
                    observations=str(row.get("Observations") or "")[:2000] or None,
                    created_by_id=created_by,
                )
                self.session.add(obj)
                self.session.flush()
                new_id = obj.id
            self.id_maps.put("napt", legacy_id, new_id)
            self.stats["inserted"] += 1

    def _load_consignations(self) -> None:
        for row in load_table_rows("consignation"):
            legacy_id = row.get("IDconsignation")
            napt_id = self.id_maps.get("napt", row.get("Num"))
            if napt_id is None:
                self.log_reject(legacy_id, "napt_introuvable", row)
                continue
            numero = f"CONS-{legacy_id}"
            date_ouv = parse_datetime(row.get("datecreation")) or datetime.now()
            if self.dry_run:
                self.stats["inserted"] += 1
                continue
            obj = Consignation(
                napt_id=napt_id,
                numero_consignation=numero,
                statut="levee",
                date_ouverture=date_ouv,
                agent_consignateur_id=self.system_user_id,
                observations=str(row.get("Observation") or "")[:2000] or None,
            )
            self.session.add(obj)
            self.stats["inserted"] += 1

    def _load_destinataires(self) -> None:
        for row in load_table_rows("Destinataire"):
            legacy_id = row.get("IDDestinataires")
            nom = str(row.get("prénomnom") or row.get("prenomnom") or "").strip()
            if not nom:
                self.log_reject(legacy_id, "destinataire_vide", row)
                continue
            if self.dry_run:
                self.stats["inserted"] += 1
                continue
            obj = Destinataire(
                nom=nom[:200],
                telephone=str(row.get("Telephone") or "")[:20] or None,
                service_id=self.fk.service_id(str(row.get("Service") or "")),
                is_active=True,
            )
            self.session.add(obj)
            self.stats["inserted"] += 1
