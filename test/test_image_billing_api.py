from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.ai as ai_module


class ImageBillingApiTests(unittest.TestCase):
    def test_generation_omitted_model_uses_gpt_image_2(self) -> None:
        identity = {"id": "admin", "name": "Admin", "role": "admin", "source": "local"}
        payloads = []
        app = FastAPI()
        app.include_router(ai_module.create_router())
        client = TestClient(app)

        def fake_handle(payload):
            payloads.append(payload)
            return {"created": 1, "data": [{"b64_json": "ZmFrZQ=="}]}

        with mock.patch.object(ai_module, "require_identity", return_value=identity), mock.patch.object(
            ai_module,
            "check_request",
            return_value=None,
        ), mock.patch.object(
            ai_module.openai_v1_image_generations,
            "handle",
            side_effect=fake_handle,
        ):
            response = client.post(
                "/v1/images/generations",
                headers={"Authorization": "Bearer local-admin"},
                json={"prompt": "cat"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(payloads[0]["model"], "gpt-image-2")

    def test_generation_exception_refunds_by_key_id_without_raw_key(self) -> None:
        identity = {
            "id": "sub2api:93",
            "name": "user@example.test",
            "role": "user",
            "source": "sub2api",
            "token": "sk-secret-value",
            "sub2api_key_id": 93,
        }
        app = FastAPI()
        app.include_router(ai_module.create_router())
        client = TestClient(app, raise_server_exceptions=False)

        with mock.patch.object(ai_module, "require_identity", return_value=identity), mock.patch.object(
            ai_module,
            "check_request",
            return_value=None,
        ), mock.patch.object(
            ai_module.sub2api_billing_service,
            "debit_image_balance",
            return_value=(SimpleNamespace(key_id=93), Decimal("0.04"), Decimal("0.04"), Decimal("9.96")),
        ), mock.patch.object(
            ai_module.sub2api_billing_service,
            "refund_user_balance",
            return_value=Decimal("10"),
        ) as refund, mock.patch.object(
            ai_module.openai_v1_image_generations,
            "handle",
            side_effect=RuntimeError("upstream failed"),
        ):
            response = client.post(
                "/v1/images/generations",
                headers={"Authorization": "Bearer sk-secret-value"},
                json={"prompt": "cat", "model": "codex-gpt-image-2", "size": "1024x1024"},
            )

        self.assertEqual(response.status_code, 502)
        refund.assert_called_once()
        self.assertEqual(refund.call_args.kwargs["api_key_id"], 93)
        self.assertNotIn("raw_key", refund.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
