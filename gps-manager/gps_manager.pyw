# gps_manager.pyw – Modular Simulation Platform (Stitch-inspired dark theme)
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import json, os, sys, threading, time, random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
SHARED_DIR = os.path.join(ROOT_DIR, 'shared')
DEVICES_DIR = os.path.join(ROOT_DIR, 'simulator', 'devices')
sys.path.insert(0, SHARED_DIR)

import importlib.util
spec = importlib.util.spec_from_file_location("device_core", os.path.join(SHARED_DIR, "device_core.py"))
device_core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device_core)

devices = []
device_by_imei = {}
threads = {}
running = False

def load_devices():
    global devices, device_by_imei
    devices.clear(); device_by_imei.clear()
    for folder in sorted(os.listdir(DEVICES_DIR)):
        full = os.path.join(DEVICES_DIR, folder)
        if os.path.isdir(full):
            config_file = os.path.join(full, "config.json")
            if os.path.exists(config_file):
                try:
                    with open(config_file, "r", encoding="utf-8-sig") as f:
                        content = f.read()
                    if not content.strip():
                        print(f"Skipping empty config: {folder}")
                        continue
                    cfg = json.loads(content)
                    cfg['state_file'] = os.path.join(full, "state.json")
                    cfg['device_id'] = len(devices) + 1
                    dev = device_core.GPSDevice(cfg)
                    devices.append(dev)
                    device_by_imei[dev.imei] = dev
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Skipping invalid config in {folder}: {e}")
    refresh_all_views()

def start_device(imei):
    dev = device_by_imei.get(imei)
    if not dev or imei in threads: return
    t = threading.Thread(target=dev.run, daemon=True)
    t.start()
    threads[imei] = t
    log_event(f"Started device {imei}")
    refresh_all_views()

def stop_device(imei):
    dev = device_by_imei.get(imei)
    if not dev or imei not in threads: return
    dev.online = False
    if dev.protocol and dev.protocol.sock:
        try: dev.protocol.sock.close()
        except: pass
    del threads[imei]
    log_event(f"Stopped device {imei}")
    refresh_all_views()

def start_all():
    for dev in devices:
        start_device(dev.imei)
    status_var.set("Simulation RUNNING (all devices)")

def stop_all():
    for imei in list(threads.keys()):
        stop_device(imei)
    status_var.set("Simulation STOPPED")

def toggle_all():
    if threads: stop_all()
    else: start_all()

def edit_device(imei):
    folder = None
    for d in os.listdir(DEVICES_DIR):
        path = os.path.join(DEVICES_DIR, d, "config.json")
        if os.path.exists(path):
            with open(path) as f: cfg = json.load(f)
            if cfg.get("imei") == imei:
                folder = os.path.join(DEVICES_DIR, d); break
    if not folder: return
    cfg_file = os.path.join(folder, "config.json")
    with open(cfg_file) as f: cfg = json.load(f)
    for key in ["imei","sim","protocol","server_ip","server_port","start_lat","start_lon","start_heading","start_altitude"]:
        current = cfg.get(key, "")
        new_val = simpledialog.askstring("Edit", f"{key} (current: {current}):", parent=root)
        if new_val is not None:
            if key in ["start_lat","start_lon"]:
                try: cfg[key] = float(new_val)
                except ValueError: pass
            elif key in ["start_heading","start_altitude","server_port"]:
                try: cfg[key] = int(new_val)
                except ValueError: pass
            else: cfg[key] = new_val
    with open(cfg_file, "w") as f: json.dump(cfg, f, indent=4)
    load_devices()
    messagebox.showinfo("Success", "Device updated.", parent=root)

def delete_device(imei):
    if not messagebox.askyesno("Confirm", f"Delete device {imei}?", parent=root): return
    for d in os.listdir(DEVICES_DIR):
        path = os.path.join(DEVICES_DIR, d, "config.json")
        if os.path.exists(path):
            with open(path) as f: cfg = json.load(f)
            if cfg.get("imei") == imei:
                import shutil
                shutil.rmtree(os.path.join(DEVICES_DIR, d)); break
    load_devices()

