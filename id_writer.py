import serial
import time

ser = serial.Serial('/dev/tty.usbmodem5AE60578161', 1000000, timeout=0.1)

def checksum(data):
    return (~sum(data) & 0xFF)

def write_register(servo_id, register, value):
    packet = [
        0xFF, 0xFF,
        servo_id,
        0x04,
        0x03,
        register,
        value
    ]
    packet.append(checksum(packet[2:]))
    ser.write(bytearray(packet))
    time.sleep(0.05)

def set_id(old_id, new_id):
    write_register(old_id, 55, 0)   # unlock EEPROM
    time.sleep(0.05)
    write_register(old_id, 5, new_id)  # write new ID
    print(f"Set ID {old_id} → {new_id}")

set_id(1, 6)

ser.close()
