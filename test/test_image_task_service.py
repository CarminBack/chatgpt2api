from __future__ import annotations

import json
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace

from services.config import config
from services.image_task_service import ImageTaskService


OWNER = {"id": "owner-1", "name": "Owner", "role": "admin"}
OTHER_OWNER = {"id": "owner-2", "name": "Other", "role": "user"}


def wait_for_task(service: ImageTaskService, identity: dict[str, object], task_id: str, status: str, timeout: float = 2.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        result = service.list_tasks(identity, [task_id])
        last = (result.get("items") or [None])[0]
        if last and last.get("status") == status:
            return last
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} did not reach {status}, last={last}")


class ImageTaskServiceTests(unittest.TestCase):
    def make_service(self, path: Path, handler=None) -> ImageTaskService:
        return ImageTaskService(
            path,
            generation_handler=handler or (lambda _payload: {"data": [{"url": "http://example.test/image.png"}]}),
            edit_handler=handler or (lambda _payload: {"data": [{"url": "http://example.test/edit.png"}]}),
            retention_days_getter=lambda: 30,
        )

    def test_duplicate_submit_uses_existing_task(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            calls = 0

            def handler(_payload):
                nonlocal calls
                calls += 1
                time.sleep(0.05)
                return {"data": [{"url": "http://example.test/image.png"}]}

            service = self.make_service(Path(tmp_dir) / "image_tasks.json", handler)
            first = service.submit_generation(
                OWNER,
                client_task_id="task-1",
                prompt="cat",
                model="gpt-image-2",
                size=None,
                base_url="http://local.test",
            )
            second = service.submit_generation(
                OWNER,
                client_task_id="task-1",
                prompt="cat",
                model="gpt-image-2",
                size=None,
                base_url="http://local.test",
            )

            self.assertEqual(first["id"], "task-1")
            self.assertEqual(second["id"], "task-1")
            task = wait_for_task(service, OWNER, "task-1", "success")
            self.assertEqual(task["data"][0]["url"], "http://example.test/image.png")
            self.assertEqual(calls, 1)

    def test_different_owner_cannot_query_task(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(Path(tmp_dir) / "image_tasks.json")
            service.submit_generation(
                OWNER,
                client_task_id="private-task",
                prompt="cat",
                model="gpt-image-2",
                size=None,
                base_url="http://local.test",
            )

            wait_for_task(service, OWNER, "private-task", "success")
            result = service.list_tasks(OTHER_OWNER, ["private-task"])

            self.assertEqual(result["items"], [])
            self.assertEqual(result["missing_ids"], ["private-task"])

    def test_success_task_persists_to_new_service_instance(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "image_tasks.json"
            service = self.make_service(path)
            service.submit_generation(
                OWNER,
                client_task_id="persisted-task",
                prompt="cat",
                model="gpt-image-2",
                size=None,
                base_url="http://local.test",
            )
            wait_for_task(service, OWNER, "persisted-task", "success")

            reloaded = self.make_service(path)
            result = reloaded.list_tasks(OWNER, ["persisted-task"])

            self.assertEqual(result["missing_ids"], [])
            self.assertEqual(result["items"][0]["status"], "success")
            self.assertEqual(result["items"][0]["data"][0]["url"], "http://example.test/image.png")

    def test_startup_marks_unfinished_tasks_as_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "image_tasks.json"
            path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "queued-task",
                                "owner_id": "owner-1",
                                "status": "queued",
                                "mode": "generate",
                                "model": "gpt-image-2",
                                "created_at": "2099-01-01 00:00:00",
                                "updated_at": "2099-01-01 00:00:00",
                            },
                            {
                                "id": "running-task",
                                "owner_id": "owner-1",
                                "status": "running",
                                "mode": "generate",
                                "model": "gpt-image-2",
                                "created_at": "2099-01-01 00:00:00",
                                "updated_at": "2099-01-01 00:00:00",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            service = self.make_service(path)
            result = service.list_tasks(OWNER, ["queued-task", "running-task"])

            self.assertEqual([item["status"] for item in result["items"]], ["error", "error"])
            self.assertTrue(all("已中断" in item.get("error", "") for item in result["items"]))

    def test_startup_retains_expired_task_while_refund_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "image_tasks.json"
            path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "expired-billed-task",
                                "owner_id": "sub2api:93",
                                "status": "error",
                                "mode": "generate",
                                "model": "codex-gpt-image-2",
                                "created_at": "2000-01-01 00:00:00",
                                "updated_at": "2000-01-01 00:00:00",
                                "billing_api_key_id": 93,
                                "billing_amount": "0.04",
                                "billing_refund_pending": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("services.image_task_service.threading.Thread.start") as start:
                service = self.make_service(path)

            result = service.list_tasks({"id": "sub2api:93"}, ["expired-billed-task"])
            self.assertEqual(result["missing_ids"], [])
            self.assertEqual(result["items"][0]["status"], "error")
            self.assertIn('"billing_refund_pending": true', path.read_text(encoding="utf-8"))
            start.assert_called_once_with()

    def test_startup_refunds_persisted_billed_task_without_storing_token(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "image_tasks.json"
            path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "billed-task",
                                "owner_id": "sub2api:93",
                                "status": "running",
                                "mode": "generate",
                                "model": "codex-gpt-image-2",
                                "created_at": "2099-01-01 00:00:00",
                                "updated_at": "2099-01-01 00:00:00",
                                "billing_api_key_id": 93,
                                "billing_amount": "0.04",
                                "billing_refund_pending": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("services.image_task_service.threading.Thread.start"), mock.patch.object(
                __import__("services.image_task_service", fromlist=["sub2api_billing_service"]).sub2api_billing_service,
                "refund_user_balance",
                return_value=Decimal("10.04"),
            ) as refund:
                service = self.make_service(path)
                service._recover_pending_refunds()

            refund.assert_called_once_with(
                api_key_id=93,
                amount=Decimal("0.04"),
                task_id="billed-task",
                mode="generate",
                model="codex-gpt-image-2",
                prompt_preview="",
                error="服务已重启，未完成的图片任务已中断",
            )
            persisted = path.read_text(encoding="utf-8")
            self.assertNotIn("billing_token", persisted)
            self.assertIn('"billing_refund_pending": false', persisted)
            self.assertIn('"billing_refunded": true', persisted)

    def test_billed_success_persists_key_id_without_raw_token(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "image_tasks.json"
            identity = {
                "id": "sub2api:93",
                "name": "user@example.test",
                "role": "user",
                "source": "sub2api",
                "token": "sk-secret-value",
                "sub2api_key_id": 93,
            }
            billing_identity = SimpleNamespace(key_id=93)
            with mock.patch(
                "services.image_task_service.sub2api_billing_service.debit_image_balance",
                return_value=(billing_identity, Decimal("0.04"), Decimal("0.04"), Decimal("9.96")),
            ):
                service = self.make_service(path)
                service.submit_generation(
                    identity,
                    client_task_id="billed-success",
                    prompt="cat",
                    model="codex-gpt-image-2",
                    size="1024x1024",
                )
                wait_for_task(service, identity, "billed-success", "success")

            persisted = path.read_text(encoding="utf-8")
            self.assertNotIn("sk-secret-value", persisted)
            self.assertIn('"billing_api_key_id": 93', persisted)
            self.assertIn('"billing_refund_pending": false', persisted)

    def test_success_persistence_failure_refunds_billed_task(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "image_tasks.json"
            identity = {
                "id": "sub2api:93",
                "name": "user@example.test",
                "role": "user",
                "source": "sub2api",
                "token": "sk-secret-value",
                "sub2api_key_id": 93,
            }
            billing_identity = SimpleNamespace(key_id=93)
            service = self.make_service(path)
            original_save = service._save_locked
            save_calls = 0

            def fail_success_save_once():
                nonlocal save_calls
                save_calls += 1
                if save_calls == 3:
                    raise OSError("disk unavailable")
                original_save()

            with mock.patch.object(
                service,
                "_save_locked",
                side_effect=fail_success_save_once,
            ), mock.patch(
                "services.image_task_service.sub2api_billing_service.debit_image_balance",
                return_value=(billing_identity, Decimal("0.04"), Decimal("0.04"), Decimal("9.96")),
            ), mock.patch(
                "services.image_task_service.sub2api_billing_service.refund_user_balance",
                return_value=Decimal("10.00"),
            ) as refund:
                service.submit_generation(
                    identity,
                    client_task_id="persistence-failed",
                    prompt="cat",
                    model="codex-gpt-image-2",
                    size="1024x1024",
                )
                task = wait_for_task(service, identity, "persistence-failed", "error")

            refund.assert_called_once()
            self.assertIn("disk unavailable", task["error"])
            persisted = path.read_text(encoding="utf-8")
            self.assertIn('"status": "error"', persisted)
            self.assertIn('"billing_refund_pending": false', persisted)

    def test_1k_only_identity_scales_larger_task_before_handler(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            seen_size = ""

            def handler(payload):
                nonlocal seen_size
                seen_size = str(payload.get("size") or "")
                return {"data": [{"url": "http://example.test/image.png"}]}

            service = self.make_service(Path(tmp_dir) / "image_tasks.json", handler)
            identity = {
                "id": "sub2api:93",
                "name": "limited",
                "role": "user",
                "source": "sub2api",
                "sub2api_user_id": 39,
                "sub2api_key_id": 93,
            }
            with mock.patch.dict(config.data, {"image_1k_only_sub2api_user_ids": [39]}):
                service.submit_generation(
                    identity,
                    client_task_id="too-large",
                    prompt="cat",
                    model="gpt-image-2",
                    size="2048x2048",
                    base_url="http://local.test",
                )

            task = wait_for_task(service, identity, "too-large", "success")
            self.assertEqual(seen_size, "1024x1024")
            self.assertEqual(task["size"], "1024x1024")

    def test_key_policy_routes_async_task_and_forwards_observe_metadata(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            seen_payload: dict[str, object] = {}

            def handler(payload):
                seen_payload.update(payload)
                return {"data": [{"url": "http://example.test/image.png"}]}

            service = self.make_service(Path(tmp_dir) / "image_tasks.json", handler)
            identity = {
                "id": "canvas-key-id",
                "name": "Canvas Channel 22",
                "role": "user",
                "source": "local",
            }
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
                service.submit_generation(
                    identity,
                    client_task_id="canvas-4k",
                    prompt="cat",
                    model="gpt-image-2",
                    size="3840x2160",
                )
                task = wait_for_task(service, identity, "canvas-4k", "success")

            self.assertEqual(task["model"], "codex-gpt-image-2")
            self.assertEqual(task["size"], "3840x2160")
            self.assertEqual(seen_payload["model"], "codex-gpt-image-2")
            self.assertEqual(seen_payload["_image_output_size_mode"], "observe")
            self.assertEqual(seen_payload["_image_policy_identity_id"], "canvas-key-id")


if __name__ == "__main__":
    unittest.main()
