from protocol_handler import ProtocolHandler
import socket, struct, datetime

class QueclinkProtocol(ProtocolHandler):
    def connect_and_login(self):
        try:
            self.sock = socket.socket(); self.sock.settimeout(10)
            self.sock.connect((self.dev.server_ip, self.dev.server_port))
            # Queclink login: +RESP:GTFRI,<imei>,<serial>...
            imei = self.dev.imei
            login_str = f"+RESP:GTFRI,{imei},,{self.dev.sim}$"
            self.sock.sendall(login_str.encode())
            resp = self.sock.recv(128)
            if b"+ACK:GTFRI" in resp:
                self.connected = True; self.dev.online = True; return True
        except: pass
        self.connected = False; self.dev.online = False; return False

    def send_location(self):
        if not self.connected: return
        try:
            d = self.dev
            now = datetime.datetime.utcnow()
            timestamp = now.strftime("%y%m%d%H%M%S")
            lat = d.latitude * 10000000
            lon = d.longitude * 10000000
            speed = d.speed_kmh
            heading = d.heading
            alt = d.altitude
            # Minimal +RESP:GTFRI (we'll send a position report)
            report = f"+RESP:GTFRI,{d.imei},,{d.sim},,{timestamp},{lat:.0f},{lon:.0f},{speed:.1f},{heading:.0f},{alt:.1f},0,0,0,0,0$"
            self.sock.sendall(report.encode())
        except: self.connected=False; self.dev.online=False

    def send_heartbeat(self):
        self.send_location()  # heartbeat is often a location with same data

    def handle_sms_command(self, cmd):
        return "Queclink OK"
