import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from app.core.email.schemas import NotificationEmail
from app.core.email.service import EmailService
from app.core.email.settings_schemas import EmailSettingsUpdateRequest
from app.core.email.settings_service import get_effective_email_settings
from app.modules.acquisition.service import _send_autonomous_run_notification


def _email_config(*, always_cc_email: str | None):
    return SimpleNamespace(
        smtp_host="mail.example.test",
        smtp_port=587,
        smtp_user="sender@example.test",
        smtp_password="secret",
        smtp_tls=True,
        mail_from_email="sender@example.test",
        mail_from_name="CERTI_nt",
        mail_always_cc_email=always_cc_email,
        acquisition_notification_admin_email=None,
    )


def _settings_payload(**overrides):
    values = {
        "smtp_host": "mail.example.test",
        "smtp_port": 587,
        "smtp_user": "sender@example.test",
        "smtp_password": None,
        "smtp_tls": True,
        "mail_from_email": "sender@example.test",
        "mail_from_name": "CERTI_nt",
        "mail_always_cc_email": "archive@example.test",
        "acquisition_notification_admin_email": None,
    }
    values.update(overrides)
    return values


class EmailAlwaysCcTest(unittest.TestCase):
    def _send_message(self, *, to_email: str, always_cc_email: str | None):
        service = EmailService()
        payload = NotificationEmail(to_email=to_email, subject="Test", body="Corpo")
        with patch("app.core.email.service.smtplib.SMTP") as smtp_class:
            smtp = smtp_class.return_value.__enter__.return_value
            service._send_with_config(payload, _email_config(always_cc_email=always_cc_email))
            return smtp.send_message.call_args.args[0], smtp

    def test_global_cc_is_added_to_every_message(self):
        message, smtp = self._send_message(
            to_email="user@example.test",
            always_cc_email="archive@example.test",
        )

        self.assertEqual(message["To"], "user@example.test")
        self.assertEqual(message["Cc"], "archive@example.test")
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with("sender@example.test", "secret")
        smtp.send_message.assert_called_once_with(message)

    def test_empty_global_cc_preserves_current_behavior(self):
        message, _smtp = self._send_message(to_email="user@example.test", always_cc_email=None)

        self.assertIsNone(message["Cc"])

    def test_cc_is_not_duplicated_when_it_matches_to_case_insensitively(self):
        message, _smtp = self._send_message(
            to_email="Archive@Example.test",
            always_cc_email="archive@example.test",
        )

        self.assertEqual(message["To"], "Archive@Example.test")
        self.assertIsNone(message["Cc"])

    def test_settings_schema_accepts_and_normalizes_global_cc(self):
        payload = EmailSettingsUpdateRequest(**_settings_payload(mail_always_cc_email="  archive@example.test  "))

        self.assertEqual(str(payload.mail_always_cc_email), "archive@example.test")

    def test_settings_schema_rejects_invalid_global_cc(self):
        with self.assertRaises(ValidationError):
            EmailSettingsUpdateRequest(**_settings_payload(mail_always_cc_email="not-an-email"))

    def test_database_email_settings_include_global_cc(self):
        row = SimpleNamespace(
            smtp_host="db-mail.example.test",
            smtp_port=25,
            smtp_user="db-user",
            smtp_password_encrypted=None,
            smtp_tls=False,
            mail_from_email="db@example.test",
            mail_from_name="DB mail",
            mail_always_cc_email="db-archive@example.test",
            acquisition_notification_admin_email=None,
        )
        with patch("app.core.email.settings_service._settings_row", return_value=row):
            config = get_effective_email_settings(SimpleNamespace())

        self.assertEqual(config.source, "db")
        self.assertEqual(config.mail_always_cc_email, "db-archive@example.test")

    def test_ai_admin_recipient_is_skipped_when_already_global_cc(self):
        run = SimpleNamespace(
            id=7,
            notification_email="user@example.test",
            admin_notification_email="archive@example.test",
            ddt_document_ids="[]",
            certificate_document_ids="[]",
            totale_documenti_certificato=0,
            righe_create=1,
            righe_processate=1,
            totale_righe_target=1,
            match_proposti=1,
            chimica_rilevata=1,
            proprieta_rilevate=1,
            note_rilevate=1,
            ultimo_errore=None,
        )
        with (
            patch(
                "app.modules.acquisition.service.get_effective_email_settings",
                return_value=_email_config(always_cc_email="ARCHIVE@example.test"),
            ),
            patch("app.modules.acquisition.service.email_service.send_notification") as send_notification,
        ):
            _send_autonomous_run_notification(
                db=SimpleNamespace(),
                run=run,
                actor_email="USER@example.test",
                success=True,
            )

        send_notification.assert_called_once()
        payload = send_notification.call_args.args[0]
        self.assertEqual(payload.to_email, "user@example.test")


if __name__ == "__main__":
    unittest.main()
