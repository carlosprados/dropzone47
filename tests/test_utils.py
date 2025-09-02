import unittest

from dropzone47.download import build_format_string, pick_files_for_choice
from dropzone47.utils import humanize_duration, sizeof_fmt


class TestUtils(unittest.TestCase):
    def test_humanize_duration(self):
        self.assertEqual(humanize_duration(None), "unknown")
        self.assertEqual(humanize_duration(65), "01:05")
        self.assertEqual(humanize_duration(3605), "01:00:05")

    def test_sizeof_fmt(self):
        self.assertEqual(sizeof_fmt(500), "500.0 B")
        self.assertEqual(sizeof_fmt(1536), "1.5 KB")
        self.assertEqual(sizeof_fmt(1048576), "1.0 MB")

    def test_build_format_string(self):
        self.assertEqual(build_format_string("audio", 720), "bestaudio/best")
        fmt = build_format_string("video", 480)
        self.assertIn("bestvideo[height<=480]", fmt)
        self.assertIn("+bestaudio", fmt)

    def test_pick_files_for_choice(self):
        files = [
            "/tmp/video-abc.mp4",
            "/tmp/video-abc.webm",
            "/tmp/audio-abc.mp3",
            "/tmp/other.txt",
        ]
        self.assertEqual(pick_files_for_choice(files, "audio"), ["/tmp/audio-abc.mp3"])
        self.assertEqual(pick_files_for_choice(files, "video"), ["/tmp/video-abc.mp4"])
        self.assertEqual(pick_files_for_choice(files, "noop"), [])


if __name__ == "__main__":
    unittest.main()

