from decimal import Decimal
import unittest

from services.sub2api_billing_service import Sub2APIBillingService, Sub2APIKeyIdentity


def make_identity(
    *,
    balance: str = "100",
    quota: str = "0",
    quota_used: str = "0",
    allow_image_generation: object = True,
) -> Sub2APIKeyIdentity:
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
        allow_image_generation=allow_image_generation,
        image_price_1k=Decimal("0.10"),
        image_price_2k=Decimal("0.20"),
        image_price_4k=Decimal("0.40"),
        image_rate_multiplier=Decimal("1"),
        user_group_rate_multiplier=Decimal("0.4"),
    )


class Sub2APIBillingServiceTests(unittest.TestCase):
    def test_image_unit_price_uses_size_tier_and_user_multiplier(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity()

        self.assertEqual(service.image_unit_price(identity, size="1024x1024"), Decimal("0.04000000"))
        self.assertEqual(service.image_unit_price(identity, size="2048x2048"), Decimal("0.08000000"))
        self.assertEqual(service.image_unit_price(identity, size="3840x2160"), Decimal("0.16000000"))

    def test_rejects_when_key_quota_remaining_is_insufficient(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="100", quota="0.01", quota_used="0.08")

        error = service._insufficient_funds_error(identity, Decimal("0.04"))

        self.assertIn("秘钥余额不足", error)
        self.assertIn("-0.07", error)

    def test_charge_balance_uses_key_remaining_when_key_quota_is_set(self) -> None:
        service = Sub2APIBillingService()
        identity = make_identity(balance="100", quota="1.00", quota_used="0.08")

        balance = service._charge_balance_before(identity)

        self.assertEqual(balance, Decimal("0.92"))


if __name__ == "__main__":
    unittest.main()
