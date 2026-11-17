from pydantic import BaseModel, Field
from datetime import datetime


class RoleAssignment(BaseModel):
    """Attribution d'un rôle avec périmètre optionnel."""

    role_id: int
    scope_service_id: int | None = None


class RoleInfo(BaseModel):
    """Rôle assigné à un utilisateur (lecture)."""

    role_id: int
    role_nom: str
    scope_service_id: int | None = None

    model_config = {"from_attributes": True}


class UtilisateurCreate(BaseModel):
    login: str = Field(..., min_length=1, max_length=100)
    # Absent pour un compte de l'annuaire (connexion avec le mot de passe Windows)
    password: str | None = Field(default=None, min_length=8, max_length=255)
    annuaire: bool = Field(default=False, description="Compte importé de l'Active Directory")
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    matricule: str | None = Field(default=None, max_length=20)
    telephone: str | None = Field(default=None, max_length=20)
    roles: list[RoleAssignment] = Field(..., min_length=1)


class UtilisateurUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    prenom: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    matricule: str | None = Field(default=None, max_length=20)
    telephone: str | None = Field(default=None, max_length=20)
    roles: list[RoleAssignment] | None = Field(default=None, min_length=1)


class UtilisateurResponse(BaseModel):
    id: int
    login: str
    nom: str
    prenom: str
    email: str | None
    matricule: str | None = None
    telephone: str | None
    is_active: bool
    premiere_connexion: bool
    roles: list[RoleInfo]

    model_config = {"from_attributes": True}


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=255)


class PermissionInfo(BaseModel):
    id: int
    ressource: str
    action: str
    description: str | None = None


class RoleDetailResponse(BaseModel):
    id: int
    nom: str
    description: str | None
    permissions: list[PermissionInfo]
    is_active: bool = True
    # Rôle prévu par SIRV2 (BCC, BRC…) : nom figé, ne peut pas être désactivé
    systeme: bool = False
    nombre_utilisateurs: int = 0


class RoleCreate(BaseModel):
    nom: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    description: str | None = Field(default=None, max_length=255)
    permission_ids: list[int] = Field(default_factory=list, max_length=200)


class RoleUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    permission_ids: list[int] | None = Field(default=None, max_length=200)


class AuditLogResponse(BaseModel):
    id: int
    table_name: str
    record_id: int
    action: str
    user_id: int
    user_login: str | None = None
    old_values: str | None
    new_values: str | None
    created_at: datetime


class AppSettingsResponse(BaseModel):
    sms_gateway_url: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    seuil_fugitif_minutes: int
    environment: str


class AppSettingsUpdate(BaseModel):
    seuil_fugitif_minutes: int | None = Field(default=None, ge=1, le=120)


class AnnuaireUtilisateur(BaseModel):
    """Compte Active Directory proposé à l'ajout (page Utilisateurs → Ajouter depuis l'annuaire)."""

    login: str
    prenom: str | None = None
    nom: str | None = None
    nom_affiche: str | None = None
    email: str | None = None
    telephone: str | None = None
    matricule: str | None = None
    service: str | None = None
    fonction: str | None = None
    deja_dans_sir: bool = False
