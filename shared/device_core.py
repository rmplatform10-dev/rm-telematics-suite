from utils import move_towards, crc_xor
import socket, struct, time, random, threading, json, os, math, datetime, sys
from protocol_handler import ProtocolHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

start_device_cb = None
stop_device_cb = None

def register_control_callbacks(start_cb, stop_cb):
    global start_device_cb, stop_device_cb
    start_device_cb = start_cb
    stop_device_cb = stop_cb

def get_protocol_class(protocol_type):
    import importlib.util
    import sys
    # Mapping from protocol name to relative module path (within protocols/)
    handlers = {
        "GT06": "GT06.gt06_handler",
        "Teltonika": "Teltonika.teltonika_handler",
        "Concox": "Concox.concox_handler",
        "Coban": "Coban.coban_handler",
        "Queclink": "Queclink.queclink_handler",
        "Meitrack": "Meitrack.meitrack_handler",
        "Jimi": "Jimi.jimi_handler",
        "Ruptela": "Ruptela.ruptela_handler",
    }
    if protocol_type in handlers:
        mod_path = handlers[protocol_type]
        # Full path to the module file (e.g., protocols/GT06/gt06_handler.py)
        module_dir = os.path.join(BASE_DIR, "protocols", mod_path.replace(".", os.sep) + ".py")
        if not os.path.exists(module_dir):
            # Fallback: try without subfolder (old structure)
            module_dir = os.path.join(BASE_DIR, mod_path.replace(".", os.sep) + ".py")
        # Load module dynamically
        spec = importlib.util.spec_from_file_location(mod_path.split(".")[-1], module_dir)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        # Class name is the module name with first letter capitalized + "Protocol"
        class_name = protocol_type + "Protocol"
        return getattr(module, class_name)
    return None
def move_towards(lat, lon, heading_deg, distance_m):
    R=6371000; d=distance_m/R; brg=math.radians(heading_deg)
    lat1=math.radians(lat); lon1=math.radians(lon)
    lat2=math.asin(math.sin(lat1)*math.cos(d)+math.cos(lat1)*math.sin(d)*math.cos(brg))
    lon2=lon1+math.atan2(math.sin(brg)*math.sin(d)*math.cos(lat1),math.cos(d)-math.sin(lat1)*math.sin(lat2))
    return math.degrees(lat2),math.degrees(lon2)

