# Import all models so that:
# 1. SQLAlchemy can resolve all relationships at mapper configuration time
# 2. Alembic autogenerate detects all tables via Base.metadata
#
# IMPORTANT: import order matters — tables with no FK deps come first.

from app.models.geo import Agence, Delegation, Region, Service  # noqa: F401
from app.models.referentiel import (  # noqa: F401
    Cause,
    DirectionSource,
    Entreprise,
    Nature,
    Prestataire,
    Siege,
    Signalisation,
    Statut,
    TypeEnd,
    TypeReseau,
)
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.reseau import (  # noqa: F401
    EquipementTransport,
    Feeder,
    PosteLigne,
    PosteSource,
    SousFeeder,
    SourceTransport,
    Troncon,
    Poste,
)
from app.models.interruptions import (  # noqa: F401
    Interruption,
    InterruptionDistribution,
    InterruptionTransport,
    PosteInterruption,
)
from app.models.interruption_workflow import EtapeWorkflow, Workflow  # noqa: F401
from app.models.interruption_statut_historique import InterruptionStatutHistorique  # noqa: F401
from app.models.indicateurs import EnergieNd, NombreClientMois, ObjectifIndicateur, SaifiSaidi  # noqa: F401
from app.models.napt import Consignation, Napt  # noqa: F401
from app.models.clients import ContratsUniteReleve, PosteUniteReleve  # noqa: F401
from app.models.notifications import Destinataire, EmailEnvoye, GroupeEnvoi, SmsEnvoye  # noqa: F401
from app.models.rapports import RapportGenere  # noqa: F401
from app.models.sig import NoeudSig, TronconSig  # noqa: F401
from app.models.assistant_ml import (  # noqa: F401
    AssistantConversation,
    MlFeatureSnapshot,
    MlPrediction,
)

__all__ = [
    "InterruptionStatutHistorique",
    # Geo
    "Region",
    "Delegation",
    "Agence",
    "Service",
    # Référentiel
    "Cause",
    "Siege",
    "Signalisation",
    "Nature",
    "TypeEnd",
    "TypeReseau",
    "Statut",
    "DirectionSource",
    "Entreprise",
    "Prestataire",
    # Utilisateurs & RBAC
    "Permission",
    "Role",
    "RolePermission",
    "Utilisateur",
    "UserRole",
    # Audit
    "AuditLog",
    # Réseau
    "PosteSource",
    "Feeder",
    "SousFeeder",
    "Poste",
    "Troncon",
    "EquipementTransport",
    "SourceTransport",
    "PosteLigne",
    # Interruptions
    "Interruption",
    "InterruptionDistribution",
    "InterruptionTransport",
    "PosteInterruption",
    "EtapeWorkflow",
    "Workflow",
    # Indicateurs
    "EnergieNd",
    "SaifiSaidi",
    "NombreClientMois",
    "ObjectifIndicateur",
    # NAPT
    "Napt",
    "Consignation",
    # Notifications
    "Destinataire",
    "GroupeEnvoi",
    "ContratsUniteReleve",
    "PosteUniteReleve",
    "SmsEnvoye",
    "EmailEnvoye",
    # Rapports
    "RapportGenere",
    "NoeudSig",
    "TronconSig",
    # Assistant ML
    "MlFeatureSnapshot",
    "MlPrediction",
    "AssistantConversation",
]
