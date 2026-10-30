"""L'identifiant de connexion est nettoyé des espaces autour (copier-coller)."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest


def test_login_sans_espaces() -> None:
    assert LoginRequest(login=" mamadou.sene2 ", password="x").login == "mamadou.sene2"
    with pytest.raises(ValidationError):
        LoginRequest(login="   ", password="x")
