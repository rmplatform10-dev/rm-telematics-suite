import socket, struct, datetime
from protocol_handler import ProtocolHandler

class TeltonikaProtocol(ProtocolHandler):
    def build_imei_packet(self):
        imei=self.dev.imei.replace('-','').strip()[:15].ljust(15,'0')
        return (len(imei).to_bytes(2,'big')+imei.encode())
    def build_avl_data(self):
        d=self.dev; now=datetime.datetime.utcnow(); ts=int(now.timestamp()*1000)
        lat=int(d.latitude*10000000); lon=int(d.longitude*10000000)
        alt=int(d.altitude); ang=int(d.heading); spd=int(d.speed_kmh); sat=d.satellites
        payload=struct.pack('>Q',ts)+b'\x00'
        payload+=struct.pack('>i',lat)+struct.pack('>i',lon)+struct.pack('>H',alt)+struct.pack('>H',ang)+bytes([sat])+struct.pack('>H',spd)
        payload+=struct.pack('>H',0)+struct.pack('>B',1)+struct.pack('>B',1)+struct.pack('>B',1 if d.ignition else 0)
        preamble=b'\x00\x00\x00\x00'; data_len=len(payload)
        pkt=preamble+struct.pack('>I',data_len)+payload
        crc_val=0
        for b in pkt[8:]: crc_val^=b
        pkt+=struct.pack('>I',crc_val)
        return pkt
    def connect_and_login(self):
        try:
            self.sock=socket.socket(); self.sock.settimeout(10)
            self.sock.connect((self.dev.server_ip,self.dev.server_port))
            self.sock.sendall(self.build_imei_packet())
            resp=self.sock.recv(1)
            if resp==b'\x01': self.connected=True; self.dev.online=True; return True
        except: pass
        self.connected=False; self.dev.online=False; return False
    def send_location(self):
        if not self.connected: return
        try: self.sock.sendall(self.build_avl_data())
        except: self.connected=False; self.dev.online=False
    def send_heartbeat(self): self.send_location()
    def handle_sms_command(self, cmd):
        parts=cmd.strip().split()
        if not parts: return "Empty"
        action=parts[0].lower()
        if action=='server' and len(parts)==3:
            self.dev.server_ip=parts[1]; self.dev.server_port=int(parts[2])
            self.disconnect()
            self.dev.save_state()
            return "OK"
        elif action=='reboot': self.disconnect(); return "Rebooting"
        elif action=='loc':
            self.send_location()
            d=self.dev
            return f"Lat:{d.latitude:.6f} Lon:{d.longitude:.6f} Spd:{d.speed_kmh:.1f} Ign:{'ON' if d.ignition else 'OFF'}"
        elif action=='status': return f"IGN:{self.dev.ignition} SPD:{self.dev.speed_kmh:.1f}"
        return "Unknown"
