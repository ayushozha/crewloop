"""Webhook signature verification tests (the only auth on /webhooks/*)."""
import base64
import hashlib
import hmac

from app.signature import verify_webhook

SECRET = "whsec_test"
BODY = b'{"event":"agent.message","channel":"sms"}'


def _hex_sig(secret: str = SECRET, body: bytes = BODY) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _b64_sig(secret: str = SECRET, body: bytes = BODY) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def test_valid_hex_signature():
    assert verify_webhook(SECRET, BODY, _hex_sig())


def test_valid_base64_signature():
    assert verify_webhook(SECRET, BODY, _b64_sig())


def test_sha256_prefix_is_stripped():
    assert verify_webhook(SECRET, BODY, f"sha256={_hex_sig()}")


def test_missing_signature_rejected():
    assert not verify_webhook(SECRET, BODY, None)
    assert not verify_webhook(SECRET, BODY, "")


def test_wrong_secret_rejected():
    assert not verify_webhook("other-secret", BODY, _hex_sig())


def test_tampered_body_rejected():
    assert not verify_webhook(SECRET, BODY + b"x", _hex_sig())
