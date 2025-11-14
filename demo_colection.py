import tinytuya
import time
import csv
from datetime import datetime
import os
import sys

# ----------------------------
# CONFIGURATION (Cloud Mode)
# ----------------------------
API_REGION = "sg"
API_KEY = "htuaxqpwyd7fhhp5cqn3"
API_SECRET = "a05a16ec5a9b4daba8c4947320172831"
DEVICE_ID = "a32bc8e7d1a6db3d9abhib"

CSV_FILE = "demo.csv"
POLL_INTERVAL = 5 # seconds
# ----------------------------

# --- 1. Cloud Connection & Error Check ---
try:
    # Initialize Cloud connection
    cloud = tinytuya.Cloud(
        apiRegion=API_REGION,
        apiKey=API_KEY,
        apiSecret=API_SECRET,
        apiDeviceID=DEVICE_ID
    )
    # Ping the cloud to verify credentials immediately (optional, but good practice)
    cloud.getdevices() 
    print("✅ Successfully connected to Tuya Cloud.")
except Exception as e:
    print(f"❌ FATAL ERROR: Could not initialize or connect to Tuya Cloud. Check credentials and region: {e}")
    sys.exit(1)

# --- 2. CSV Initialization and Energy Load ---
file_exists = os.path.isfile(CSV_FILE)
with open(CSV_FILE, "a", newline="") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow([
            "Timestamp", "Voltage (V)", "Current (A)", "Power (W)", "Energy (kWh)", "Status"
        ])

# Initialize or resume cumulative energy
energy_kwh = 0.0
if file_exists:
    try:
        with open(CSV_FILE, "r") as f:
            lines = f.readlines()
            if len(lines) > 1:
                last_line = lines[-1].strip().split(',')
                # Assuming Energy is in the 5th column (index 4)
                energy_kwh = float(last_line[4]) 
                print(f"Resuming Energy counter from: {energy_kwh:.3f} kWh")
    except Exception:
        pass # Ignore if reading fails

print(f"Cloud logging started, writing to {CSV_FILE}... Press Ctrl+C to stop.")

# --- 3. Main Polling Loop ---
last_poll_time = time.time() 

try:
    while True:
        current_time = time.time()
        # Calculate time elapsed since last successful poll for accurate energy calculation
        time_elapsed = current_time - last_poll_time 

        try:
            # 💡 CORRECTION APPLIED HERE: Use cloud.getstatus()
            resp = cloud.getstatus(DEVICE_ID)
            
            # The status list is under the "result" key
            data = resp.get("result", []) 

            # Initialize variables
            voltage = current = power = 0.0
            status_on = False

            # Map the list of DPS entries to a dictionary for easier access
            data_points = {item.get("code"): item.get("value") for item in data}

            # Extract and convert values
            voltage_raw = data_points.get("cur_voltage") or data_points.get("voltage")
            current_raw = data_points.get("cur_current") or data_points.get("current")
            power_raw = data_points.get("cur_power") or data_points.get("power")
            status_val = data_points.get("switch_1") or data_points.get("switch")

            # Conversion and Cleaning
            # Ensure raw values are not None before attempting conversion
            if voltage_raw is not None:
                voltage = float(voltage_raw) / 10.0 # 0.1 V units -> V
            if current_raw is not None:
                current = float(current_raw) / 1000.0 # mA -> A
            if power_raw is not None:
                power = float(power_raw) / 10.0 # 0.1 W units -> W
            if status_val is not None:
                status_on = bool(status_val)

            # Energy calculation (W * Time elapsed in seconds / 3600 seconds/hour / 1000 W/kW)
            energy_kwh += (power * time_elapsed) / 3600 / 1000 
            
            last_poll_time = current_time # Reset poll time for next iteration

            timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

            # Print to console
            print(f"{timestamp} | Voltage: {voltage:.1f} V | Current: {current:.3f} A | "
                  f"Power: {power:.1f} W | Energy: {energy_kwh:.3f} kWh | "
                  f"Status: {'ON' if status_on else 'OFF'}")

            # Write to CSV
            with open(CSV_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, voltage, current, power,
                    round(energy_kwh, 6), 'ON' if status_on else 'OFF'
                ])

        except Exception as e:
            # This handles transient API errors, network issues, etc.
            print(f"⚠️ Warning: Error reading cloud data: {e}. Skipping this poll cycle.")

        # Sleep to maintain the POLL_INTERVAL target
        time.sleep(POLL_INTERVAL - (time.time() - current_time)) 

except KeyboardInterrupt:
    print("\n👋 Logging stopped by user (Ctrl+C).")