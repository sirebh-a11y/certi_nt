import unittest
from io import BytesIO
import smtplib
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.core.email.schemas import NotificationEmail
from app.core.email.service import EmailNotSubmitted, EmailService
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

    def test_tracked_smtp_uses_actual_data_acceptance_boundary(self):
        # Exercise the real smtplib conversation against a scripted socket. No network.
        config = _email_config(always_cc_email=None)
        config.smtp_tls, config.smtp_user = False, ''
        payload = NotificationEmail(to_email='quality@example.test', subject='Test', body='test')
        cases = [
            ('connection accepted but no greeting', [], EmailNotSubmitted),
            ('disconnect before recipient response', [220,250,250], EmailNotSubmitted),
            ('recipient refused', [220,250,250,550,250,221], EmailNotSubmitted),
            ('disconnect waiting for DATA permission', [220,250,250,250], EmailNotSubmitted),
            ('body sent but no final response', [220,250,250,250,354], smtplib.SMTPServerDisconnected),
            ('body explicitly refused', [220,250,250,250,354,554,250,221], EmailNotSubmitted),
            ('accepted even if QUIT fails', [220,250,250,250,354,250,500], None),
            ('normal acceptance', [220,250,250,250,354,250,221], None),
        ]
        for name, replies, error in cases:
            sock = Mock()
            sock.makefile.return_value = BytesIO(b''.join(f'{n} response\r\n'.encode() for n in replies))
            with self.subTest(name=name), patch.object(smtplib.SMTP, '_get_socket', return_value=sock):
                if error:
                    with self.assertRaises(error):
                        EmailService()._send_with_config(payload, config, timeout=10, track_delivery=True)
                else:
                    EmailService()._send_with_config(payload, config, timeout=10, track_delivery=True)

    def test_tracked_smtp_login_and_tls_failures_are_safe_to_retry(self):
        config = _email_config(always_cc_email=None)
        payload = NotificationEmail(to_email='quality@example.test', subject='Test', body='test')
        for step in ('starttls','login'):
            config.smtp_tls = step=='starttls'
            sock = Mock()
            sock.makefile.return_value = BytesIO(b'220 hello\r\n221 bye\r\n')
            with self.subTest(step=step), patch.object(smtplib.SMTP, '_get_socket', return_value=sock), \
                    patch.object(smtplib.SMTP, step, side_effect=smtplib.SMTPAuthenticationError(535,b'refused')), \
                    patch.object(smtplib.SMTP, 'send_message') as submit:
                with self.assertRaises(EmailNotSubmitted):
                    EmailService()._send_with_config(payload, config, timeout=10, track_delivery=True)
                submit.assert_not_called()

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
