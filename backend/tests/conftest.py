import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.auth import create_access_token, hash_password
from backend.app.database.base import Base
from backend.app.database.session import get_db
from backend.app.main import app
from backend.app.models.organization import Membership, Organization, User


@event.listens_for(Session, "before_flush")
def _test_tenant_defaults(session, *_):
    org_id = session.info.get("test_organization_id")
    if org_id:
        for item in session.new:
            if hasattr(item, "organization_id") and getattr(item, "organization_id", None) is None:
                item.organization_id = org_id


@pytest.fixture()
def client_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    org = Organization(name="Test organization")
    db.add(org)
    db.flush()
    user = User(email="test@example.com", password_hash=hash_password("test-password-123"))
    db.add(user)
    db.flush()
    db.add(Membership(organization_id=org.id, user_id=user.id, role="admin"))
    db.commit()
    db.info["test_organization_id"] = org.id
    db.info["test_user_id"] = user.id
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(client_db):
    db = client_db

    def override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override
    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = "Bearer " + create_access_token(db.info["test_user_id"], db.info["test_organization_id"], "admin")
        yield test_client
    app.dependency_overrides.clear()
