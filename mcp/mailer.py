"""Outgoing account emails over SMTP; development mode may log links instead."""

import asyncio
import os
import smtplib
from email.message import EmailMessage

from app_logging import get_logger, is_dev_env

SUBJECTS = {
    "register": "szukaj.dom — aktywuj konto",
    "reset": "szukaj.dom — potwierdź zmianę hasła",
}
INTROS = {
    "register": "Ktoś (pewnie Ty) zakłada konto w szukaj.dom na ten adres email.",
    "reset": "Ktoś (pewnie Ty) ustawił nowe hasło do konta w szukaj.dom.",
}


class MailerUnavailable(RuntimeError):
    pass


def compose_message(sender: str, recipient: str, purpose: str, link: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = SUBJECTS[purpose]
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"{INTROS[purpose]}\n\n"
        f"Otwórz link i kliknij „Potwierdź”, żeby to aktywować (ważny 60 minut, jednorazowy):\n{link}\n\n"
        "Jeśli to nie Ty, zignoruj tę wiadomość — nic się nie zmieni.\n"
    )
    return message


class SmtpMailer:
    def __init__(self, host=None, port=None, user=None, password=None, sender=None, starttls=None, app_env=None):
        self.host = os.getenv("SMTP_HOST", "") if host is None else host
        self.port = int(os.getenv("SMTP_PORT") or "587") if port is None else port
        self.user = os.getenv("SMTP_USER", "") if user is None else user
        self.password = os.getenv("SMTP_PASSWORD", "") if password is None else password
        self.sender = (os.getenv("SMTP_FROM") or self.user or "szukaj@localhost") if sender is None else sender
        self.starttls = (os.getenv("SMTP_STARTTLS", "true").strip().lower() != "false") if starttls is None else starttls
        self.dev_mode = is_dev_env(app_env)

    @property
    def available(self) -> bool:
        return bool(self.host) or self.dev_mode

    def _send(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
            if self.starttls:
                smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(message)

    async def send_link(self, recipient: str, purpose: str, link: str) -> None:
        if not self.host:
            if self.dev_mode:
                get_logger().warning("SMTP not configured; %s link for %s: %s", purpose, recipient, link)
                return
            raise MailerUnavailable("SMTP_HOST is not configured")
        try:
            await asyncio.to_thread(self._send, compose_message(self.sender, recipient, purpose, link))
        except (OSError, smtplib.SMTPException) as exc:
            raise MailerUnavailable(type(exc).__name__) from exc
