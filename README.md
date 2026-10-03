# Glucose Ambient Hue Monitor 🩸💡

An automated ambient IoT indicator running as a headless daemon on a Raspberry Pi 3B+ to control a Philips Hue smart lamp based on real-time Continuous Glucose Monitor (CGM) thresholds.

## Architecture

Dexcom Share Cloud API -> Raspberry Pi 3B+ (Systemd) -> Philips Hue Bridge -> Philips Hue Bloom / Go

## Prerequisites

### 1. Dexcom Share Setup
The Dexcom Share API requires at least one active follower to broadcast live telemetry:
1. Open the Dexcom App (G6, G7, or ONE) on your phone.
2. Navigate to Share / Follow.
3. Enable sharing and invite at least one contact (e.g. an alternate personal email).
4. Verify the invitation so the follower status shows active.

### 2. Regional Configuration
Dexcom routes account authentication by geography:
* Canada, UK, Europe, Australia: set "dexcom_region": "ous" (Outside US)
* United States: set "dexcom_region": "us"

### 3. Hardware
* Raspberry Pi 3B+ (Raspberry Pi OS Lite, connected to local LAN)
* Philips Hue Bridge (connected via Ethernet to local router)
* Philips Hue Bloom or Go (Color & White Ambiance)

## Setup & Installation

1. Clone repository:
   git clone https://github.com/<your-username>/glucose_hue.git
   cd glucose_hue

2. Configure dependencies:
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

3. Runtime Configuration:
   cp config.example.json config.json

4. Service Persistence:
   Install systemd/glucose-hue.service to /etc/systemd/system/ for persistence on boot.

## Color Alert Tiers (mg/dL)
* Red: Urgent Low (<= 55) or Urgent High (>= 250)
* Yellow: Low (56-70) or High (181-249)
* Green: Target In-Range (80-140)
* Blue: Sensor warm-up, missed reading, or stale signal

## License
MIT
