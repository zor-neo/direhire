from typing import Any

import httpx


class TelegramSender:
    def __init__(self, bot_token: str) -> None:
        self.endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send(self, destination: str, text: str) -> str:
        with httpx.Client(trust_env=False, timeout=20) as client:
            response = client.post(
                self.endpoint,
                json={"chat_id": destination, "text": text, "protect_content": True},
            )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        if not body.get("ok") or not isinstance(body.get("result"), dict):
            raise ValueError("telegram delivery was not accepted")
        return str(body["result"]["message_id"])


class WhatsAppSender:
    def __init__(self, access_token: str, phone_number_id: str, graph_version: str) -> None:
        self.access_token = access_token
        self.endpoint = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"

    def send(self, destination: str, text: str) -> str:
        with httpx.Client(trust_env=False, timeout=20) as client:
            response = client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": destination.removeprefix("+"),
                    "type": "text",
                    "text": {"preview_url": False, "body": text},
                },
            )
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages or not isinstance(messages[0], dict):
            raise ValueError("whatsapp delivery was not accepted")
        return str(messages[0]["id"])
