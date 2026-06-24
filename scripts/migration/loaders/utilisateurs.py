"""Loader vague 4 — utilisateurs et RBAC."""

from __future__ import annotations

from typing import Any

from passlib.context import CryptContext
from sqlalchemy import select

from app.models.utilisateurs import Role, UserRole, Utilisateur

from scripts.migration.config import get_settings
from scripts.migration.hfsql_odbc import load_table_rows
from scripts.migration.loaders.base import BaseLoader
from scripts.migration.transforms.fk_resolver import FkResolver
from scripts.migration.transforms.rows import row_get

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

RBAC_FLAGS: list[tuple[str, str, str]] = [
    ("typeuser", "BCC", "BCC"),
    ("adminscr", "ADMIN_SCR", "national"),
    ("disparcheur", "DISPATCHER", "national"),
    ("adminditpatching", "ADMIN_DISPATCHING", "national"),
    ("adminsaqs", "ADMIN_SAQS", "national"),
    ("superviseur", "SUPERVISEUR", "service"),
]


class UtilisateursLoader(BaseLoader):
    entity_name = "utilisateurs"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fk = FkResolver(self.id_maps)
        self._role_cache: dict[str, int] = {}
        self._system_user_id: int | None = None

    def run(self) -> dict[str, Any]:
        self._ensure_system_user()
        self._load_utilisateurs()
        self.id_maps.save("utilisateurs")
        return self.summary()

    def _ensure_system_user(self) -> None:
        login = get_settings().migration_system_login
        if self.dry_run:
            self._system_user_id = 1
            self.id_maps.put("utilisateurs", login, 1)
            return
        existing = self.session.execute(
            select(Utilisateur).where(Utilisateur.login == login)
        ).scalar_one_or_none()
        if existing:
            self._system_user_id = existing.id
        else:
            user = Utilisateur(
                login=login,
                password_hash=_pwd_context.hash("ChangeMeMigration!"),
                nom="System",
                prenom="Migration",
                is_active=True,
                premiere_connexion=True,
            )
            self.session.add(user)
            self.session.flush()
            self._system_user_id = user.id
        self.id_maps.put("utilisateurs", login, self._system_user_id)

    def _role_id(self, role_nom: str) -> int | None:
        if role_nom in self._role_cache:
            return self._role_cache[role_nom]
        if self.dry_run:
            rid = len(self._role_cache) + 1
            self._role_cache[role_nom] = rid
            return rid
        role = self.session.execute(select(Role).where(Role.nom == role_nom)).scalar_one_or_none()
        if role is None:
            return None
        self._role_cache[role_nom] = role.id
        return role.id

    def _load_utilisateurs(self) -> None:
        seen_logins: set[str] = set()
        for row in load_table_rows("Utilisateurs"):
            legacy_id = row_get(row, "IDUser", "iduser")
            login = str(row_get(row, "Login", "login") or "").strip().lower()
            if not login or login in seen_logins:
                self.log_reject(legacy_id, "login_invalide_ou_doublon", row)
                continue
            seen_logins.add(login)
            if self.id_maps.get("utilisateurs", login):
                self.stats["skipped"] += 1
                continue
            raw_pwd = str(row_get(row, "mdp") or "ChangeMeMigration!")
            pwd_hash = _pwd_context.hash(raw_pwd)
            nom = str(row_get(row, "Nom", "nom") or login)[:100]
            prenom = str(row_get(row, "Prénom", "Prenom", "prenom", "prénom") or "")[:100]
            email = str(row_get(row, "Email", "email") or "").strip() or None
            if self.dry_run:
                new_id = len(self.id_maps.load("utilisateurs")) + 1
            else:
                user = Utilisateur(
                    login=login,
                    password_hash=pwd_hash,
                    nom=nom,
                    prenom=prenom,
                    email=email,
                    is_active=True,
                    premiere_connexion=True,
                )
                self.session.add(user)
                self.session.flush()
                new_id = user.id
                self._assign_roles(user.id, row)
            self.id_maps.put("utilisateurs", legacy_id, new_id)
            self.id_maps.put("utilisateurs", login, new_id)
            self.stats["inserted"] += 1

    def _assign_roles(self, user_id: int, row: dict) -> None:
        service_scope = self.fk.service_id(str(row_get(row, "Service", "service") or ""))
        typeuser = str(row_get(row, "typeuser", "Typeuser") or "").strip().upper()
        for flag_field, role_nom, scope in RBAC_FLAGS:
            if flag_field == "typeuser":
                active = typeuser == role_nom
            else:
                active = row_get(row, flag_field) in (True, 1, "1")
            if not active:
                continue
            role_id = self._role_id(role_nom)
            if role_id is None:
                continue
            scope_id = service_scope if scope == "service" else None
            ur = UserRole(
                utilisateur_id=user_id,
                role_id=role_id,
                scope_service_id=scope_id,
            )
            self.session.add(ur)

    def system_user_id(self) -> int:
        return self._system_user_id or 1
