# Glucose Ambient Hue Monitor 🩸💡

An automated ambient IoT indicator running as a headless daemon on a Raspberry Pi 3B+ to control a Philips Hue smart lamp based on real-time Continuous Glucose Monitor (CGM) thresholds.

## Architecture

```text
[Dexcom Share Cloud API]
          │ (HTTPS Polling Daemon)
          ▼
[Raspberry Pi 3B+] (Headless Debian / Systemd)
          │ (Local REST API over Subnet)
          ▼
[Philips Hue Bridge]
          │ (Zigbee Light Link)
          ▼
[Philips Hue Bloom / Go]
```

## Prerequisites

### 1. Dexcom Share Setup
The Dexcom Share API requires at least one active follower to broadcast live telemetry:
1. Open the **Dexcom App** (G6, G7, or ONE) on your phone.
2. Navigate to **Share / Follow**.
3. Enable sharing and invite at least one contact (e.g. an alternate personal email).
4. Verify the invitation so the follower status shows active.

### 2. Regional Configuration
Dexcom routes account authentication by geography:
* **Canada, UK, Europe, Australia:** Set `"dexcom_region": "ous"` (Outside US).
* **United States:** Set `"dexcom_region": "us"`.

### 3. Local Hardware
* **Raspberry Pi 3B+** (running Raspberry Pi OS Lite, connected to local LAN)
* **Philips Hue Bridge** (connected via Ethernet to the local router)
* **Philips Hue Bloom or Go** (Color & White Ambiance)

## Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/jeaend/glucose_hue.git](https://github.com/jeaend/glucose_hue.git)
   cd glucose_hue
   ```

2. **Configure dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Runtime Configuration:**
   Copy the example template and supply your local Bridge IP, API token, and Dexcom credentials:
   ```bash
   cp config.example.json config.json
   ```

4. **Service Persistence:**
   Install `systemd/glucose-hue.service` to `/etc/systemd/system/` for automatic background execution across reboots.

## Color Alert Tiers (mg/dL)

| Range (mg/dL) | Color State | Alert Meaning |
|---|---|---|
| < 60 | **Dark Red** | Urgent Low |
| 60 – 79 | **Light Red** | Approaching Low |
| 80 – 160 | **Green** | Target In-Range |
| 161 – 200 | **Light Green** | Elevated |
| 201 – 250 | **Light Yellow** | High Warning |
| 251+ | **Dark Yellow** | Urgent High / Spike |
| *No signal / stale* | **Blue** | Sensor warmup or offline |

## License
MIT