def add_device():
    name = simpledialog.askstring("Add Device", "Folder name (e.g., Device_010):", parent=root)
    if not name: return
    imei = simpledialog.askstring("IMEI", "IMEI:", parent=root)
    if not imei: return
    sim = simpledialog.askstring("SIM", "SIM number:", parent=root)
    if not sim: return
    proto = simpledialog.askstring("Protocol", "Protocol (GT06/Teltonika/Concox/...):", parent=root)
    if not proto: return
    try:
        lat = float(simpledialog.askstring("Latitude", "Start latitude:", parent=root))
        lon = float(simpledialog.askstring("Longitude", "Start longitude:", parent=root))
        heading = int(simpledialog.askstring("Heading", "Start heading (degrees):", parent=root))
        alt = int(simpledialog.askstring("Altitude", "Start altitude (meters):", parent=root))
    except (TypeError, ValueError):
        messagebox.showerror("Error", "Invalid coordinate values."); return
    folder = os.path.join(DEVICES_DIR, name)
    os.makedirs(folder, exist_ok=True)
    cfg = {
        "imei": imei, "sim": sim, "protocol": proto,
        "server_ip": "127.0.0.1", "server_port": 5023,
        "start_lat": lat, "start_lon": lon, "start_heading": heading, "start_altitude": alt,
        "device_model": proto, "serial_number": f"S{random.randint(100000,999999)}",
        "iccid": "", "imsi": "", "external_power_voltage": 12.6, "route": []
    }
    with open(os.path.join(folder, "config.json"), "w") as f: json.dump(cfg, f, indent=4)
    load_devices()
    messagebox.showinfo("Success", f"Device {name} added.", parent=root)

log_lines = []
def log_event(msg):
    timestamp = time.strftime("%H:%M:%S")
    log_lines.append(f"[{timestamp}] {msg}")
    if len(log_lines) > 200:
        log_lines.pop(0)
    if 'monitor_text' in globals():
        monitor_text.config(state=tk.NORMAL)
        monitor_text.insert(tk.END, f"{log_lines[-1]}\n")
        monitor_text.see(tk.END)
        monitor_text.config(state=tk.DISABLED)

def refresh_all_views():
    refresh_table()
    refresh_device_cards()

def refresh_table():
    for row in table.get_children(): table.delete(row)
    for dev in devices:
        speed = dev.speed_kmh
        ign = "ON" if dev.ignition else "OFF"
        online = "Connected" if dev.protocol and dev.protocol.connected else "Disconnected"
        table.insert("", "end", values=(
            dev.device_id, dev.imei, dev.sim, dev.protocol_type,
            f"{dev.latitude:.6f}, {dev.longitude:.6f}",
            f"{speed:.1f} km/h", ign, online
        ))

def refresh_device_cards():
    for widget in cards_frame.winfo_children():
        widget.destroy()
    for dev in devices:
        card = tk.Frame(cards_frame, bg="#33373b", bd=0, highlightthickness=0)
        card.pack(fill=tk.X, padx=5, pady=3)
        is_active = dev.imei in threads
        tk.Label(card, text=f"{dev.protocol_type} | IMEI: {dev.imei}", fg="white", bg="#33373b",
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=2)
        tk.Label(card, text=f"SIM: {dev.sim}  Speed: {dev.speed_kmh:.1f} km/h  Ign: {'ON' if dev.ignition else 'OFF'}",
                 fg="#aaa", bg="#33373b").grid(row=1, column=0, columnspan=3, sticky="w", padx=8)
        btn_frame = tk.Frame(card, bg="#33373b")
        btn_frame.grid(row=2, column=0, columnspan=3, sticky="e", padx=8, pady=4)
        if is_active:
            tb.Button(btn_frame, text="Stop", bootstyle="danger-outline", width=8,
                      command=lambda d=dev.imei: stop_device(d)).pack(side=tk.LEFT, padx=2)
        else:
            tb.Button(btn_frame, text="Start", bootstyle="success-outline", width=8,
                      command=lambda d=dev.imei: start_device(d)).pack(side=tk.LEFT, padx=2)
        tb.Button(btn_frame, text="Locate", bootstyle="info-outline", width=8,
                  command=lambda d=dev: log_event(f"Locate {d.imei}: {d.latitude:.6f}, {d.longitude:.6f}")).pack(side=tk.LEFT, padx=2)
        tb.Button(btn_frame, text="Edit", bootstyle="warning-outline", width=6,
                  command=lambda d=dev.imei: edit_device(d)).pack(side=tk.LEFT, padx=2)
        tb.Button(btn_frame, text="Delete", bootstyle="danger-outline", width=7,
                  command=lambda d=dev.imei: delete_device(d)).pack(side=tk.LEFT, padx=2)

# GUI
root = tb.Window(themename="cyborg")
root.title("GPS Device Manager")
root.geometry("1200x750")
root.minsize(1000, 600)

