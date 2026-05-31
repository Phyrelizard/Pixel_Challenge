import socket
import struct
import time

SIM_IP = "192.168.2.250"   # <-- put Windows simulator IP here
PORT = 5568

def make_test_packet(universe, r, g, b):
    # Minimal packet shaped exactly how our simulator parser expects E1.31/sACN.
    packet = bytearray(126 + 512)

    # ACN packet identifier at bytes 4..15
    packet[4:16] = b"ASC-E1.17\x00\x00\x00"

    # Universe at bytes 113..114
    packet[113:115] = struct.pack(">H", universe)

    # Property value count at bytes 123..124.
    # 513 = 1 DMX start code + 512 DMX slots.
    packet[123:125] = struct.pack(">H", 513)

    # DMX data starts at byte 126.
    for i in range(170):
        base = 126 + i * 3
        if base + 2 < len(packet):
            packet[base + 0] = r
            packet[base + 1] = g
            packet[base + 2] = b

    return bytes(packet)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"Sending test E1.31 packets to {SIM_IP}:{PORT}")
print("Universe 1 should turn red, U2 green, U3 blue.")

packets = [
    make_test_packet(1, 255, 0, 0),
    make_test_packet(2, 0, 255, 0),
    make_test_packet(3, 0, 0, 255),
]

end = time.time() + 10
while time.time() < end:
    for packet in packets:
        sock.sendto(packet, (SIM_IP, PORT))
    time.sleep(0.05)

print("Done.")