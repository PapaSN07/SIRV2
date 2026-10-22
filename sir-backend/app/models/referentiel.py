from sqlalchemy import NVARCHAR, Boolean, CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Valid values for type_reseau
TYPE_RESEAU_VALUES = ("distribution", "transport", "commun")


class Cause(Base):
    __tablename__ = "causes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    # distribution | transport | commun
    type_reseau: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "type_reseau IN ('distribution', 'transport', 'commun')",
            name="ck_cause_type_reseau",
        ),
    )


class Siege(Base):
    __tablename__ = "sieges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    # distribution | transport | commun
    type_reseau: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "type_reseau IN ('distribution', 'transport', 'commun')",
            name="ck_siege_type_reseau",
        ),
    )


class Signalisation(Base):
    __tablename__ = "signalisations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    # distribution | transport | commun
    type_reseau: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "type_reseau IN ('distribution', 'transport', 'commun')",
            name="ck_signalisation_type_reseau",
        ),
    )


class Nature(Base):
    __tablename__ = "natures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


STATUT_IDS: dict[str, int] = {"en_cours": 1, "cloture": 2, "valide": 3, "archive": 4}
DIRECTION_SOURCE_IDS: dict[str, int] = {"distribution": 1, "transport": 2, "omvg": 3}


class Statut(Base):
    """Statut d'interruption — ids figés (cf. STATUT_IDS), seedés par Alembic."""

    __tablename__ = "statuts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DirectionSource(Base):
    """Direction source (distribution / transport / omvg) — ids figés (cf. DIRECTION_SOURCE_IDS)."""

    __tablename__ = "direction_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)


class Entreprise(Base):
    __tablename__ = "entreprises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Prestataire(Base):
    __tablename__ = "prestataires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TypeEnd(Base):
    __tablename__ = "types_end"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class TypeReseau(Base):
    """Référentiel HFSQL TypeReseau (MT, BT, …), distinct du discriminant distribution/transport."""

    __tablename__ = "types_reseaux"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
