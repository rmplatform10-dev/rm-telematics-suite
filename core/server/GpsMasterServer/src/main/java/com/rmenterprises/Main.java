package com.rmenterprises;

import java.io.*;
import java.net.*;
import java.util.concurrent.*;

public class Main {
    private static final int PORT = 9871;

    public static void main(String[] args) {
        ExecutorService pool = Executors.newCachedThreadPool();
        System.out.println("🚀 RM GpsMasterServer (Production) starting on port " + PORT);
        try (ServerSocket server = new ServerSocket(PORT)) {
            while (true) {
                Socket client = server.accept();
                pool.execute(() -> handleClient(client));
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private static void handleClient(Socket client) {
        System.out.println("[+] New client: " + client.getInetAddress());
        try (InputStream in = client.getInputStream();
             OutputStream out = client.getOutputStream()) {
            byte[] buffer = new byte[4096];
            int len;
            while ((len = in.read(buffer)) != -1) {
                String hex = bytesToHex(buffer, len);
                System.out.println("[DATA] " + hex);
                // GT06 login ack
                if (len >= 14 && (buffer[0] & 0xFF) == 0x78 && (buffer[1] & 0xFF) == 0x78 && buffer[3] == 0x01) {
                    byte serialHi = buffer[12];
                    byte serialLo = buffer[13];
                    byte[] payload = {0x01, serialHi, serialLo};
                    byte crc = 0;
                    for (byte b : payload) crc ^= b;
                    byte[] response = {0x78, 0x78, (byte)payload.length, payload[0], payload[1], payload[2], crc, 0x0D, 0x0A};
                    out.write(response);
                    System.out.println("[ACK] Sent login response");
                }
                // TODO: decode other protocols, store in database
            }
        } catch (IOException e) {
            System.out.println("[-] Client disconnected: " + client.getInetAddress());
        }
    }

    private static String bytesToHex(byte[] b, int n) {
        StringBuilder s = new StringBuilder();
        for (int i=0; i<n; i++) s.append(String.format("%02X ", b[i]));
        return s.toString();
    }
}
