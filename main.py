import serial
import socket
import threading
import os

# 🔹 CHANGE THESE
COM_PORT = 'COM3'
PI_IP = '10.161.34.210'
PI_PORT = 12345
RECEIVE_PORT = 12346

# Shared event: signals main thread that image is fully received
image_ready = threading.Event()

# ─────────────────────────────────────────────
# FUNCTION: Receive image from Pi (runs in background thread)
# ─────────────────────────────────────────────
def receive_image():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', RECEIVE_PORT))
    server.listen(1)

    print("📡 Image receiver listening on port", RECEIVE_PORT)

    try:
        conn, addr = server.accept()
        print("✅ Pi connected for image transfer:", addr)

        try:
            # Read 8-byte length header first
            raw_size = b''
            while len(raw_size) < 8:
                chunk = conn.recv(8 - len(raw_size))
                if not chunk:
                    raise ConnectionError("Connection lost during header read")
                raw_size += chunk

            file_size = int.from_bytes(raw_size, byteorder='big')
            print(f"📦 Expecting {file_size} bytes")

            # Receive exactly file_size bytes
            received = 0
            with open("received.jpg", "wb") as f:
                while received < file_size:
                    data = conn.recv(min(4096, file_size - received))
                    if not data:
                        raise ConnectionError(f"Lost connection at {received}/{file_size} bytes")
                    f.write(data)
                    received += len(data)

            print(f"🎉 Image saved ({received} bytes) → received.jpg")
            image_ready.set()  # Signal main thread: image is ready

        except Exception as e:
            print(f"❌ Receive error: {e}")
            if os.path.exists("received.jpg"):
                os.remove("received.jpg")  # Clean up incomplete file

        finally:
            conn.close()

    finally:
        server.close()


# ─────────────────────────────────────────────
# FUNCTION: Send capture command to Pi
# ─────────────────────────────────────────────
def send_capture_command():
    retries = 3
    for attempt in range(1, retries + 1):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)  # Don't hang if Pi is unreachable
            s.connect((PI_IP, PI_PORT))
            s.sendall(b'CAPTURE')
            s.close()
            print("📤 CAPTURE command sent to Pi")
            return True
        except Exception as e:
            print(f"⚠️ Attempt {attempt}/{retries} failed: {e}")
    print("❌ Could not reach Pi after all retries")
    return False


# ─────────────────────────────────────────────
# MAIN: Serial loop — keeps running for multiple captures
# ─────────────────────────────────────────────
def main():
    # Start image receiver thread before anything else
    receiver_thread = threading.Thread(target=receive_image, daemon=True)
    receiver_thread.start()

    try:
        ser = serial.Serial(COM_PORT, 9600, timeout=1)
        print(f"🔌 Listening on {COM_PORT} for Nano signals...")

        while True:
            try:
                line = ser.readline().decode(errors='replace').strip()
                if not line:
                    continue  # Timeout tick — keep looping

                print("Nano:", line)

                if line == "SENSOR_HIGH":
                    print("🚀 Trigger received → sending command to Pi")

                    if send_capture_command():
                        print("⏳ Waiting for image...")
                        received = image_ready.wait(timeout=15)  # Wait max 15s

                        if received:
                            print("✅ Image ready — proceed to next step (AI / TTS)")
                            image_ready.clear()  # Reset for next capture
                        else:
                            print("⏰ Timeout: Pi didn't send image in time")

            except UnicodeDecodeError:
                pass  # Ignore garbled bytes from serial

    except serial.SerialException as e:
        print(f"❌ Serial error: {e}")

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")

    finally:
        if ser.is_open:
            ser.close()
            print("🔌 Serial port closed")


if __name__ == "__main__":
    main()