from __future__ import annotations

import unittest
from unittest import mock

from fastapi import HTTPException

from api import support
from services.config import config
from services.sub2api_billing_service import Sub2APIBillingError


class RequireIdentityTests(unittest.TestCase):
    def test_local_identity_does_not_depend_on_sub2api_database(self) -> None:
        local_identity = {"id": "admin", "name": "Admin", "role": "admin"}
        with mock.patch.object(support, "_legacy_admin_identity", return_value=local_identity), mock.patch.object(
            support.auth_service,
            "authenticate",
            return_value=None,
        ), mock.patch.object(
            support.sub2api_billing_service,
            "validate_api_key",
            side_effect=RuntimeError("database unavailable"),
        ) as validate_api_key, mock.patch.dict(config.data, {"sub2api_billing_enabled": True}):
            identity = support.require_identity("Bearer local-admin-key")

        self.assertEqual(identity["id"], "admin")
        self.assertEqual(identity["token"], "local-admin-key")
        validate_api_key.assert_not_called()

    def test_sub2api_database_failure_returns_service_unavailable(self) -> None:
        with mock.patch.object(support, "_legacy_admin_identity", return_value=None), mock.patch.object(
            support.auth_service,
            "authenticate",
            return_value=None,
        ), mock.patch.object(
            support.sub2api_billing_service,
            "validate_api_key",
            side_effect=RuntimeError("database unavailable"),
        ), mock.patch.dict(config.data, {"sub2api_billing_enabled": True}):
            with self.assertRaises(HTTPException) as ctx:
                support.require_identity("Bearer token2-key")

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertNotIn("database unavailable", str(ctx.exception.detail))

    def test_invalid_sub2api_key_still_returns_unauthorized(self) -> None:
        with mock.patch.object(support, "_legacy_admin_identity", return_value=None), mock.patch.object(
            support.auth_service,
            "authenticate",
            return_value=None,
        ), mock.patch.object(
            support.sub2api_billing_service,
            "validate_api_key",
            side_effect=Sub2APIBillingError("invalid key"),
        ), mock.patch.dict(config.data, {"sub2api_billing_enabled": True}):
            with self.assertRaises(HTTPException) as ctx:
                support.require_identity("Bearer invalid-token2-key")

        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
