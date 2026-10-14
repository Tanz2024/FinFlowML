"""Idempotently seed disposable browser accounts for the acceptance database."""
import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.core.auth import hash_password
from backend.app.models.organization import Membership, Organization, User

url = os.environ["DATABASE_URL"]
if "finflowml_acceptance" not in url:
    raise SystemExit("refusing to seed a non-acceptance database")
engine = create_engine(url)
password = "Acceptance-password-123!"
with Session(engine) as db:
    for org_name in ("Acceptance Alpha", "Acceptance Beta"):
        org = db.scalar(select(Organization).where(Organization.name == org_name))
        if not org:
            org = Organization(name=org_name); db.add(org); db.flush()
        for role in ("admin", "reviewer", "accountant", "viewer"):
            email = f"{role}@{org_name.split()[-1].lower()}.acceptance.test"
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                user = User(email=email, password_hash=hash_password(password)); db.add(user); db.flush()
            if not db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.organization_id == org.id)):
                db.add(Membership(user_id=user.id, organization_id=org.id, role=role))
    db.commit()
print("acceptance accounts seeded; password is TEST-ONLY")
