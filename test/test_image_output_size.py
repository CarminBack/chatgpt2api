from __future__ import annotations

from io import BytesIO
import unittest
from unittest import mock

from PIL import Image

from services.image_output_size import observe_image_output_size


def png_bytes(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


class ImageOutputSizeTests(unittest.TestCase):
    def test_passthrough_does_not_inspect_or_log(self) -> None:
        with mock.patch("services.image_output_size.logger.info") as info, mock.patch(
            "services.image_output_size.logger.warning"
        ) as warning:
            observe_image_output_size(
                b"not-an-image",
                requested_size="2048x2048",
                output_size_mode="passthrough",
                identity_id="ordinary-key-id",
                model="gpt-image-2",
            )

        info.assert_not_called()
        warning.assert_not_called()

    def test_observe_logs_requested_and_actual_dimensions(self) -> None:
        with mock.patch("services.image_output_size.logger.info") as info:
            observe_image_output_size(
                png_bytes(2048, 1024),
                requested_size="2048x1024",
                output_size_mode="observe",
                identity_id="canvas-key-id",
                model="codex-gpt-image-2",
            )

        event = info.call_args.args[0]
        self.assertEqual(event["event"], "image_output_size_observed")
        self.assertEqual(event["identity_id"], "canvas-key-id")
        self.assertEqual(event["requested_width"], 2048)
        self.assertEqual(event["requested_height"], 1024)
        self.assertEqual(event["actual_width"], 2048)
        self.assertEqual(event["actual_height"], 1024)
        self.assertTrue(event["exact_match"])

    def test_invalid_image_only_logs_warning(self) -> None:
        with mock.patch("services.image_output_size.logger.warning") as warning:
            observe_image_output_size(
                b"not-an-image",
                requested_size="3840x2160",
                output_size_mode="observe",
                identity_id="canvas-key-id",
                model="codex-gpt-image-2",
            )

        event = warning.call_args.args[0]
        self.assertEqual(event["event"], "image_output_size_inspect_failed")
        self.assertEqual(event["identity_id"], "canvas-key-id")
        self.assertEqual(event["error_type"], "UnidentifiedImageError")


if __name__ == "__main__":
    unittest.main()
