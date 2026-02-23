"""
Tests for security utilities: Fernet encryption, HTML sanitisation,
URL validation, and audit logging.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestHTMLSanitisation:
    """Test bleach-based HTML sanitiser."""

    def test_strips_script_tags(self):
        from app.services.security import sanitize_html
        dirty  = '<p>Hello</p><script>alert("xss")</script>'
        result = sanitize_html(dirty)
        assert "<script>" not in result
        assert "alert" not in result

    def test_strips_onclick_attr(self):
        from app.services.security import sanitize_html
        dirty  = '<a href="http://example.com" onclick="steal()">click</a>'
        result = sanitize_html(dirty)
        assert "onclick" not in result

    def test_allows_safe_tags(self):
        from app.services.security import sanitize_html
        safe   = "<p>Hello <b>world</b></p>"
        result = sanitize_html(safe)
        assert "Hello" in result

    def test_empty_string(self):
        from app.services.security import sanitize_html
        assert sanitize_html("") == ""

    def test_strips_iframe(self):
        from app.services.security import sanitize_html
        dirty  = '<iframe src="evil.com"></iframe>'
        result = sanitize_html(dirty)
        assert "<iframe" not in result


class TestTextSanitisation:
    def test_collapses_whitespace(self):
        from app.services.security import sanitize_text
        result = sanitize_text("hello   world\t\n!")
        assert "  " not in result

    def test_max_length(self):
        from app.services.security import sanitize_text
        long_text = "a" * 20_000
        result    = sanitize_text(long_text, max_length=1000)
        assert len(result) == 1000

    def test_empty_string(self):
        from app.services.security import sanitize_text
        assert sanitize_text("") == ""


class TestURLValidation:
    def test_valid_https(self):
        from app.services.security import validate_url
        valid, reason = validate_url("https://example.com")
        assert valid is True

    def test_valid_http(self):
        from app.services.security import validate_url
        valid, _ = validate_url("http://phishing-test.org/login")
        assert valid is True

    def test_rejects_ftp(self):
        from app.services.security import validate_url
        valid, reason = validate_url("ftp://files.example.com")
        assert valid is False
        assert "ftp" in reason.lower() or "not allowed" in reason.lower()

    def test_rejects_private_ip_ssrf(self):
        from app.services.security import validate_url
        valid, reason = validate_url("http://192.168.1.1/admin")
        assert valid is False
        assert "SSRF" in reason or "private" in reason.lower()

    def test_rejects_localhost(self):
        from app.services.security import validate_url
        valid, reason = validate_url("http://127.0.0.1:8080/internal")
        assert valid is False

    def test_empty_url(self):
        from app.services.security import validate_url
        valid, _ = validate_url("")
        assert valid is False


class TestFernetEncryption:
    """Test Fernet field-level encryption helpers."""

    def test_encrypt_decrypt_roundtrip(self):
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()

        with patch("app.services.security.settings") as mock_settings:
            mock_settings.FERNET_KEY = test_key
            mock_settings.SECRET_KEY = "test_secret"
            mock_settings.ALLOWED_HTML_TAGS = "a,b,i"

            # Reset cached fernet
            import app.services.security as sec
            sec._fernet        = None
            sec._fernet_loaded = False

            plaintext  = "sensitive-user-email@example.com"
            ciphertext = sec.encrypt_field(plaintext)
            recovered  = sec.decrypt_field(ciphertext)

            assert ciphertext != plaintext
            assert recovered  == plaintext

    def test_passthrough_when_no_key(self):
        with patch("app.services.security.settings") as mock_settings:
            mock_settings.FERNET_KEY       = ""
            mock_settings.SECRET_KEY       = "test_secret"
            mock_settings.ALLOWED_HTML_TAGS = "a,b"

            import app.services.security as sec
            sec._fernet        = None
            sec._fernet_loaded = False

            value  = "this-should-pass-through"
            result = sec.encrypt_field(value)
            assert result == value


class TestAuditLog:
    def test_logs_without_error(self, caplog):
        import logging
        from app.services.security import audit_log

        with caplog.at_level(logging.INFO):
            audit_log(
                event="TEST_EVENT",
                user_id="user_42",
                ip="1.2.3.4",
                details={"action": "scan"},
            )
        # Should not raise

    def test_hash_pii_is_deterministic(self):
        from app.services.security import hash_pii
        assert hash_pii("email@example.com") == hash_pii("email@example.com")

    def test_hash_pii_different_inputs(self):
        from app.services.security import hash_pii
        assert hash_pii("a@b.com") != hash_pii("c@d.com")
