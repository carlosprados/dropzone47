import unittest

from dropzone47.ratelimit import RateLimiter


class TestRateLimiter(unittest.TestCase):
    def test_allows_up_to_quota_then_blocks(self) -> None:
        rl = RateLimiter(max_events=2, window_seconds=100)
        self.assertTrue(rl.allow(1))
        self.assertTrue(rl.allow(1))
        self.assertFalse(rl.allow(1))
        # A different key has its own budget.
        self.assertTrue(rl.allow(2))

    def test_zero_disables_limit(self) -> None:
        rl = RateLimiter(max_events=0, window_seconds=100)
        for _ in range(50):
            self.assertTrue(rl.allow(7))
        self.assertEqual(rl.retry_after(7), 0)

    def test_window_expiry_frees_slots(self) -> None:
        rl = RateLimiter(max_events=1, window_seconds=10)
        clock = {"t": 1000.0}
        rl._now = lambda: clock["t"]  # type: ignore[method-assign]
        self.assertTrue(rl.allow(1))
        self.assertFalse(rl.allow(1))
        self.assertGreater(rl.retry_after(1), 0)
        clock["t"] += 11  # advance past the window
        self.assertTrue(rl.allow(1))


if __name__ == "__main__":
    unittest.main()
