from __future__ import annotations

import unittest
from unittest import mock

from services.config import config
from services.image_access_policy import constrain_image_size, image_max_side, is_1k_only_identity


class ImageAccessPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._patcher = mock.patch.dict(
            config.data,
            {
                "image_1k_only_sub2api_user_ids": [39],
                "image_1k_only_sub2api_key_ids": [93],
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


if __name__ == "__main__":
    unittest.main()
