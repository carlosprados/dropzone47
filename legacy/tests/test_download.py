import os
import tempfile
import unittest
from unittest import mock

from dropzone47 import download
from dropzone47.download import (
    build_outtmpl,
    build_ydl_progress_opts,
    find_output_files,
    video_height_ladder,
)


def _touch(path: str) -> None:
    with open(path, "w") as f:
        f.write("x")


class TestFindOutputFiles(unittest.TestCase):
    def test_scopes_to_dir_and_id_and_skips_temp(self) -> None:
        with tempfile.TemporaryDirectory() as dest:
            # Matching final artifacts for the target id.
            _touch(os.path.join(dest, "clip-VID123.mp4"))
            _touch(os.path.join(dest, "clip-VID123.mp3"))
            # Partial/temp files for the same id must be ignored.
            _touch(os.path.join(dest, "clip-VID123.mp4.part"))
            _touch(os.path.join(dest, "clip-VID123.f137.ytdl"))
            # A different video id must not be picked up.
            _touch(os.path.join(dest, "other-OTHER99.mp4"))

            found = find_output_files("VID123", dest)

            self.assertEqual(
                found,
                [
                    os.path.join(dest, "clip-VID123.mp3"),
                    os.path.join(dest, "clip-VID123.mp4"),
                ],
            )

    def test_isolated_per_user_dir(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            user_a = os.path.join(root, "1")
            user_b = os.path.join(root, "2")
            os.makedirs(user_a)
            os.makedirs(user_b)
            _touch(os.path.join(user_a, "clip-SAME.mp4"))
            _touch(os.path.join(user_b, "clip-SAME.mp4"))

            self.assertEqual(
                find_output_files("SAME", user_a), [os.path.join(user_a, "clip-SAME.mp4")]
            )
            self.assertEqual(
                find_output_files("SAME", user_b), [os.path.join(user_b, "clip-SAME.mp4")]
            )


class TestVideoHeightLadder(unittest.TestCase):
    def test_descending_and_capped(self) -> None:
        with mock.patch.object(download, "VIDEO_HEIGHT_LADDER", [720, 480, 360, 240]):
            self.assertEqual(video_height_ladder(720), [720, 480, 360, 240])
            # Rungs above the cap are dropped.
            self.assertEqual(video_height_ladder(480), [480, 360, 240])

    def test_always_includes_max_height(self) -> None:
        with mock.patch.object(download, "VIDEO_HEIGHT_LADDER", [480, 360]):
            # 1080 is not in the ladder but must still be the first rung.
            self.assertEqual(video_height_ladder(1080), [1080, 480, 360])

    def test_empty_ladder_falls_back_to_max(self) -> None:
        with mock.patch.object(download, "VIDEO_HEIGHT_LADDER", []):
            self.assertEqual(video_height_ladder(720), [720])


class TestYdlOpts(unittest.TestCase):
    def test_outtmpl_under_dest_dir(self) -> None:
        tmpl = build_outtmpl("/data/99")
        self.assertTrue(tmpl.startswith("/data/99/"))
        self.assertIn("%(id)s", tmpl)

    def test_audio_kbps_and_noplaylist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Keep the yt-dlp cache dir (rooted at DOWNLOAD_DIR) inside the temp dir.
            with mock.patch.object(download, "DOWNLOAD_DIR", tmp):
                opts = build_ydl_progress_opts(
                    "audio",
                    max_height=720,
                    progress_hook=lambda d: None,
                    dest_dir=os.path.join(tmp, "7"),
                    audio_kbps=96,
                )
            self.assertTrue(opts["noplaylist"])
            pp = [p for p in opts["postprocessors"] if p["key"] == "FFmpegExtractAudio"]
            self.assertEqual(pp[0]["preferredquality"], "96")

    def test_video_has_no_audio_postprocessor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(download, "DOWNLOAD_DIR", tmp):
                opts = build_ydl_progress_opts(
                    "video",
                    max_height=480,
                    progress_hook=lambda d: None,
                    dest_dir=os.path.join(tmp, "7"),
                )
            self.assertNotIn("postprocessors", opts)
            self.assertEqual(opts["merge_output_format"], "mp4")


if __name__ == "__main__":
    unittest.main()
