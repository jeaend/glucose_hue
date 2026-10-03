import json
import logging
import requests

logger = logging.getLogger(__name__)

class HueController:
    """Controls a Philips Hue light via the local Bridge REST API."""

    # Hue (0-65535), Saturation (0-254), Brightness (1-254)
    COLOR_PRESETS = {
        "DARK_RED":     {"hue": 0,     "sat": 254, "bri": 220},  # < 60
        "LIGHT_RED":    {"hue": 2000,  "sat": 140, "bri": 180},  # 60 - 79
        "GREEN":        {"hue": 25500, "sat": 254, "bri": 160},  # 80 - 160
        "LIGHT_GREEN":  {"hue": 21000, "sat": 160, "bri": 160},  # 161 - 200
        "LIGHT_YELLOW": {"hue": 14000, "sat": 140, "bri": 180},  # 201 - 250
        "DARK_YELLOW":  {"hue": 10500, "sat": 254, "bri": 200},  # 251+ (Amber/Dark Yellow)
        "BLUE":         {"hue": 46920, "sat": 254, "bri": 140},  # Stale / Offline
        "WHITE":        {"hue": 0,     "sat": 0,   "bri": 100},  # Fallback
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
