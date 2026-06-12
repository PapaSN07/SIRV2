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


class TypeEnd(Base):
    __tablename__ = "types_end"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
