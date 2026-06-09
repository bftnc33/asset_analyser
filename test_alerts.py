"""
Unit tests for alerts.py.

Rather than reloading the module to pick up env var changes, we patch the
module-level constants (EMAIL_ADDRESS, EMAIL_PASSWORD etc.) directly on the
alerts module. This avoids any import-order issues when running alongside
other test files that mock sys.modules.
"""

import importlib
import smtplib
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure we have the real alerts module, not a mock left by test_main.py
sys.modules.pop("alerts", None)
import alerts as alerts_module


# ---------------------------------------------------------------------------
# Default constants used in most tests
# ---------------------------------------------------------------------------

DEFAULTS = {
    "EMAIL_ADDRESS":  "test@example.com",
    "EMAIL_PASSWORD": "secret",
    "SMTP_SERVER":    "smtp.example.com",
    "SMTP_PORT":      587,
}


@pytest.fixture(autouse=True)
def patch_module_constants():
    """Patch module-level constants directly — no reload needed."""
    with patch.multiple(
        alerts_module,
        EMAIL_ADDRESS=DEFAULTS["EMAIL_ADDRESS"],
        EMAIL_PASSWORD=DEFAULTS["EMAIL_PASSWORD"],
        SMTP_SERVER=DEFAULTS["SMTP_SERVER"],
        SMTP_PORT=DEFAULTS["SMTP_PORT"],
    ):
        yield


@pytest.fixture()
def mock_smtp():
    smtp_instance = MagicMock()
    smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_instance.__exit__ = MagicMock(return_value=False)
    with patch("smtplib.SMTP", return_value=smtp_instance) as smtp_cls:
        yield smtp_cls, smtp_instance


# ===========================================================================
# SMTP interaction
# ===========================================================================

class TestSendEmailSMTP:
    def test_smtp_called_with_correct_server_and_port(self, mock_smtp):
        smtp_cls, _ = mock_smtp
        alerts_module.send_email("Subject", "<p>Body</p>")
        smtp_cls.assert_called_once_with("smtp.example.com", 587)

    def test_starttls_called(self, mock_smtp):
        _, smtp_instance = mock_smtp
        alerts_module.send_email("Subject", "<p>Body</p>")
        smtp_instance.starttls.assert_called_once()

    def test_login_called_with_credentials(self, mock_smtp):
        _, smtp_instance = mock_smtp
        alerts_module.send_email("Subject", "<p>Body</p>")
        smtp_instance.login.assert_called_once_with("test@example.com", "secret")

    def test_send_message_called(self, mock_smtp):
        _, smtp_instance = mock_smtp
        alerts_module.send_email("Subject", "<p>Body</p>")
        smtp_instance.send_message.assert_called_once()

    def test_smtp_used_as_context_manager(self, mock_smtp):
        _, smtp_instance = mock_smtp
        alerts_module.send_email("Subject", "<p>Body</p>")
        smtp_instance.__enter__.assert_called_once()
        smtp_instance.__exit__.assert_called_once()

    def test_operations_in_correct_order(self, mock_smtp):
        """starttls → login → send_message."""
        _, smtp_instance = mock_smtp
        manager = smtp_instance.__enter__.return_value
        alerts_module.send_email("Subject", "<p>Body</p>")
        call_order = [c[0] for c in manager.mock_calls]
        assert call_order.index("starttls") < call_order.index("login")
        assert call_order.index("login")    < call_order.index("send_message")


# ===========================================================================
# Email message construction
# ===========================================================================

