from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from services.auth_service import auth_service
from services.config import DATA_DIR


class RedeemCodeError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: object) -> str:
    return str(value or "").strip()


def _non_negative_int(value: object, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _hash_code(code: str) -> str:
    return hashlib.sha256(_clean(code).upper().encode("utf-8")).hexdigest()


def _parse_datetime(value: object) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RedeemCodeError("过期时间格式无效，请使用 ISO 时间格式") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _mask_code(code: str) -> str:
    text = _clean(code).upper()
    if len(text) <= 10:
        return text[:2] + "****" + text[-2:]
    return text[:7] + "-****-" + text[-4:]


class RedeemCodeService:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = Lock()
        self._ensure_schema()

    @contextmanager
    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS redeem_codes (
                    id TEXT PRIMARY KEY,
                    code_hash TEXT NOT NULL UNIQUE,
                    display_code TEXT NOT NULL,
                    image_quota INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    redeemed_at TEXT,
                    redeemed_by_id TEXT,
                    redeemed_by_name TEXT,
                    redeemed_by_role TEXT
                )
                """
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_redeem_codes_hash ON redeem_codes (code_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_redeem_codes_redeemed_by ON redeem_codes (redeemed_by_id)")
            conn.commit()

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["enabled"] = bool(item.get("enabled"))
        item["image_quota"] = _non_negative_int(item.get("image_quota"), 0)
        item["status"] = self._status(item)
        return item

    def _status(self, item: dict[str, Any]) -> str:
        if not bool(item.get("enabled", True)):
            return "disabled"
        if _clean(item.get("redeemed_at")):
            return "redeemed"
        expires_at = _parse_datetime(item.get("expires_at")) if _clean(item.get("expires_at")) else None
        if expires_at and expires_at <= datetime.now(timezone.utc):
            return "expired"
        return "available"

    def _make_code(self, prefix: str) -> str:
        safe_prefix = "".join(ch for ch in _clean(prefix).upper() if ch.isalnum())[:8] or "RC"
        token = secrets.token_urlsafe(18).replace("_", "").replace("-", "").upper()[:20]
        return f"{safe_prefix}-{token[:4]}-{token[4:8]}-{token[8:12]}-{token[12:16]}"

    def list_codes(self) -> list[dict[str, Any]]:
        self._ensure_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM redeem_codes ORDER BY created_at DESC").fetchall()
        return [self._row_to_item(row) for row in rows]

    def create_codes(self, *, count: int, image_quota: int, expires_at: object = None, prefix: str = "RC") -> list[dict[str, Any]]:
        count = _non_negative_int(count, 0)
        image_quota = _non_negative_int(image_quota, 0)
        if count <= 0 or count > 500:
            raise RedeemCodeError("生成数量必须在 1-500 之间")
        if image_quota <= 0:
            raise RedeemCodeError("兑换图片额度必须大于 0")
        parsed_expires_at = _parse_datetime(expires_at)
        expires_text = parsed_expires_at.isoformat() if parsed_expires_at else None
        if parsed_expires_at and parsed_expires_at <= datetime.now(timezone.utc):
            raise RedeemCodeError("过期时间必须晚于当前时间")
        created = []
        with self._lock:
            self._ensure_schema()
            with self._connect() as conn:
                for _ in range(count):
                    for _attempt in range(20):
                        code = self._make_code(prefix)
                        code_hash = _hash_code(code)
                        item_id = uuid.uuid4().hex[:12]
                        try:
                            conn.execute(
                                """
                                INSERT INTO redeem_codes (
                                    id, code_hash, display_code, image_quota, enabled,
                                    created_at, expires_at, redeemed_at, redeemed_by_id,
                                    redeemed_by_name, redeemed_by_role
                                ) VALUES (?, ?, ?, ?, 1, ?, ?, NULL, NULL, NULL, NULL)
                                """,
                                (item_id, code_hash, _mask_code(code), image_quota, _now_iso(), expires_text),
                            )
                            created.append({
                                "id": item_id,
                                "code": code,
                                "display_code": _mask_code(code),
                                "image_quota": image_quota,
                                "enabled": True,
                                "created_at": _now_iso(),
                                "expires_at": expires_text,
                                "status": "available",
                            })
                            break
                        except sqlite3.IntegrityError:
                            continue
                    else:
                        raise RedeemCodeError("兑换码生成冲突，请重试")
                conn.commit()
        return created

    def verify_code(self, code: str) -> dict[str, Any]:
        normalized = _clean(code)
        if not normalized:
            raise RedeemCodeError("请输入兑换码")
        self._ensure_schema()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM redeem_codes WHERE code_hash = ?", (_hash_code(normalized),)).fetchone()
        if row is None:
            return {"ok": False, "exists": False, "status": "missing", "error": "兑换码不存在"}
        item = self._row_to_item(row)
        return {"ok": item["status"] == "available", "exists": True, "item": item, "status": item["status"]}

    def redeem(self, code: str, identity: dict[str, object]) -> dict[str, Any]:
        normalized = _clean(code)
        if not normalized:
            raise RedeemCodeError("请输入兑换码")
        if identity.get("role") != "user":
            raise RedeemCodeError("只有普通用户可以兑换图片额度")
        user_id = _clean(identity.get("id"))
        if not user_id:
            raise RedeemCodeError("当前用户身份无效，请重新登录")
        with self._lock:
            self._ensure_schema()
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM redeem_codes WHERE code_hash = ?", (_hash_code(normalized),)).fetchone()
                if row is None:
                    raise RedeemCodeError("兑换码不存在")
                item = self._row_to_item(row)
                status = item["status"]
                if status == "disabled":
                    raise RedeemCodeError("兑换码已禁用")
                if status == "redeemed":
                    raise RedeemCodeError("兑换码已被兑换")
                if status == "expired":
                    raise RedeemCodeError("兑换码已过期")
                amount = _non_negative_int(item.get("image_quota"), 0)
                if amount <= 0:
                    raise RedeemCodeError("兑换码额度无效")
                updated_user = auth_service.add_image_quota(user_id, amount)
                if updated_user is None:
                    raise RedeemCodeError("当前用户不存在或无法增加额度")
                redeemed_at = _now_iso()
                conn.execute(
                    """
                    UPDATE redeem_codes
                    SET redeemed_at = ?, redeemed_by_id = ?, redeemed_by_name = ?, redeemed_by_role = ?
                    WHERE id = ? AND redeemed_at IS NULL
                    """,
                    (redeemed_at, user_id, _clean(identity.get("name")), _clean(identity.get("role")), item["id"]),
                )
                conn.commit()
                item.update({
                    "redeemed_at": redeemed_at,
                    "redeemed_by_id": user_id,
                    "redeemed_by_name": _clean(identity.get("name")),
                    "redeemed_by_role": _clean(identity.get("role")),
                    "status": "redeemed",
                })
                return {"item": item, "image_quota_added": amount, "profile": updated_user}

    def set_enabled(self, code_id: str, enabled: bool) -> dict[str, Any] | None:
        normalized_id = _clean(code_id)
        if not normalized_id:
            return None
        self._ensure_schema()
        with self._lock:
            with self._connect() as conn:
                conn.execute("UPDATE redeem_codes SET enabled = ? WHERE id = ?", (1 if enabled else 0, normalized_id))
                conn.commit()
                row = conn.execute("SELECT * FROM redeem_codes WHERE id = ?", (normalized_id,)).fetchone()
        return self._row_to_item(row) if row else None


redeem_code_service = RedeemCodeService(DATA_DIR / "accounts.db")
