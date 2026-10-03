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
    """
    Direct local controller for Philips Hue lights over HTTP REST API.
    Bypasses Hue cloud services to ensure instant local network response.
    """

    def __init__(self, config: dict):
        """
        Initialize the local Hue bridge controller.

        Args:
            config: Dictionary containing 'bridge_ip' (or 'ip'), 'api_token'
                    (or 'username'), and 'light_id' (e.g. 11 for Bedroom Light Luka).
        """
        self.bridge_ip = config.get("bridge_ip") or config.get("ip")
        self.token = config.get("api_token") or config.get("username")
        self.light_id = str(config.get("light_id", 11))
        self.url = f"http://{self.bridge_ip}/api/{self.token}/lights/{self.light_id}/state"

    def set_brightness(self, bri: int) -> bool:
        """
        Send an HTTP PUT command to set brightness on the target Hue light.

        Args:
            bri: Brightness level from 1 (dimmest nightlight) to 254 (maximum output).

        Returns:
            bool: True if the bridge confirmed the state change, False otherwise.
        """
        # Clamp brightness to the hardware limits of Hue bulbs
        bri = max(1, min(254, int(bri)))
        payload = {"on": True, "bri": bri}

        try:
            resp = requests.put(self.url, json=payload, timeout=5)
            data = resp.json()
            if isinstance(data, list) and any("success" in item for item in data):
                logger.info(f"Bedroom Light Luka (ID {self.light_id}) brightness -> {bri}")
                return True
            logger.warning(f"Hue bridge unexpected response: {data}")
            return False
        except Exception as exc:
            logger.error(f"Failed to communicate with Hue Bridge at {self.bridge_ip}: {exc}")
            return False


def get_brightness(sgv: int) -> int:
    """
    Evaluate the binary blood glucose threshold logic.

    Rules:
        - SGV <= 130 mg/dL: In range / normal -> Dim nightlight mode (bri: 1)
        - SGV > 130 mg/dL:  High / rising      -> Alert mode (bri: 254)

    Args:
        sgv: Blood glucose concentration in mg/dL.

    Returns:
        int: Brightness value (1 or 254).
    """
    return 1 if sgv <= 130 else 254


def calculate_sync_sleep(reading_dt: datetime) -> int:
    """
    Calculate dynamic sleep duration to align with Dexcom's 5-minute hardware cycle.

    Instead of sleeping a static 300 seconds (which drifts out of phase), this
    inspects how old the latest reading is and sleeps just enough time for the
    next reading to be measured and uploaded to Dexcom Share.

    Args:
        reading_dt: UTC datetime when the CGM sensor recorded the value.

    Returns:
        int: Number of seconds to sleep before the next poll.
    """
    now = datetime.now(timezone.utc)
    seconds_old = (now - reading_dt).total_seconds()

    target_interval = 300   # Dexcom hardware measures every 5 minutes (300s)
    cloud_buffer = 15       # Margin allowing BLE transfer to phone and HTTPS upload to Share

    # Normal case: reading is fresh (< 5 minutes old)
    if 0 <= seconds_old < target_interval:
        sleep_needed = (target_interval - seconds_old) + cloud_buffer
        logger.info(
            f"Reading is {int(seconds_old)}s old. Syncing sleep to next cycle: {int(sleep_needed)}s"
        )
        return int(sleep_needed)

    # Edge case: reading is stale (> 5m old) due to Bluetooth dropout or sensor warmup.
    # Fall back to a fast retry to catch the stream as soon as it recovers.
    logger.info(f"Reading is {int(seconds_old)}s old (stale/delayed). Quick re-poll in 45s.")
    return 45


def main():
    """
    Main background daemon loop.
    Polls Dexcom Share, sets Hue light brightness, and phase-locks sleep cycles.
    """
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

                # Dynamically sleep until the next 5-minute Dexcom window
                sleep_duration = calculate_sync_sleep(reading_dt)
            else:
                # Fallback if Dexcom Share returns empty or network temporarily fails
                logger.warning("No fresh reading. Standby dim (bri: 1). Retrying in 60s.")
                hue.set_brightness(1)
                sleep_duration = 60

        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            sleep_duration = 60

        time.sleep(sleep_duration)


if __name__ == "__main__":
    main()
