import os
import tempfile
import unittest
from unittest import mock

from dropzone47 import session


class TestSessionStore(unittest.TestCase):
    def test_roundtrip_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "sessions.sqlite3")
            with mock.patch.object(session, "_DB_PATH", db):
                self.assertIsNone(session.load_session(42))

                session.save_session(42, {"url": "u", "title": "T", "id": "vid"})
                loaded = session.load_session(42)
                self.assertEqual(loaded, {"url": "u", "title": "T", "id": "vid"})

                # Upsert overwrites the previous row.
                session.save_session(42, {"url": "u2", "title": "T2", "id": "vid2"})
                updated = session.load_session(42)
                assert updated is not None
                self.assertEqual(updated["id"], "vid2")

                session.delete_session(42)
                self.assertIsNone(session.load_session(42))


if __name__ == "__main__":
    unittest.main()
