# Import all models so that:
# 1. SQLAlchemy can resolve all relationships at mapper configuration time
# 2. Alembic autogenerate detects all tables via Base.metadata
#
# IMPORTANT: import order matters — tables with no FK deps come first.

from app.models.geo import Agence, Delegation, Region, Service  # noqa: F401
from app.models.referentiel import Cause, Nature, Siege, Signalisation, TypeEnd  # noqa: F401
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
from app.models.indicateurs import EnergieNd, NombreClientMois, SaifiSaidi  # noqa: F401
from app.models.napt import Consignation, Napt  # noqa: F401
from app.models.notifications import Destinataire, EmailEnvoye, SmsEnvoye  # noqa: F401

__all__ = [
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
    # Indicateurs
    "EnergieNd",
    "SaifiSaidi",
    "NombreClientMois",
    # NAPT
    "Napt",
    "Consignation",
    # Notifications
    "Destinataire",
    "SmsEnvoye",
    "EmailEnvoye",
]
