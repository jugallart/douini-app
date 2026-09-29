from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from douini.settings import settings

logger = logging.getLogger(__name__)


def send_verification_email(email: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?{urlencode({'token': token})}"

    if not settings.SMTP_HOST:
        logger.info("DEV MODE — verification link: %s", link)
        return

    msg = EmailMessage()
    msg["Subject"] = "Confirmez votre adresse email — Douini Run"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Confirmez votre adresse email pour acceder a Douini Run :\n\n{link}\n\n"
        "Ce lien est valable 30 minutes.\n\nL'equipe Douini Run\n"
    )
    _smtp_send(msg)


def send_reset_email(email: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?{urlencode({'token': token})}"

    if not settings.SMTP_HOST:
        logger.info("DEV MODE — reset link: %s", link)
        return

    msg = EmailMessage()
    msg["Subject"] = "Reinitialisation de votre mot de passe — Douini Run"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Vous avez demande a reinitialiser votre mot de passe :\n\n{link}\n\n"
        "Ce lien est valable 30 minutes.\n\nL'equipe Douini Run\n"
    )
    _smtp_send(msg)


def _smtp_send(message: EmailMessage) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls(context=context)
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message)
