#!/usr/bin/env python3
"""RM Telematics Dashboard Server - serves React build + live API"""
import http.server
import json, os, sys, threading, time, urllib.parse

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
SHARED_DIR = os.path.join(ROOT_DIR, 'shared')
DEVICES_DIR = os.path.join(ROOT_DIR, 'simulator', 'devices')
sys.path.insert(0, SHARED_DIR)

# runtime config loader (optional)
try:
    import runtime as rm_runtime
    RM_CONFIG = rm_runtime.load_config()
except Exception:
    RM_CONFIG = {}

import importlib.util
spec = importlib.util.spec_from_file_location("device_core", os.path.join(SHARED_DIR, "device_core.py"))
device_core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device_core)

devices = []
device_by_imei = {}
threads = {}

# In-memory monitor log for SMS and state transitions
monitor_log = []
def add_monitor(entry):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    monitor_log.append(f"[{ts}] {entry}")
    if len(monitor_log) > 2000:
        monitor_log.pop(0)


def load_devices():
    global devices, device_by_imei
    devices.clear(); device_by_imei.clear()
    if not os.path.exists(DEVICES_DIR):
        return
    for folder in sorted(os.listdir(DEVICES_DIR)):
        full = os.path.join(DEVICES_DIR, folder)
        if os.path.isdir(full):
            config_file = os.path.join(full, "config.json")
            if os.path.exists(config_file):
                try:
                    with open(config_file, encoding='utf-8-sig') as f:
                        content = f.read()
                    if not content.strip():
                        continue
                    cfg = json.loads(content)
                    cfg['state_file'] = os.path.join(full, "state.json")
                    cfg['device_id'] = len(devices) + 1
                    dev = device_core.GPSDevice(cfg)
                    # attach monitor logger to device so protocol handlers can log
                    try:
                        setattr(dev, 'monitor', add_monitor)
                    except Exception:
                        pass
                    devices.append(dev)
                    device_by_imei[dev.imei] = dev
                except Exception as e:
                    print(f"Skipping {folder}: {e}")


load_devices()

# Register control callbacks with device_core so protocols can start/stop devices
try:
    device_core.register_control_callbacks(lambda i: start_device(i), lambda i: stop_device(i))
except Exception:
    pass


def start_device(imei):
    if imei in threads: return
    dev = device_by_imei.get(imei)
    if dev:
        t = threading.Thread(target=dev.run, daemon=True)
        t.start()
        threads[imei] = t
        add_monitor(f"Device {imei} started")


