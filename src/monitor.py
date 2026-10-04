import time
import json
import logging
from datetime import datetime, timezone, time as dtime
from typing import Tuple, List, Dict, Any, Optional
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
        self.light_id = str(config.get("light_id", 14))
        self.url = f"http://{self.bridge_ip}/api/{self.token}/lights/{self.light_id}/state"
        self.light_name = self._fetch_light_name()

    def _fetch_light_name(self) -> str:
        """Dynamically fetch the configured light name from the Hue bridge."""
        try:
            r = requests.get(
                f"http://{self.bridge_ip}/api/{self.token}/lights/{self.light_id}",
                timeout=4
            )
            if r.status_code == 200:
                return r.json().get("name", f"Light {self.light_id}")
        except Exception:
            pass
        return f"Light {self.light_id}"

    def set_state(self, xy: List[float], bri: int, alert: str = "none") -> bool:
        """
        Send an HTTP PUT command to set xy color coordinates, brightness, and alert pulse.

        Args:
            xy: Two-element list [x, y] CIE 1931 color coordinates.
            bri: Brightness level clamped between 1 and 254.
            alert: 'none' for steady state, 'lselect' for breathing pulse.
        """
        bri = max(1, min(254, int(bri)))
        payload = {"on": True, "xy": xy, "bri": bri, "alert": alert}

        try:
            resp = requests.put(self.url, json=payload, timeout=5)
            data = resp.json()
            if isinstance(data, list) and any("success" in item for item in data):
                logger.info(
                    f"{self.light_name} (ID {self.light_id}) -> Color: {xy}, Brightness: {bri}, Alert: {alert}"
                )
                return True
            logger.warning(f"Hue bridge unexpected response: {data}")
            return False
        except Exception as exc:
            logger.error(f"Failed to communicate with Hue Bridge at {self.bridge_ip}: {exc}")
            return False


def get_glucose_state(sgv: int) -> Tuple[List[float], int, str, str]:
    """
    Maps glucose (mg/dL) to color coordinates (xy), baseline brightness, label, and alert style.

    Ranges:
        - SGV < 55:          Urgent Low (Pulsing Deep Red)
        - 55 <= SGV <= 75:   Low (Steady Red)
        - 76 <= SGV <= 160:  In Target (Green)
        - 161 <= SGV <= 200: Rising (Light Yellow)
        - SGV > 200:         High (Dark Amber Yellow)
    """
    if sgv < 55:
        # Breathing pulse alert (lselect) for critical lows
        return [0.675, 0.322], 254, "URGENT LOW (Pulsing Red)", "lselect"
    elif sgv <= 75:
        return [0.675, 0.322], 200, "LOW ALERT (Steady Red)", "none"
    elif sgv <= 160:
        return [0.210, 0.700], 140, "IN TARGET (Green)", "none"
    elif sgv <= 200:
        # Light Lemon Yellow
        return [0.460, 0.490], 160, "RISING (Light Yellow)", "none"
    else:
        # Dark Amber Yellow (clearly distinct from red)
        return [0.550, 0.440], 200, "HIGH (Dark Yellow)", "none"


def parse_time_str(t_str: str) -> dtime:
    """Helper to convert 'HH:MM' string to datetime.time."""
    h, m = map(int, t_str.split(":"))
    return dtime(h, m)


def is_time_in_range(start: dtime, end: dtime, check_time: dtime) -> bool:
    """
    Checks if check_time is between start and end.
    Handles ranges that span across midnight (e.g. 22:30 -> 07:30).
    """
    if start <= end:
        return start <= check_time < end
    else:
        return check_time >= start or check_time < end


def apply_time_based_intensity(base_bri: int, sgv: int, schedule: List[Dict[str, Any]]) -> int:
    """
    Dynamically finds the active time interval from the config schedule.
    Supports low glucose safety overrides and 1% night mode floor.
    """
    if not schedule:
        return base_bri

    now_time = datetime.now().astimezone().time()

    for window in schedule:
        start = parse_time_str(window["start"])
        end = parse_time_str(window["end"])

        if is_time_in_range(start, end, now_time):
            # Critical low safety override: always pierce through night dimming
            if sgv < 55:
                logger.info(f"Active window: {window.get('name', 'Custom')} (Urgent Low Override -> 100%)")
                return 254
            elif sgv <= 75 and "low_override_bri" in window:
                logger.info(f"Active window: {window.get('name', 'Custom')} (Low Safety Override)")
                return window["low_override_bri"]

            scale = window.get("scale", 1.0)
            target_bri = int(base_bri * scale)

            if "max_bri" in window:
                target_bri = min(window["max_bri"], target_bri)

            logger.info(f"Active window: {window.get('name', 'Custom')} (Scale: {scale})")
            # Clamp between hardware min 1% (~2) and max (254)
            return max(2, min(254, target_bri))

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

    logger.info(f"Reading is {int(seconds_old)}s old. Quick re-poll in 45s.")
    return 45


def main():
    with open("config.json", "r") as f:
        config = json.load(f)

    cgm = CGMClient(config["cgm"])
    hue = LocalHueController(config["hue"])
    schedule_cfg = config.get("schedule", [])
    logger.info(f"Glucose Monitor started for {hue.light_name} (ID {hue.light_id}).")

    while True:
        try:
            sgv, trend, reading_dt = cgm.get_latest_reading()

            if sgv is not None and reading_dt is not None:
                # Check for stale reading (> 15 minutes old)
                age_seconds = (datetime.now(timezone.utc) - reading_dt).total_seconds()
                
                if age_seconds > 900:  # 15 minutes
                    logger.warning(f"Data is stale ({int(age_seconds / 60)}m old). Setting soft blue indicator.")
                    # Soft Dim Blue for stale/sensor dropout
                    hue.set_state(xy=[0.168, 0.131], bri=10, alert="none")
                    sleep_duration = 60
                else:
                    xy, base_bri, label, alert = get_glucose_state(sgv)
                    final_bri = apply_time_based_intensity(base_bri, sgv, schedule_cfg)

                    logger.info(
                        f"SGV: {sgv} mg/dL | Trend: {trend} -> Setting: {label} (Bri: {final_bri})"
                    )
                    hue.set_state(xy=xy, bri=final_bri, alert=alert)
                    sleep_duration = calculate_sync_sleep(reading_dt)
            else:
                logger.warning("No reading received from CGM. Setting standby dim.")
                hue.set_state(xy=[0.168, 0.131], bri=5, alert="none")
                sleep_duration = 60

        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            sleep_duration = 60

        time.sleep(sleep_duration)


if __name__ == "__main__":
    main()