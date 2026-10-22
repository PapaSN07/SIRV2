from datetime import datetime

from sqlalchemy import NVARCHAR, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ressource: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    action: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)
    description: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)

    __table_args__ = (UniqueConstraint("ressource", "action", name="uq_permission_ressource_action"),)

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission", lazy="select"
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # BCC | BRC | DISPATCHER | ADMIN_SCR | ADMIN_DISPATCHING | ADMIN_SAQS | SUPERVISEUR
    nom: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="role", lazy="selectin"
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="role", lazy="select"
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship("Permission", back_populates="role_permissions")


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    nom: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    prenom: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    email: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    telephone: Mapped[str | None] = mapped_column(NVARCHAR(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    premiere_connexion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    direction_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("direction_sources.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=MSSQL_NOW,
        onupdate=func.now(),
    )

    # Relationships
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="utilisateur", lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        "AuditLog", back_populates="user", lazy="select"
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    # Nullable: national roles (ADMIN_SCR, DISPATCHER…) have no service scope
    scope_service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True
    )

    __table_args__ = (
        UniqueConstraint("utilisateur_id", "role_id", name="uq_user_role"),
    )

    # Relationships
    utilisateur: Mapped["Utilisateur"] = relationship(
        "Utilisateur", back_populates="user_roles"
    )
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")
    scope_service: Mapped["Service | None"] = relationship(  # noqa: F821
        "Service", foreign_keys=[scope_service_id], lazy="select"
    )