def stop_device(imei):
    # If thread not tracked, still mark offline
    if imei not in threads:
        dev = device_by_imei.get(imei)
        if dev:
            dev.online = False
            add_monitor(f"Device {imei} marked offline (no running thread)")
        return
    dev = device_by_imei.get(imei)
    if dev:
        dev.online = False
        if getattr(dev, 'protocol', None) and getattr(dev.protocol, 'sock', None):
            try: dev.protocol.sock.close()
            except Exception as e: print(f"Error stopping {imei}: {e}")
        add_monitor(f"Device {imei} stopped")
    if imei in threads:
        del threads[imei]


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/devices':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            data = []
            for dev in devices:
                data.append({
                    'id': dev.device_id,
                    'imei': dev.imei,
                    'sim': dev.sim,
                    'protocol': dev.protocol_type,
                    'model': getattr(dev, 'device_model', dev.protocol_type),
                    'serial': getattr(dev, 'serial_number', ''),
                    'state': dev.state,
                    'speed': round(dev.speed_kmh, 1),
                    'latitude': round(dev.latitude, 6),
                    'longitude': round(dev.longitude, 6),
                    'heading': round(dev.heading, 1),
                    'ignition': dev.ignition,
                    'power': 'External' if dev.external_power else 'Backup Battery',
                    'battery': round(dev.internal_battery_pct, 0),
                    'gsm': dev.gsm_signal,
                    'gps': dev.gps_signal,
                    'satellites': dev.satellites,
                    'online': dev.online,
                    'active': dev.imei in threads,
                    'name': f'{dev.protocol_type}-{str(dev.imei)[-4:]}',
                    'lat': round(dev.latitude, 6),
                    'lng': round(dev.longitude, 6),
                    'signal': min(100, round(dev.gsm_signal / 31 * 100)),
                    'altitude': getattr(dev, 'altitude', 0),
                    'odometer': round(getattr(dev, 'odometer', 0), 1),
                    'type': getattr(dev, 'device_model', 'Car'),
                    'ipAddress': getattr(dev, 'server_ip', None),
                    'port': getattr(dev, 'server_port', None),
                    'driver': None,
                    'destination': None,
                    'temperature': None,
                    'lastUpdate': 'Live',
                    'path': [],
                    'activeAlerts': [],
                    'status': (
                        'OFFLINE' if not dev.online and dev.imei not in threads else
                        'MOVING'  if dev.speed_kmh > 0 else
                        'ONLINE'
                    ),
                })
            self.wfile.write(json.dumps(data).encode())
            return
        elif parsed.path == '/api/status':
            # also expose monitor size
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            status = {
                'devices_total': len(devices),
                'devices_active': len(threads),
                'gateway_running': False,
                'monitor_entries': len(monitor_log),
            }
            self.wfile.write(json.dumps(status).encode())
            return
        elif parsed.path == '/api/monitor':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'log': monitor_log[-200:]}).encode())
            return
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            status = {
                'devices_total': len(devices),
                'devices_active': len(threads),
                'gateway_running': False,
            }
            self.wfile.write(json.dumps(status).encode())
            return
        # Also serve a small runtime config for front-end bundles that request /config
        if parsed.path == '/config':
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            api = RM_CONFIG.get('api_base', 'http://localhost:8080') if isinstance(RM_CONFIG, dict) else 'http://localhost:8080'
            cfg = {'apiBase': api}
            self.wfile.write(json.dumps(cfg).encode())
            return

        # Serve static files; fallback to index.html for SPA
        path = self.translate_path(parsed.path)
        if not os.path.exists(path) or os.path.isdir(path):
            self.path = '/index.html'
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode() if content_length else ''
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if parsed.path == '/api/device/start':
            imei = data.get('imei')
            if imei:
                start_device(imei)
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'result':'ok'}).encode())
            return
        elif parsed.path == '/api/device/stop':
            imei = data.get('imei')
            if imei:
                stop_device(imei)
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'result':'ok'}).encode())
            return
        elif parsed.path == '/api/device/add':
            try:
                name = (data.get('name') or '').strip()
                imei = (data.get('imei') or '').strip()
                sim = (data.get('sim') or '').strip()
                proto = data.get('protocol','GT06')
                lat = float(data.get('start_lat',28.6139))
                lon = float(data.get('start_lon',77.2090))
                heading = int(data.get('start_heading',90))
                alt = int(data.get('start_altitude',100))
                if not imei:
                    raise ValueError('IMEI is required')
                # sanitize name
                if not name:
                    name = imei
                safe_name = ''.join(c for c in name if c.isalnum() or c in ('-','_')).strip() or imei
                folder = os.path.join(DEVICES_DIR, safe_name)
                # ensure unique folder if exists
                if os.path.exists(folder):
                    i = 1
                    while True:
                        candidate = f"{safe_name}_{i}"
                        folder = os.path.join(DEVICES_DIR, candidate)
                        if not os.path.exists(folder):
                            break
                        i += 1
                os.makedirs(folder, exist_ok=True)
                # server defaults from runtime config
                server_ip = RM_CONFIG.get('gateway_host','127.0.0.1') if isinstance(RM_CONFIG, dict) else '127.0.0.1'
                server_port = int(RM_CONFIG.get('gateway_port',5023)) if isinstance(RM_CONFIG, dict) else 5023
                cfg = {
                    "imei": imei, "sim": sim, "protocol": proto,
                    "server_ip": server_ip, "server_port": server_port,
                    "start_lat": lat, "start_lon": lon,
                    "start_heading": heading, "start_altitude": alt,
                    "device_model": proto, "serial_number": f"S{os.urandom(3).hex().upper()}",
                    "iccid": "", "imsi": "", "external_power_voltage": 12.6, "route": []
                }
                with open(os.path.join(folder, "config.json"), "w", encoding='utf-8') as f:
                    json.dump(cfg, f, indent=4)
                load_devices()
                add_monitor(f"Device added: {imei} ({safe_name})")
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                # return the device entry so UI can show it immediately
                dev = device_by_imei.get(imei)
                if dev:
                    self.wfile.write(json.dumps({'result':'ok','device':{'imei':dev.imei,'sim':dev.sim}}).encode())
                else:
                    self.wfile.write(json.dumps({'result':'ok'}).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error':str(e)}).encode())
            return
        elif parsed.path == '/api/device/delete':
            imei = data.get('imei')
            if imei:
                stop_device(imei)
                for d in os.listdir(DEVICES_DIR):
                    path = os.path.join(DEVICES_DIR, d, "config.json")
                    if os.path.exists(path):
                        with open(path) as f:
                            cfg = json.load(f)
                        if cfg.get("imei") == imei:
                            import shutil
                            shutil.rmtree(os.path.join(DEVICES_DIR, d))
                            break
                load_devices()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'result':'ok'}).encode())
            return
        elif parsed.path == '/api/sms':
            sim = data.get('sim')
            cmd = data.get('command')
            dev = None
            for d in devices:
                if d.sim == sim:
                    dev = d
                    break
            if dev:
                with dev.lock:
                    dev.sms_inbox.append(cmd)
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'result':'ok'}).encode())
            else:
                self.send_response(404)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error':'SIM not found'}).encode())
            return
        self.send_response(404)
        self.end_headers()


if __name__ == '__main__':
    DASHBOARD_HOST = RM_CONFIG.get('dashboard_host', '') if isinstance(RM_CONFIG, dict) else ''
    DASHBOARD_PORT = int(RM_CONFIG.get('dashboard_port', 8080)) if isinstance(RM_CONFIG, dict) else 8080
    host_display = DASHBOARD_HOST if DASHBOARD_HOST else 'localhost'
    print(f"Dashboard server starting at http://{host_display}:{DASHBOARD_PORT}")
    print(f"Serving files from {BASE_DIR}")

    httpd = http.server.HTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), DashboardHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
