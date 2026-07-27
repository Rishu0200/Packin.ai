import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.models import Base, User
from app.db.session import get_db
from app.core.security import hash_password
from app.main import app


@pytest.fixture
def client():
    # StaticPool is required here — plain sqlite:///:memory: gives each new
    # connection its own separate empty database, so tables created in
    # setup wouldn't be visible to the connection the route handlers use.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed one test user directly, bypassing the app's startup seed() so
    # this test doesn't depend on real seed data or a real bootstrap password.
    db = TestSession()
    db.add(User(username="testuser", hashed_password=hash_password("testpass123"),
                role="staff", active=True))
    db.commit()
    db.close()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_login_with_correct_credentials_returns_token(client):
    res = client.post("/auth/login", data={"username": "testuser", "password": "testpass123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_with_wrong_password_is_rejected(client):
    res = client.post("/auth/login", data={"username": "testuser", "password": "wrongpass"})
    assert res.status_code == 401


def test_protected_endpoint_rejects_missing_token(client):
    res = client.get("/inventory")
    assert res.status_code == 401


def test_protected_endpoint_accepts_valid_token(client):
    login_res = client.post("/auth/login", data={"username": "testuser", "password": "testpass123"})
    token = login_res.json()["access_token"]

    res = client.get("/inventory", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_health_endpoint_stays_public(client):
    res = client.get("/health")
    assert res.status_code == 200
