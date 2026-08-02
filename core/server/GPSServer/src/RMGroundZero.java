import java.io.*;
import java.net.*;

public class RMGroundZero {
    public static void main(String[] args) {
        int port = 9871;
        try (ServerSocket server = new ServerSocket(port)) {
            System.out.println("🚀 RM ENTERPRISES: MASTER SERVER ONLINE");
            System.out.println("📡 Listening on port " + port + ". Waiting for tracker...");

            while (true) {
                try (Socket socket = server.accept();
                     InputStream in = socket.getInputStream();
                     OutputStream out = socket.getOutputStream()) {

                    System.out.println("\n[!] TRACKER CONNECTED: " + socket.getInetAddress());
                    byte[] buffer = new byte[1024];
                    int length;

                    while ((length = in.read(buffer)) != -1) {
                        StringBuilder hex = new StringBuilder();
                        for (int i = 0; i < length; i++) {
                            hex.append(String.format("%02X ", buffer[i]));
                        }
                        System.out.println("📦 DATA RECEIVED: " + hex.toString());

                        if (length >= 4 && (buffer[0] & 0xFF) == 0x78 && (buffer[1] & 0xFF) == 0x78 && buffer[3] == 0x01) {
                            System.out.println("✅ GT06 Login Protocol Detected.");
                            if (length >= 14) {
                                byte serialHi = buffer[12];
                                byte serialLo = buffer[13];
                                byte[] payload = {0x01, serialHi, serialLo};
                                byte crc = 0;
                                for (byte b : payload) crc ^= b;
                                byte[] response = new byte[]{0x78, 0x78, (byte)payload.length, payload[0], payload[1], payload[2], crc, 0x0D, 0x0A};
                                out.write(response);
                                System.out.println("✅ Login Handshake Sent (CRC correct)!");
                            }
                        }
                    }
                } catch (IOException e) {
                    System.out.println("🔌 Connection lost.");
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
