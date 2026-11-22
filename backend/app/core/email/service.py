from email.message import EmailMessage
import smtplib

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.email.schemas import NotificationEmail
from app.core.email.settings_service import get_effective_email_settings
from app.core.logs.service import log_service


class EmailNotSubmitted(Exception):
    """SMTP could not have accepted the message; a later attempt is safe."""


class _TrackedSMTP(smtplib.SMTP):
    # smtplib waits for 354 before transmitting the body. A dropped connection
    # during EHLO, TLS, AUTH, MAIL or RCPT therefore cannot cause a duplicate.
    body_possible = False

    def data(self, msg):
        self._awaiting_data = True
        try:
            return super().data(msg)
        finally:
            self._awaiting_data = False

    def getreply(self):
        code, reply = super().getreply()
        if getattr(self, '_awaiting_data', False) and code == 354:
            self.body_possible = True
        return code, reply


class EmailService:
    def send_notification(self, payload: NotificationEmail, db: Session | None = None) -> None:
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            config = get_effective_email_settings(db)
            self._send_with_config(payload, config)
        finally:
            if close_db:
                db.close()

    def _send_with_config(self, payload: NotificationEmail, config, *, timeout=None, track_delivery=False) -> None:
        message = EmailMessage()
        message["From"] = f"{config.mail_from_name} <{config.mail_from_email}>"
        message["To"] = payload.to_email
        cc_email = (config.mail_always_cc_email or "").strip()
        if cc_email and cc_email.casefold() != payload.to_email.casefold():
            message["Cc"] = cc_email
        message["Subject"] = payload.subject
        message.set_content(payload.body)

        transport = _TrackedSMTP if track_delivery else smtplib.SMTP
        smtp = None
        accepted = False
        try:
            with transport(config.smtp_host, config.smtp_port, **({'timeout': timeout} if timeout is not None else {})) as smtp:
                if config.smtp_tls:
                    smtp.starttls()
                if config.smtp_user:
                    smtp.login(config.smtp_user, config.smtp_password)
                smtp.send_message(message)
                accepted = True
        except Exception as exc:
            if not track_delivery:
                raise  # Preserve the error contract for all other mail.
            if not accepted:
                if (smtp is None or not smtp.body_possible or isinstance(exc, (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused))
                    or isinstance(exc, smtplib.SMTPDataError) and 400 <= exc.smtp_code < 600):
                    raise EmailNotSubmitted() from exc
                raise  # A disconnect during DATA may follow acceptance. Never blindly retry.
            # QUIT failed after SMTP explicitly accepted the message.

        log_service.record("email", f"Notification sent to {payload.to_email}")


email_service = EmailService()
