"""Vérifie que le schéma SQL Server par défaut est dbo."""

from app.core.database import Base, metadata
from app.models.utilisateurs import Utilisateur


def test_metadata_schema_is_dbo() -> None:
    assert metadata.schema == "dbo"


def test_model_tables_use_dbo_schema() -> None:
    assert Utilisateur.__table__.schema == "dbo"
    assert Base.metadata.schema == "dbo"
