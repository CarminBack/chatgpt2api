from __future__ import annotations

import unittest
from unittest.mock import patch

from services.protocol import conversation
from utils.helper import UpstreamHTTPError


class _FakeAccountService:
    def __init__(self) -> None:
        self.tokens = iter(["token-limited", "token-ok"])
        self.usage_limits: list[tuple[str, object]] = []
        self.results: list[tuple[str, bool]] = []

    def get_available_access_token(self, **_kwargs) -> str:
        return next(self.tokens)

    @staticmethod
    def get_account(token: str) -> dict:
        return {"email": f"{token}@example.com"}

    def mark_image_usage_limited(self, token: str, resets_at: object = None) -> None:
        self.usage_limits.append((token, resets_at))

    def mark_image_result(self, token: str, success: bool) -> None:
        self.results.append((token, success))


class _FakeBackend:
    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        self.progress_callback = None

    def close(self) -> None:
        pass


class CodexUsageLimitRetryTests(unittest.TestCase):
    def test_usage_limit_marks_account_and_retries_another_codex_account(self) -> None:
        fake_accounts = _FakeAccountService()

        def fake_stream(backend, request, index, total):
            if backend.access_token == "token-limited":
                raise UpstreamHTTPError(
                    "/backend-api/codex/responses",
                    429,
                    {
                        "error": {
                            "type": "usage_limit_reached",
                            "message": "The usage limit has been reached",
                            "resets_at": 1784780253,
                        }
                    },
                )
            yield conversation.ImageOutput(
                kind="result",
                model=request.model,
                index=index,
                total=total,
                data=[{"b64_json": "image-data"}],
            )

        request = conversation.ConversationRequest(
            model="codex-gpt-image-2",
            prompt="test",
        )
        with (
            patch.object(conversation, "account_service", fake_accounts),
            patch.object(conversation, "OpenAIBackendAPI", _FakeBackend),
            patch.object(conversation, "stream_codex_image_outputs", fake_stream),
        ):
            outputs = conversation._generate_single_image(request, 1, 1)

        self.assertEqual(fake_accounts.usage_limits, [("token-limited", 1784780253)])
        self.assertEqual(fake_accounts.results, [("token-ok", True)])
        self.assertEqual(outputs[0].account_email, "token-ok@example.com")

    def test_other_429_is_not_treated_as_usage_limit(self) -> None:
        error = UpstreamHTTPError(
            "/backend-api/codex/responses",
            429,
            {"error": {"type": "rate_limit_error", "resets_at": 1784780253}},
        )

        self.assertIsNone(conversation.codex_usage_limit_reset_at(error))


if __name__ == "__main__":
    unittest.main()
