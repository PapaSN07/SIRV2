from sqlalchemy import NVARCHAR, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    delegations: Mapped[list["Delegation"]] = relationship(
        "Delegation", back_populates="region", lazy="select"
    )


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    region: Mapped["Region"] = relationship("Region", back_populates="delegations")
    agences: Mapped[list["Agence"]] = relationship(
        "Agence", back_populates="delegation", lazy="select"
    )


class Agence(Base):
    __tablename__ = "agences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delegation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("delegations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    delegation: Mapped["Delegation"] = relationship("Delegation", back_populates="agences")
    services: Mapped[list["Service"]] = relationship(
        "Service", back_populates="agence", lazy="select"
    )


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agences.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    agence: Mapped["Agence"] = relationship("Agence", back_populates="services")
