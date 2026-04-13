from scservo_sdk import PortHandler, PacketHandler, COMM_SUCCESS
import time

PORT      = "/dev/tty.usbmodem5AE60578161"
BAUD_RATE = 1_000_000

SERVO_IDS = [1, 2, 3, 4, 5, 6]

ADDR_TORQUE_ENABLE    = 40
ADDR_GOAL_POSITION    = 42
ADDR_PRESENT_POSITION = 56
ADDR_MOVING_SPEED     = 46
ADDR_GOAL_ACCEL       = 41
ADDR_MAX_TORQUE       = 16
ADDR_TORQUE_LIMIT     = 34
ADDR_PRESENT_VOLTAGE  = 62

# Home position per servo (in degrees)
HOME_DEGREES = {1: 180, 2: 100, 3: 240, 4: 180, 5: 30, 6: 270}

# Software limits per servo (min_degrees, max_degrees)
LIMITS = {
    1: (90,  270),
    2: (0,   180),
    3: (180, 350),
    4: (90,  270),
    5: (0,   90),
    6: (180, 350),
}

HOME_TICKS = {sid: int(deg * 4095 / 360) for sid, deg in HOME_DEGREES.items()}
positions  = dict(HOME_TICKS)

portHandler   = PortHandler(PORT)
packetHandler = PacketHandler(0)

portHandler.openPort()
portHandler.setBaudRate(BAUD_RATE)

def read_pos(sid):
    v, r, e = packetHandler.read2ByteTxRx(portHandler, sid, ADDR_PRESENT_POSITION)
    if r == COMM_SUCCESS and e == 0:
        return v
    return None

def read_voltage(sid):
    v, r, e = packetHandler.read1ByteTxRx(portHandler, sid, ADDR_PRESENT_VOLTAGE)
    if r == COMM_SUCCESS and e == 0:
        return v / 10.0
    return None

def recover(sid):
    packetHandler.write1ByteTxRx(portHandler, sid, ADDR_TORQUE_ENABLE, 0)
    time.sleep(0.1)
    packetHandler.write1ByteTxRx(portHandler, sid, ADDR_TORQUE_ENABLE, 1)

def write_pos(sid, pos):
    pos = max(0, min(4095, pos))
    r, e = packetHandler.write2ByteTxRx(portHandler, sid, ADDR_GOAL_POSITION, pos)
    if r != COMM_SUCCESS or e != 0:
        recover(sid)
        r, e = packetHandler.write2ByteTxRx(portHandler, sid, ADDR_GOAL_POSITION, pos)
    return r == COMM_SUCCESS and e == 0

def deg_to_ticks(deg):
    return int((deg / 360.0) * 4095)

def ticks_to_deg(ticks):
    return ticks * 360 / 4095

def check_limits(sid, target_deg):
    """Returns (allowed, clamped_deg). Warns if out of range."""
    lo, hi = LIMITS[sid]
    if target_deg < lo:
        print(f"  ⚠ Servo {sid}: {target_deg:.1f}° is below min limit ({lo}°), clamping.")
        return False, lo
    if target_deg > hi:
        print(f"  ⚠ Servo {sid}: {target_deg:.1f}° is above max limit ({hi}°), clamping.")
        return False, hi
    return True, target_deg

def set_max_torque(sid, value=1000):
    packetHandler.write1ByteTxRx(portHandler, sid, 55, 0)
    time.sleep(0.05)
    packetHandler.write2ByteTxRx(portHandler, sid, ADDR_MAX_TORQUE, value)
    time.sleep(0.05)
    packetHandler.write1ByteTxRx(portHandler, sid, 55, 1)
    packetHandler.write2ByteTxRx(portHandler, sid, ADDR_TORQUE_LIMIT, value)

# ── Enable torque, set max torque, and home all servos ───────────────────────
print("Setting max torque and homing all servos...")
for sid in SERVO_IDS:
    packetHandler.write1ByteTxRx(portHandler, sid, ADDR_TORQUE_ENABLE, 1)
    packetHandler.write2ByteTxRx(portHandler, sid, ADDR_MOVING_SPEED, 100)
    packetHandler.write1ByteTxRx(portHandler, sid, ADDR_GOAL_ACCEL, 10)
    set_max_torque(sid, 1000)
    write_pos(sid, HOME_TICKS[sid])
    lo, hi = LIMITS[sid]
    print(f"  Servo {sid}: homing to {HOME_DEGREES[sid]}°  (limits: {lo}°–{hi}°)")

time.sleep(3.0)

# ── Check voltages ────────────────────────────────────────────────────────────
print()
print("Voltage readings:")
for sid in SERVO_IDS:
    v = read_voltage(sid)
    if v is not None:
        flag = " ⚠ LOW" if v < 6.5 else ""
        print(f"  Servo {sid}: {v:.1f}V{flag}")
    else:
        print(f"  Servo {sid}: not responding")

# Confirm positions
print()
print("Positions after homing:")
for sid in SERVO_IDS:
    p = read_pos(sid)
    if p is not None:
        positions[sid] = p
        print(f"  Servo {sid}: {p} ticks ({ticks_to_deg(p):.1f}°)")
    else:
        print(f"  Servo {sid}: not responding")

# ── CLI loop ──────────────────────────────────────────────────────────────────
print("\nServo controller ready.")
print("Format: <servo_id> <+/-degrees>")
print("Example: 2 30   OR   5 -15")
print("Type 'v' to check voltages, 'l' to show limits, 'q' to quit\n")

while True:
    cmd = input(">> ").strip()

    if cmd.lower() == "q":
        break

    if cmd.lower() == "v":
        for sid in SERVO_IDS:
            v = read_voltage(sid)
            if v is not None:
                flag = " ⚠ LOW" if v < 6.5 else ""
                print(f"  Servo {sid}: {v:.1f}V{flag}")
            else:
                print(f"  Servo {sid}: not responding")
        continue

    if cmd.lower() == "l":
        for sid in SERVO_IDS:
            lo, hi = LIMITS[sid]
            current = ticks_to_deg(positions[sid])
            print(f"  Servo {sid}: {lo}°–{hi}°  (current: {current:.1f}°)")
        continue

    try:
        sid_str, deg_str = cmd.split()
        sid = int(sid_str)
        delta_deg = float(deg_str)

        if sid not in positions:
            print("Invalid servo ID (use 1–6)")
            continue

        delta_ticks = deg_to_ticks(abs(delta_deg))
        if delta_deg < 0:
            delta_ticks *= -1

        new_pos     = positions[sid] + delta_ticks
        target_deg  = ticks_to_deg(new_pos)

        # Check and clamp to software limits
        allowed, clamped_deg = check_limits(sid, target_deg)
        new_pos = int(clamped_deg * 4095 / 360)
        new_pos = max(0, min(4095, new_pos))

        if write_pos(sid, new_pos):
            positions[sid] = new_pos
            print(f"Servo {sid} → {new_pos} ticks ({ticks_to_deg(new_pos):.1f}°)")
        else:
            print(f"Servo {sid}: write failed (check connection and power)")

    except ValueError:
        print("Invalid input. Use: <id> <degrees>")

# Disable torque on exit
for sid in SERVO_IDS:
    packetHandler.write1ByteTxRx(portHandler, sid, ADDR_TORQUE_ENABLE, 0)
portHandler.closePort()
print("Done.")
