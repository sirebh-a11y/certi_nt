from email.message import EmailMessage
import smtplib

from app.core.config import settings
from app.core.email.schemas import NotificationEmail
from app.core.logs.service import log_service


class EmailService:
    def send_notification(self, payload: NotificationEmail) -> None:
        message = EmailMessage()
        message["From"] = f"{settings.mail_from_name} <{settings.mail_from_email}>"
        message["To"] = payload.to_email
        message["Subject"] = payload.subject
        message.set_content(payload.body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if not settings.is_development and settings.smtp_tls:
                smtp.starttls()
            if not settings.is_development and settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)

        log_service.record("email", f"Notification sent to {payload.to_email}")


email_service = EmailService()
