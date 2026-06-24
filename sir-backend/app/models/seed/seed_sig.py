"""Seeder topologie SIG minimal — jeu dev Docker (sans HFSQL).

Lie les tronçons SIG aux feeders du seed_reseau (FD-DKR-01, FD-THS-01).

Usage :
    from app.models.seed.seed_sig import seed_sig
    await seed_sig(db)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reseau import Feeder
from app.models.sig import NoeudSig, TronconSig

_NOEUDS: list[tuple[int, int, str, str]] = [
    # (legacy_id, legacy_fid, nom, feeder_code)
    (900_001, 910_001, "Nœud amont Plateau", "FD-DKR-01"),
    (900_002, 910_002, "Nœud aval Plateau", "FD-DKR-01"),
    (900_003, 910_003, "Nœud amont Thiès", "FD-THS-01"),
    (900_004, 910_004, "Nœud aval Thiès", "FD-THS-01"),
]

_TRONCONS: list[tuple[int, int | None, str, str, str, str, str, str]] = [
    # (legacy_id, legacy_fid, feeder_code, nom_troncon, amont_nom, amont_code, aval_nom, aval_code)
    (
        900_101,
        920_101,
        "FD-DKR-01",
        "Tronçon SIG Plateau A",
        "Nœud amont Plateau",
        "ND-DKR-A",
        "Nœud aval Plateau",
        "ND-DKR-B",
    ),
    (
        900_102,
        920_102,
        "FD-DKR-01",
        "Tronçon SIG Plateau B",
        "Nœud aval Plateau",
        "ND-DKR-B",
        "Poste BT Plateau",
        "ND-DKR-C",
    ),
    (
        900_201,
        920_201,
        "FD-THS-01",
        "Tronçon SIG Thiès A",
        "Nœud amont Thiès",
        "ND-THS-A",
        "Nœud aval Thiès",
        "ND-THS-B",
    ),
    (
        900_202,
        920_202,
        "FD-THS-01",
        "Tronçon SIG Thiès B",
        "Nœud aval Thiès",
        "ND-THS-B",
        "Poste Thiès Centre",
        "ND-THS-C",
    ),
]

_LOAD_DATE = datetime(2026, 1, 1, 0, 0, 0)


async def _get_feeder(db: AsyncSession, code: str) -> Feeder:
    result = await db.execute(select(Feeder).where(Feeder.code == code))
    feeder = result.scalar_one_or_none()
    if feeder is None:
        raise ValueError(f"Feeder '{code}' introuvable — exécuter seed_reseau d'abord")
    return feeder


async def _upsert_noeud(
    db: AsyncSession,
    *,
    legacy_id: int,
    legacy_fid: int,
    nom: str,
    feeder: Feeder,
) -> NoeudSig:
    result = await db.execute(select(NoeudSig).where(NoeudSig.legacy_id == legacy_id))
    noeud = result.scalar_one_or_none()
    if noeud is None:
        noeud = NoeudSig(
            legacy_id=legacy_id,
            legacy_fid=legacy_fid,
            nom=nom,
            nom_feeder=feeder.libelle,
            feeder_id=feeder.id,
            categorie="poste",
        )
        db.add(noeud)
    else:
        noeud.nom = nom
        noeud.nom_feeder = feeder.libelle
        noeud.feeder_id = feeder.id
    await db.flush()
    return noeud


async def _upsert_troncon(
    db: AsyncSession,
    *,
    legacy_id: int,
    legacy_fid: int | None,
    feeder: Feeder,
    nom_troncon: str,
    nom_amont: str,
    code_amont: str,
    nom_aval: str,
    code_aval: str,
) -> TronconSig:
    result = await db.execute(select(TronconSig).where(TronconSig.legacy_id == legacy_id))
    troncon = result.scalar_one_or_none()
    if troncon is None:
        troncon = TronconSig(
            legacy_id=legacy_id,
            legacy_fid=legacy_fid,
            nom_feeder=feeder.libelle,
            feeder_id=feeder.id,
            nom_troncon=nom_troncon,
            nom_noeud_amont=nom_amont,
            code_noeud_amont=code_amont,
            nom_noeud_aval=nom_aval,
            code_noeud_aval=code_aval,
            tension_kv=30.0,
            longueur_m=500.0,
            date_chargement=_LOAD_DATE,
        )
        db.add(troncon)
    else:
        troncon.legacy_fid = legacy_fid
        troncon.nom_feeder = feeder.libelle
        troncon.feeder_id = feeder.id
        troncon.nom_troncon = nom_troncon
        troncon.nom_noeud_amont = nom_amont
        troncon.code_noeud_amont = code_amont
        troncon.nom_noeud_aval = nom_aval
        troncon.code_noeud_aval = code_aval
        troncon.tension_kv = 30.0
        troncon.longueur_m = 500.0
        troncon.date_chargement = _LOAD_DATE
    await db.flush()
    return troncon


async def seed_sig(db: AsyncSession) -> dict[str, int]:
    """Charge nœuds et tronçons SIG minimaux pour les feeders dev."""
    feeder_cache: dict[str, Feeder] = {}
    noeud_count = 0
    troncon_count = 0

    for legacy_id, legacy_fid, nom, feeder_code in _NOEUDS:
        if feeder_code not in feeder_cache:
            feeder_cache[feeder_code] = await _get_feeder(db, feeder_code)
        await _upsert_noeud(
            db,
            legacy_id=legacy_id,
            legacy_fid=legacy_fid,
            nom=nom,
            feeder=feeder_cache[feeder_code],
        )
        noeud_count += 1

    for (
        legacy_id,
        legacy_fid,
        feeder_code,
        nom_troncon,
        nom_amont,
        code_amont,
        nom_aval,
        code_aval,
    ) in _TRONCONS:
        if feeder_code not in feeder_cache:
            feeder_cache[feeder_code] = await _get_feeder(db, feeder_code)
        await _upsert_troncon(
            db,
            legacy_id=legacy_id,
            legacy_fid=legacy_fid,
            feeder=feeder_cache[feeder_code],
            nom_troncon=nom_troncon,
            nom_amont=nom_amont,
            code_amont=code_amont,
            nom_aval=nom_aval,
            code_aval=code_aval,
        )
        troncon_count += 1

    await db.flush()
    return {"noeuds_sig": noeud_count, "troncons_sig": troncon_count}
