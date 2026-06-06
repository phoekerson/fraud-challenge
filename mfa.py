"""
MFA TOTP — RFC 6238 (Time-based One-Time Password), 100% bibliothèque standard.

Compatible avec **Google Authenticator** et **Microsoft Authenticator** :
- secret encodé en Base32,
- HMAC-SHA1, 6 chiffres, période de 30 s,
- URI `otpauth://totp/...` que les applications scannent (QR) ou saisissent.

Aucune dépendance externe : utilisable hors-ligne et auditable.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITS = 6
PERIOD = 30  # secondes


def generate_secret(length: int = 20) -> str:
    """Génère un secret aléatoire encodé en Base32 (sans padding)."""
    return base64.b32encode(secrets.token_bytes(length)).decode("utf-8").rstrip("=")


def _b32decode(secret: str) -> bytes:
    secret = secret.strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret + padding)


def totp_at(secret: str, for_time: float | None = None,
            digits: int = DIGITS, period: int = PERIOD) -> str:
    """Calcule le code TOTP pour un instant donné (par défaut : maintenant)."""
    if for_time is None:
        for_time = time.time()
    counter = int(for_time // period)
    key = _b32decode(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code_int % (10 ** digits)).zfill(digits)


def verify(secret: str, code: str, window: int = 1) -> bool:
    """Vérifie un code en tolérant ±`window` périodes (décalage d'horloge)."""
    if not code:
        return False
    code = code.strip()
    now = time.time()
    for w in range(-window, window + 1):
        if hmac.compare_digest(totp_at(secret, now + w * PERIOD), code):
            return True
    return False


def provisioning_uri(secret: str, account: str, issuer: str = "AEGIS") -> str:
    """URI `otpauth://` à transformer en QR code pour les apps Authenticator."""
    label = quote(f"{issuer}:{account}")
    params = (
        f"secret={secret}"
        f"&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD}"
    )
    return f"otpauth://totp/{label}?{params}"


def qr_data_uri(text: str) -> str | None:
    """QR code en PNG (data URI) si la bibliothèque `qrcode` est installée, sinon None."""
    try:
        import io

        import qrcode  # dépendance optionnelle

        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None
