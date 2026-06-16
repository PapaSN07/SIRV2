from sqlalchemy import NVARCHAR, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)  # create | update | delete
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    old_values: Mapped[str | None] = mapped_column(NVARCHAR(4000), nullable=True)
    new_values: Mapped[str | None] = mapped_column(NVARCHAR(4000), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )

    # Relationships
    user: Mapped["Utilisateur"] = relationship("Utilisateur", foreign_keys=[user_id])  # noqa: F821