# Sidebar
sidebar = tk.Frame(root, bg="#1c1e22", width=200)
sidebar.pack(side=tk.LEFT, fill=tk.Y)
sidebar.pack_propagate(False)
tb.Label(sidebar, text="NAVIGATION", font=("Segoe UI", 10, "bold"), foreground="#aaa", background="#1c1e22").pack(pady=(20,5), padx=15, anchor=tk.W)

def show_tab(tab_name):
    dashboard_frame.pack_forget()
    control_frame.pack_forget()
    monitor_frame.pack_forget()
    if tab_name == "dashboard":
        dashboard_frame.pack(fill=tk.BOTH, expand=True)
    elif tab_name == "control":
        control_frame.pack(fill=tk.BOTH, expand=True)
    elif tab_name == "monitor":
        monitor_frame.pack(fill=tk.BOTH, expand=True)

tb.Button(sidebar, text="  Dashboard", bootstyle="link-light", command=lambda: show_tab("dashboard")).pack(pady=2, padx=10, fill=tk.X)
tb.Button(sidebar, text="  Device Control", bootstyle="link-light", command=lambda: show_tab("control")).pack(pady=2, padx=10, fill=tk.X)
tb.Button(sidebar, text="  Monitor", bootstyle="link-light", command=lambda: show_tab("monitor")).pack(pady=2, padx=10, fill=tk.X)
tb.Separator(sidebar, bootstyle="secondary").pack(fill=tk.X, padx=10, pady=10)
tb.Button(sidebar, text="  Exit", bootstyle="link-light", command=root.quit).pack(pady=2, padx=10, fill=tk.X)

main_frame = tk.Frame(root, bg="#272b30")
main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

status_var = tb.StringVar(value="Simulation STOPPED")
status_bar = tb.Label(main_frame, textvariable=status_var, bootstyle="info-inverse", anchor=tk.W, padding=(10,2))
status_bar.pack(side=tk.BOTTOM, fill=tk.X)

# Dashboard
dashboard_frame = tk.Frame(main_frame, bg="#272b30")
toolbar = tk.Frame(dashboard_frame, bg="#272b30")
toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
tb.Button(toolbar, text="Start All / Stop All", bootstyle="success-outline", command=toggle_all).pack(side=tk.LEFT, padx=3)
tb.Button(toolbar, text="Add Device", bootstyle="primary-outline", command=add_device).pack(side=tk.LEFT, padx=3)
tb.Button(toolbar, text="Refresh", bootstyle="secondary-outline", command=refresh_all_views).pack(side=tk.LEFT, padx=3)
table_frame = tk.Frame(dashboard_frame, bg="#272b30")
table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
columns = ("ID","IMEI","SIM","Protocol","Position","Speed","Ignition","Connection")
table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse", height=15)
for col in columns:
    table.heading(col, text=col)
    table.column(col, width=120, anchor=tk.CENTER)
vsb = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
table.configure(yscrollcommand=vsb.set)
vsb.pack(side=tk.RIGHT, fill=tk.Y)
table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Device Control
control_frame = tk.Frame(main_frame, bg="#272b30")
control_toolbar = tk.Frame(control_frame, bg="#272b30")
control_toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
tb.Button(control_toolbar, text="Start All", bootstyle="success-outline", command=start_all).pack(side=tk.LEFT, padx=3)
tb.Button(control_toolbar, text="Stop All", bootstyle="danger-outline", command=stop_all).pack(side=tk.LEFT, padx=3)
tb.Button(control_toolbar, text="Add Device", bootstyle="primary-outline", command=add_device).pack(side=tk.LEFT, padx=3)
canvas = tk.Canvas(control_frame, bg="#272b30", highlightthickness=0)
scrollbar = ttk.Scrollbar(control_frame, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas, bg="#272b30")
scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.create_window((0,0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
cards_frame = tk.Frame(scrollable_frame, bg="#272b30")
cards_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# Monitor
monitor_frame = tk.Frame(main_frame, bg="#272b30")
tb.Label(monitor_frame, text="Event Log", font=("Segoe UI", 11, "bold"), background="#272b30", foreground="white").pack(pady=5)
monitor_text = tk.Text(monitor_frame, bg="#1c1e22", fg="white", insertbackground="white", state=tk.DISABLED, wrap=tk.WORD)
monitor_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

show_tab("dashboard")
load_devices()

def auto_refresh():
    if threads:
        refresh_all_views()
    root.after(1000, auto_refresh)
auto_refresh()

# Force window visible
root.update_idletasks()
root.deiconify()
root.lift()
root.attributes('-topmost', True)
root.after(100, lambda: root.attributes('-topmost', False))
root.mainloop()
