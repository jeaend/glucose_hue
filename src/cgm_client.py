import logging
from datetime import timezone
from pydexcom import Dexcom, Region

logger = logging.getLogger("glucose_hue")


class CGMClient:
    def __init__(self, config: dict):
        username = config.get("dexcom_username")
        password = config.get("dexcom_password")
        region_str = config.get("dexcom_region", "ous").lower()
        region = Region.OUS if region_str == "ous" else Region.US

        logger.info(f"Authenticating with Dexcom ({region_str.upper()})...")
        self.dexcom = Dexcom(username=username, password=password, region=region)
        logger.info("Dexcom authentication successful.")

    def get_latest_reading(self):
        """
        Returns (sgv, trend_description, reading_datetime)
        """
        try:
            reading = self.dexcom.get_latest_glucose_reading()
            if reading:
                dt = reading.datetime
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return reading.value, reading.trend_description, dt
            return None, None, None
        except Exception as e:
            logger.error(f"Error querying Dexcom: {e}")
            return None, None, None
