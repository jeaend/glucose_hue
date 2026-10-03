import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from pydexcom import Dexcom, Region

logger = logging.getLogger("glucose_hue")


class CGMClient:
    """
    Client interface for querying blood glucose data from Dexcom Share servers.
    Handles authentication across geographic regions (US vs. OUS/Canada)
    and normalizes timestamps to UTC for phase-locked sleep calculations.
    """

    def __init__(self, config: dict):
        """
        Initialize and authenticate the Dexcom Share session.

        Args:
            config: Dictionary containing 'dexcom_username', 'dexcom_password',
                    and optional 'dexcom_region' ('ous' or 'us').
        """
        username = config.get("dexcom_username")
        password = config.get("dexcom_password")
        region_str = config.get("dexcom_region", "ous").lower()

        region = Region.OUS if region_str == "ous" else Region.US

        logger.info(f"Authenticating with Dexcom ({region_str.upper()})...")
        self.dexcom = Dexcom(username=username, password=password, region=region)
        logger.info("Dexcom authentication successful.")

    def get_latest_reading(self) -> Tuple[Optional[int], Optional[str], Optional[datetime]]:
        """
        Fetch the most recent glucose entry from Dexcom Share.

        Returns:
            Tuple of:
                - sgv (int or None): Serum glucose value in mg/dL.
                - trend (str or None): Direction description (e.g. 'steady').
                - reading_datetime (datetime or None): Timezone-aware UTC timestamp
                  representing when the sensor took the measurement.
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
            logger.error(f"Error querying Dexcom Share API: {e}")
            return None, None, None
