from decimal import Decimal
import unittest
from unittest import mock

from services.sub2api_billing_service import Sub2APIBillingError, Sub2APIBillingService, Sub2APIKeyIdentity


class FakeCursor:
    def __init__(self, rows: list[dict | None] | None = None) -> None:
        self.rows = list(rows or [])
        self.calls: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql: str, params=None) -> None:
        self.calls.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.fake_cursor = cursor
        self.commit_calls = 0
        self.exit_exception_type = object()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.exit_exception_type = exc_type
        return False

    def cursor(self):
        return self.fake_cursor

    def commit(self) -> None:
        self.commit_calls += 1


def make_identity(*, balance: str, quota: str, quota_used: str) -> Sub2APIKeyIdentity:
    return Sub2APIKeyIdentity(
        key="sk-test",
        key_id=1,
        user_id=1,
        user_email="user@example.test",
        key_status="active",
        user_status="active",
        balance=Decimal(balance),
        key_quota=Decimal(quota),
        key_quota_used=Decimal(quota_used),
        group_id=12,
        group_name="image2",
        group_status="active",
        allow_image_generation=True,
    )


class Sub2APIBillingServiceTests(unittest.TestCase):
    @staticmethod
    def database_row(*, balance: str = "100", quota: str = "1", quota_used: str = "0") -> dict:
        return {
            "key_id": 1,
            "user_id": 1,
            "user_email": "user@example.test",
            "email": "user@example.test",
            "key_status": "active",
            "user_status": "active",
            "balance": Decimal(balance),
            "quota": Decimal(quota),
            "quota_used": Decimal(quota_used),
            "group_id": 12,
            "group_name": "image2",
            "group_status": "active",
            "allow_image_generation": True,
            "image_price_1k": Decimal("0.1"),
            "image_price_2k": Decimal("0.2"),
            "image_price_4k": Decimal("0.4"),
            "image_rate_multiplier": Decimal("1"),
            "user_group_rate_multiplier": Decimal("1"),
        }

    def test_rejects_when_key_quota_remaining_is_insufficient(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="100", quota="0.01", quota_used="0.08")

        error = service._insufficient_funds_error(identity, Decimal("0.04"))

        self.assertIn("秘钥余额不足", error)
        self.assertIn("-0.07", error)

    def test_rejects_when_user_balance_is_insufficient_even_if_key_quota_is_sufficient(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="0.01", quota="1.00", quota_used="0.08")

        error = service._insufficient_funds_error(identity, Decimal("0.04"))

        self.assertIn("余额不足", error)
        self.assertNotIn("秘钥余额不足", error)

    def test_allows_when_user_balance_and_key_quota_are_sufficient(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="100", quota="1.00", quota_used="0.08")

        error = service._insufficient_funds_error(identity, Decimal("0.04"))

        self.assertEqual(error, "")

    def test_rejects_when_user_balance_is_insufficient_without_key_quota(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="0.01", quota="0", quota_used="0.08")

        error = service._insufficient_funds_error(identity, Decimal("0.04"))

        self.assertIn("余额不足", error)
        self.assertNotIn("秘钥余额不足", error)

    def test_charge_balance_uses_key_remaining_when_key_quota_is_set(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="100", quota="1.00", quota_used="0.08")

        balance = service._charge_balance_before(identity)

        self.assertEqual(balance, Decimal("0.92"))

    def test_insufficient_funds_log_commits_without_storing_raw_key(self) -> None:
        cursor = FakeCursor([self.database_row(balance="0.01", quota="0")])
        connection = FakeConnection(cursor)
        service = Sub2APIBillingService()

        with mock.patch.object(service, "_connect", return_value=connection):
            with self.assertRaises(Sub2APIBillingError):
                service.debit_user_balance(
                    raw_key="sk-secret-value",
                    amount=Decimal("0.04"),
                    task_id="task-failed",
                )

        self.assertEqual(connection.commit_calls, 1)
        self.assertIsNone(connection.exit_exception_type)
        insert_params = next(params for sql, params in cursor.calls if "INSERT INTO custom_image_billing_logs" in sql)
        self.assertEqual(insert_params[1], "failed")
        self.assertEqual(insert_params[4], "[redacted]")
        self.assertNotIn("sk-secret-value", repr(insert_params))

    def test_refund_is_idempotent_by_key_and_task(self) -> None:
        first_cursor = FakeCursor([
            self.database_row(balance="10", quota="0", quota_used="0.04"),
            {"id": 41},
        ])
        second_cursor = FakeCursor([
            self.database_row(balance="10.04", quota="0", quota_used="0"),
            None,
            {"id": 42},
        ])
        connections = [FakeConnection(first_cursor), FakeConnection(second_cursor)]
        service = Sub2APIBillingService()

        with mock.patch.object(service, "_connect", side_effect=connections):
            first_balance = service.refund_user_balance(
                api_key_id=1,
                amount=Decimal("0.04"),
                task_id="task-refund",
            )
            second_balance = service.refund_user_balance(
                api_key_id=1,
                amount=Decimal("0.04"),
                task_id="task-refund",
            )

        self.assertEqual(first_balance, Decimal("10.04"))
        self.assertEqual(second_balance, Decimal("10.04"))
        self.assertTrue(any("UPDATE users SET balance" in sql for sql, _ in first_cursor.calls))
        self.assertFalse(any("UPDATE users SET balance" in sql for sql, _ in second_cursor.calls))


if __name__ == "__main__":
    unittest.main()
