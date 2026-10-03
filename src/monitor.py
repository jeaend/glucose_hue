import json
import logging
import os
import time
from cgm_client import CGMClient
from hue_controller import HueController

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Missing config file at {CONFIG_PATH}. Copy from config.example.json.")
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def evaluate_glucose(sgv: int) -> str:
    """
    Maps blood glucose (mg/dL) to lamp color tiers:
      < 60       -> Dark Red
      60 - 79    -> Light Red
      80 - 160   -> Green
      161 - 200  -> Light Green
      201 - 250  -> Light Yellow
      251+       -> Dark Yellow
    """
    if sgv < 60:
        return "DARK_RED"
    elif sgv <= 79:
        return "LIGHT_RED"
    elif sgv <= 160:
        return "GREEN"
    elif sgv <= 200:
        return "LIGHT_GREEN"
    elif sgv <= 250:
        return "LIGHT_YELLOW"
    else:
        return "DARK_YELLOW"

def main():
    config = load_config()
    hue = HueController(
        bridge_ip=config["hue"]["bridge_ip"],
        api_token=config["hue"]["api_token"],
        light_id=config["hue"]["light_id"]
    )
    cgm = CGMClient(config["cgm"])
    poll_interval = config["cgm"].get("poll_interval_seconds", 300)

    logger.info("Glucose Hue Monitor daemon initialized.")

    while True:
        sgv, trend = cgm.get_latest_reading()

        if sgv is None:
            logger.warning("No fresh glucose reading. Setting lamp to standby BLUE.")
            hue.set_color("BLUE")
        else:
            color = evaluate_glucose(sgv)
            logger.info("Reading: %d mg/dL (Trend: %s) -> Color: %s", sgv, trend, color)
            hue.set_color(color)

        time.sleep(poll_interval)

if __name__ == "__main__":
    main()
