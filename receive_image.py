import socket
import os

HOST = '0.0.0.0'
PORT = 9000  # Valid port (1024–65535)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow restart without "Address in use" error
server.bind((HOST, PORT))
server.listen(1)

print("📡 Waiting for Raspberry Pi connection...")

conn, addr = server.accept()
print("✅ Connected from:", addr)

print("📥 Receiving image...")

try:
    # Step 1: Read the 8-byte header to know exact file size
    raw_size = conn.recv(8)
    if len(raw_size) < 8:
        raise ValueError("Incomplete header received")
    file_size = int.from_bytes(raw_size, byteorder='big')
    print(f"📦 Expecting {file_size} bytes")

    # Step 2: Receive exactly that many bytes
    received = 0
    with open("received.jpg", "wb") as file:
        while received < file_size:
            chunk = conn.recv(min(4096, file_size - received))
            if not chunk:
                raise ConnectionError(f"Connection lost! Got {received}/{file_size} bytes")
            file.write(chunk)
            received += len(chunk)

    print(f"✅ Image saved ({received} bytes) → received.jpg")

except Exception as e:
    print(f"❌ Error: {e}")
    # Remove incomplete file if transfer failed
    if os.path.exists("received.jpg"):
        os.remove("received.jpg")

finally:
    conn.close()
    server.close()
    print("🔴 Connection closed")