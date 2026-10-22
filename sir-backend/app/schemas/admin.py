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
    password: str = Field(..., min_length=8, max_length=255)
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    telephone: str | None = Field(default=None, max_length=20)
    roles: list[RoleAssignment] = Field(..., min_length=1)


class UtilisateurUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    prenom: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    telephone: str | None = Field(default=None, max_length=20)
    roles: list[RoleAssignment] | None = Field(default=None, min_length=1)


class UtilisateurResponse(BaseModel):
    id: int
    login: str
    nom: str
    prenom: str
    email: str | None
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
