#!/usr/bin/env python3
import socket

HOST = '127.0.0.1'
PORT = 9999

def main():
    print("Mobile SMS Sender")
    sim = input("SIM: ").strip()
    cmd = input("Command (loc/status/reboot/server): ").strip()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(f"SMS:{sim}:{cmd}".encode())
            resp = s.recv(1024).decode()
            print(f"Response: {resp}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
