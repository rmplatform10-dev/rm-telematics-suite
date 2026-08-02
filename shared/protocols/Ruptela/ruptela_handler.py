from protocol_handler import ProtocolHandler
import socket, struct, datetime

class RuptelaProtocol(ProtocolHandler):
    def connect_and_login(self):
        try:
            self.sock = socket.socket(); self.sock.settimeout(10)
            self.sock.connect((self.dev.server_ip, self.dev.server_port))
            # Ruptela login: IMEI as 8 bytes BCD + 0x01
            imei = self.dev.imei.replace('-','').strip()[:15].ljust(15,'0')
            bcd = bytes.fromhex(imei) if len(imei)%2==0 else bytes.fromhex('0'+imei)
            bcd = bcd[:8].rjust(8, b'\x00')
            payload = b'\x01' + bcd  # login type 1
            pkt = payload + bytes([self.crc_xor(payload)])
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
            lat = int(d.latitude * 10000000)
            lon = int(d.longitude * 10000000)
            speed = int(d.speed_kmh)
            heading = int(d.heading)
            alt = int(d.altitude)
            # Ruptela data: 0x10 (record id) + timestamp + coordinates + io
            ts = int(now.timestamp())
            payload = b'\x10' + struct.pack('>I', ts) + struct.pack('>i', lat) + struct.pack('>i', lon) + struct.pack('>H', speed) + struct.pack('>H', heading) + struct.pack('>H', alt)
            pkt = payload + bytes([self.crc_xor(payload)])
            self.sock.sendall(pkt)
        except: self.connected=False; self.dev.online=False

    def send_heartbeat(self):
        self.send_location()

    def handle_sms_command(self, cmd):
        return "Ruptela OK"
