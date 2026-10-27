"""Schémas Pydantic — notifications (Sprint 8)."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NotificationEventType(StrEnum):
    INTERRUPTION_CREEE = "interruption_creee"
    INTERRUPTION_CLOTUREE = "interruption_cloturee"
    INTERRUPTION_VALIDEE = "interruption_validee"
    INTERRUPTION_RENVOYEE = "interruption_renvoyee"
    INTERRUPTION_ALERTE_24H = "interruption_alerte_24h"
    RAPPORT_PRET = "rapport_pret"
    NAPT_SOUMIS = "napt_soumis"


class DestinataireCreate(BaseModel):
    nom: str = Field(..., min_length=1, max_length=200)
    telephone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    utilisateur_id: int | None = Field(None, ge=1)
    service_id: int | None = Field(None, ge=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and "@" not in value:
            raise ValueError("Format email invalide")
        return value

    @model_validator(mode="after")
    def require_contact(self) -> "DestinataireCreate":
        if not self.telephone and not self.email:
            raise ValueError("Au moins un téléphone ou un email est requis")
        return self


class DestinataireUpdate(BaseModel):
    nom: str | None = Field(None, min_length=1, max_length=200)
    telephone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=255)
    utilisateur_id: int | None = Field(None, ge=1)
    service_id: int | None = Field(None, ge=1)
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and "@" not in value:
            raise ValueError("Format email invalide")
        return value


class DestinataireResponse(BaseModel):
    id: int
    nom: str
    telephone: str | None
    email: str | None
    utilisateur_id: int | None
    service_id: int | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class EmailEnvoyeResponse(BaseModel):
    id: int
    destinataire_id: int
    entity_type: str | None
    entity_id: int | None
    sujet: str
    corps: str
    statut: str
    sent_at: datetime | None
    erreur: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SmsEnvoyeResponse(BaseModel):
    id: int
    destinataire_id: int
    entity_type: str | None
    entity_id: int | None
    contenu: str
    statut: str
    sent_at: datetime | None
    erreur: str | None
    created_at: datetime
    destinataire_nom: str | None = None
    destinataire_telephone: str | None = None
    utilisateur_login: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ManualSmsSendRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=160)
    destinataire_ids: list[int] | None = None
    utilisateur_ids: list[int] | None = None

    @model_validator(mode="after")
    def require_recipients(self) -> "ManualSmsSendRequest":
        dest = self.destinataire_ids or []
        users = self.utilisateur_ids or []
        if not dest and not users:
            raise ValueError("Au moins un destinataire ou utilisateur est requis")
        return self


class ManualSmsSendResponse(BaseModel):
    sent_count: int
    sms_ids: list[int]


class NotificationEvent(BaseModel):
    event_type: str
    entity_type: str
    entity_id: int
    message: str
    service_id: int | None = None
    created_at: datetime
