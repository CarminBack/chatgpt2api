from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from services.register_service import RegisterService


class RegisterServiceValidationTests(unittest.TestCase):
    def make_service(self, directory: str) -> RegisterService:
        return RegisterService(Path(directory) / "register_config.json")

    def test_enabled_cloudmail_requires_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(tmp_dir)

            with self.assertRaisesRegex(ValueError, "CloudMailGen"):
                service.update({
                    "mail": {
                        "providers": [
                            {"type": "cloudmail_gen", "enable": True, "domain": []},
                        ]
                    }
                })

    def test_disabled_cloudmail_can_be_saved_without_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = self.make_service(tmp_dir)

            result = service.update({
                "mail": {
                    "providers": [
                        {"type": "cloudmail_gen", "enable": False, "domain": []},
                    ]
                }
            })

        self.assertEqual(result["mail"]["providers"][0]["type"], "cloudmail_gen")


if __name__ == "__main__":
    unittest.main()
