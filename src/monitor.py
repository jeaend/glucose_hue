import time
import json
import logging
from datetime import datetime, timezone, time as dtime
from typing import Tuple, List, Dict, Any
import requests
from cgm_client import CGMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("glucose_hue")


class LocalHueController:
    """
    Direct local controller for Philips Hue lights over HTTP REST API.
    Bypasses cloud relays to ensure low-latency local execution.
    """

    def __init__(self, config: dict):
        self.bridge_ip = config.get("bridge_ip") or config.get("ip")
        self.token = config.get("api_token") or config.get("username")
        self.light_id = str(config.get("light_id", 11))
        self.url = f"http://{self.bridge_ip}/api/{self.token}/lights/{self.light_id}/state"

    def set_color_and_brightness(self, xy: List[float], bri: int) -> bool:
        """
        Send an HTTP PUT command to set xy color coordinates and brightness.

        Args:
            xy: Two-element list [x, y] CIE 1931 color coordinates.
            bri: Brightness level clamped between 1 and 254.
        """
        bri = max(1, min(254, int(bri)))
        payload = {"on": True, "xy": xy, "bri": bri}

        try:
            resp = requests.put(self.url, json=payload, timeout=5)
            data = resp.json()
            if isinstance(data, list) and any("success" in item for item in data):
                logger.info(
                    f"Bedroom Light Luka (ID {self.light_id}) -> Color: {xy}, Brightness: {bri}"
                )
                return True
            logger.warning(f"Hue bridge unexpected response: {data}")
            return False
        except Exception as exc:
            logger.error(f"Failed to communicate with Hue Bridge at {self.bridge_ip}: {exc}")
            return False


def get_glucose_state(sgv: int) -> Tuple[List[float], int, str]:
    """
    Maps glucose (mg/dL) to color coordinates (xy), baseline brightness, and label.

    Ranges:
        - SGV < 70:         Red (Low Alert)
        - 70 <= SGV <= 130: Green (In Target)
        - 131 <= SGV <= 180: Yellow (Elevated)
        - SGV > 180:        Orange (High Alert)
    """
    if sgv < 70:
        return [0.675, 0.322], 254, "LOW ALERT (Red)"
    elif sgv <= 130:
        return [0.216, 0.709], 80, "IN TARGET (Green)"
    elif sgv <= 180:
        return [0.543, 0.426], 160, "ELEVATED (Yellow)"
    else:
        return [0.648, 0.351], 254, "HIGH ALERT (Orange)"


def parse_time_str(t_str: str) -> dtime:
    """Helper to convert 'HH:MM' string to datetime.time."""
    h, m = map(int, t_str.split(":"))
    return dtime(h, m)


def is_time_in_range(start: dtime, end: dtime, check_time: dtime) -> bool:
    """
    Checks if check_time is between start and end.
    Properly handles ranges that span across midnight (e.g. 22:30 -> 08:00).
    """
    if start <= end:
        return start <= check_time < end
    else:
        # Crosses midnight
        return check_time >= start or check_time < end


def apply_time_based_intensity(base_bri: int, sgv: int, schedule: List[Dict[str, Any]]) -> int:
    """
    Dynamically finds the active time interval from the config schedule.
    Supports arbitrary lists of intervals and low-glucose safety overrides.
    """
    if not schedule:
        return base_bri

    now_time = datetime.now().astimezone().time()

    for window in schedule:
        start = parse_time_str(window["start"])
        end = parse_time_str(window["end"])

        if is_time_in_range(start, end, now_time):
            # Check for low glucose emergency override
            if sgv < 70 and "low_override_bri" in window:
                logger.info(f"Active window: {window.get('name', 'Custom')} (Emergency Low Override)")
                return window["low_override_bri"]

            scale = window.get("scale", 1.0)
            target_bri = int(base_bri * scale)

            if "max_bri" in window:
                target_bri = min(window["max_bri"], target_bri)

            logger.info(f"Active window: {window.get('name', 'Custom')} (Scale: {scale})")
            return max(1, min(254, target_bri))

    # Fallback if current time falls outside all specified windows
    return base_bri


def calculate_sync_sleep(reading_dt: datetime) -> int:
    """
    Calculates dynamic sleep duration to align with Dexcom's 5-minute hardware cycle.
    """
    now = datetime.now(timezone.utc)
    seconds_old = (now - reading_dt).total_seconds()
    target_interval = 300
    cloud_buffer = 15

    if 0 <= seconds_old < target_interval:
        sleep_needed = (target_interval - seconds_old) + cloud_buffer
        logger.info(
            f"Reading is {int(seconds_old)}s old. Syncing sleep to next cycle: {int(sleep_needed)}s"
        )
        return int(sleep_needed)

    logger.info(f"Reading is {int(seconds_old)}s old (stale/delayed). Quick re-poll in 45s.")
    return 45


def main():
    with open("config.json", "r") as f:
        config = json.load(f)

    cgm = CGMClient(config["cgm"])
    hue = LocalHueController(config["hue"])
    schedule_cfg = config.get("schedule", [])
    logger.info("Glucose Monitor started (Arbitrary Schedule Windows Mode).")

    while True:
        try:
            sgv, trend, reading_dt = cgm.get_latest_reading()

            if sgv is not None and reading_dt is not None:
                xy, base_bri, label = get_glucose_state(sgv)
                final_bri = apply_time_based_intensity(base_bri, sgv, schedule_cfg)

                logger.info(
                    f"SGV: {sgv} mg/dL | Trend: {trend} -> Setting: {label} (Bri: {final_bri})"
                )
                hue.set_color_and_brightness(xy, final_bri)

                sleep_duration = calculate_sync_sleep(reading_dt)
            else:
                logger.warning("No fresh reading. Setting standby dim. Retrying in 60s.")
                hue.set_color_and_brightness([0.457, 0.410], 5)
                sleep_duration = 60

        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            sleep_duration = 60

        time.sleep(sleep_duration)


if __name__ == "__main__":
    main()
