#!/usr/bin/env python3
"""GPS Gateway - Dummy TCP listener supporting all eight protocols"""
import socket, threading, datetime

HOST = '0.0.0.0'
PORT = 5023

def handle_client(conn, addr):
    print(f"[GW] New connection from {addr}")
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            hex_str = data.hex()
            now = datetime.datetime.now().strftime('%H:%M:%S')
            print(f"[GW] [{now}] RAW: {hex_str}")

            # GT06 / Concox / Coban login (starts with 78 78, type 0x01)
            if data[:2] == b'\x78\x78' and len(data) >= 4 and data[3] == 0x01:
                serial = data[12:14] if len(data) >= 14 else b'\x00\x01'
                payload = b'\x01' + serial
                crc = 0
                for b in payload:
                    crc ^= b
                resp = bytes([0x78, 0x78, len(payload)]) + payload + bytes([crc, 0x0D, 0x0A])
                conn.sendall(resp)
                print("[GW] Sent GT06/Concox/Coban login ack")

            # Teltonika IMEI packet (first two bytes = length, then ASCII IMEI)
            elif len(data) >= 17:
                imei_len = int.from_bytes(data[:2], 'big')
                if imei_len in (15, 16) and len(data) == 2 + imei_len and data[2:].isalnum():
                    conn.sendall(b'\x01')
                    print("[GW] Sent Teltonika login ack")

            # Queclink text login: "+RESP:GTFRI,..."
            if data.startswith(b'+'):
                try:
                    text = data.decode()
                    if text.startswith('+RESP:GTFRI'):
                        conn.sendall(b'+ACK:GTFRI,OK$')
                        print("[GW] Sent Queclink login ack")
                except: pass

            # Meitrack text login: "##,imei:..."
            if data.startswith(b'##'):
                try:
                    text = data.decode()
                    if 'imei:' in text:
                        conn.sendall(b'LOAD')
                        print("[GW] Sent Meitrack login ack")
                except: pass

            # Jimi binary login: 0x7E ... 0x7E
            if data[:1] == b'\x7E':
                # send generic response
                conn.sendall(b'\x7E\x80\x01\x00\x00\x7E')
                print("[GW] Sent Jimi login ack")

            # Ruptela binary login: first byte 0x01, length variable
            if data[:1] == b'\x01' and len(data) >= 9:
                # send ack: 0x01 (type) + serial? We'll just echo a simple ack
                conn.sendall(b'\x01\x00\x00')
                print("[GW] Sent Ruptela login ack")

    except Exception as e:
        print(f"[GW] Error: {e}")
    finally:
        conn.close()
        print(f"[GW] Connection closed: {addr}")

def main():
    print(f"[GW] GPS Gateway listener started on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(50)
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr))
            t.daemon = True
            t.start()

if __name__ == '__main__':
    main()
