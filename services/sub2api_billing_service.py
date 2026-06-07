from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from services.config import config


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


class Sub2APIBillingService:
    def __init__(self) -> None:
        self._dsn: str | None = None

    def _get_dsn(self) -> str:
        dsn = config.sub2api_billing_dsn
        if not dsn:
            raise Sub2APIBillingError("sub2api 计费 DSN 未配置")
        return dsn

    def _connect(self):
        return psycopg2.connect(self._get_dsn(), cursor_factory=RealDictCursor)

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
  mode TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  prompt_preview TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT ''
)
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
        api_key: str,
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
  task_id, amount, balance_before, balance_after, mode, model, prompt_preview, error
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""",
            (
                action,
                status,
                user_id,
                api_key_id,
                api_key,
                user_email,
                task_id,
                str(amount),
                str(balance_before),
                str(balance_after),
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

    def validate_api_key(self, raw_key: str) -> Sub2APIKeyIdentity:
        key = str(raw_key or "").strip()
        if not key:
            raise Sub2APIBillingError("API key 不能为空")
        sql = """
SELECT k.id AS key_id, k.key, k.user_id, k.status AS key_status, k.quota, k.quota_used,
       u.email AS user_email, u.status AS user_status, u.balance
FROM api_keys k
JOIN users u ON u.id = k.user_id
WHERE k.key = %s AND k.deleted_at IS NULL
LIMIT 1
"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (key,))
                row = cur.fetchone()
        if not row:
            raise Sub2APIBillingError("sub2api API key 不存在")
        if str(row["key_status"] or "").lower() != "active":
            raise Sub2APIBillingError("sub2api API key 已禁用")
        if str(row["user_status"] or "").lower() != "active":
            raise Sub2APIBillingError("sub2api 用户已禁用")
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
        )

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
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._ensure_log_table(cur)
                cur.execute(
                    """
SELECT k.id AS key_id, k.key, k.user_id, k.status AS key_status, k.quota, k.quota_used,
       u.email AS user_email, u.status AS user_status, u.balance
FROM api_keys k
JOIN users u ON u.id = k.user_id
WHERE k.key = %s AND k.deleted_at IS NULL
FOR UPDATE
""",
                    (key,),
                )
                row = cur.fetchone()
                if not row:
                    raise Sub2APIBillingError("sub2api API key 不存在")
                if str(row["key_status"] or "").lower() != "active":
                    raise Sub2APIBillingError("sub2api API key 已禁用")
                if str(row["user_status"] or "").lower() != "active":
                    raise Sub2APIBillingError("sub2api 用户已禁用")
                balance = self._to_decimal(row["balance"])
                if balance < amount:
                    self._log_event(
                        cur,
                        action="debit",
                        status="failed",
                        user_id=int(row["user_id"]),
                        api_key_id=int(row["key_id"]),
                        api_key=key,
                        user_email=str(row["user_email"] or "").strip(),
                        task_id=task_id,
                        amount=amount,
                        balance_before=balance,
                        balance_after=balance,
                        mode=mode,
                        model=model,
                        prompt_preview=prompt_preview,
                        error=f"余额不足：当前 {balance}，需要 {amount}",
                    )
                    raise Sub2APIBillingError(f"余额不足：当前 {balance}，需要 {amount}")
                next_balance = balance - amount
                cur.execute(
                    "UPDATE users SET balance = %s, updated_at = now() WHERE id = %s",
                    (str(next_balance), int(row["user_id"])),
                )
                self._log_event(
                    cur,
                    action="debit",
                    status="success",
                    user_id=int(row["user_id"]),
                    api_key_id=int(row["key_id"]),
                    api_key=key,
                    user_email=str(row["user_email"] or "").strip(),
                    task_id=task_id,
                    amount=amount,
                    balance_before=balance,
                    balance_after=next_balance,
                    mode=mode,
                    model=model,
                    prompt_preview=prompt_preview,
                )
            conn.commit()
        identity = Sub2APIKeyIdentity(
            key=key,
            key_id=int(row["key_id"]),
            user_id=int(row["user_id"]),
            user_email=str(row["user_email"] or "").strip(),
            key_status=str(row["key_status"] or ""),
            user_status=str(row["user_status"] or ""),
            balance=next_balance,
            key_quota=self._to_decimal(row.get("quota")),
            key_quota_used=self._to_decimal(row.get("quota_used")),
        )
        return identity, next_balance

    def refund_user_balance(
        self,
        *,
        raw_key: str,
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
        key = str(raw_key or "").strip()
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._ensure_log_table(cur)
                cur.execute(
                    """
SELECT k.id AS key_id, k.user_id, u.email, u.balance
FROM api_keys k
JOIN users u ON u.id = k.user_id
WHERE k.key = %s AND k.deleted_at IS NULL
FOR UPDATE
""",
                    (key,),
                )
                row = cur.fetchone()
                if not row:
                    raise Sub2APIBillingError("退款失败：sub2api API key 不存在")
                balance = self._to_decimal(row["balance"])
                next_balance = balance + amount
                cur.execute(
                    "UPDATE users SET balance = %s, updated_at = now() WHERE id = %s",
                    (str(next_balance), int(row["user_id"])),
                )
                self._log_event(
                    cur,
                    action="refund",
                    status="success",
                    user_id=int(row["user_id"]),
                    api_key_id=int(row["key_id"]),
                    api_key=key,
                    user_email=str(row["email"] or "").strip(),
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
        user_email: str = "",
        action: str = "",
        status: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> list[dict[str, Any]]:
        sql = [
            "SELECT id, created_at, action, status, user_id, api_key_id, api_key, user_email, task_id, amount, balance_before, balance_after, mode, model, prompt_preview, error",
            "FROM custom_image_billing_logs",
            "WHERE 1=1",
        ]
        params: list[Any] = []
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
            sql.append("AND created_at::date >= %s::date")
            params.append(start_date.strip())
        if end_date.strip():
            sql.append("AND created_at::date <= %s::date")
            params.append(end_date.strip())
        sql.append("ORDER BY id DESC LIMIT %s")
        params.append(max(1, min(int(limit or 200), 1000)))
        query = "\n".join(sql)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._ensure_log_table(cur)
                cur.execute(query, params)
                rows = cur.fetchall() or []
        return [dict(row) for row in rows]


sub2api_billing_service = Sub2APIBillingService()
