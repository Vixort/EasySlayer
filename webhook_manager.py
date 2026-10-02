import os
import json
import uuid
import time
import datetime
import threading
import urllib.request
import urllib.error

class DiscordWebhookManager:
    """
    Manages Discord Webhook dispatches with rich embeds,
    attached fish screenshots, and session statistics.
    Runs asynchronously in background threads to never block automation.
    """
    def __init__(self, config=None):
        self.config = config or {}

    def update_config(self, config):
        self.config = config

    def send_catch_notification(self, fish_name, total_caught, total_failed, image_bytes=None):
        """Sends rich embed when a fish is successfully caught."""
        webhook_url = self.config.get("webhook_url", "").strip()
        if not self.config.get("webhook_enabled", False) or not webhook_url:
            return

        total_attempts = total_caught + total_failed
        success_rate = (total_caught / total_attempts * 100.0) if total_attempts > 0 else 100.0
        failure_rate = (total_failed / total_attempts * 100.0) if total_attempts > 0 else 0.0

        embed = {
            "title": "🎣 Fish Caught Successfully!",
            "description": f"Successfully reeled in a **{fish_name}**!",
            "color": 0xFACC15,  # Bright golden color
            "fields": [
                {
                    "name": "🐟 Fish Species",
                    "value": f"**{fish_name}**",
                    "inline": True
                },
                {
                    "name": "🎯 Total Attempts",
                    "value": f"{total_attempts}",
                    "inline": True
                },
                {
                    "name": "📊 Success Rate",
                    "value": f"**{success_rate:.1f}%**",
                    "inline": True
                },
                {
                    "name": "✅ Total Caught",
                    "value": f"{total_caught} fish",
                    "inline": True
                },
                {
                    "name": "❌ Total Failed",
                    "value": f"{total_failed} fish",
                    "inline": True
                },
                {
                    "name": "📉 Failure Rate",
                    "value": f"{failure_rate:.1f}%",
                    "inline": True
                }
            ],
            "footer": {
                "text": "EasySlayer Autonomous Fishing Suite"
            },
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        if image_bytes:
            embed["thumbnail"] = {"url": "attachment://fish.png"}

        threading.Thread(
            target=self._dispatch_webhook,
            args=(webhook_url, embed, image_bytes, "fish.png"),
            daemon=True
        ).start()

    def send_test_message(self, webhook_url, callback=None):
        """Sends a test embed to verify webhook connectivity."""
        embed = {
            "title": "✅ EasySlayer Webhook Connected!",
            "description": "Your Discord webhook is configured correctly and ready to receive fish catch alerts!",
            "color": 0x10B981,  # Emerald Green
            "fields": [
                {"name": "Status", "value": "Operational", "inline": True},
                {"name": "Vision Engine", "value": "Multi-Strategy v2.0", "inline": True},
                {"name": "Auto-Collect", "value": "Verified Loop Active", "inline": True}
            ],
            "footer": {"text": "EasySlayer Testing Utility"},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        def _worker():
            success, msg = self._dispatch_webhook(webhook_url, embed)
            if callback:
                callback(success, msg)

        threading.Thread(target=_worker, daemon=True).start()

    def _dispatch_webhook(self, webhook_url, embed_dict, image_bytes=None, filename="fish.png"):
        if not webhook_url:
            return False, "Missing Webhook URL"

        boundary = f"----EasySlayerBoundary{uuid.uuid4().hex}"
        body = bytearray()

        # Part 1: payload_json
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="payload_json"\r\n')
        body.extend(b"Content-Type: application/json\r\n\r\n")
        body.extend(json.dumps({"embeds": [embed_dict]}).encode("utf-8"))
        body.extend(b"\r\n")

        # Part 2: Image attachment (if provided)
        if image_bytes:
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'.encode("utf-8"))
            body.extend(b"Content-Type: image/png\r\n\r\n")
            body.extend(image_bytes)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(
            webhook_url,
            data=bytes(body),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "EasySlayer-Webhook/1.0"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if 200 <= response.status < 300:
                    return True, "Success"
                return False, f"HTTP {response.status}"
        except urllib.error.HTTPError as e:
            return False, f"HTTP Error {e.code}: {e.reason}"
        except Exception as e:
            return False, str(e)
