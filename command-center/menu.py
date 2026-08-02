#!/usr/bin/env python3
import json, os, sys, threading, time, socket, importlib.util, random

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(BASE_DIR, '..', 'shared')
DEVICES_DIR = os.path.join(BASE_DIR, '..', 'simulator', 'devices')
sys.path.insert(0, SHARED_DIR)

# Load the device engine from shared
spec = importlib.util.spec_from_file_location("device_core", os.path.join(SHARED_DIR, "device_core.py"))
device_core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device_core)

devices = []
device_by_sim = {}
device_by_imei = {}
threads = []
sms_server_port = 9999

def load_devices():
    global devices, device_by_sim, device_by_imei, threads
    devices.clear(); device_by_sim.clear(); device_by_imei.clear()
    for t in threads: t.join(timeout=0)
    threads.clear()
    for folder in sorted(os.listdir(DEVICES_DIR)):
        full = os.path.join(DEVICES_DIR, folder)
        if os.path.isdir(full):
            config_file = os.path.join(full, "config.json")
            if os.path.exists(config_file):
                with open(config_file, encoding='utf-8-sig') as f: cfg = json.load(f)
                cfg['state_file'] = os.path.join(full, "state.json")
                cfg['device_id'] = len(devices) + 1
                dev = device_core.GPSDevice(cfg)
                devices.append(dev)
                device_by_sim[dev.sim] = dev
                device_by_imei[dev.imei] = dev

def start_all():
    global threads
    for dev in devices:
        t = threading.Thread(target=dev.run, daemon=True)
        t.start()
        threads.append(t)
        print(f"Started {dev.imei} (SIM {dev.sim})")

def stop_all():
    # can't easily stop threads, just mark them offline
    for dev in devices:
        dev.online = False
        if dev.protocol and dev.protocol.sock:
            try: dev.protocol.sock.close()
            except: pass
    print("Devices stopped.")

def status_all():
    for dev in devices:
        print(f"ID:{dev.device_id} IMEI:{dev.imei} SIM:{dev.sim} Model:{dev.protocol_type} State:{dev.state} Speed:{dev.speed_kmh:.1f} Ign:{'ON' if dev.ignition else 'OFF'} Power:{'Ext' if dev.external_power else 'Bat'} Bat:{dev.internal_battery_pct:.0f}% GSM:{dev.gsm_signal} GPS:{'Valid' if dev.gps_signal else 'Lost'} Sat:{dev.satellites} Conn:{'Yes' if (dev.protocol and dev.protocol.connected) else 'No'}")

def add_device():
    name = input("Folder name (e.g., Device_010): ").strip()
    imei = input("IMEI: ").strip()
    sim = input("SIM: ").strip()
    proto = input("Protocol (GT06/Teltonika/...): ").strip()
    lat = float(input("Start lat: "))
    lon = float(input("Start lon: "))
    heading = int(input("Start heading: "))
    alt = int(input("Start altitude: "))
    folder = os.path.join(DEVICES_DIR, name)
    os.makedirs(folder, exist_ok=True)
    cfg = { "imei":imei, "sim":sim, "protocol":proto, "server_ip":"127.0.0.1", "server_port":5023,
            "start_lat":lat, "start_lon":lon, "start_heading":heading, "start_altitude":alt,
            "device_model":proto, "serial_number":f"S{random.randint(100000,999999)}",
            "iccid":"", "imsi":"", "external_power_voltage":12.6, "route":[] }
    with open(os.path.join(folder, "config.json"), "w") as f: json.dump(cfg, f, indent=4)
    print(f"Device {name} added.")

def edit_device():
    load_devices()
    name = input("Device folder name to edit: ").strip()
    folder = os.path.join(DEVICES_DIR, name)
    if not os.path.isdir(folder):
        print("Not found."); return
    with open(os.path.join(folder, "config.json")) as f: cfg = json.load(f)
    for k in ["imei","sim","protocol","server_ip","server_port","start_lat","start_lon","start_heading","start_altitude"]:
        new = input(f"{k} [{cfg.get(k)}]: ").strip()
        if new: cfg[k] = type(cfg[k])(new) if k not in ["imei","sim","protocol","server_ip"] else new
    with open(os.path.join(folder, "config.json"), "w") as f: json.dump(cfg, f, indent=4)
    print("Updated.")

def delete_device():
    name = input("Device folder name to delete: ").strip()
    folder = os.path.join(DEVICES_DIR, name)
    if os.path.isdir(folder):
        import shutil, random
        shutil.rmtree(folder)
        print("Deleted.")
    else:
        print("Not found.")

def send_sms(sim, cmd):
    dev = device_by_sim.get(sim)
    if dev:
        with dev.lock: dev.sms_inbox.append(cmd)
        return f"SMS sent to {sim}"
    return f"SIM {sim} not found"

# Background SMS server for mobile-simulator
def sms_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', sms_server_port))
        s.listen()
        while True:
            conn, _ = s.accept()
            with conn:
                data = conn.recv(1024).decode().strip()
                if data.startswith("SMS:"):
                    parts = data[4:].split(":",1)
                    if len(parts)==2:
                        sim, cmd = parts
                        resp = send_sms(sim, cmd)
                        conn.sendall(resp.encode())

# Main menu
def main():
    load_devices()
    threading.Thread(target=sms_server, daemon=True).start()
    while True:
        print("\n=== COMMAND CENTER ===")
        print("1. List devices")
        print("2. Add device")
        print("3. Edit device")
        print("4. Delete device")
        print("5. Start simulator")
        print("6. Stop simulator")
        print("7. View live status")
        print("8. Send SMS")
        print("9. Exit")
        choice = input("> ").strip()
        if choice == '1':
            load_devices()
            for d in devices: print(f"  {d.device_id}: IMEI={d.imei} SIM={d.sim} Proto={d.protocol_type}")
        elif choice == '2': add_device()
        elif choice == '3': edit_device()
        elif choice == '4': delete_device()
        elif choice == '5': start_all()
        elif choice == '6': stop_all()
        elif choice == '7': status_all()
        elif choice == '8':
            sim = input("SIM: ").strip()
            cmd = input("Command (loc/status/reboot/server): ").strip()
            print(send_sms(sim, cmd))
        elif choice == '9': break
    stop_all()

if __name__ == '__main__':
    main()
