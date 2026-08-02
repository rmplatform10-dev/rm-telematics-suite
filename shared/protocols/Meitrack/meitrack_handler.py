from protocol_handler import ProtocolHandler
import socket, datetime

class MeitrackProtocol(ProtocolHandler):
    def connect_and_login(self):
        try:
            self.sock = socket.socket(); self.sock.settimeout(10)
            self.sock.connect((self.dev.server_ip, self.dev.server_port))
            # Meitrack login: ##,imei:<IMEI>,A;
            imei = self.dev.imei
            login = f"##,imei:{imei},A;"
            self.sock.sendall(login.encode())
            resp = self.sock.recv(128)
            if b"LOAD" in resp or resp:
                self.connected = True; self.dev.online = True; return True
        except: pass
        self.connected = False; self.dev.online = False; return False

    def send_location(self):
        if not self.connected: return
        try:
            d = self.dev; now = datetime.datetime.utcnow()
            # Meitrack GPRMC-like string: $$<imei>,<date>,<time>,<lat>,<lon>,<speed>,<heading>,...
            date = now.strftime("%d%m%y")
            time_str = now.strftime("%H%M%S")
            lat = d.latitude * 600000  # convert to minutes*10000
            lon = d.longitude * 600000
            speed = d.speed_kmh * 1.852  # knots? simplified
            heading = d.heading
            report = f"$$,{d.imei},{date},{time_str},{lat:.0f},{lon:.0f},{speed:.1f},{heading:.0f},0,0,0,0,0,0,0,0,0,0,0,0,0*"
            self.sock.sendall(report.encode())
        except: self.connected=False; self.dev.online=False

    def send_heartbeat(self):
        self.send_location()

    def handle_sms_command(self, cmd):
        return "Meitrack OK"
