"""Schémas unifilaires : réponses de l'API."""

from datetime import datetime

from pydantic import BaseModel, Field


class SchemaUnifilaireResponse(BaseModel):
    id: int
    nom: str
    fichier: str
    region_id: int | None
    region_libelle: str | None = None
    largeur: float
    hauteur: float
    zoom_max: int
    nb_postes: int
    importe_le: datetime


class PosteSchemaResponse(BaseModel):
    """Poste du schéma : symbole et libellé (points PDF, origine en haut à gauche)."""

    id: int
    rang: int
    libelle: str | None
    forme: str
    puissance_kva: int | None
    x0: float
    y0: float
    x1: float
    y1: float
    lx0: float | None
    ly0: float | None
    lx1: float | None
    ly1: float | None
    poste_id: int | None
    poste_code: str | None = None
    poste_libelle: str | None = None
    rapprochement: str | None


class PostesEntreRequest(BaseModel):
    debut_id: int = Field(ge=1, description="Poste du schéma où commence la section")
    fin_id: int = Field(ge=1, description="Poste du schéma où finit la section")


class DerivationResponse(BaseModel):
    depuis_id: int | None = Field(description="Poste du chemin d'où part la dérivation (repère)")
    postes: list[PosteSchemaResponse]


class PostesEntreResponse(BaseModel):
    """Postes entre deux postes : le long de la ligne, en antenne, et dérivations à choisir."""

    chemin: list[PosteSchemaResponse]
    antennes: list[PosteSchemaResponse]
    derivations: list[DerivationResponse]
    postes_hors_limite: int
    trace: list[tuple[float, float]]


class AssociationPosteRequest(BaseModel):
    poste_id: int | None = Field(default=None, ge=1, description="Poste SIRV2 ; null pour dissocier")


# ── Rapprochement Schéma / SIG / SIR ────────────────────────────────────────────


class NoeudSigCourtResponse(BaseModel):
    id: int
    nom: str | None
    nom_feeder: str | None
    station: str | None
    categorie: str | None


class PosteSirCourtResponse(BaseModel):
    id: int
    code: str
    libelle: str
    feeder_libelle: str | None = None
    poste_source_libelle: str | None = None


class LigneRapprochementResponse(BaseModel):
    """Un poste du schéma, son nœud SIG et son poste SIR (ou la décision SIR)."""

    id: int
    rang: int
    libelle: str | None
    sig: NoeudSigCourtResponse | None
    rapprochement_sig: str | None
    sir: PosteSirCourtResponse | None
    rapprochement: str | None
    statut_sir: str | None
    demande_id: int | None = None


class CompteursRapprochementResponse(BaseModel):
    total: int
    sans_nom: int
    sig_relies: int
    sig_ambigus: int
    sir_relies: int
    sir_ambigus: int
    a_creer: int
    inactifs: int
    a_traiter: int


class RapprochementSigResponse(BaseModel):
    relies: int
    ambigus: int
    non_trouves: int


class LienSigRequest(BaseModel):
    noeud_sig_id: int | None = Field(default=None, ge=1, description="Nœud SIG ; null pour délier")


class StatutSirRequest(BaseModel):
    statut_sir: str | None = Field(default=None, pattern="^inactif$", description="inactif, ou null pour annuler")


class SuggestionCreationResponse(BaseModel):
    """Pré-remplissage de la recherche assistée : nom du schéma, feeder du SIG ou des postes voisins."""

    libelle: str
    poste_source_id: int | None
    poste_source_libelle: str | None
    feeder_id: int | None
    feeder_libelle: str | None
    origine: str | None = Field(description="sig (feeder du nœud SIG), voisins (postes voisins du schéma) ou null")


class PosteACreerRequest(BaseModel):
    libelle: str = Field(min_length=2, max_length=200)
    feeder_id: int = Field(ge=1)


class ValidationPosteRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20, description="Code SIR ; généré si absent")


class RejetPosteRequest(BaseModel):
    motif: str = Field(min_length=3, max_length=500)


class PosteACreerResponse(BaseModel):
    id: int
    schema_nom: str | None
    libelle_schema: str | None
    libelle: str
    poste_source_id: int
    poste_source_libelle: str | None
    feeder_id: int
    feeder_libelle: str | None
    noeud_sig_nom: str | None
    statut: str
    motif_rejet: str | None
    poste_id: int | None
    poste_code: str | None
    propose_par: str | None
    propose_le: datetime
    traite_par: str | None
    traite_le: datetime | None
