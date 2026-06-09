"""Demo-mode gate tests: with DEMO_MODE off (pilot mode), every simulation
entry point must refuse with 501 instead of fabricating success."""
import pytest
from fastapi import HTTPException

from app.config import settings
from app.demo import require_demo_mode


def test_pilot_mode_blocks_simulations(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    with pytest.raises(HTTPException) as exc:
        require_demo_mode("Scripted voice-call demo")
    assert exc.value.status_code == 501
    assert "demo-only" in exc.value.detail


def test_demo_mode_allows_simulations(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    require_demo_mode("Scripted voice-call demo")  # must not raise


@pytest.mark.anyio
async def test_simulated_payment_hold_is_disabled_in_pilot_mode(monkeypatch):
    from app.sponsors import create_payment_hold

    monkeypatch.setattr(settings, "demo_mode", False)
    result = await create_payment_hold(
        job_id="j1", contractor_id="c1", amount=100.0, release_conditions=[], execute_real=False
    )
    assert result["status"] == "disabled"
    assert "pilot mode" in result["reason"]


@pytest.mark.anyio
async def test_simulated_sms_is_disabled_in_pilot_mode(monkeypatch):
    from app.sponsors import send_agentphone_sms

    monkeypatch.setattr(settings, "demo_mode", False)
    result = await send_agentphone_sms(to_number="+14155550100", body="hi", send_real=False)
    assert result["status"] == "disabled"


def test_app_wires_up():
    """Importing the app catches router/middleware wiring errors without a DB."""
    from app.main import app

    assert app.title == "CrewLoop API"
    paths = {route.path for route in app.routes}
    assert "/api/shifts" in paths
    assert "/api/contractors/import" in paths
    assert "/health" in paths
