"""Unit tests for deterministic percentage-rollout bucketing."""

import unittest

from app.engine.rollout import bucket_for


class RolloutTests(unittest.TestCase):
    def test_bucket_is_deterministic_for_same_flag_and_user(self):
        buckets = [bucket_for("new_checkout_flow", "user-123") for _ in range(10)]

        self.assertEqual(len(set(buckets)), 1)
        self.assertGreaterEqual(buckets[0], 0)
        self.assertLessEqual(buckets[0], 99)

    def test_different_flags_bucket_users_independently(self):
        user_keys = [f"user-{index}" for index in range(100)]
        first_flag_buckets = [
            bucket_for("new_checkout_flow", user_key) for user_key in user_keys
        ]
        second_flag_buckets = [
            bucket_for("billing_redesign", user_key) for user_key in user_keys
        ]

        self.assertNotEqual(first_flag_buckets, second_flag_buckets)

    def test_fifty_percent_rollout_is_approximately_half(self):
        buckets = [
            bucket_for("new_checkout_flow", f"user-{index}")
            for index in range(1000)
        ]
        enabled_count = sum(bucket < 50 for bucket in buckets)

        self.assertGreaterEqual(enabled_count, 400)
        self.assertLessEqual(enabled_count, 600)

    def test_bucket_is_always_in_range(self):
        buckets = [bucket_for("new_checkout_flow", f"user-{index}") for index in range(1000)]

        self.assertTrue(all(0 <= bucket <= 99 for bucket in buckets))


if __name__ == "__main__":
    unittest.main()
