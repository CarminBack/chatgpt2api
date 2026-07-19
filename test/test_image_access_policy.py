from __future__ import annotations

import unittest
from unittest import mock

from services.config import config
from services.image_access_policy import (
    ImageAccessPolicyError,
    apply_image_request_policy,
    constrain_image_size,
    image_key_policy,
    image_max_side,
    is_1k_only_identity,
)


class ImageAccessPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._patcher = mock.patch.dict(
            config.data,
            {
                "image_1k_only_sub2api_user_ids": [39],
                "image_1k_only_sub2api_key_ids": [93],
                "image_key_policies": {},
            },
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()

    def test_image_max_side_defaults_to_1k(self) -> None:
        self.assertEqual(image_max_side(None), 1024)
        self.assertEqual(image_max_side("auto"), 1024)
        self.assertEqual(image_max_side("1024x1536"), 1536)

    def test_matches_sub2api_user_or_key(self) -> None:
        self.assertTrue(is_1k_only_identity({"source": "sub2api", "sub2api_user_id": 39}))
        self.assertTrue(is_1k_only_identity({"source": "local+sub2api", "sub2api_key_id": 93}))
        self.assertFalse(is_1k_only_identity({"source": "local", "sub2api_user_id": 39, "sub2api_key_id": 93}))

    def test_preserves_1k_and_scales_larger_sizes_for_limited_identity(self) -> None:
        identity = {"source": "sub2api", "sub2api_user_id": 39}

        self.assertIsNone(constrain_image_size(identity, None))
        self.assertEqual(constrain_image_size(identity, "auto"), "auto")
        self.assertEqual(constrain_image_size(identity, "1024x1024"), "1024x1024")
        self.assertEqual(constrain_image_size(identity, "1024x1536"), "683x1024")
        self.assertEqual(constrain_image_size(identity, "3840x2160"), "1024x576")

    def test_allows_larger_sizes_for_unlimited_identity(self) -> None:
        self.assertEqual(constrain_image_size({"source": "sub2api", "sub2api_user_id": 40}, "2048x2048"), "2048x2048")

    def test_no_key_policy_preserves_payload(self) -> None:
        payload = {"model": "gpt-image-2", "size": "2048x2048", "prompt": "cat"}

        result = apply_image_request_policy({"id": "ordinary-user", "source": "local"}, payload)

        self.assertEqual(result, payload)
        self.assertIsNot(result, payload)

    def test_local_identity_policy_routes_model_and_enables_observe(self) -> None:
        identity = {"id": "canvas-key-id", "source": "local"}
        with mock.patch.dict(
            config.data,
            {
                "image_key_policies": {
                    "canvas-key-id": {
                        "max_resolution_tier": "4k",
                        "output_size_mode": "observe",
                        "route_model": "codex-gpt-image-2",
                    }
                }
            },
        ):
            policy = image_key_policy(identity)
            result = apply_image_request_policy(
                identity,
                {"model": "gpt-image-2", "size": "3840x2160"},
            )

        self.assertEqual(policy.max_resolution_tier, "4k")
        self.assertEqual(result["model"], "codex-gpt-image-2")
        self.assertEqual(result["size"], "3840x2160")
        self.assertEqual(result["_image_output_size_mode"], "observe")
        self.assertEqual(result["_image_policy_identity_id"], "canvas-key-id")

    def test_4k_policy_accepts_supported_landscape_and_portrait_sizes(self) -> None:
        identity = {"id": "canvas-key-id"}
        with mock.patch.dict(
            config.data,
            {"image_key_policies": {"canvas-key-id": {"max_resolution_tier": "4k"}}},
        ):
            for size in ("1024x1024", "2048x2048", "3840x2160", "2160x3840"):
                with self.subTest(size=size):
                    result = apply_image_request_policy(identity, {"size": size})
                    self.assertEqual(result["size"], size)

    def test_4k_policy_rejects_oversized_square(self) -> None:
        identity = {"id": "canvas-key-id"}
        with mock.patch.dict(
            config.data,
            {"image_key_policies": {"canvas-key-id": {"max_resolution_tier": "4k"}}},
        ):
            with self.assertRaisesRegex(ImageAccessPolicyError, "up to 4K"):
                apply_image_request_policy(identity, {"size": "3840x3840"})

    def test_2k_policy_rejects_4k_size(self) -> None:
        identity = {"id": "two-k-key-id"}
        with mock.patch.dict(
            config.data,
            {"image_key_policies": {"two-k-key-id": {"max_resolution_tier": "2k"}}},
        ):
            with self.assertRaisesRegex(ImageAccessPolicyError, "up to 2K"):
                apply_image_request_policy(identity, {"size": "3840x2160"})

    def test_passthrough_policy_does_not_add_internal_metadata(self) -> None:
        identity = {"id": "passthrough-key-id"}
        with mock.patch.dict(
            config.data,
            {
                "image_key_policies": {
                    "passthrough-key-id": {
                        "max_resolution_tier": "4k",
                        "output_size_mode": "passthrough",
                    }
                }
            },
        ):
            result = apply_image_request_policy(identity, {"model": "gpt-image-2", "size": "2048x2048"})

        self.assertNotIn("_image_output_size_mode", result)
        self.assertNotIn("_image_policy_identity_id", result)


if __name__ == "__main__":
    unittest.main()
