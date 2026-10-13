"""Explicit local account bootstrap; all values must be supplied through the environment."""

import os

from backend.app.core.auth import hash_password
from backend.app.database.session import SessionLocal
from backend.app.models.organization import Membership, Organization, User


def main() -> None:
    email = os.environ.get("BOOTSTRAP_EMAIL", "").strip().lower()
    password = os.environ.get("BOOTSTRAP_PASSWORD", "")
    organization_name = os.environ.get("BOOTSTRAP_ORGANIZATION", "").strip()
    if not email or not password or not organization_name:
        raise SystemExit("Set BOOTSTRAP_EMAIL, BOOTSTRAP_PASSWORD, and BOOTSTRAP_ORGANIZATION")
    with SessionLocal.begin() as db:
        organization = Organization(name=organization_name)
        user = User(email=email, password_hash=hash_password(password))
        db.add_all([organization, user])
        db.flush()
        db.add(Membership(organization_id=organization.id, user_id=user.id, role="admin"))
    print(f"Created local organization {organization_name!r} and admin {email!r}")


if __name__ == "__main__":
    main()
