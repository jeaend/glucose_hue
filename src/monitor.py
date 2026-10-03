import time
import json
import logging
from datetime import datetime, timezone
import requests
from cgm_client import CGMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("glucose_hue")


class LocalHueController:
    def __init__(self, config: dict):
        self.bridge_ip = config.get("bridge_ip") or config.get("ip")
        self.token = config.get("api_token") or config.get("username")
        self.light_id = str(config.get("light_id", 11))
        self.url = f"http://{self.bridge_ip}/api/{self.token}/lights/{self.light_id}/state"

    def set_brightness(self, bri: int):
        bri = max(1, min(254, int(bri)))
        payload = {"on": True, "bri": bri}
        try:
            resp = requests.put(self.url, json=payload, timeout=5)
            data = resp.json()
            if isinstance(data, list) and any("success" in item for item in data):
                logger.info(f"Bedroom Light Luka (ID {self.light_id}) brightness -> {bri}")
                return True
            logger.warning(f"Hue bridge response: {data}")
            return False
        except Exception as exc:
            logger.error(f"Failed to communicate with Hue Bridge: {exc}")
            return False


def get_brightness(sgv: int) -> int:
    return 1 if sgv <= 130 else 254


def calculate_sync_sleep(reading_dt: datetime) -> int:
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
    logger.info("Glucose Monitor started (Timestamp-Synchronized Sleep Mode).")

    while True:
        try:
            sgv, trend, reading_dt = cgm.get_latest_reading()

            if sgv is not None and reading_dt is not None:
                bri = get_brightness(sgv)
                label = "REALLY DARK (bri: 1)" if bri == 1 else "SUPER BRIGHT (bri: 254)"
                logger.info(f"SGV: {sgv} mg/dL | Trend: {trend} -> Setting: {label}")
                hue.set_brightness(bri)
                sleep_duration = calculate_sync_sleep(reading_dt)
            else:
                logger.warning("No fresh reading. Standby dim (bri: 1). Retry in 60s.")
                hue.set_brightness(1)
                sleep_duration = 60

        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            sleep_duration = 60

        time.sleep(sleep_duration)


if __name__ == "__main__":
    main()
