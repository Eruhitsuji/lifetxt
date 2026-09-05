"""Tests for the CLI localization foundation (#631).

Covers locale normalization/precedence, the message catalog's missing-key
and English-fallback behavior, and that ``--lang`` never reaches a
downstream parser as an unrecognized argument.
"""

import unittest

from lifetxt import i18n
from lifetxt.entrypoint import _extract_lang_arg


class NormalizeLocaleTests(unittest.TestCase):
    def test_bare_ja_normalizes_to_ja(self):
        self.assertEqual(i18n.normalize_locale("ja"), "ja")

    def test_posix_style_ja_locale_normalizes_to_ja(self):
        self.assertEqual(i18n.normalize_locale("ja_JP"), "ja")
        self.assertEqual(i18n.normalize_locale("ja_JP.UTF-8"), "ja")

    def test_bcp47_style_ja_locale_normalizes_to_ja(self):
        self.assertEqual(i18n.normalize_locale("ja-JP"), "ja")

    def test_case_insensitive(self):
        self.assertEqual(i18n.normalize_locale("JA"), "ja")
        self.assertEqual(i18n.normalize_locale("En-US"), "en")

    def test_unsupported_locale_normalizes_to_none(self):
        self.assertIsNone(i18n.normalize_locale("fr_FR"))
        self.assertIsNone(i18n.normalize_locale("de"))

    def test_empty_or_none_normalizes_to_none(self):
        self.assertIsNone(i18n.normalize_locale(None))
        self.assertIsNone(i18n.normalize_locale(""))
        self.assertIsNone(i18n.normalize_locale("   "))

    def test_posix_c_and_posix_locale_normalize_to_none(self):
        self.assertIsNone(i18n.normalize_locale("C"))
        self.assertIsNone(i18n.normalize_locale("POSIX"))


class ResolveLocalePrecedenceTests(unittest.TestCase):
    def test_explicit_wins_over_everything(self):
        self.assertEqual(
            i18n.resolve_locale(explicit="ja", env={"LIFETXT_LANG": "en"}), "ja"
        )

    def test_env_var_used_when_no_explicit_value(self):
        self.assertEqual(
            i18n.resolve_locale(explicit=None, env={"LIFETXT_LANG": "ja"}), "ja"
        )

    def test_unsupported_explicit_value_falls_through_to_env(self):
        self.assertEqual(
            i18n.resolve_locale(explicit="fr", env={"LIFETXT_LANG": "ja"}), "ja"
        )

    def test_no_signal_at_all_falls_back_to_english_or_os_locale(self):
        # With no explicit value and no env var, resolution must still
        # return one of the supported locales (never raise, never blank).
        result = i18n.resolve_locale(explicit=None, env={})
        self.assertIn(result, i18n.SUPPORTED_LOCALES)


class LocaleContextTests(unittest.TestCase):
    def test_default_current_locale_is_english(self):
        self.assertEqual(i18n.current_locale(), i18n.DEFAULT_LOCALE)

    def test_locale_context_overrides_current_locale(self):
        with i18n.locale_context("ja"):
            self.assertEqual(i18n.current_locale(), "ja")
        self.assertEqual(i18n.current_locale(), i18n.DEFAULT_LOCALE)


class CatalogTests(unittest.TestCase):
    def test_missing_message_id_returns_the_id_itself_not_a_crash(self):
        self.assertEqual(i18n.translate("no.such.message.id"), "no.such.message.id")

    def test_missing_translation_for_a_known_id_falls_back_to_english(self):
        i18n.register_messages({"test.partial": {"en": "English only"}})
        with i18n.locale_context("ja"):
            self.assertEqual(i18n.translate("test.partial"), "English only")

    def test_registered_translation_is_returned_for_its_locale(self):
        i18n.register_messages({"test.greeting": {"en": "Hello", "ja": "こんにちは"}})
        self.assertEqual(i18n.translate("test.greeting", locale="en"), "Hello")
        self.assertEqual(i18n.translate("test.greeting", locale="ja"), "こんにちは")

    def test_format_kwargs_are_applied(self):
        i18n.register_messages({"test.count": {"en": "{n} item(s)"}})
        self.assertEqual(i18n.translate("test.count", locale="en", n=3), "3 item(s)")

    def test_format_mismatch_returns_unformatted_text_rather_than_raising(self):
        i18n.register_messages({"test.bad_format": {"en": "{missing}"}})
        self.assertEqual(i18n.translate("test.bad_format", locale="en"), "{missing}")

    def test_register_messages_merges_rather_than_replaces(self):
        i18n.register_messages({"test.merge": {"en": "English"}})
        i18n.register_messages({"test.merge": {"ja": "日本語"}})
        self.assertEqual(i18n.translate("test.merge", locale="en"), "English")
        self.assertEqual(i18n.translate("test.merge", locale="ja"), "日本語")


class ExtractLangArgTests(unittest.TestCase):
    def test_no_lang_flag_returns_argv_unchanged(self):
        cleaned, lang = _extract_lang_arg(["today"])
        self.assertEqual(cleaned, ["today"])
        self.assertIsNone(lang)

    def test_space_separated_lang_flag_is_removed_and_captured(self):
        cleaned, lang = _extract_lang_arg(["--lang", "ja", "today"])
        self.assertEqual(cleaned, ["today"])
        self.assertEqual(lang, "ja")

    def test_equals_form_lang_flag_is_removed_and_captured(self):
        cleaned, lang = _extract_lang_arg(["--lang=ja", "today"])
        self.assertEqual(cleaned, ["today"])
        self.assertEqual(lang, "ja")

    def test_missing_value_raises(self):
        with self.assertRaises(ValueError):
            _extract_lang_arg(["--lang"])


if __name__ == "__main__":
    unittest.main()
