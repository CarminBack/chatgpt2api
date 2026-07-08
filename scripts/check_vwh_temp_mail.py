from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.vwh_temp_mail_service import VwhTempMailClient


def _print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a vwh/temp-mail Worker inbox.")
    parser.add_argument("email", nargs="?", help="Email address to query, for example test@mewinyou.shop")
    parser.add_argument("--api-base", default="https://temp-mail.supermewinyou.workers.dev", help="vwh/temp-mail API base URL")
    parser.add_argument("--message-id", help="Fetch one message body by inbox message id")
    parser.add_argument("--health", action="store_true", help="Check Worker/database health")
    parser.add_argument("--domains", action="store_true", help="List accepted domains")
    parser.add_argument("--wait", action="store_true", help="Poll until the mailbox receives at least one message")
    parser.add_argument("--timeout", type=float, default=180, help="Polling timeout in seconds")
    parser.add_argument("--interval", type=float, default=5, help="Polling interval in seconds")
    args = parser.parse_args()

    client = VwhTempMailClient(args.api_base)

    if args.health:
        _print_json(client.health())

    if args.domains:
        _print_json(client.domains())

    if args.message_id:
        _print_json(client.get_message(args.message_id))

    if args.email:
        if args.wait:
            message = client.wait_for_message(args.email, timeout=args.timeout, interval=args.interval)
            _print_json(message.raw if message else {"success": True, "result": []})
        else:
            _print_json([message.raw for message in client.list_messages(args.email)])

    if not any([args.health, args.domains, args.message_id, args.email]):
        parser.error("provide --health, --domains, --message-id, or an email address")


if __name__ == "__main__":
    main()
