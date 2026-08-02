import socket, struct, datetime
from protocol_handler import ProtocolHandler

class GT06Protocol(ProtocolHandler):
    def build_login(self):
        imei=self.dev.imei.replace('-','').strip()[:15].ljust(15,'0')
        bcd=bytes.fromhex(imei) if len(imei)%2==0 else bytes.fromhex('0'+imei)
        bcd=bcd[:8].rjust(8,b'\x00')
        serial=struct.pack('>H',self.dev.device_id%65535)
        payload=b'\x01'+bcd+serial
        pkt=bytes([0x78,0x78,len(payload)])+payload
        return pkt+bytes([self.crc_xor(payload),0x0D,0x0A])
    def build_location(self):
        d=self.dev; now=datetime.datetime.utcnow()
        dt=bytes([now.year-2000,now.month,now.day,now.hour,now.minute,now.second])
        lat=int(d.latitude*30000)&0xFFFFFFFF; lon=int(d.longitude*30000)&0xFFFFFFFF
        speed_byte=int(d.speed_kmh)&0xFF
        course=int(d.heading*10)%3600
        acc_byte=0x01 if d.ignition else 0x00
        payload=b'\x22'+dt+struct.pack('>I',lat)+struct.pack('>I',lon)+bytes([speed_byte])+struct.pack('>H',course)
        payload+=b'\x00\x00\x00\x00'
        payload+=struct.pack('>H',d.device_id&0xFFFF)
        payload+=bytes([acc_byte])
        pkt=bytes([0x78,0x78,len(payload)])+payload
        return pkt+bytes([self.crc_xor(payload),0x0D,0x0A])
    def build_heartbeat(self):
        payload=b'\x0A'
        pkt=bytes([0x78,0x78,len(payload)])+payload
        return pkt+bytes([self.crc_xor(payload),0x0D,0x0A])
    def build_alarm(self, alarm_type):
        # Simplified: alarm packet type 0x26 with alarm flag
        # For now, we'll send a location packet with an alarm flag in the status byte (not implemented).
        # Just send location; we'll integrate alarm later if needed.
        return self.build_location()
    def connect_and_login(self):
        try:
            self.sock=socket.socket(); self.sock.settimeout(10)
            self.sock.connect((self.dev.server_ip,self.dev.server_port))
            self.sock.sendall(self.build_login())
            resp=self.sock.recv(64)
            if resp:
                self.connected=True; self.dev.online=True; return True
        except: pass
        self.connected=False; self.dev.online=False; return False
    def send_location(self):
        if not self.connected: return
        try: self.sock.sendall(self.build_location())
        except: self.connected=False; self.dev.online=False
    def send_heartbeat(self):
        if not self.connected: return
        try: self.sock.sendall(self.build_heartbeat())
        except: self.connected=False; self.dev.online=False
    def handle_sms_command(self, cmd):
        parts=cmd.strip().split()
        if not parts: return "Empty"
        action=parts[0].lower()
        if action=='server' and len(parts)==3:
            self.dev.server_ip=parts[1]; self.dev.server_port=int(parts[2])
            self.disconnect()
            self.dev.save_state()
            return f"Server changed to {self.dev.server_ip}:{self.dev.server_port}"
        elif action=='reboot':
            self.disconnect()
            return "Rebooting"
        elif action=='loc':
            self.send_location()
            d=self.dev
            return f"Lat:{d.latitude:.6f} Lon:{d.longitude:.6f} Spd:{d.speed_kmh:.1f} Ign:{'ON' if d.ignition else 'OFF'}"
        elif action=='status':
            return f"IGN:{self.dev.ignition} SPD:{self.dev.speed_kmh:.1f} GPS:{self.dev.gps_signal} GSM:{self.dev.gsm_signal}"
        return "Unknown"
