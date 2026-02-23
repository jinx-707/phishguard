"""
Security utilities for the Threat Intelligence Platform.

Provides:
  1.  Fernet symmetric encryption for PII / sensitive fields at rest.
  2.  bleach-based HTML sanitisation to strip XSS payloads before storage.
  3.  URL validation helpers beyond Pydantic's basic checks.
  4.  Audit log helper that writes structured security events to both
      the structlog stream and the `audit_logs` DB table.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import bleach
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# 1. Fernet Encryption
# ══════════════════════════════════════════════════════════════════════════════

_fernet = None
_fernet_loaded = False


def _get_fernet():
    """Lazily initialise Fernet cipher from FERNET_KEY env var."""
    global _fernet, _fernet_loaded
    if _fernet_loaded:
        return _fernet
    _fernet_loaded = True

    key = settings.FERNET_KEY
    if not key:
        logger.warning(
            "FERNET_KEY not set — field-level encryption is DISABLED. "
            "Set FERNET_KEY in production!"
        )
        return None

    try:
        from cryptography.fernet import Fernet, InvalidToken  # noqa: F401
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        logger.info("Fernet encryption initialised.")
    except Exception as e:
        logger.error("Invalid FERNET_KEY — encryption disabled", error=str(e))
    return _fernet


def encrypt_field(value: str) -> str:
    """
    Encrypt a string field using Fernet (AES-128-CBC + HMAC-SHA256).
    Returns the original value unchanged if encryption is disabled.
    """
    cipher = _get_fernet()
    if cipher is None:
        return value
    try:
        return cipher.encrypt(value.encode()).decode()
    except Exception as e:
        logger.error("Encryption failed", error=str(e))
        return value


def decrypt_field(token: str) -> str:
    """
    Decrypt a Fernet-encrypted field.
    Returns the token unchanged if encryption is disabled.
    """
    cipher = _get_fernet()
    if cipher is None:
        return token
    try:
        from cryptography.fernet import InvalidToken
        return cipher.decrypt(token.encode()).decode()
    except Exception as e:
        logger.error("Decryption failed", error=str(e))
        return token


def hash_pii(value: str) -> str:
    """
    One-way SHA-256 hash for PII values that need lookup (e.g. email).
    Salted with the SECRET_KEY so rainbow tables won't work.
    """
    salt = settings.SECRET_KEY.encode()
    return hashlib.sha256(salt + value.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# 2. HTML Sanitisation (bleach)
# ══════════════════════════════════════════════════════════════════════════════

# Tags and attributes explicitly allowed through bleach
_ALLOWED_TAGS = [t.strip() for t in settings.ALLOWED_HTML_TAGS.split(",") if t.strip()]
_ALLOWED_ATTRS: dict = {
    "a": ["href", "title"],
}


def sanitize_html(raw_html: str, strip: bool = True) -> str:
    """
    Strip XSS vectors from raw HTML using bleach.

    Parameters
    ----------
    raw_html : HTML string from user input
    strip    : if True, strip disallowed tags entirely (safer).
               if False, escape them to HTML entities.

    Returns a clean, safe HTML string.
    """
    if not raw_html:
        return ""
    try:
        cleaned = bleach.clean(
            raw_html,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRS,
            strip=strip,
        )
        if len(cleaned) < len(raw_html):
            logger.warning(
                "HTML sanitisation stripped content",
                original_len=len(raw_html),
                clean_len=len(cleaned),
            )
        return cleaned
    except Exception as e:
        logger.error("HTML sanitisation failed", error=str(e))
        # Fail closed — return empty string rather than raw user content
        return ""


def sanitize_text(text: str, max_length: int = 10_000) -> str:
    """
    Light sanitisation for plain-text content:
      - Strip leading/trailing whitespace
      - Collapse multiple spaces
      - Enforce max length
    """
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text[:max_length]


# ══════════════════════════════════════════════════════════════════════════════
# 3. URL Validation
# ══════════════════════════════════════════════════════════════════════════════

_ALLOWED_SCHEMES = {"http", "https"}
_PRIVATE_RANGES  = re.compile(
    r"^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|127\.|::1)"
)


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate that a URL:
      - Uses http or https scheme
      - Is not pointing at a private IP range (SSRF prevention)
      - Is parseable

    Returns (is_valid: bool, reason: str)
    """
    if not url:
        return False, "URL is empty"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "URL is not parseable"

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False, f"Scheme '{parsed.scheme}' is not allowed (use http/https)"

    host = (parsed.hostname or "").lower()
    if _PRIVATE_RANGES.match(host):
        return False, f"Private/internal IP target rejected (SSRF prevention): {host}"

    if not host:
        return False, "URL has no hostname"

    return True, "OK"


# ══════════════════════════════════════════════════════════════════════════════
# 4. Audit Logging
# ══════════════════════════════════════════════════════════════════════════════

def audit_log(
    event:   str,
    user_id: Optional[str]  = None,
    ip:      Optional[str]  = None,
    details: Optional[dict] = None,
) -> None:
    """
    Write a security audit event to the structlog stream.
    In production this should also be pushed to the `audit_logs` DB table
    and/or shipped to your SIEM (e.g. AWS CloudWatch / Splunk).

    Parameters
    ----------
    event   : short event name, e.g. "LOGIN_SUCCESS", "SCAN_HIGH_RISK"
    user_id : authenticated user ID (or None for anonymous)
    ip      : client IP address
    details : arbitrary extra detail dict
    """
    logger.info(
        event=event,
        user_id=user_id or "anonymous",
        ip_address=ip or "unknown",
        timestamp=datetime.utcnow().isoformat(),
        **(details or {}),
    )


async def audit_log_db(
    event:   str,
    user_id: Optional[str]  = None,
    ip:      Optional[str]  = None,
    details: Optional[dict] = None,
    db=None,
) -> None:
    """Async version — also persists to the `audit_logs` table when `db` supplied."""
    audit_log(event, user_id, ip, details)  # always log to stream

    if db is None:
        return

    try:
        from app.models.db import AuditLog
        entry = AuditLog(
            event=event,
            user_id=user_id,
            ip_address=ip,
            details=details or {},
            created_at=datetime.utcnow(),
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        logger.warning("Audit log DB write failed", error=str(e))
