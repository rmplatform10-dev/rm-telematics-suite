from protocol_handler import ProtocolHandler
import socket, struct, datetime

class JimiProtocol(ProtocolHandler):
    def connect_and_login(self):
        try:
            self.sock = socket.socket(); self.sock.settimeout(10)
            self.sock.connect((self.dev.server_ip, self.dev.server_port))
            # Jimi login: 7E ... 7E (JT808)
            # We'll send a simplified registration message: 7E 0100 ...
            imei = self.dev.imei[:15].encode()
            body = b'\x01\x00' + imei  # placeholder registration
            # full packet with escape
            pkt = b'\x7E' + body + b'\x7E'
            self.sock.sendall(pkt)
            resp = self.sock.recv(64)
            if resp:
                self.connected = True; self.dev.online = True; return True
        except: pass
        self.connected = False; self.dev.online = False; return False

    def send_location(self):
        if not self.connected: return
        try:
            d = self.dev; now = datetime.datetime.utcnow()
            # JT808 location report (simplified)
            lat = int(d.latitude * 1000000)
            lon = int(d.longitude * 1000000)
            speed = int(d.speed_kmh)
            heading = int(d.heading)
            alt = int(d.altitude)
            body = struct.pack('>I', int(now.timestamp())) + struct.pack('>I',lat) + struct.pack('>I',lon) + struct.pack('>H', speed) + struct.pack('>H', heading) + struct.pack('>H', alt)
            pkt = b'\x7E\x02\x00' + body + b'\x7E'
            self.sock.sendall(pkt)
        except: self.connected=False; self.dev.online=False

    def send_heartbeat(self):
        if not self.connected: return
        try:
            self.sock.sendall(b'\x7E\x00\x02\x7E')
        except: self.connected=False; self.dev.online=False

    def handle_sms_command(self, cmd):
        return "Jimi OK"
