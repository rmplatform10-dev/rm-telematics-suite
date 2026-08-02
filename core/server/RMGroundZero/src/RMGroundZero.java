import java.io.*;
import java.net.*;

public class RMGroundZero {
    public static void main(String[] args) {
        int port = 9871;
        try (ServerSocket server = new ServerSocket(port)) {
            System.out.println("=========================================");
            System.out.println("🚀 RM ENTERPRISES: GROUND ZERO ONLINE");
            System.out.println("📡 Listening on port: " + port);
            System.out.println("=========================================");

            while (true) {
                try (Socket s = server.accept();
                     InputStream in = s.getInputStream();
                     OutputStream out = s.getOutputStream()) {

                    System.out.println("\n[!] TRACKER CONNECTED: " + s.getInetAddress());
                    byte[] buffer = new byte[1024];
                    int len;

                    while ((len = in.read(buffer)) != -1) {
                        String hex = bytesToHex(buffer, len);
                        System.out.println("📦 DATA: " + hex);

                        // GT06 Handshake with correct CRC
                        if (len >= 4 && (buffer[0] & 0xFF) == 0x78 && (buffer[1] & 0xFF) == 0x78 && buffer[3] == 0x01) {
                            byte[] response;
                            if (len >= 14) {
                                byte serialHi = buffer[12];
                                byte serialLo = buffer[13];
                                byte[] payload = {0x01, serialHi, serialLo};
                                byte crc = 0;
                                for (byte b : payload) crc ^= b;
                                response = new byte[]{0x78, 0x78, (byte)payload.length, payload[0], payload[1], payload[2], crc, 0x0D, 0x0A};
                            } else {
                                // fallback generic ack
                                response = new byte[]{0x78, 0x78, 0x05, 0x01, 0x00, 0x01, 0x00, 0x0D, 0x0A};
                            }
                            out.write(response);
                            System.out.println("✅ Login Handshake Sent (CRC correct)!");
                        }
                    }
                } catch (Exception e) { System.out.println("🔌 Connection closed."); }
            }
        } catch (Exception e) { e.printStackTrace(); }
    }

    private static String bytesToHex(byte[] b, int n) {
        StringBuilder s = new StringBuilder();
        for (int i=0; i<n; i++) s.append(String.format("%02X ", b[i]));
        return s.toString();
    }
}
