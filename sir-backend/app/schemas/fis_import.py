"""Schémas Pydantic — import fichiers FIS (Fiche d'Incidents et de Suivi)."""

from datetime import datetime

from pydantic import BaseModel, Field


class FisImportStatsResponse(BaseModel):
    """Statistiques d'un import FIS."""

    total_lignes: int = Field(..., description="Nombre total de lignes dans le fichier FIS")
    importees: int = Field(..., description="Interruptions créées avec succès")
    doublons_ignores: int = Field(..., description="Lignes ignorées (numéro déjà en base)")
    erreurs: int = Field(..., description="Lignes en erreur")
    end_total_kwh: float = Field(..., description="END total importé (kWh)")
    end_total_mwh: float = Field(..., description="END total importé (MWh)")


class FisImportResponse(BaseModel):
    """Réponse après import d'un fichier FIS."""

    stats: FisImportStatsResponse
    periode_debut: datetime | None = Field(None, description="Date de la première interruption importée")
    periode_fin: datetime | None = Field(None, description="Date de la dernière interruption importée")
    services_touches: list[str] = Field(
        default_factory=list,
        description="Services de distribution concernés par l'import",
    )
    erreurs_detail: list[str] = Field(
        default_factory=list,
        description="Détail des erreurs ligne par ligne (max 50)",
    )
