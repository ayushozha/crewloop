"""Shared-password middleware tests. No DB: the gate must reject before any
route handler runs, and open paths must stay open."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _password(monkeypatch):
    monkeypatch.setattr(settings, "app_password", "pilot-secret")


def test_protected_path_without_header_is_401():
    assert client.get("/api/contractors").status_code == 401


def test_wrong_password_is_401():
    r = client.get("/api/contractors", headers={"X-App-Password": "nope"})
    assert r.status_code == 401


def test_correct_password_passes_the_gate():
    r = client.get("/api/contractors", headers={"X-App-Password": "pilot-secret"})
    # No DB in tests, so the handler itself fails — the point is the gate let it through.
    assert r.status_code != 401


def test_uppercase_path_still_gated():
    assert client.get("/API/contractors").status_code == 401


def test_duplicate_slashes_still_gated():
    # "//api/..." can't be sent via the test client (it parses as a
    # protocol-relative URL), but the same collapse logic covers it.
    assert client.get("/api//contractors").status_code == 401


def test_health_stays_open():
    assert client.get("/health").status_code == 200


def test_webhooks_stay_open():
    # Signature verification is the webhook's own auth; the gate must not 401 it.
    r = client.post("/webhooks/sponge", json={})
    assert r.status_code != 401


def test_options_preflight_not_blocked():
    r = client.options(
        "/api/contractors",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code != 401


def test_gate_disabled_when_password_unset(monkeypatch):
    monkeypatch.setattr(settings, "app_password", None)
    r = client.get("/api/contractors")
    assert r.status_code != 401
