import unittest

from services.vwh_temp_mail_service import VwhTempMailClient


class VwhTempMailClientTests(unittest.TestCase):
    def test_domains_returns_string_list(self) -> None:
        client = VwhTempMailClient("https://example.test", request_json=lambda path: {"success": True, "result": ["mewinyou.shop", ""]})

        self.assertEqual(client.domains(), ["mewinyou.shop"])

    def test_list_messages_uses_encoded_email_path(self) -> None:
        seen_paths: list[str] = []

        def request_json(path: str):
            seen_paths.append(path)
            return {
                "success": True,
                "result": [
                    {
                        "id": "msg_1",
                        "from_address": "sender@example.com",
                        "to_address": "codex@mewinyou.shop",
                        "subject": "hello",
                        "received_at": 1783504520,
                    }
                ],
            }

        client = VwhTempMailClient("https://example.test", request_json=request_json)
        messages = client.list_messages("codex@mewinyou.shop")

        self.assertEqual(seen_paths, ["/emails/codex%40mewinyou.shop"])
        self.assertEqual(messages[0].id, "msg_1")
        self.assertEqual(messages[0].subject, "hello")

    def test_get_message_uses_inbox_path(self) -> None:
        seen_paths: list[str] = []

        def request_json(path: str):
            seen_paths.append(path)
            return {"success": True, "result": {"id": "abc", "text": "body"}}

        client = VwhTempMailClient("https://example.test", request_json=request_json)

        self.assertEqual(client.get_message("abc"), {"id": "abc", "text": "body"})
        self.assertEqual(seen_paths, ["/inbox/abc"])

    def test_failed_response_raises(self) -> None:
        client = VwhTempMailClient("https://example.test", request_json=lambda path: {"success": False, "error": "bad"})

        with self.assertRaises(RuntimeError):
            client.domains()


if __name__ == "__main__":
    unittest.main()
