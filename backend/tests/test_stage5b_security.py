from backend.app.core.auth import create_access_token, hash_password
from backend.app.models.organization import Membership, Organization, User


def test_unauthorized_requests_are_rejected(client):
    response = client.get("/receipts/pending", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_login_returns_short_lived_token(client):
    response = client.post("/auth/login", json={"email": "test@example.com", "password": "test-password-123"})
    assert response.status_code == 200
    assert response.json()["expires_in"] == 15 * 60


def test_cross_organization_receipt_is_not_visible(client, client_db):
    other = Organization(name="Other organization")
    user = User(email="other@example.com", password_hash=hash_password("other-password-123"))
    client_db.add_all([other, user])
    client_db.flush()
    client_db.add(Membership(organization_id=other.id, user_id=user.id, role="viewer"))
    client_db.commit()
    response = client.get(
        "/receipts/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": "Bearer " + create_access_token(user.id, other.id, "viewer")},
    )
    assert response.status_code == 404


def test_pending_receipt_cannot_be_manual_expense(client):
    receipt = client.post("/receipts", json={"company": "Unapproved", "total": "2.00", "currency": "USD"}).json()
    response = client.post("/expenses", json={"receipt_id": receipt["id"], "amount": "2.00", "currency": "USD"})
    assert response.status_code == 409
