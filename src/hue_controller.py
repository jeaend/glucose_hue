import requests
import json
import logging

logger = logging.getLogger(__name__)

class HueController:
    """Controls a Philips Hue light via the local Bridge REST API."""

    COLOR_PRESETS = {
        "RED": {"hue": 0, "sat": 254, "bri": 200},          # High / Urgent alert
        "YELLOW": {"hue": 12750, "sat": 254, "bri": 180},   # Warning / Edge
        "GREEN": {"hue": 25500, "sat": 254, "bri": 140},    # In Target Range
        "BLUE": {"hue": 46920, "sat": 254, "bri": 140},     # Stale / Informational
        "WHITE": {"hue": 0, "sat": 0, "bri": 100},          # Neutral fallback
    }

    def __init__(self, bridge_ip: str, api_token: str, light_id: str):
        self.endpoint = f"http://{bridge_ip}/api/{api_token}/lights/{light_id}/state"

    def set_color(self, color_name: str) -> bool:
        color_payload = self.COLOR_PRESETS.get(color_name.upper(), self.COLOR_PRESETS["WHITE"]).copy()
        color_payload["on"] = True

        try:
            response = requests.put(
                self.endpoint,
                data=json.dumps(color_payload),
                timeout=5
            )
            response.raise_for_status()
            logger.info("Hue state updated to %s", color_name)
            return True
        except requests.RequestException as exc:
            logger.error("Failed to update Hue light: %s", exc)
            return False
