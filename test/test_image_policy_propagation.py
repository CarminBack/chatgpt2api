from __future__ import annotations

import unittest
from unittest import mock

from services.protocol import openai_v1_image_edit, openai_v1_image_generations
from services.protocol.conversation import ImageOutput


class ImagePolicyPropagationTests(unittest.TestCase):
    def _result_output(self, model: str) -> list[ImageOutput]:
        return [
            ImageOutput(
                kind="result",
                model=model,
                index=1,
                total=1,
                data=[{"url": "https://example.test/image.png"}],
            )
        ]

    def test_generation_handler_copies_observe_metadata_to_request(self) -> None:
        captured = []

        def stream(request):
            captured.append(request)
            return iter(self._result_output(request.model))

        with mock.patch.object(openai_v1_image_generations, "stream_image_outputs_with_pool", side_effect=stream):
            result = openai_v1_image_generations.handle({
                "prompt": "cat",
                "model": "codex-gpt-image-2",
                "size": "3840x2160",
                "_image_output_size_mode": "observe",
                "_image_policy_identity_id": "canvas-key-id",
            })

        self.assertEqual(result["data"][0]["url"], "https://example.test/image.png")
        self.assertEqual(captured[0].size, "3840x2160")
        self.assertEqual(captured[0].output_size_mode, "observe")
        self.assertEqual(captured[0].policy_identity_id, "canvas-key-id")

    def test_edit_handler_copies_observe_metadata_to_request(self) -> None:
        captured = []

        def stream(request):
            captured.append(request)
            return iter(self._result_output(request.model))

        with mock.patch.object(openai_v1_image_edit, "stream_image_outputs_with_pool", side_effect=stream):
            result = openai_v1_image_edit.handle({
                "prompt": "edit cat",
                "images": [(b"image-bytes", "image.png", "image/png")],
                "model": "codex-gpt-image-2",
                "size": "2048x2048",
                "_image_output_size_mode": "observe",
                "_image_policy_identity_id": "canvas-key-id",
            })

        self.assertEqual(result["data"][0]["url"], "https://example.test/image.png")
        self.assertEqual(captured[0].size, "2048x2048")
        self.assertEqual(captured[0].output_size_mode, "observe")
        self.assertEqual(captured[0].policy_identity_id, "canvas-key-id")


if __name__ == "__main__":
    unittest.main()
