#!/usr/bin/env python3
"""Virtual GPS Emulator - Non‑blocking connection + always‑on SMS"""
import socket, struct, time, random, threading, json, sys, os, math, datetime, argparse
from abc import ABC, abstractmethod

def move_towards(lat, lon, heading_deg, distance_m):
    R=6371000; d=distance_m/R; brg=math.radians(heading_deg)
    lat1=math.radians(lat); lon1=math.radians(lon)
    lat2=math.asin(math.sin(lat1)*math.cos(d)+math.cos(lat1)*math.sin(d)*math.cos(brg))
    lon2=lon1+math.atan2(math.sin(brg)*math.sin(d)*math.cos(lat1),math.cos(d)-math.sin(lat1)*math.sin(lat2))
    return math.degrees(lat2),math.degrees(lon2)
def crc_xor(data):
    cs=0
    for b in data: cs^=b
    return cs

class ProtocolHandler(ABC):
    def __init__(self,dev): self.dev=dev; self.sock=None; self.connected=False
    @abstractmethod
    def connect_and_login(self): pass
    @abstractmethod
    def send_location(self): pass
    @abstractmethod
    def send_heartbeat(self): pass
    @abstractmethod
    def handle_sms_command(self, cmd): pass
    def disconnect(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.connected=False; self.dev.online=False

class GT06Protocol(ProtocolHandler):
    def build_login(self):
        imei=self.dev.imei.replace('-','').strip()[:15].ljust(15,'0')
        bcd=bytes.fromhex(imei) if len(imei)%2==0 else bytes.fromhex('0'+imei)
        bcd=bcd[:8].rjust(8,b'\x00')
        serial=struct.pack('>H',self.dev.device_id%65535)
        payload=b'\x01'+bcd+serial
        pkt=bytes([0x78,0x78,len(payload)])+payload
        return pkt+bytes([crc_xor(payload),0x0D,0x0A])
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
        return pkt+bytes([crc_xor(payload),0x0D,0x0A])
    def build_heartbeat(self):
        payload=b'\x0A'
        pkt=bytes([0x78,0x78,len(payload)])+payload
        return pkt+bytes([crc_xor(payload),0x0D,0x0A])
    def connect_and_login(self):
        try:
            self.sock=socket.socket(); self.sock.settimeout(10)
            self.sock.connect((self.dev.server_ip,self.dev.server_port))
            self.sock.sendall(self.build_login())
            resp=self.sock.recv(64)
            if resp:
                self.connected=True; self.dev.online=True; return True
        except Exception as e:
            pass
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
            return "OK"
        elif action=='reboot': self.disconnect(); return "Rebooting"
        elif action=='loc':
            self.send_location()
            d=self.dev
            return f"Lat:{d.latitude:.6f} Lon:{d.longitude:.6f} Spd:{d.speed_kmh:.1f} Ign:{'ON' if d.ignition else 'OFF'}"
        elif action=='status': return f"IGN:{self.dev.ignition} SPD:{self.dev.speed_kmh:.1f}"
        return "Unknown"

class GPSDevice:
    def __init__(self, config, dev_id):
        self.device_id=dev_id; self.imei=config['imei']; self.sim=config.get('sim','1111111111')
        self.protocol_type=config.get('protocol','GT06')
        self.server_ip=config['server_ip']; self.server_port=config['server_port']
        self.latitude=config.get('start_lat',28.6139); self.longitude=config.get('start_lon',77.2090)
        self.heading=config.get('start_heading',random.randint(0,359))
        self.speed_kmh=0.0; self.ignition=False; self.external_power=True
        self.gps_signal=True; self.gsm_signal=random.randint(20,31)
        self.satellites=random.randint(12,20); self.hdop=round(random.uniform(0.5,2.0),1)
        self.altitude=config.get('start_altitude',random.randint(100,300))
        self.odometer=random.randint(50000,200000); self.engine_hours=random.randint(1000,5000)
        self.internal_battery_pct=100; self.online=False
        self.state='PARKED_IGN_OFF'; self.state_timer=0
        self.stagger_delay=random.uniform(0,60)
        self.cruise_speed=random.randint(50,65)
        self.max_speed_burst=False; self.speed_burst_timer=0
        self.route_waypoints=config.get('route',[])
        self.lock=threading.Lock(); self.protocol=None; self.gsm_lost=False; self.sms_inbox=[]

    def update_sensors(self, dt):
        if random.random()<0.02: self.gsm_signal=max(0,min(31,self.gsm_signal+random.randint(-5,5)))
        if not self.gsm_lost and random.random()<0.001: self.gsm_lost=True
        if self.gsm_lost and random.random()<0.05: self.gsm_lost=False
        if self.gps_signal and random.random()<0.0005: self.gps_signal=False
        if not self.gps_signal and random.random()<0.01: self.gps_signal=True
        if self.external_power: self.internal_battery_pct=min(100, self.internal_battery_pct+0.01*dt)
        else: self.internal_battery_pct-=0.005*dt
        if self.internal_battery_pct<0: self.internal_battery_pct=0

    def update_movement(self, dt):
        if self.stagger_delay>0:
            self.stagger_delay-=dt; return
        if self.state=='PARKED_IGN_OFF':
            self.state_timer+=dt
            if self.state_timer>random.uniform(30,600):
                self.ignition=True; self.state='IDLE'; self.state_timer=0
        elif self.state=='IDLE':
            self.state_timer+=dt
            if self.state_timer>random.uniform(5,30):
                self.state='ACCELERATING'; self.target_speed=self.cruise_speed; self.state_timer=0
        elif self.state=='ACCELERATING':
            accel=0.5+1.0*random.random()
            self.speed_kmh+=accel*dt*3.6
            if self.speed_kmh>=self.target_speed:
                self.speed_kmh=self.target_speed; self.state='CRUISING'; self.state_timer=0
        elif self.state=='CRUISING':
            self.speed_kmh+=random.uniform(-0.3,0.3); self.speed_kmh=max(0,self.speed_kmh)
            if not self.max_speed_burst and random.random()<0.0005:
                self.max_speed_burst=True; self.speed_burst_timer=0; self.target_speed=random.randint(95,100)
            if self.max_speed_burst:
                self.speed_burst_timer+=dt
                if self.speed_burst_timer>20: self.max_speed_burst=False; self.target_speed=self.cruise_speed
            self.state_timer+=dt
            if self.state_timer>random.uniform(40,120) and random.random()<0.3:
                self.state='SLOWING'; self.target_speed=0; self.state_timer=0
        elif self.state=='SLOWING':
            decel=0.8+1.2*random.random()
            self.speed_kmh-=decel*dt*3.6
            if self.speed_kmh<=0:
                self.speed_kmh=0; self.state='STOPPED'; self.stop_duration=random.uniform(20,90); self.state_timer=0
        elif self.state=='STOPPED':
            self.state_timer+=dt
            if self.state_timer>self.stop_duration:
                if random.random()<0.7: self.state='ACCELERATING'; self.target_speed=random.randint(45,65)
                else: self.state='PARKING'
                self.state_timer=0
        elif self.state=='PARKING': self.ignition=False; self.state='PARKED_IGN_OFF'; self.state_timer=0
        if self.speed_kmh>0: self.heading+=random.uniform(-3,3); self.heading%=360
        if self.speed_kmh>0 and self.gps_signal:
            dist_m=(self.speed_kmh/3.6)*dt
            self.latitude,self.longitude=move_towards(self.latitude,self.longitude,self.heading,dist_m)
            self.odometer+=int(dist_m); self.engine_hours+=dt/3600
        if self.speed_kmh==0 and self.gps_signal:
            drift=random.uniform(-0.00005,0.00005); self.latitude+=drift; self.longitude+=drift

    def run_loop(self):
        time.sleep(self.stagger_delay)
        if self.protocol_type=='GT06': self.protocol=GT06Protocol(self)
        elif self.protocol_type=='Teltonika': self.protocol=TeltonikaProtocol(self)
        else: print(f"Unsupported {self.protocol_type}"); return

        # Background connection keeper
        def keep_connected():
            while True:
                if not self.protocol.connected:
                    self.protocol.connect_and_login()
                time.sleep(5)

        threading.Thread(target=keep_connected, daemon=True).start()

        last_loc=time.time(); last_hb=time.time()
        while True:
            try:
                dt=1.0; time.sleep(1)
                with self.lock:
                    self.update_sensors(dt); self.update_movement(dt)
                    while self.sms_inbox:
                        cmd=self.sms_inbox.pop(0)
                        resp=self.protocol.handle_sms_command(cmd)
                        print(f"\n[SMS RESPONSE from {self.sim}] {resp}\nSIM> ", end='', flush=True)
                now=time.time()
                if not self.gsm_lost:
                    if now-last_loc>=10: self.protocol.send_location(); last_loc=now
                    if now-last_hb>=30: self.protocol.send_heartbeat(); last_hb=now
            except Exception as e:
                print(f"[{self.imei}] Error: {e}")

class Emulator:
    def __init__(self, config_file):
        self.config=json.load(open(config_file,'r'))
        self.devices=[]; self.device_by_sim={}
    def load_devices(self):
        for i,cfg in enumerate(self.config['devices']):
            d=GPSDevice(cfg,i+1); self.devices.append(d); self.device_by_sim[d.sim]=d
    def start_all(self):
        threads=[]
        for d in self.devices:
            t=threading.Thread(target=d.run_loop); t.daemon=True; t.start()
            threads.append(t)
        return threads

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config', default=os.path.join(os.path.dirname(__file__),'Config','config.json'))
    args=parser.parse_args()
    emu=Emulator(args.config); emu.load_devices(); threads=emu.start_all()
    print(f"Started {len(threads)} devices.")
    print("SMS commands: sms <sim> <command>")
    while True:
        try:
            raw=input("SIM> ").strip()
            if not raw: continue
            if raw.lower()=='exit': break
            if raw.lower().startswith('sms '):
                parts=raw.split(' ',2)
                if len(parts)>=3:
                    sim=parts[1]; sms_cmd=parts[2]
                    dev=emu.device_by_sim.get(sim)
                    if dev:
                        with dev.lock: dev.sms_inbox.append(sms_cmd)
                        print(f"[SMS] Sent to {sim}")
                    else: print(f"SIM {sim} not found")
                else: print("Usage: sms <sim> <command>")
            else: print("Unknown command")
        except (KeyboardInterrupt, EOFError): break
    print("Exiting.")
