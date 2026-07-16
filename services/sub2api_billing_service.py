from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from services.config import config

SERVICE_NAME = "image3"
REDACTED_API_KEY = "[redacted]"


class Sub2APIBillingError(Exception):
    pass


@dataclass(frozen=True)
class Sub2APIKeyIdentity:
    key: str
    key_id: int
    user_id: int
    user_email: str
    key_status: str
    user_status: str
    balance: Decimal
    key_quota: Decimal
    key_quota_used: Decimal
    group_id: int | None = None
    group_name: str = ""
    group_status: str = ""
    allow_image_generation: bool | None = None
    image_price_1k: Decimal | None = None
    image_price_2k: Decimal | None = None
    image_price_4k: Decimal | None = None
    image_rate_multiplier: Decimal = Decimal("1")
    user_group_rate_multiplier: Decimal = Decimal("1")


class Sub2APIBillingService:
    def _get_dsn(self) -> str:
        dsn = config.sub2api_billing_dsn
        if not dsn:
            raise Sub2APIBillingError("sub2api 计费 DSN 未配置")
        return dsn

    def _connect(self):
        return psycopg2.connect(self._get_dsn(), cursor_factory=RealDictCursor, connect_timeout=5)

    @staticmethod
    def _ensure_log_table(cur) -> None:
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS custom_image_billing_logs (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  action TEXT NOT NULL,
  status TEXT NOT NULL,
  user_id BIGINT NOT NULL,
  api_key_id BIGINT NOT NULL,
  api_key TEXT NOT NULL,
  user_email TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '',
  amount NUMERIC(20,8) NOT NULL DEFAULT 0,
  balance_before NUMERIC(20,8) NOT NULL DEFAULT 0,
  balance_after NUMERIC(20,8) NOT NULL DEFAULT 0,
  refunded_at TIMESTAMPTZ,
  service TEXT NOT NULL DEFAULT 'image3',
  mode TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  prompt_preview TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT ''
)
"""
        )
        cur.execute("ALTER TABLE custom_image_billing_logs ADD COLUMN IF NOT EXISTS service TEXT NOT NULL DEFAULT 'legacy'")
        cur.execute("ALTER TABLE custom_image_billing_logs ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMPTZ")
        cur.execute(
            "UPDATE custom_image_billing_logs SET api_key = %s WHERE api_key IS DISTINCT FROM %s",
            (REDACTED_API_KEY, REDACTED_API_KEY),
        )
        cur.execute(
            """
UPDATE custom_image_billing_logs AS debit
SET refunded_at = refund.created_at
FROM custom_image_billing_logs AS refund
WHERE debit.refunded_at IS NULL
  AND debit.service = refund.service
  AND debit.api_key_id = refund.api_key_id
  AND debit.task_id = refund.task_id
  AND debit.amount = refund.amount
  AND debit.action = 'debit'
  AND debit.status = 'success'
  AND refund.action = 'refund'
  AND refund.status = 'success'
"""
        )

    @staticmethod
    def _log_event(
        cur,
        *,
        action: str,
        status: str,
        user_id: int,
        api_key_id: int,
        user_email: str,
        task_id: str = "",
        amount: Decimal | str | float | int = Decimal("0"),
        balance_before: Decimal | str | float | int = Decimal("0"),
        balance_after: Decimal | str | float | int = Decimal("0"),
        mode: str = "",
        model: str = "",
        prompt_preview: str = "",
        error: str = "",
    ) -> None:
        cur.execute(
            """
