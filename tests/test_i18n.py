import unittest
from unittest import mock

from dropzone47 import i18n
from dropzone47.i18n import t


class TestI18n(unittest.TestCase):
    def test_formats_placeholders(self) -> None:
        msg = t("downloading", title="Song", choice="audio")
        self.assertIn("Song", msg)
        self.assertIn("audio", msg)

    def test_unknown_key_returns_key(self) -> None:
        self.assertEqual(t("does_not_exist"), "does_not_exist")

    def test_spanish_catalog(self) -> None:
        with mock.patch.object(i18n, "BOT_LANG", "es"):
            self.assertEqual(t("cancel_requested"), "Cancelación solicitada. ⏹️")

    def test_unknown_language_falls_back_to_english(self) -> None:
        with mock.patch.object(i18n, "BOT_LANG", "fr"):
            self.assertEqual(t("btn_audio"), i18n.MESSAGES["en"]["btn_audio"])

    def test_catalogs_share_keys(self) -> None:
        self.assertEqual(set(i18n.MESSAGES["en"]), set(i18n.MESSAGES["es"]))


if __name__ == "__main__":
    unittest.main()
