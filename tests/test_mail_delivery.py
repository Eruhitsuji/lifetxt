import io
import os
import unittest
from unittest import mock

from lifetxt.mail_delivery import (
    MailDeliveryError,
    append_local_file,
    resolve_smtp_credentials,
    send_slack_webhook,
    send_smtp_text,
    split_email_addresses,
)


class SplitEmailAddressesTests(unittest.TestCase):
    def test_splits_comma_separated_string(self):
        self.assertEqual(
            split_email_addresses("a@example.com, b@example.com"),
            ["a@example.com", "b@example.com"],
        )

    def test_flattens_list(self):
        self.assertEqual(
            split_email_addresses(["a@example.com", "b@example.com, c@example.com"]),
            ["a@example.com", "b@example.com", "c@example.com"],
        )

    def test_empty_value_yields_empty_list(self):
        self.assertEqual(split_email_addresses(None), [])


class ResolveSmtpCredentialsTests(unittest.TestCase):
    def test_missing_host_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MailDeliveryError):
                resolve_smtp_credentials("H", "U", "P")

    def test_missing_credentials_raises(self):
        with mock.patch.dict(os.environ, {"H": "smtp.example.com"}, clear=True):
            with self.assertRaises(MailDeliveryError):
                resolve_smtp_credentials("H", "U", "P")

    def test_complete_credentials_return(self):
        with mock.patch.dict(
            os.environ,
            {"H": "smtp.example.com", "U": "me", "P": "secret"},
            clear=True,
        ):
            self.assertEqual(
                resolve_smtp_credentials("H", "U", "P"),
                ("smtp.example.com", "me", "secret"),
            )


class SendSmtpTextTests(unittest.TestCase):
    def test_dry_run_never_touches_smtplib(self):
        output = io.StringIO()
        with mock.patch("smtplib.SMTP") as smtp_cls:
            result = send_smtp_text(
                "subject", "body", "a@example.com", dry_run=True, output=output
            )
        self.assertTrue(result)
        smtp_cls.assert_not_called()
        self.assertIn("[dry-run]", output.getvalue())

    def test_no_recipients_raises(self):
        with self.assertRaises(MailDeliveryError):
            send_smtp_text("subject", "body", [], dry_run=True)

    def test_real_send_uses_starttls_and_login(self):
        smtp_instance = mock.MagicMock()
        smtp_instance.__enter__.return_value = smtp_instance
        with mock.patch("smtplib.SMTP", return_value=smtp_instance) as smtp_cls:
            with mock.patch.dict(
                os.environ,
                {"H": "smtp.example.com", "U": "me", "P": "secret"},
                clear=True,
            ):
                send_smtp_text(
                    "subject",
                    "body",
                    ["a@example.com"],
                    host_env="H",
                    user_env="U",
                    pass_env="P",
                )
        smtp_cls.assert_called_once_with("smtp.example.com", timeout=10)
        smtp_instance.starttls.assert_called_once()
        smtp_instance.login.assert_called_once_with("me", "secret")
        smtp_instance.sendmail.assert_called_once()


class SendSlackWebhookTests(unittest.TestCase):
    def test_dry_run_never_opens_url(self):
        with mock.patch("urllib.request.urlopen") as urlopen_mock:
            result = send_slack_webhook("hello", "SLACK_URL", dry_run=True)
        self.assertTrue(result)
        urlopen_mock.assert_not_called()

    def test_missing_env_raises_when_not_dry_run(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MailDeliveryError):
                send_slack_webhook("hello", "SLACK_URL", dry_run=False)


class AppendLocalFileTests(unittest.TestCase):
    def test_dry_run_does_not_write(self, tmp_path=None):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "digest.md")
            append_local_file(path, "hello", dry_run=True)
            self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
