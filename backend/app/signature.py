import hashlib
import hmac


def verify_webhook(secret: str, body: bytes, signature_header: str | None) -> bool:
    # AgentPhone signs with HMAC-SHA256 in the X-Webhook-Signature header.
    # Format isn't documented; accept either hex or base64 to be safe.
    if not signature_header:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    hex_sig = digest.hex()
    import base64
    b64_sig = base64.b64encode(digest).decode("ascii")
    candidate = signature_header.strip()
    # Strip common prefixes like "sha256=".
    if "=" in candidate and candidate.split("=", 1)[0].lower().startswith("sha"):
        candidate = candidate.split("=", 1)[1]
    return hmac.compare_digest(candidate, hex_sig) or hmac.compare_digest(candidate, b64_sig)
