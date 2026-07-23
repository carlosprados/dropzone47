import os
import tempfile
import unittest
from unittest import mock

from dropzone47.download import build_format_string, pick_files_for_choice
from dropzone47.utils import humanize_duration, is_valid_url, sizeof_fmt, user_download_dir


class TestUtils(unittest.TestCase):
    def test_humanize_duration(self) -> None:
        self.assertEqual(humanize_duration(None), "unknown")
        self.assertEqual(humanize_duration(65), "01:05")
        self.assertEqual(humanize_duration(3605), "01:00:05")

    def test_sizeof_fmt(self) -> None:
        self.assertEqual(sizeof_fmt(500), "500.0 B")
        self.assertEqual(sizeof_fmt(1536), "1.5 KB")
        self.assertEqual(sizeof_fmt(1048576), "1.0 MB")

    def test_build_format_string(self) -> None:
        self.assertEqual(build_format_string("audio", 720), "bestaudio/best")
        fmt = build_format_string("video", 480)
        self.assertIn("bestvideo[height<=480]", fmt)
        self.assertIn("+bestaudio", fmt)

    def test_pick_files_for_choice(self) -> None:
        files = [
            "/tmp/video-abc.mp4",
            "/tmp/video-abc.webm",
            "/tmp/audio-abc.mp3",
            "/tmp/other.txt",
        ]
        self.assertEqual(pick_files_for_choice(files, "audio"), ["/tmp/audio-abc.mp3"])
        self.assertEqual(pick_files_for_choice(files, "video"), ["/tmp/video-abc.mp4"])
        self.assertEqual(pick_files_for_choice(files, "noop"), [])

    def test_is_valid_url(self) -> None:
        self.assertTrue(is_valid_url("https://youtu.be/abc"))
        self.assertTrue(is_valid_url("http://example.com/x?y=1"))
        self.assertFalse(is_valid_url("not a url"))
        self.assertFalse(is_valid_url("ftp://host/file"))
        self.assertFalse(is_valid_url("youtube.com/watch?v=abc"))
        self.assertFalse(is_valid_url(""))

    def test_user_download_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("dropzone47.utils.DOWNLOAD_DIR", tmp):
                path = user_download_dir(4242)
            self.assertEqual(path, os.path.join(tmp, "4242"))
            self.assertTrue(os.path.isdir(path))


if __name__ == "__main__":
    unittest.main()

