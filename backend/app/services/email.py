"""Outbound email.

Only transactional security mail: password resets. Nothing about a user's
finances is ever emailed.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional
from urllib.parse import quote

from app.core.config import settings

logger = logging.getLogger("bearly.email")


class EmailError(RuntimeError):
    pass


def _send(to: str, subject: str, text: str, html: Optional[str] = None) -> None:
    if not settings.email_configured:
        raise EmailError("SMTP is not configured (BEARLY_SMTP_HOST is empty)")

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=15) as server:
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                if settings.smtp_starttls:
                    server.starttls(context=context)
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
    except Exception as exc:  # noqa: BLE001
        # The address is deliberately not logged.
        raise EmailError("SMTP delivery failed: %s" % type(exc).__name__) from exc


def send_password_reset(to: str, token: str) -> None:
    link = "%s/reset-password?token=%s" % (settings.app_base_url.rstrip("/"), quote(token))
    minutes = settings.password_reset_minutes

    text = (
        "Someone asked to reset the password for your Bearly account.\n\n"
        "Use this link within %d minutes:\n%s\n\n"
        "If this wasn't you, you can ignore this email — your password will not change.\n"
    ) % (minutes, link)

    html = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'max-width:520px;margin:0 auto;padding:32px 24px;color:#0b0b0b">'
        '<p style="font-size:17px;font-weight:600;margin:0 0 16px">Reset your Bearly password</p>'
        '<p style="font-size:14px;line-height:1.6;color:#52514e;margin:0 0 24px">'
        "Someone asked to reset the password for your account. This link works for the "
        "next %d minutes.</p>"
        '<p style="margin:0 0 24px"><a href="%s" '
        'style="display:inline-block;background:#0e6d5f;color:#fff;text-decoration:none;'
        'padding:11px 20px;border-radius:8px;font-size:14px;font-weight:500">'
        "Choose a new password</a></p>"
        '<p style="font-size:13px;line-height:1.6;color:#898781;margin:0">'
        "If this wasn't you, ignore this email — nothing will change.</p></div>"
    ) % (minutes, link)

    _send(to, "Reset your Bearly password", text, html)
    logger.info("Password reset email dispatched")  # no address, no token
