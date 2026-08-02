from abc import ABC, abstractmethod
import time

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
    def crc_xor(self, data):
        cs=0
        for b in data: cs^=b
        return cs