INSERT INTO custom_image_billing_logs (
  action, status, user_id, api_key_id, api_key, user_email,
  task_id, amount, balance_before, balance_after, service, mode, model, prompt_preview, error
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""",
            (
                action,
                status,
                user_id,
                api_key_id,
                REDACTED_API_KEY,
                user_email,
                task_id,
                str(amount),
                str(balance_before),
                str(balance_after),
                SERVICE_NAME,
                mode,
                model,
                prompt_preview,
                error,
            ),
        )

    @staticmethod
    def _to_decimal(value: object) -> Decimal:
        try:
            return Decimal(str(value or 0))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @classmethod
    def _optional_decimal(cls, value: object) -> Decimal | None:
        if value is None or str(value).strip() == "":
            return None
        return cls._to_decimal(value)

    @staticmethod
    def _is_false(value: object) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"0", "false", "no", "off"}
        return value is False

    @staticmethod
    def _size_tier(size: str | None) -> str:
        text = str(size or "").strip().lower()
        numbers = [int(item) for item in re.findall(r"\d+", text)]
        max_side = max(numbers) if numbers else 1024
        if max_side <= 1024:
            return "1k"
        if max_side <= 2048:
            return "2k"
        return "4k"

    def _identity_from_row(self, key: str, row: dict[str, Any]) -> Sub2APIKeyIdentity:
        group_id = row.get("group_id")
        return Sub2APIKeyIdentity(
            key=key,
            key_id=int(row["key_id"]),
            user_id=int(row["user_id"]),
            user_email=str(row["user_email"] or "").strip(),
            key_status=str(row["key_status"] or ""),
            user_status=str(row["user_status"] or ""),
            balance=self._to_decimal(row["balance"]),
            key_quota=self._to_decimal(row.get("quota")),
            key_quota_used=self._to_decimal(row.get("quota_used")),
            group_id=int(group_id) if group_id is not None else None,
            group_name=str(row.get("group_name") or "").strip(),
            group_status=str(row.get("group_status") or "").strip(),
            allow_image_generation=row.get("allow_image_generation"),
            image_price_1k=self._optional_decimal(row.get("image_price_1k")),
            image_price_2k=self._optional_decimal(row.get("image_price_2k")),
            image_price_4k=self._optional_decimal(row.get("image_price_4k")),
            image_rate_multiplier=self._to_decimal(row.get("image_rate_multiplier") or 1) or Decimal("1"),
            user_group_rate_multiplier=self._to_decimal(row.get("user_group_rate_multiplier") or 1) or Decimal("1"),
        )

    def _validate_row(self, row: dict[str, Any] | None) -> None:
        if not row:
            raise Sub2APIBillingError("sub2api API key 不存在")
        if str(row["key_status"] or "").lower() != "active":
            raise Sub2APIBillingError("sub2api API key 已禁用")
        if str(row["user_status"] or "").lower() != "active":
            raise Sub2APIBillingError("sub2api 用户已禁用")
        group_status = str(row.get("group_status") or "").strip().lower()
        if group_status and group_status != "active":
            raise Sub2APIBillingError("sub2api 分组已禁用")
        allowed_group_ids = config.sub2api_billing_allowed_group_ids
        allowed_group_names = config.sub2api_billing_allowed_group_names
        if allowed_group_ids or allowed_group_names:
            group_id = row.get("group_id")
            try:
                normalized_group_id = int(group_id) if group_id is not None else 0
            except (TypeError, ValueError):
                normalized_group_id = 0
            group_name = str(row.get("group_name") or "").strip().lower()
            if normalized_group_id not in allowed_group_ids and group_name not in allowed_group_names:
                allowed = ", ".join([*allowed_group_names, *[str(item) for item in allowed_group_ids]])
                raise Sub2APIBillingError(f"当前 sub2api 分组不允许访问 image3，请使用 {allowed} 分组的密钥")

    def _select_key_sql(self, *, for_update: bool = False) -> str:
        suffix = "FOR UPDATE OF k, u" if for_update else "LIMIT 1"
        return f"""
SELECT
  k.id AS key_id, k.key, k.user_id, k.status AS key_status, k.quota, k.quota_used, k.group_id,
  u.email AS user_email, u.status AS user_status, u.balance,
  g.name AS group_name, g.status AS group_status, g.allow_image_generation,
  g.image_price_1k, g.image_price_2k, g.image_price_4k, g.image_rate_multiplier,
  ugrm.rate_multiplier AS user_group_rate_multiplier
FROM api_keys k
JOIN users u ON u.id = k.user_id
LEFT JOIN groups g ON g.id = k.group_id AND g.deleted_at IS NULL
LEFT JOIN user_group_rate_multipliers ugrm ON ugrm.user_id = k.user_id AND ugrm.group_id = k.group_id
WHERE k.key = %s AND k.deleted_at IS NULL
{suffix}
"""

    @staticmethod
    def _usage_window_starts_sql() -> str:
        return """
window_5h_start = COALESCE(window_5h_start, now()),
window_1d_start = COALESCE(window_1d_start, now()),
window_7d_start = COALESCE(window_7d_start, now())
"""

    def _increment_key_usage(self, cur, *, key_id: int, amount: Decimal) -> None:
        cur.execute(
            f"""
UPDATE api_keys
SET
  quota_used = COALESCE(quota_used, 0) + %s,
  usage_5h = COALESCE(usage_5h, 0) + %s,
  usage_1d = COALESCE(usage_1d, 0) + %s,
  usage_7d = COALESCE(usage_7d, 0) + %s,
  last_used_at = now(),
  updated_at = now(),
  {self._usage_window_starts_sql()}
WHERE id = %s
""",
            (str(amount), str(amount), str(amount), str(amount), key_id),
        )

    def _decrement_key_usage(self, cur, *, key_id: int, amount: Decimal) -> None:
        cur.execute(
            f"""
UPDATE api_keys
SET
  quota_used = GREATEST(COALESCE(quota_used, 0) - %s, 0),
  usage_5h = GREATEST(COALESCE(usage_5h, 0) - %s, 0),
  usage_1d = GREATEST(COALESCE(usage_1d, 0) - %s, 0),
  usage_7d = GREATEST(COALESCE(usage_7d, 0) - %s, 0),
  updated_at = now()
WHERE id = %s
""",
            (str(amount), str(amount), str(amount), str(amount), key_id),
        )

    def validate_api_key(self, raw_key: str) -> Sub2APIKeyIdentity:
        key = str(raw_key or "").strip()
        if not key:
            raise Sub2APIBillingError("API key 不能为空")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(self._select_key_sql(), (key,))
                row = cur.fetchone()
        self._validate_row(row)
        return self._identity_from_row(key, row)

    def image_unit_price(self, identity: Sub2APIKeyIdentity, *, size: str | None = None) -> Decimal:
        if self._is_false(identity.allow_image_generation):
            raise Sub2APIBillingError("当前 sub2api 分组未开启图片生成")
        tier = self._size_tier(size)
        group_price = {
            "1k": identity.image_price_1k,
            "2k": identity.image_price_2k,
            "4k": identity.image_price_4k,
        }[tier]
        base_price = group_price if group_price is not None else self._to_decimal(config.image_price_per_request)
        group_multiplier = identity.image_rate_multiplier if identity.image_rate_multiplier > 0 else Decimal("1")
        user_multiplier = (
            identity.user_group_rate_multiplier
            if identity.user_group_rate_multiplier > 0
            else Decimal("1")
        )
        multiplier = group_multiplier * user_multiplier
        return (base_price * multiplier).quantize(Decimal("0.00000001"))

    def image_charge_amount(
        self,
        raw_key: str,
        *,
        image_count: int = 1,
        size: str | None = None,
    ) -> tuple[Sub2APIKeyIdentity, Decimal, Decimal]:
        identity = self.validate_api_key(raw_key)
        unit_price = self.image_unit_price(identity, size=size)
        amount = unit_price * Decimal(max(0, int(image_count or 0)))
        return identity, unit_price, amount.quantize(Decimal("0.00000001"))

    def _uses_key_quota(self, identity: Sub2APIKeyIdentity) -> bool:
        return self._to_decimal(identity.key_quota) > 0

    def _key_remaining(self, identity: Sub2APIKeyIdentity) -> Decimal:
        return self._to_decimal(identity.key_quota) - self._to_decimal(identity.key_quota_used)

    def _insufficient_funds_error(self, identity: Sub2APIKeyIdentity, amount: Decimal) -> str:
        balance = self._to_decimal(identity.balance)
        if balance < amount:
            return f"余额不足：当前 {balance}，需要 {amount}"
        if self._uses_key_quota(identity):
            key_remaining = self._key_remaining(identity)
            if key_remaining < amount:
                return f"秘钥余额不足：当前 {key_remaining}，需要 {amount}"
        return ""

    def _charge_balance_before(self, identity: Sub2APIKeyIdentity) -> Decimal:
        if self._uses_key_quota(identity):
            return self._key_remaining(identity)
        return self._to_decimal(identity.balance)

    def _display_balance_after_refund(self, *, key_quota: Decimal, key_quota_used: Decimal, amount: Decimal) -> Decimal:
        key_remaining = key_quota - key_quota_used
        if key_quota > 0:
            return min(key_quota, key_remaining + amount)
        return key_remaining + amount

    def debit_user_balance(
        self,
        *,
        raw_key: str,
        amount: Decimal,
        task_id: str = "",
        mode: str = "",
        model: str = "",
        prompt_preview: str = "",
    ) -> tuple[Sub2APIKeyIdentity, Decimal]:
        amount = self._to_decimal(amount)
        if amount <= 0:
            raise Sub2APIBillingError("扣费金额必须大于 0")
        key = str(raw_key or "").strip()
        failure_error = ""
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._ensure_log_table(cur)
                cur.execute(self._select_key_sql(for_update=True), (key,))
                row = cur.fetchone()
                self._validate_row(row)
                identity = self._identity_from_row(key, row)
                balance_before = self._charge_balance_before(identity)
                insufficient_error = self._insufficient_funds_error(identity, amount)
                if insufficient_error:
                    self._log_event(
                        cur,
                        action="debit",
                        status="failed",
                        user_id=identity.user_id,
                        api_key_id=identity.key_id,
                        user_email=identity.user_email,
                        task_id=task_id,
                        amount=amount,
                        balance_before=balance_before,
                        balance_after=balance_before,
                        mode=mode,
                        model=model,
                        prompt_preview=prompt_preview,
                        error=insufficient_error,
                    )
                    failure_error = insufficient_error
                    next_balance = balance_before
                else:
                    next_balance = balance_before - amount
                    user_balance_after = self._to_decimal(identity.balance) - amount
                    cur.execute(
                        "UPDATE users SET balance = %s, updated_at = now() WHERE id = %s",
                        (str(user_balance_after), identity.user_id),
                    )
                    self._increment_key_usage(cur, key_id=identity.key_id, amount=amount)
                    self._log_event(
                        cur,
                        action="debit",
                        status="success",
                        user_id=identity.user_id,
                        api_key_id=identity.key_id,
                        user_email=identity.user_email,
                        task_id=task_id,
                        amount=amount,
                        balance_before=balance_before,
                        balance_after=next_balance,
                        mode=mode,
                        model=model,
                        prompt_preview=prompt_preview,
                    )
            conn.commit()
        if failure_error:
            raise Sub2APIBillingError(failure_error)
        return identity, next_balance

    def debit_image_balance(
        self,
        *,
        raw_key: str,
        image_count: int = 1,
        size: str | None = None,
        task_id: str = "",
        mode: str = "",
        model: str = "",
        prompt_preview: str = "",
    ) -> tuple[Sub2APIKeyIdentity, Decimal, Decimal, Decimal]:
        identity, unit_price, amount = self.image_charge_amount(raw_key, image_count=image_count, size=size)
        _, balance_after = self.debit_user_balance(
            raw_key=raw_key,
            amount=amount,
            task_id=task_id,
            mode=mode,
            model=model,
            prompt_preview=prompt_preview,
        )
        return identity, unit_price, amount, balance_after

    def refund_user_balance(
        self,
        *,
        api_key_id: int,
        amount: Decimal,
        task_id: str = "",
        mode: str = "",
        model: str = "",
        prompt_preview: str = "",
        error: str = "",
    ) -> Decimal:
        amount = self._to_decimal(amount)
        if amount <= 0:
            return Decimal("0")
        key_id = int(api_key_id or 0)
        if key_id <= 0:
            raise Sub2APIBillingError("退款失败：sub2api API key ID 无效")
        task_id = str(task_id or "").strip()
        if not task_id:
            raise Sub2APIBillingError("退款失败：task_id 不能为空")
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._ensure_log_table(cur)
                cur.execute(
                    """
SELECT k.id AS key_id, k.user_id, k.quota, k.quota_used, u.email AS user_email, u.balance
FROM api_keys k
JOIN users u ON u.id = k.user_id
WHERE k.id = %s
FOR UPDATE OF k, u
""",
                    (key_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise Sub2APIBillingError("退款失败：sub2api API key 不存在")
                cur.execute(
                    """
SELECT id
FROM custom_image_billing_logs
WHERE service = %s
  AND api_key_id = %s
  AND task_id = %s
  AND amount = %s
  AND action = 'debit'
  AND status = 'success'
  AND refunded_at IS NULL
ORDER BY id DESC
LIMIT 1
FOR UPDATE
""",
                    (SERVICE_NAME, key_id, task_id, str(amount)),
                )
                debit_row = cur.fetchone()
                key_quota = self._to_decimal(row.get("quota"))
                key_quota_used = self._to_decimal(row.get("quota_used"))
                user_balance = self._to_decimal(row["balance"])
                if not debit_row:
                    cur.execute(
                        """
SELECT id
FROM custom_image_billing_logs
WHERE service = %s
  AND api_key_id = %s
  AND task_id = %s
  AND amount = %s
  AND action = 'refund'
  AND status = 'success'
ORDER BY id DESC
LIMIT 1
""",
                        (SERVICE_NAME, key_id, task_id, str(amount)),
                    )
                    if cur.fetchone():
                        current_balance = (
                            key_quota - key_quota_used
                            if key_quota > 0
                            else user_balance
                        )
                        conn.commit()
                        return current_balance
                    raise Sub2APIBillingError("退款失败：找不到对应的未退款扣费记录")
                if key_quota > 0:
                    balance = key_quota - key_quota_used
                    next_balance = self._display_balance_after_refund(
                        key_quota=key_quota,
                        key_quota_used=key_quota_used,
                        amount=amount,
                    )
                else:
                    balance = user_balance
                    next_balance = user_balance + amount
                cur.execute(
                    "UPDATE custom_image_billing_logs SET refunded_at = now() WHERE id = %s",
                    (int(debit_row["id"]),),
                )
                cur.execute(
                    "UPDATE users SET balance = %s, updated_at = now() WHERE id = %s",
                    (str(user_balance + amount), int(row["user_id"])),
                )
                self._decrement_key_usage(cur, key_id=int(row["key_id"]), amount=amount)
                self._log_event(
                    cur,
                    action="refund",
                    status="success",
                    user_id=int(row["user_id"]),
                    api_key_id=int(row["key_id"]),
                    user_email=str(row["user_email"] or "").strip(),
                    task_id=task_id,
                    amount=amount,
                    balance_before=balance,
                    balance_after=next_balance,
                    mode=mode,
                    model=model,
                    prompt_preview=prompt_preview,
                    error=error,
                )
            conn.commit()
        return next_balance

    def list_logs(
        self,
        *,
        limit: int = 200,
        api_key_id: int | None = None,
        user_email: str = "",
        action: str = "",
        status: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        sql = [
            "SELECT id, created_at, action, status, user_id, api_key_id, api_key, user_email, task_id, amount, balance_before, balance_after, service, mode, model, prompt_preview, error",
            "FROM custom_image_billing_logs",
            "WHERE 1=1",
        ]
        params: list[Any] = []
        if api_key_id is not None:
            sql.append("AND api_key_id = %s")
            params.append(int(api_key_id))
        if user_email.strip():
            sql.append("AND user_email ILIKE %s")
            params.append(f"%{user_email.strip()}%")
        if action.strip():
            sql.append("AND action = %s")
            params.append(action.strip())
        if status.strip():
            sql.append("AND status = %s")
            params.append(status.strip())
        if start_date.strip():
            sql.append("AND (created_at AT TIME ZONE 'Asia/Shanghai')::date >= %s::date")
            params.append(start_date.strip())
        if end_date.strip():
            sql.append("AND (created_at AT TIME ZONE 'Asia/Shanghai')::date <= %s::date")
            params.append(end_date.strip())
        sql.append("ORDER BY id DESC LIMIT %s")
        params.append(max(1, min(int(limit or 200), 1000)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._ensure_log_table(cur)
                cur.execute("\n".join(sql), params)
                rows = cur.fetchall() or []
        return [dict(row) for row in rows]


sub2api_billing_service = Sub2APIBillingService()
