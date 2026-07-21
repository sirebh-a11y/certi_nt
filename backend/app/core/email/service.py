from email.message import EmailMessage
import smtplib

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.email.schemas import NotificationEmail
from app.core.email.settings_service import get_effective_email_settings
from app.core.logs.service import log_service


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

    def _send_with_config(self, payload: NotificationEmail, config) -> None:
        message = EmailMessage()
        message["From"] = f"{config.mail_from_name} <{config.mail_from_email}>"
        message["To"] = payload.to_email
        cc_email = (config.mail_always_cc_email or "").strip()
        if cc_email and cc_email.casefold() != payload.to_email.casefold():
            message["Cc"] = cc_email
        message["Subject"] = payload.subject
        message.set_content(payload.body)

        with smtplib.SMTP(config.smtp_host, config.smtp_port) as smtp:
            if config.smtp_tls:
                smtp.starttls()
            if config.smtp_user:
                smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(message)

        log_service.record("email", f"Notification sent to {payload.to_email}")


email_service = EmailService()
