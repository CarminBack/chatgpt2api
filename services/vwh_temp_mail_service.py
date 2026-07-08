from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen


RequestFn = Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class VwhTempMailMessage:
    id: str
    from_address: str
    to_address: str
    subject: str
    received_at: int | float | str | None = None
    has_attachments: bool = False
    attachment_count: int = 0
    raw: dict[str, Any] | None = None


class VwhTempMailClient:
    """Small client for vwh/temp-mail Workers.

    This client intentionally only talks to the vwh/temp-mail API. It is not
    wired into the account registration flow.
    """

    def __init__(self, api_base: str, timeout: float = 20, request_json: RequestFn | None = None) -> None:
        self.api_base = str(api_base or "").strip().rstrip("/")
        if not self.api_base:
            raise ValueError("api_base is required")
        self.timeout = float(timeout)
        self._request_json = request_json or self._default_request_json

    def _default_request_json(self, path: str) -> dict[str, Any]:
        url = f"{self.api_base}{path}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "chatgpt2api-vwh-temp-mail/1.0"})
        with urlopen(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
        data = json.loads(body or "{}")
        if not isinstance(data, dict):
            raise RuntimeError(f"vwh/temp-mail returned non-object JSON for {path}")
        return data

    @staticmethod
    def _result(data: dict[str, Any], path: str) -> Any:
        if data.get("success") is False:
            raise RuntimeError(f"vwh/temp-mail request failed for {path}: {data}")
        return data.get("result")

    @staticmethod
    def _message_from_raw(raw: dict[str, Any]) -> VwhTempMailMessage:
        return VwhTempMailMessage(
            id=str(raw.get("id") or ""),
            from_address=str(raw.get("from_address") or raw.get("from") or ""),
            to_address=str(raw.get("to_address") or raw.get("to") or ""),
            subject=str(raw.get("subject") or ""),
            received_at=raw.get("received_at"),
            has_attachments=bool(raw.get("has_attachments") or False),
            attachment_count=int(raw.get("attachment_count") or 0),
            raw=raw,
        )

    def health(self) -> dict[str, Any]:
        path = "/health"
        result = self._result(self._request_json(path), path)
        return result if isinstance(result, dict) else {}

    def domains(self) -> list[str]:
        path = "/domains"
        result = self._result(self._request_json(path), path)
        if not isinstance(result, list):
            return []
        return [str(item) for item in result if str(item or "").strip()]

    def list_messages(self, email_address: str) -> list[VwhTempMailMessage]:
        email = str(email_address or "").strip()
        if not email:
            raise ValueError("email_address is required")
        path = f"/emails/{quote(email, safe='')}"
        result = self._result(self._request_json(path), path)
        if not isinstance(result, list):
            return []
        return [self._message_from_raw(item) for item in result if isinstance(item, dict)]

    def get_message(self, message_id: str) -> dict[str, Any]:
        value = str(message_id or "").strip()
        if not value:
            raise ValueError("message_id is required")
        path = f"/inbox/{quote(value, safe='')}"
        result = self._result(self._request_json(path), path)
        return result if isinstance(result, dict) else {"result": result}

    def wait_for_message(self, email_address: str, timeout: float = 180, interval: float = 5) -> VwhTempMailMessage | None:
        deadline = time.monotonic() + max(0.0, float(timeout))
        while time.monotonic() <= deadline:
            messages = self.list_messages(email_address)
            if messages:
                return messages[0]
            time.sleep(max(0.2, float(interval)))
        return None
