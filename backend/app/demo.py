"""Demo-mode gate.

Pilot rule from the June 2026 hardening: simulated flows must be impossible to
reach by accident. Anything that fakes an external side effect (scripted
contractor replies, pretend vendor checkout, fabricated payment/email refs)
calls require_demo_mode() first and dies with a 501 unless DEMO_MODE=true.
"""
from fastapi import HTTPException

from .config import settings


class DemoModeDisabled(Exception):
    """Raised by non-route code paths when a simulation is requested in pilot mode."""

    def __init__(self, feature: str):
        self.feature = feature
        super().__init__(f"{feature} is demo-only and DEMO_MODE is off")


def require_demo_mode(feature: str) -> None:
    if not settings.demo_mode:
        raise HTTPException(
            status_code=501,
            detail=(
                f"{feature} is a demo-only simulation and is disabled in pilot mode. "
                "Set DEMO_MODE=true to re-enable it for demos."
            ),
        )
