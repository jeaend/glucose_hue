# Glucose Ambient Hue Monitor 🩸💡

An automated ambient glucose level indicator running as a headless daemon on a Raspberry Pi 3B+ to control a Philips Hue smart lamp based on real-time Continuous Glucose Monitor (CGM) thresholds and light intensity based on timing. 

## Architecture

```text
[Dexcom Share Cloud API]
          │ (HTTPS Polling Daemon)
          ▼
[Raspberry Pi 3B+] (Headless Debian / Systemd)
          │ (Local REST API over Subnet)
          ▼
[Philips Hue Bridge]
          │ 
          ▼
[Philips Hue Go]
```

## Prerequisites

Local Hardware Used in my Setup
* **Raspberry Pi 3B+** (running Raspberry Pi OS Lite)
* **Philips Hue Bridge** (connected via Ethernet to the local router)
* **Philips Hue Go** (connected to Bridge)

* **Dexcom G7** with share activated (should also work for G6 and one)

## Setup
### Dexcom Share Setup
The Dexcom Share API requires at least one active follower to broadcast live telemetry:
1. Open the **Dexcom App** on your phone.
2. Navigate to **Share / Follow**.
3. Enable sharing and invite at least one contact with Trend and Graph (e.g. an alternate personal email, could do a your_email+share@xxx.com).

### Philips Hue Setup

The monitor bypasses cloud relays and communicates directly with your Philips Hue Bridge over your local area network using the local Hue REST API.
Make sure you have the bridge setup, lamp connected.


## Installation

> **Note:** All the following steps are meant to be executed directly in the Raspberry Pi terminal (via SSH or a direct monitor/keyboard session).

### 0. Connect via SSH (Optional)
If running headless from your computer, connect to your Pi first:
```bash
ssh <username>@<raspberry_pi_ip>
# Example: ssh yourraspberrypiname@raspberrypi.local
``` 

### 1. Raspberry Pi Initial Setup
On a fresh install of Raspberry Pi OS Lite, update the system packages and install the prerequisites:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl
```

### 2. Clone the Repository
```bash
git clone [https://github.com/jeaend/glucose_hue.git](https://github.com/jeaend/glucose_hue.git)
cd glucose_hue
```

### 3. Configure Dependencies
Set up an isolated virtual environment and install project packages:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Runtime Configuration
Copy the template and supply your local Bridge IP, API token, Dexcom credentials, and schedule preferences:

```bash
cp config.example.json config.json
nano config.json
```
   
#### "cgm":
- This is the main account credentials, not the person receiving the shared data
- "dexcom_username": Use your phone number with area code, eg. "+19998887777" 
- "dexcom_password": self explanatory, eh
- "dexcom_region": Dexcom routes account authentication by geography:* **Canada, UK, Europe, Australia:** Set `"dexcom_region": "ous"` (Outside US) or **United States:** Set `"dexcom_region": "us"`
This needs to match your Dexcom account setup.

#### "hue": 
- "bridge_ip": Ensure your Hue Bridge is on the same local subnet as the Raspberry Pi. You can find its IP address (`bridge_ip`) via your router’s DHCP client list or inside the official Hue app (Settings → Bridge settings → Network settings 

- "api_token": Philips Hue requires a whitelist token for local HTTP requests
1. Physically press the large round button on top of your Philips Hue Bridge.
2. Within 30 seconds, run the following command from your terminal (replacing `<BRIDGE_IP>` with your bridge's actual IP) from the first step:
   ```bash
   curl -X POST -d '{"devicetype":"glucose_monitor#pi"}' http://<BRIDGE_IP>/api
   
   The response will look sth like 
   ```json
   [{"success":{"username":"1028d6642...b32"}}]
   ```
3. use the username string as the api_token
- "light_id": 
1. Query all connected lights using your Bridge IP and API token:
   ```bash
   curl http://<BRIDGE_IP>/api/<YOUR_API_TOKEN>/lights
   ```
2. The bridge returns a JSON map containing all paired lights. Locate your target light by its configured name, use the number as your id:
   ```json
      {
        "11": {
          "state": { "on": true, "bri": 80 },
          "name": "Glucose monitor Lamp",
        }
      }
   ```
   
#### "schedule":
Defines time-of-day windows to scale lamp brightness automatically (e.g. keeping it dim at night so it doesn't wake you up, but brighter during the day). You can modify, add, or remove windows in the list to fit your personal daily routine. Just ensure all 24 hours of the day are covered so the lamp always knows what brightness level to use.
- "name": A label for the window (e.g. "Day", "Night", "Evening") for logging.
- "start" and "end": 24-hour time format (`"HH:MM"`). Windows spanning past midnight (e.g. `"22:30"` to `"08:00"`) work automatically.
- "scale": Multiplier from `0.0` to `1.0` applied to default brightness.
- "max_bri": (Optional) Hard cap on brightness (`1`-`254`) during this window so normal readings stay subtle.
- "low_override_bri": (Optional) Brightness level (`1`-`254`) to jump to if glucose hits an urgent low, bypassing `scale` and `max_bri` to get your attention immediately.

### 5. Background Daemon Setup (systemd)

To make the monitor run 24/7 and automatically start whenever the Raspberry Pi boots or reboots, install it as a `systemd` system service.

> **Note:** Before copying, verify that `User`, `WorkingDirectory`, and `ExecStart` inside `systemd/glucose-hue.service` match your Raspberry Pi username and virtual environment path.

Run these commands directly on the Raspberry Pi:

1. **Copy the service file into the system folder:**
   ```bash
   sudo cp systemd/glucose-hue.service /etc/systemd/system/
   ```

2. **Reload systemd to pick up the new file:**
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Enable auto-start on boot and start the daemon immediately:**
   ```bash
   sudo systemctl enable --now glucose-hue.service
   ```

4. **Verify the service is running:**
   ```bash
   sudo systemctl status glucose-hue.service
   ```

5. **Follow live logs in real time:**
   ```bash
   journalctl -u glucose-hue.service -f
   ```
   *(Press `Ctrl + C` anytime to exit log viewing without stopping the service.)*
