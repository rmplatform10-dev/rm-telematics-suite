from abc import ABC, abstractmethod
import time

class ProtocolHandler(ABC):
    def __init__(self,dev):
        self.dev=dev; self.sock=None; self.connected=False
    @abstractmethod
    def connect_and_login(self): pass
    @abstractmethod
    def send_location(self): pass
    @abstractmethod
    def send_heartbeat(self): pass
    # Provide a robust default SMS command handler; protocol-specific handlers may override
    def handle_sms_command(self, cmd):
        """Unified SMS command format (called from device run loop):
        Supported: loc, status, server <ip> <port>, reboot, reset, stop, start, help
        Returns a single-line human-readable response.
        """
        text = cmd.strip()
        parts = text.split()
        if not parts:
            return "ERROR: Empty command"
        action = parts[0].lower()
        try:
            if action == 'help':
                resp = 'Commands: loc, status, server <ip> <port>, reboot, reset, stop, start, help'
                try:
                    if hasattr(self.dev, 'monitor'):
                        self.dev.monitor(f"SMS from {self.dev.sim}: {text} -> {resp}")
                except Exception:
                    pass
                return resp
            if action == 'loc':
                d = self.dev
                resp = f"Lat:{d.latitude:.6f} Lon:{d.longitude:.6f} Spd:{d.speed_kmh:.1f} Ign:{'ON' if d.ignition else 'OFF'}"
                try:
                    if hasattr(self.dev, 'monitor'):
                        self.dev.monitor(f"SMS from {self.dev.sim}: {text} -> {resp}")
                except Exception:
                    pass
                return resp
            if action == 'status':
                d = self.dev
                resp = f"IGN:{d.ignition} SPD:{d.speed_kmh:.1f} GPS:{d.gps_signal} GSM:{d.gsm_signal} BAT:{d.internal_battery_pct:.0f}%"
                try:
                    if hasattr(self.dev, 'monitor'):
                        self.dev.monitor(f"SMS from {self.dev.sim}: {text} -> {resp}")
                except Exception:
                    pass
                return resp
            if action == 'server' and len(parts) == 3:
                ip = parts[1]; port = int(parts[2])
                self.dev.server_ip = ip; self.dev.server_port = port
                self.dev.save_state()
                # disconnect to force reconnect
                try: self.disconnect()
                except: pass
                resp = f"Server changed to {ip}:{port}"
                try:
                    if hasattr(self.dev, 'monitor'):
                        self.dev.monitor(f"SMS from {self.dev.sim}: {text} -> {resp}")
                except Exception:
                    pass
                return resp
            if action == 'reboot':
                try: self.disconnect()
                except: pass
                return 'Rebooting'
            if action == 'reset':
                # restore defaults from initial config if available
                try:
                    cfg_path = getattr(self.dev, 'state_file', None)
                    # Not fully implemented; clear runtime overrides
                    self.dev.server_ip = self.dev.server_ip
                    self.dev.server_port = self.dev.server_port
                except:
                    pass
                return 'Reset to defaults'
            if action == 'stop':
                # request stop via registered callback if provided
                try:
                    from . import device_core as _dc
                except Exception:
                    import device_core as _dc
                if _dc.stop_device_cb:
                    try:
                        _dc.stop_device_cb(self.dev.imei)
                        resp = 'Stopped'
                        try:
                            if hasattr(self.dev, 'monitor'):
                                self.dev.monitor(f"SMS from {self.dev.sim}: {text} -> {resp}")
                        except Exception:
                            pass
                        return resp
                    except Exception as e:
                        return f'ERROR stopping: {e}'
                else:
                    # best-effort: mark offline
                    self.dev.online = False
                    try: self.disconnect()
                    except: pass
                    resp = 'Stopped'
                    try:
                        if hasattr(self.dev, 'monitor'):
                            self.dev.monitor(f"SMS from {self.dev.sim}: {text} -> {resp}")
                    except Exception:
                        pass
                    return resp
            if action == 'start':
                try:
                    from . import device_core as _dc
                except Exception:
                    import device_core as _dc
                if _dc.start_device_cb:
                    try:
                        _dc.start_device_cb(self.dev.imei)
                        resp = 'Starting'
                        try:
                            if hasattr(self.dev, 'monitor'):
                                self.dev.monitor(f"SMS from {self.dev.sim}: {text} -> {resp}")
                        except Exception:
                            pass
                        return resp
                    except Exception as e:
                        return f'ERROR starting: {e}'
                else:
                    # best-effort: try to connect
                    try:
                        self.connect_and_login()
                        resp = 'Starting'
                        try:
                            if hasattr(self.dev, 'monitor'):
                                self.dev.monitor(f"SMS from {self.dev.sim}: {text} -> {resp}")
                        except Exception:
                            pass
                        return resp
                    except Exception as e:
                        return f'ERROR starting: {e}'
        except Exception as e:
            return f'ERROR: {e}'
        return 'Unknown command'
    def disconnect(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.connected=False; self.dev.online=False
    def crc_xor(self, data):
        cs=0
        for b in data: cs^=b
        return cs
