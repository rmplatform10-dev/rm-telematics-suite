from protocol_handler import ProtocolHandler
import socket, struct, datetime, time

class ConcoxProtocol(ProtocolHandler):
    def connect_and_login(self):
        try:
            self.sock = socket.socket(); self.sock.settimeout(10)
            self.sock.connect((self.dev.server_ip, self.dev.server_port))
            # Concox login packet similar to GT06 but with model differences; we send a generic login
            imei = self.dev.imei.replace('-','').strip()[:15].ljust(15,'0')
            bcd = bytes.fromhex(imei) if len(imei)%2==0 else bytes.fromhex('0'+imei)
            bcd = bcd[:8].rjust(8, b'\x00')
            serial = struct.pack('>H', self.dev.device_id % 65535)
            payload = b'\x01' + bcd + serial
            pkt = bytes([0x78, 0x78, len(payload)]) + payload
            crc = self.crc_xor(payload)
            pkt += bytes([crc, 0x0D, 0x0A])
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
            dt = bytes([now.year-2000, now.month, now.day, now.hour, now.minute, now.second])
            lat = int(d.latitude*30000)&0xFFFFFFFF
            lon = int(d.longitude*30000)&0xFFFFFFFF
            speed = int(d.speed_kmh)&0xFF
            course = int(d.heading*10)%3600
            acc = 0x01 if d.ignition else 0x00
            payload = b'\x22' + dt + struct.pack('>I',lat) + struct.pack('>I',lon) + bytes([speed]) + struct.pack('>H',course) + b'\x00\x00\x00\x00' + struct.pack('>H', d.device_id&0xFFFF) + bytes([acc])
            pkt = bytes([0x78,0x78,len(payload)]) + payload
            pkt += bytes([self.crc_xor(payload), 0x0D, 0x0A])
            self.sock.sendall(pkt)
        except: self.connected=False; self.dev.online=False

    def send_heartbeat(self):
        if not self.connected: return
        try:
            payload = b'\x0A'
            pkt = bytes([0x78,0x78,len(payload)]) + payload
            pkt += bytes([self.crc_xor(payload), 0x0D, 0x0A])
            self.sock.sendall(pkt)
        except: self.connected=False; self.dev.online=False

    def handle_sms_command(self, cmd):
        return "Concox OK"
