from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("CHATGPT2API_AUTH_KEY", "test-auth")

from services.protocol import conversation


class _Backend:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.progress_callback = None
        self.closed = False

    def close(self) -> None:
        self.closed = True


class ImageModelRoutingTests(unittest.TestCase):
    def _run_model(self, model: str):
        result = conversation.ImageOutput(
            kind="result",
            model=model,
            index=0,
            total=1,
            data=[{"b64_json": "ZmFrZQ=="}],
        )
        backend = _Backend("token-1")
        with (
            mock.patch.object(
                conversation.account_service,
                "get_available_access_token",
                return_value="token-1",
            ) as select_account,
            mock.patch.object(
                conversation.account_service,
                "get_account",
                return_value={"email": "image@example.test"},
            ),
            mock.patch.object(conversation.account_service, "mark_image_result") as mark_result,
            mock.patch.object(conversation, "OpenAIBackendAPI", return_value=backend),
            mock.patch.object(
                conversation,
                "stream_image_outputs",
                return_value=iter([result]),
            ) as web_stream,
            mock.patch.object(
                conversation,
                "stream_codex_image_outputs",
                return_value=iter([result]),
            ) as codex_stream,
        ):
            outputs = conversation._generate_single_image(
                conversation.ConversationRequest(model=model, prompt="cat"),
                0,
                1,
            )

        self.assertEqual(outputs, [result])
        mark_result.assert_called_once_with("token-1", True)
        self.assertTrue(backend.closed)
        return select_account, web_stream, codex_stream

    def test_gpt_image_2_uses_web_route_without_codex_account_filter(self) -> None:
        select_account, web_stream, codex_stream = self._run_model("gpt-image-2")

        select_account.assert_called_once_with(
            plan_type=None,
            source_type=None,
            plan_types=None,
        )
        web_stream.assert_called_once()
        codex_stream.assert_not_called()

    def test_codex_gpt_image_2_keeps_paid_codex_route(self) -> None:
        select_account, web_stream, codex_stream = self._run_model("codex-gpt-image-2")

        select_account.assert_called_once_with(
            plan_type=None,
            source_type="codex",
            plan_types=("plus", "team", "pro"),
        )
        web_stream.assert_not_called()
        codex_stream.assert_called_once()


if __name__ == "__main__":
    unittest.main()