class GPSDevice:
    def __init__(self, config):
        self.device_id = config.get('device_id',1)
        self.imei = config['imei']
        self.sim = config.get('sim','1111111111')
        self.protocol_type = config.get('protocol','GT06')
        self.device_model = config.get('device_model', 'UNKNOWN')
        self.serial_number = config.get('serial_number', f"S{random.randint(100000,999999)}")
        self.iccid = config.get('iccid', '')
        self.imsi = config.get('imsi', '')
        self.server_ip = config['server_ip']
        self.server_port = config['server_port']
        self.latitude = config.get('start_lat',28.6139)
        self.longitude = config.get('start_lon',77.2090)
        self.heading = config.get('start_heading',random.randint(0,359))
        self.speed_kmh = 0.0
        self.ignition = False
        self.external_power = True
        self.external_power_voltage = config.get('external_power_voltage', 12.6)
        self.gps_signal = True
        self.gsm_signal = random.randint(20,31)
        self.satellites = random.randint(12,20)
        self.hdop = round(random.uniform(0.5,2.0),1)
        self.altitude = config.get('start_altitude',random.randint(100,300))
        self.odometer = config.get('odometer', random.randint(50000,200000))
        self.engine_hours = config.get('engine_hours', random.randint(1000,5000))
        self.internal_battery_pct = 100
        self.online = False
        self.state = 'PARKED_IGN_OFF'
        self.state_timer = 0
        self.stagger_delay = random.uniform(0,60)
        self.cruise_speed = random.randint(50,65)
        self.max_speed_burst = False
        self.speed_burst_timer = 0
        self.route_waypoints = config.get('route', [])
        self.current_waypoint_idx = 0
        self.zero_drift_counter = 0
        self.zero_drift_active = False
        self.power_cut_timer = random.uniform(600, 3600)
        self.power_cut_duration = 0
        self.last_speed = 0.0
        self.transition_offset = random.uniform(0, 30)
        self.lock = threading.Lock()
        self.protocol = None
        self.gsm_lost = False
        self.sms_inbox = []
        self.state_file = config.get('state_file', None)
        if self.state_file and os.path.exists(self.state_file):
            try:
                with open(self.state_file,'r') as f:
                    saved = json.load(f)
                    self.server_ip = saved.get('server_ip', self.server_ip)
                    self.server_port = saved.get('server_port', self.server_port)
            except: pass

    def save_state(self):
        if not self.state_file: return
        state = {'server_ip': self.server_ip, 'server_port': self.server_port}
        try:
            with open(self.state_file,'w') as f:
                json.dump(state, f)
        except: pass

    def update_sensors(self, dt):
        if random.random()<0.02:
            self.gsm_signal = max(0,min(31, self.gsm_signal + random.randint(-5,5)))
        if not self.gsm_lost and random.random()<0.001:
            self.gsm_lost = True
        if self.gsm_lost and random.random()<0.05:
            self.gsm_lost = False
        if self.gps_signal and random.random()<0.0005:
            self.gps_signal = False
        if not self.gps_signal and random.random()<0.01:
            self.gps_signal = True
        if self.external_power:
            self.power_cut_timer -= dt
            if self.power_cut_timer <= 0:
                self.external_power = False
                self.power_cut_duration = random.uniform(120, 900)
                self.power_cut_timer = float('inf')
        else:
            self.power_cut_duration -= dt
            self.internal_battery_pct -= 0.01 * dt
            if self.power_cut_duration <= 0:
                self.external_power = True
                self.power_cut_timer = random.uniform(600, 3600)
        if self.external_power:
            self.internal_battery_pct = min(100, self.internal_battery_pct + 0.01*dt)
        else:
            if self.internal_battery_pct < 0:
                self.internal_battery_pct = 0

    def update_movement(self, dt):
        if self.stagger_delay > 0:
            self.stagger_delay -= dt
            return

        if self.route_waypoints and self.state not in ['PARKED_IGN_OFF','PARKING']:
            target = self.route_waypoints[self.current_waypoint_idx]
            target_lat, target_lon = target['lat'], target['lon']
            R = 6371000
            dlat = math.radians(target_lat - self.latitude)
            dlon = math.radians(target_lon - self.longitude)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(self.latitude)) * math.cos(math.radians(target_lat)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            dist_to_target = R * c
            if dist_to_target < 20:
                self.current_waypoint_idx = (self.current_waypoint_idx + 1) % len(self.route_waypoints)
                target = self.route_waypoints[self.current_waypoint_idx]
                target_lat, target_lon = target['lat'], target['lon']
                dlon = math.radians(target_lon - self.longitude)
                y = math.sin(dlon) * math.cos(math.radians(target_lat))
                x = math.cos(math.radians(self.latitude))*math.sin(math.radians(target_lat)) - math.sin(math.radians(self.latitude))*math.cos(math.radians(target_lat))*math.cos(dlon)
                bearing = math.degrees(math.atan2(y, x)) % 360
            else:
                y = math.sin(dlon) * math.cos(math.radians(target_lat))
                x = math.cos(math.radians(self.latitude))*math.sin(math.radians(target_lat)) - math.sin(math.radians(self.latitude))*math.cos(math.radians(target_lat))*math.cos(dlon)
                bearing = math.degrees(math.atan2(y, x)) % 360
            angle_diff = (bearing - self.heading + 180) % 360 - 180
            self.heading += max(-2, min(2, angle_diff))
            self.target_speed = self.cruise_speed
        else:
            if self.speed_kmh > 0:
                self.heading += random.uniform(-3, 3)
                self.heading %= 360

        adj_timer = self.state_timer + self.transition_offset

        if self.state == 'PARKED_IGN_OFF':
            self.state_timer += dt
            if adj_timer > random.uniform(30, 600):
                self.ignition = True
                self.state = 'IDLE'
                self.state_timer = 0
        elif self.state == 'IDLE':
            self.state_timer += dt
            if adj_timer > random.uniform(5, 30):
                self.state = 'ACCELERATING'
                self.target_speed = self.cruise_speed
                self.state_timer = 0
        elif self.state == 'ACCELERATING':
            accel = 0.5 + 1.0 * random.random()
            old_speed = self.speed_kmh
            self.speed_kmh += accel * dt * 3.6
            if self.speed_kmh >= self.target_speed:
                self.speed_kmh = self.target_speed
                self.state = 'CRUISING'
                self.state_timer = 0
            if self.speed_kmh - old_speed > 10 and old_speed > 0:
                pass  # event trigger placeholder
        elif self.state == 'CRUISING':
            old_speed = self.speed_kmh
            self.speed_kmh += random.uniform(-0.3, 0.3)
            self.speed_kmh = max(0, self.speed_kmh)
            if not self.max_speed_burst and random.random() < 0.0005:
                self.max_speed_burst = True
                self.speed_burst_timer = 0
                self.target_speed = random.randint(95, 100)
            if self.max_speed_burst:
                self.speed_burst_timer += dt
                if self.speed_burst_timer > 20:
                    self.max_speed_burst = False
                    self.target_speed = self.cruise_speed
            self.state_timer += dt
            if adj_timer > random.uniform(40, 120) and random.random() < 0.3:
                self.state = 'SLOWING'
                self.target_speed = 0
                self.state_timer = 0
            if old_speed - self.speed_kmh > 10 and old_speed > 30:
                pass  # harsh braking
        elif self.state == 'SLOWING':
            old_speed = self.speed_kmh
            decel = 0.8 + 1.2 * random.random()
            self.speed_kmh -= decel * dt * 3.6
            if self.speed_kmh <= 0:
                self.speed_kmh = 0
                self.state = 'STOPPED'
                self.stop_duration = random.uniform(20, 90)
                self.state_timer = 0
            if old_speed - self.speed_kmh > 12:
                pass  # harsh braking event
        elif self.state == 'STOPPED':
            self.state_timer += dt
            if adj_timer > self.stop_duration:
                if random.random() < 0.7:
                    self.state = 'ACCELERATING'
                    self.target_speed = random.randint(45, 65)
                else:
                    self.state = 'PARKING'
                self.state_timer = 0
        elif self.state == 'PARKING':
            self.ignition = False
            self.state = 'PARKED_IGN_OFF'
            self.state_timer = 0

        if self.speed_kmh > 0 and self.gps_signal:
            dist_m = (self.speed_kmh / 3.6) * dt
            self.latitude, self.longitude = move_towards(self.latitude, self.longitude, self.heading, dist_m)
            self.odometer += int(dist_m)
            self.engine_hours += dt / 3600
        if self.speed_kmh == 0 and self.gps_signal:
            if self.zero_drift_active:
                self.zero_drift_counter -= dt
                if self.zero_drift_counter <= 0:
                    self.zero_drift_active = False
            else:
                drift = random.uniform(-0.00005, 0.00005)
                self.latitude += drift
                self.longitude += drift
                if random.random() < 0.005:
                    self.zero_drift_active = True
                    self.zero_drift_counter = random.uniform(5, 20)
        self.last_speed = self.speed_kmh

    def run(self):
        time.sleep(self.stagger_delay)
        protocol_class = get_protocol_class(self.protocol_type)
        if protocol_class is None:
            print(f"[{self.imei}] Unsupported protocol {self.protocol_type}")
            return
        self.protocol = protocol_class(self)

        def keep_connected():
            while True:
                if not self.protocol.connected:
                    self.protocol.connect_and_login()
                time.sleep(5)
        threading.Thread(target=keep_connected, daemon=True).start()

        last_loc = time.time()
        last_hb = time.time()
        while True:
            try:
                dt = 1.0
                time.sleep(1)
                with self.lock:
                    self.update_sensors(dt)
                    self.update_movement(dt)
                    while self.sms_inbox:
                        cmd = self.sms_inbox.pop(0)
                        resp = self.protocol.handle_sms_command(cmd)
                        print(f"\n[SMS RESPONSE from {self.sim}] {resp}\nSIM> ", end='', flush=True)
                now = time.time()
                if not self.gsm_lost:
                    if now - last_loc >= 10:
                        self.protocol.send_location()
                        last_loc = now
                    if now - last_hb >= 30:
                        self.protocol.send_heartbeat()
                        last_hb = now
            except Exception as e:
                print(f"[{self.imei}] Error: {e}")



