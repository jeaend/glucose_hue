import json
import logging
import requests

logger = logging.getLogger(__name__)

class HueController:
    """Controls a Philips Hue light via the local Bridge REST API."""

    # Hue (0-65535), Saturation (0-254), Brightness (1-254)
    COLOR_PRESETS = {
        "URGENT_LOW":   {"hue": 0,     "sat": 254, "bri": 254, "alert": "lselect"}, # < 55 (Pulse Red)
        "LOW":          {"hue": 1500,  "sat": 240, "bri": 200, "alert": "none"},    # 55 - 75 (Steady Red)
        "IN_TARGET":    {"hue": 25500, "sat": 254, "bri": 160, "alert": "none"},    # 76 - 160 (Green)
        "LIGHT_YELLOW": {"hue": 13500, "sat": 140, "bri": 160, "alert": "none"},    # 161 - 200 (Rising)
        "DARK_YELLOW":  {"hue": 9500,  "sat": 254, "bri": 180, "alert": "none"},    # > 200 (Amber/Warm Yellow)
        "BLUE":         {"hue": 46920, "sat": 254, "bri": 100, "alert": "none"},    # Stale Data (>15m)
        "WHITE":        {"hue": 0,     "sat": 0,   "bri": 100, "alert": "none"},    # Fallback
    }

    def __init__(self, bridge_ip: str, api_token: str, light_id: str):
        self.endpoint = f"http://{bridge_ip}/api/{api_token}/lights/{light_id}/state"

    def get_preset_for_sgv(self, sgv: int) -> str:
        """Determines the color preset key based on SGV value."""
        if sgv < 55:
            return "URGENT_LOW"
        elif sgv <= 75:
            return "LOW"
        elif sgv <= 160:
            return "IN_TARGET"
        elif sgv <= 200:
            return "LIGHT_YELLOW"
        else:
            return "DARK_YELLOW"

    def set_glucose_state(self, sgv: int, brightness_scale: float = 1.0, is_stale: bool = False) -> bool:
        """
        Calculates preset and scales brightness for daytime vs night.
        - brightness_scale: 1.0 for daytime, ~0.01 for 1% night mode.
        """
        preset_key = "BLUE" if is_stale else self.get_preset_for_sgv(sgv)
        payload = self.COLOR_PRESETS.get(preset_key, self.COLOR_PRESETS["WHITE"]).copy()
        payload["on"] = True

        # Keep urgent low bright (critical safety), otherwise apply night scaling
        if preset_key == "URGENT_LOW":
            payload["bri"] = 254
        else:
            # Hue brightness scale is 1 to 254; ~1% is bri=2 or 3
            scaled_bri = int(payload["bri"] * brightness_scale)
            payload["bri"] = max(2, min(254, scaled_bri))

        return self._send_payload(payload, f"{preset_key} (SGV: {sgv}, Bri: {payload['bri']})")

    def _send_payload(self, payload: dict, label: str) -> bool:
        try:
            response = requests.put(
                self.endpoint,
                data=json.dumps(payload),
                timeout=5
            )
            response.raise_for_status()
            logger.info("Hue state updated to %s", label)
            return True
        except requests.RequestException as exc:
            logger.error("Failed to update Hue light: %s", exc)
            return False