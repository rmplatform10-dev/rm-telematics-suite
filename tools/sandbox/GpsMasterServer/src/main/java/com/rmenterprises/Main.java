package com.rmenterprises;

import com.fazecast.jSerialComm.SerialPort;
import java.nio.charset.StandardCharsets;

public class Main {
    public static void main(String[] args) {
        // 1. Identify your CP2102 on COM3
        SerialPort comPort = SerialPort.getCommPort("COM3");
        comPort.setBaudRate(9600);

        // 2. Open the port automatically
        if (comPort.openPort()) {
            System.out.println("RM Enterprises: Connection Successful on COM3");

            // 3. Auto-send command with \r\n to trigger the tracker's response
            String command = "PARAM#\r\n";
            comPort.writeBytes(command.getBytes(StandardCharsets.UTF_8), command.length());
            System.out.println("Sent Command: " + command.trim());

            // 4. Start the automatic listener
            try {
                byte[] buffer = new byte[1024];
                while (true) {
                    if (comPort.bytesAvailable() > 0) {
                        int len = comPort.readBytes(buffer, buffer.length);
                        String result = new String(buffer, 0, len, StandardCharsets.UTF_8);
                        System.out.print("[DEVICE RESPONSE]: " + result);
                    }
                    Thread.sleep(100);
                }
            } catch (Exception e) {
                System.err.println("Communication Error: " + e.getMessage());
            }
        } else {
            System.err.println("FATAL ERROR: Could not open COM3. Ensure no other program (like PuTTY) is using it!");
        }
    }
}