import serial
import time

PORT     = 'COM23'
BAUDRATE = 1000000
MOTOR_ID = 1

ADDR_PRESENT_POSITION = 0x38
INST_READ = 0x02


def send_packet(ser, motor_id, instruction, params):
    length = len(params) + 2
    cs = (~(motor_id + length + instruction + sum(params))) & 0xFF
    ser.reset_input_buffer()
    ser.write(bytearray([0xFF, 0xFF, motor_id, length, instruction] + params + [cs]))
    ser.flush()


def read_raw(ser, motor_id):
    send_packet(ser, motor_id, INST_READ, [ADDR_PRESENT_POSITION, 2])
    time.sleep(0.015)
    if ser.in_waiting >= 8:
        r = list(ser.read(8))
        if r[0] == 0xFF and r[1] == 0xFF and r[2] == motor_id:
            return (r[6] << 8) | r[5]
    return None


ser = serial.Serial(PORT, BAUDRATE, timeout=0.1)
print(f"已連接 {PORT}，扭矩未上電，請手動轉動馬達。Ctrl+C 離開。\n")

try:
    while True:
        raw = read_raw(ser, MOTOR_ID)
        if raw is not None:
            print(f"\r馬達 {MOTOR_ID}  原始步數: {raw:5d}", end='', flush=True)
        else:
            print(f"\r馬達 {MOTOR_ID}  讀取失敗", end='', flush=True)
except KeyboardInterrupt:
    print("\n結束。")
finally:
    ser.close()
