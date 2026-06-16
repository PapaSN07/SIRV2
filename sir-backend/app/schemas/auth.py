from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # secondes


class RefreshRequest(BaseModel):
    """Le refresh token est lu depuis le cookie HttpOnly — ce schema est intentionnellement vide."""

    pass


class MeResponse(BaseModel):
    id: int
    login: str
    nom: str
    prenom: str
    role_label: str | None
    service_id: int | None
    premiere_connexion: bool
    is_active: bool

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    login: str = Field(..., min_length=1, max_length=100)
    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)
