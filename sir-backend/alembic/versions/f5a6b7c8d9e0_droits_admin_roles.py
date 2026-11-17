"""Droits de la matrice des rôles (admin_roles:read / admin_roles:update).

Admin SCR : lecture et modification (création de rôles, matrice rôles × modules).
Admin Dispatching et Admin SAQS : lecture.

Revision ID: f5a6b7c8d9e0
Revises: e1f2a3b4c5d6
Create Date: 2026-11-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSIONS = [
    ("admin_roles", "read", "Consulter les rôles et la matrice des droits"),
    ("admin_roles", "update", "Créer des rôles et modifier la matrice des droits"),
]
_ATTRIBUTIONS = [
    ("ADMIN_SCR", "read"),
    ("ADMIN_SCR", "update"),
    ("ADMIN_DISPATCHING", "read"),
    ("ADMIN_SAQS", "read"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for ressource, action, description in _PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (ressource, action, description) "
                "SELECT :r, :a, :d WHERE NOT EXISTS "
                "(SELECT 1 FROM permissions WHERE ressource = :r AND action = :a)"
            ),
            {"r": ressource, "a": action, "d": description},
        )
    for role, action in _ATTRIBUTIONS:
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p "
                "WHERE r.nom = :role AND p.ressource = 'admin_roles' AND p.action = :a "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
                "WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ),
            {"role": role, "a": action},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE ressource = 'admin_roles')"
        )
    )
    conn.execute(sa.text("DELETE FROM permissions WHERE ressource = 'admin_roles'"))