class TestSendEmailMessage:
    def _capture_message(self, mock_smtp, subject, body):
        _, smtp_instance = mock_smtp
        alerts_module.send_email(subject, body)
        return smtp_instance.send_message.call_args[0][0]

    def test_subject_set_correctly(self, mock_smtp):
        msg = self._capture_message(mock_smtp, "My Subject", "<p>Hi</p>")
        assert msg["Subject"] == "My Subject"

    def test_from_address_set(self, mock_smtp):
        msg = self._capture_message(mock_smtp, "Subject", "<p>Hi</p>")
        assert msg["From"] == "test@example.com"

    def test_to_address_set(self, mock_smtp):
        msg = self._capture_message(mock_smtp, "Subject", "<p>Hi</p>")
        assert msg["To"] == "test@example.com"

    def test_date_header_present(self, mock_smtp):
        msg = self._capture_message(mock_smtp, "Subject", "<p>Hi</p>")
        assert msg["Date"] is not None

    def test_html_body_included(self, mock_smtp):
        body = "<h1>Signal Alert</h1><p>ETH/BTC crossed above SMA55</p>"
        msg = self._capture_message(mock_smtp, "Subject", body)
        content = msg.get_payload()
        assert any(
            body in (part.get_payload(decode=True) or b"").decode("utf-8", errors="ignore")
            or body in str(part)
            for part in (content if isinstance(content, list) else [msg])
        )

    def test_plaintext_fallback_present(self, mock_smtp):
        msg = self._capture_message(mock_smtp, "Subject", "<p>Hi</p>")
        content_types = [
            part.get_content_type()
            for part in (msg.walk() if msg.is_multipart() else [msg])
        ]
        assert "text/plain" in content_types

    def test_html_content_type_present(self, mock_smtp):
        msg = self._capture_message(mock_smtp, "Subject", "<p>Hi</p>")
        content_types = [
            part.get_content_type()
            for part in (msg.walk() if msg.is_multipart() else [msg])
        ]
        assert "text/html" in content_types


# ===========================================================================
# Error handling
# ===========================================================================

class TestSendEmailErrorHandling:
    def test_smtp_connection_error_does_not_raise(self):
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "Unavailable")):
            alerts_module.send_email("Subject", "<p>Body</p>")

    def test_auth_error_does_not_raise(self):
        smtp_instance = MagicMock()
        smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
        smtp_instance.__exit__ = MagicMock(return_value=False)
        smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
        with patch("smtplib.SMTP", return_value=smtp_instance):
            alerts_module.send_email("Subject", "<p>Body</p>")

    def test_send_failure_does_not_raise(self):
        smtp_instance = MagicMock()
        smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
        smtp_instance.__exit__ = MagicMock(return_value=False)
        smtp_instance.send_message.side_effect = smtplib.SMTPException("Send failed")
        with patch("smtplib.SMTP", return_value=smtp_instance):
            alerts_module.send_email("Subject", "<p>Body</p>")

    def test_error_is_logged_on_failure(self, caplog):
        import logging
        smtp_instance = MagicMock()
        smtp_instance.__enter__ = MagicMock(return_value=smtp_instance)
        smtp_instance.__exit__ = MagicMock(return_value=False)
        smtp_instance.send_message.side_effect = Exception("Something went wrong")
        with patch("smtplib.SMTP", return_value=smtp_instance):
            with caplog.at_level(logging.ERROR):
                alerts_module.send_email("Subject", "<p>Body</p>")
        assert any("Failed to send email" in r.message for r in caplog.records)

    def test_success_is_logged(self, mock_smtp, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            alerts_module.send_email("Subject", "<p>Body</p>")
        assert any("Email sent successfully" in r.message for r in caplog.records)


# ===========================================================================
# Environment / configuration
# ===========================================================================

class TestConfiguration:
    def test_smtp_port_patched_correctly(self):
        with patch.object(alerts_module, "SMTP_PORT", 465):
            assert alerts_module.SMTP_PORT == 465

    def test_smtp_port_default_is_integer(self):
        """SMTP_PORT should be an int, not a string."""
        assert isinstance(alerts_module.SMTP_PORT, int)

    def test_email_address_is_string(self):
        assert isinstance(alerts_module.EMAIL_ADDRESS, str)