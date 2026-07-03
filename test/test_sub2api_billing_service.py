from decimal import Decimal
import unittest

from services.sub2api_billing_service import Sub2APIBillingService, Sub2APIKeyIdentity


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
    def test_rejects_when_key_quota_remaining_is_insufficient(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="100", quota="0.01", quota_used="0.08")

        error = service._insufficient_funds_error(identity, Decimal("0.04"))

        self.assertIn("秘钥余额不足", error)
        self.assertIn("-0.07", error)

    def test_allows_when_user_balance_and_key_quota_are_sufficient(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="100", quota="1.00", quota_used="0.08")

        error = service._insufficient_funds_error(identity, Decimal("0.04"))

        self.assertEqual(error, "")

    def test_rejects_when_user_balance_is_insufficient_first(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="0.01", quota="1.00", quota_used="0.08")

        error = service._insufficient_funds_error(identity, Decimal("0.04"))

        self.assertIn("余额不足", error)
        self.assertNotIn("秘钥余额不足", error)


if __name__ == "__main__":
    unittest.main()
