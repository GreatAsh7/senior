"""
STS3215 — Read limits, fix them, verify.
Power-cycle the servo AFTER running this, before your main test.
"""

from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS
import time

PORT      = "/dev/tty.usbmodem5AE60578161"
BAUD_RATE = 1_000_000
SERVO_ID  = 1

portHandler   = PortHandler(PORT)
packetHandler = PacketHandler(0)
portHandler.openPort()
portHandler.setBaudRate(BAUD_RATE)

def r1(addr):
    v, res, err = packetHandler.read1ByteTxRx(portHandler, SERVO_ID, addr)
    return v
def r2(addr):
    v, res, err = packetHandler.read2ByteTxRx(portHandler, SERVO_ID, addr)
    return v
def w1(addr, val):
    r, e = packetHandler.write1ByteTxRx(portHandler, SERVO_ID, addr, val)
    return r == COMM_SUCCESS and e == 0
def w2(addr, val):
    r, e = packetHandler.write2ByteTxRx(portHandler, SERVO_ID, addr, val)
    return r == COMM_SUCCESS and e == 0

print("── Current EEPROM values ──")
print(f"  Min angle limit: {r2(9)}  ticks  ({r2(9)*360/4096:.1f}°)")
print(f"  Max angle limit: {r2(11)} ticks  ({r2(11)*360/4096:.1f}°)")

print("\n── Unlocking EEPROM ──")
w1(55, 0)
time.sleep(0.1)

print("── Writing full-range limits (0 → 4095) ──")
w2(9,  0)
w2(11, 4095)
time.sleep(0.1)
w1(55, 1)
time.sleep(0.1)

print("\n── Verifying ──")
min_v = r2(9)
max_v = r2(11)
print(f"  Min: {min_v} ticks = {min_v*360/4096:.1f}°  {'✓' if min_v == 0    else '✗ FAILED'}")
print(f"  Max: {max_v} ticks = {max_v*360/4096:.1f}°  {'✓' if max_v == 4095 else '✗ FAILED'}")

portHandler.closePort()
print("\n>>> Power-cycle the servo now, then re-run your main test. <<<")
