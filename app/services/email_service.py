"""
Outgoing email delivery over SMTP.

Design notes:
- All settings (host, port, credentials) are read from Flask config, which is
  populated exclusively from environment variables (see app/config.py).
- ``send()`` never raises: delivery problems are returned as an ``EmailResult``
  so callers (e.g. prayer scheduling) are never rolled back by an email failure.
- Credentials are never logged. smtplib debug output is never enabled because it
  prints the base64-encoded AUTH exchange. Recipient addresses are masked in logs.
"""
import logging
import smtplib
import socket
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from email_validator import validate_email, EmailNotValidError

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    """Outcome of an email delivery attempt."""
    status: str            # "sent", "disabled", "not_configured", "invalid_recipient", "failed"
    error: str = None      # short, credential-free error code (e.g. "authentication_failed")

    @property
    def sent(self):
        return self.status == "sent"


def mask_email(address):
    """Mask an email address for logs: 'john.doe@gmail.com' -> 'j***@gmail.com'."""
    if not address or "@" not in address:
        return "***"
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


def _build_ssl_context():
    """TLS context with certificate verification (uses certifi's CA bundle when available)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class EmailService:
    """Send transactional emails using the SMTP settings in the Flask config."""

    def __init__(self, config=None):
        if config is None:
            from flask import current_app
            config = current_app.config
        self.config = config

    # ------------------------------------------------------------------ helpers
    def _cfg(self, key, default=None):
        return self.config.get(key, default)

    def is_enabled(self):
        return bool(self._cfg("MAIL_ENABLED", False))

    def missing_settings(self):
        """Return the names of required settings that are not configured (never their values)."""
        missing = []
        if not self._cfg("MAIL_SERVER"):
            missing.append("MAIL_SERVER")
        if not self._cfg("MAIL_PORT"):
            missing.append("MAIL_PORT")
        if not self._cfg("MAIL_DEFAULT_SENDER"):
            missing.append("MAIL_DEFAULT_SENDER")
        if self._cfg("MAIL_USERNAME") and not self._cfg("MAIL_PASSWORD"):
            missing.append("MAIL_PASSWORD")
        return missing

    def _build_message(self, recipient, subject, text_body, html_body=None):
        sender = self._cfg("MAIL_DEFAULT_SENDER")
        sender_name = self._cfg("MAIL_SENDER_NAME") or ""
        reply_to = self._cfg("MAIL_REPLY_TO")
        sender_domain = sender.split("@", 1)[1] if "@" in sender else None

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((sender_name, sender)) if sender_name else sender
        msg["To"] = recipient
        if reply_to:
            msg["Reply-To"] = reply_to
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=sender_domain)
        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")
        return msg

    def _open_connection(self):
        host = self._cfg("MAIL_SERVER")
        port = int(self._cfg("MAIL_PORT"))
        timeout = int(self._cfg("MAIL_TIMEOUT", 10) or 10)
        context = _build_ssl_context()

        if self._cfg("MAIL_USE_SSL"):
            return smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)

        smtp = smtplib.SMTP(host, port, timeout=timeout)
        if self._cfg("MAIL_USE_TLS"):
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        return smtp

    # --------------------------------------------------------------- public API
    def send(self, to, subject, text_body, html_body=None):
        """
        Send an email. Never raises; returns an EmailResult describing the outcome.
        """
        override = self._cfg("MAIL_OVERRIDE_RECIPIENT")
        recipient = (override or to or "").strip()

        try:
            recipient = validate_email(recipient, check_deliverability=False).normalized
        except EmailNotValidError:
            logger.warning("Email not sent: invalid recipient address (%s).", mask_email(recipient))
            return EmailResult("invalid_recipient", "invalid_recipient")

        if not self.is_enabled():
            logger.info("Email delivery disabled (MAIL_ENABLED is off); skipped '%s' to %s.",
                        subject, mask_email(recipient))
            return EmailResult("disabled")

        missing = self.missing_settings()
        if missing:
            logger.error("Email not sent: missing mail settings %s.", ", ".join(missing))
            return EmailResult("not_configured", "not_configured")

        if override:
            logger.info("MAIL_OVERRIDE_RECIPIENT active: redirecting email for %s to %s.",
                        mask_email(to), mask_email(recipient))

        host = self._cfg("MAIL_SERVER")
        try:
            message = self._build_message(recipient, subject, text_body, html_body)
            with self._open_connection() as smtp:
                username = self._cfg("MAIL_USERNAME")
                if username:
                    smtp.login(username, self._cfg("MAIL_PASSWORD"))
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP authentication failed on %s (SMTP code %s). "
                         "Check MAIL_USERNAME / MAIL_PASSWORD.", host, exc.smtp_code)
            return EmailResult("failed", "authentication_failed")
        except smtplib.SMTPRecipientsRefused:
            logger.error("SMTP server %s refused recipient %s.", host, mask_email(recipient))
            return EmailResult("failed", "recipient_refused")
        except smtplib.SMTPSenderRefused as exc:
            logger.error("SMTP server %s refused the sender address (SMTP code %s).", host, exc.smtp_code)
            return EmailResult("failed", "sender_refused")
        except smtplib.SMTPException as exc:
            logger.error("SMTP error while sending to %s via %s: %s.",
                         mask_email(recipient), host, type(exc).__name__)
            return EmailResult("failed", "smtp_error")
        except ssl.SSLError as exc:
            logger.error("TLS/SSL error connecting to %s:%s: %s. Check MAIL_PORT / MAIL_USE_SSL / MAIL_USE_TLS.",
                         host, self._cfg("MAIL_PORT"), type(exc).__name__)
            return EmailResult("failed", "tls_error")
        except (socket.timeout, TimeoutError):
            logger.error("Timed out connecting to SMTP server %s:%s.", host, self._cfg("MAIL_PORT"))
            return EmailResult("failed", "timeout")
        except OSError as exc:
            logger.error("Could not connect to SMTP server %s:%s: %s.",
                         host, self._cfg("MAIL_PORT"), type(exc).__name__)
            return EmailResult("failed", "connection_error")
        except Exception as exc:  # defensive: an email must never break the caller
            logger.exception("Unexpected error while sending email to %s: %s.",
                             mask_email(recipient), type(exc).__name__)
            return EmailResult("failed", "unexpected_error")

        logger.info("Email '%s' sent to %s.", subject, mask_email(recipient))
        return EmailResult("sent")
