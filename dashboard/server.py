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

import importlib.util
spec = importlib.util.spec_from_file_location("device_core", os.path.join(SHARED_DIR, "device_core.py"))
device_core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device_core)

devices = []
device_by_imei = {}
threads = {}

def load_devices():
    global devices, device_by_imei
    devices.clear(); device_by_imei.clear()
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
                    devices.append(dev)
                    device_by_imei[dev.imei] = dev
                except Exception as e: print(f"Skipping {folder}: {e}")

load_devices()

def start_device(imei):
    if imei in threads: return
    dev = device_by_imei.get(imei)
    if dev:
        t = threading.Thread(target=dev.run, daemon=True)
        t.start()
        threads[imei] = t

def stop_device(imei):
    if imei not in threads: return
    dev = device_by_imei.get(imei)
    if dev:
        dev.online = False
        if dev.protocol and dev.protocol.sock:
            try: dev.protocol.sock.close()
            except Exception as e: print(f"Error stopping {imei}: {e}")
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
                    # ── React-compatible aliases ──────────────────────────
                    'name': f'{dev.protocol_type}-{str(dev.imei)[-4:]}',
                    'lat': round(dev.latitude, 6),
                    'lng': round(dev.longitude, 6),
                    'signal': min(100, round(dev.gsm_signal / 31 * 100)),
                    'altitude': getattr(dev, 'altitude', 0),
                    'odometer': round(getattr(dev, 'odometer', 0), 1),
                    'type': getattr(dev, 'device_model', 'Car'),
                    'ipAddress': dev.server_ip,
                    'port': dev.server_port,
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
        # Serve static files; fallback to index.html for SPA
        path = self.translate_path(parsed.path)
        if not os.path.exists(path) or os.path.isdir(path):
            self.path = '/index.html'
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode()
        data = json.loads(body) if body else {}
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
                name = data.get('name')
                imei = data.get('imei')
                sim = data.get('sim')
                proto = data.get('protocol','GT06')
                lat = float(data.get('start_lat',28.6139))
                lon = float(data.get('start_lon',77.2090))
                heading = int(data.get('start_heading',90))
                alt = int(data.get('start_altitude',100))
                folder = os.path.join(DEVICES_DIR, name)
                os.makedirs(folder, exist_ok=True)
                cfg = {
                    "imei": imei, "sim": sim, "protocol": proto,
                    "server_ip": "127.0.0.1", "server_port": 5023,
                    "start_lat": lat, "start_lon": lon,
                    "start_heading": heading, "start_altitude": alt,
                    "device_model": proto, "serial_number": f"S{os.urandom(3).hex().upper()}",
                    "iccid": "", "imsi": "", "external_power_voltage": 12.6, "route": []
                }
                with open(os.path.join(folder, "config.json"), "w") as f:
                    json.dump(cfg, f, indent=4)
                load_devices()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
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
    print("Dashboard server starting at http://localhost:8080")
    httpd = http.server.HTTPServer(('', 8080), DashboardHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
