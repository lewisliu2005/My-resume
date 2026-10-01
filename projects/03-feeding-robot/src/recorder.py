import serial
import time
import json
import sys
from datetime import datetime
from collections import deque

PORT      = 'COM23'
BAUDRATE  = 1000000
DURATION  = 30
READ_WAIT = 0.008   # 每次讀取等待時間（秒），調低可提升 FPS

ADDR_TORQUE_ENABLE    = 0x28
ADDR_PRESENT_POSITION = 0x38
INST_WRITE = 0x03
INST_READ  = 0x02

# 減速馬達：讀取 0-4095 循環，寫入可為任意整數（含負值）
# 正常馬達：讀寫均為 0-4095
MOTOR_CONFIG = {
    1: {'gearbox': True,  'max_steps': 12258},
    2: {'gearbox': True,  'max_steps': 12258},
    3: {'gearbox': True,  'max_steps': 12258},
    4: {'gearbox': False, 'max_steps': 4095},
    5: {'gearbox': False, 'max_steps': 4095},
    6: {'gearbox': False, 'max_steps': 4095},
}
INIT_STEPS     = 2048
WRAP_THRESHOLD = 2048   # 4096 的一半，用於判斷是否跨圈


# ─── 圈數追蹤（僅減速馬達使用）────────────────────────────────

class RevolutionTracker:
    """
    追蹤減速馬達的絕對位置。
    PRESENT_POSITION 只回傳 0-4095，跨圈時歸零（或從 0 往下到 4095）。
    用相鄰兩幀的差值偵測跨圈事件，累計絕對步數。
    初始圈數永遠為 0，初始 raw 讀值即為初始絕對步數。
    """
    def __init__(self, motor_ids):
        self._revs     = {mid: 0    for mid in motor_ids}
        self._last_raw = {mid: None for mid in motor_ids}

    def update(self, motor_id, raw):
        if raw is None:
            return None
        last = self._last_raw[motor_id]
        if last is not None:
            delta = raw - last
            if delta < -WRAP_THRESHOLD:    # 例：3900 → 100，正向跨圈
                self._revs[motor_id] += 1
            elif delta > WRAP_THRESHOLD:   # 例：100 → 3900，反向跨圈
                self._revs[motor_id] -= 1
        self._last_raw[motor_id] = raw
        return self._revs[motor_id] * 4096 + raw

    def revolution(self, motor_id):
        return self._revs[motor_id]


# ─── 低階通訊 ────────────────────────────────────────────────

def _checksum(motor_id, length, instruction, params):
    return (~(motor_id + length + instruction + sum(params))) & 0xFF


def send_packet(ser, motor_id, instruction, params):
    length = len(params) + 2
    cs = _checksum(motor_id, length, instruction, params)
    ser.reset_input_buffer()
    ser.write(bytearray([0xFF, 0xFF, motor_id, length, instruction] + params + [cs]))
    ser.flush()


def read_raw(ser, motor_id):
    """回傳原始 0-4095，讀取失敗回傳 None"""
    send_packet(ser, motor_id, INST_READ, [ADDR_PRESENT_POSITION, 2])
    time.sleep(READ_WAIT)
    if ser.in_waiting >= 8:
        r = list(ser.read(8))
        if r[0] == 0xFF and r[1] == 0xFF and r[2] == motor_id:
            return (r[6] << 8) | r[5]
    return None


def set_torque(ser, motor_id, enable):
    send_packet(ser, motor_id, INST_WRITE, [ADDR_TORQUE_ENABLE, 1 if enable else 0])
    time.sleep(0.02)


def steps_to_angle(absolute_steps, max_steps):
    return round((absolute_steps / max_steps) * 360.0, 2)


# ─── 主程式 ──────────────────────────────────────────────────

def record():
    print(f"正在開啟序列埠 {PORT} ...")
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=0.1)
    except serial.SerialException as e:
        print(f"序列埠開啟失敗：{e}")
        sys.exit(1)

    print("關閉所有馬達扭矩（可手動移動手臂）...")
    for mid in MOTOR_CONFIG:
        set_torque(ser, mid, False)

    input("按下 Enter 開始錄製 10 秒...")
    print("開始錄製！")

    gearbox_ids = [mid for mid, cfg in MOTOR_CONFIG.items() if cfg['gearbox']]
    tracker = RevolutionTracker(gearbox_ids)

    frames     = []
    fps_window = deque(maxlen=20)   # 用最近 20 幀計算滾動 FPS
    start      = time.time()

    while True:
        frame_start = time.time()
        elapsed = frame_start - start
        if elapsed >= DURATION:
            break

        frame = {'time': round(elapsed, 4), 'motors': {}}

        for mid, cfg in MOTOR_CONFIG.items():
            raw = read_raw(ser, mid)

            if cfg['gearbox']:
                absolute = tracker.update(mid, raw)
                revolution = tracker.revolution(mid)
                angle = steps_to_angle(absolute, cfg['max_steps']) if absolute is not None else None
                frame['motors'][str(mid)] = {
                    'type':       'gearbox',
                    'raw_steps':  raw,
                    'steps':      absolute,
                    'revolution': revolution,
                    'angle':      angle,
                }
            else:
                angle = steps_to_angle(raw, cfg['max_steps']) if raw is not None else None
                frame['motors'][str(mid)] = {
                    'type':  'direct',
                    'steps': raw,
                    'angle': angle,
                }

        frames.append(frame)

        # 滾動 FPS：用視窗內第一幀到最後一幀的時間差計算
        fps_window.append(time.time())
        if len(fps_window) >= 2:
            fps = (len(fps_window) - 1) / (fps_window[-1] - fps_window[0])
        else:
            fps = 0.0

        remaining = DURATION - (time.time() - start)
        print(f"\r剩餘 {remaining:.1f} 秒  |  幀數: {len(frames)}  |  FPS: {fps:.1f}", end='', flush=True)

    print(f"\n錄製完成，共 {len(frames)} 幀，取樣率約 {len(frames) / DURATION:.1f} Hz")
    ser.close()

    output = {
        'metadata': {
            'recorded_at':    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'duration_sec':   DURATION,
            'total_frames':   len(frames),
            'sample_rate_hz': round(len(frames) / DURATION, 2),
            'motor_config': {
                str(mid): {
                    'gearbox':    cfg['gearbox'],
                    'max_steps':  cfg['max_steps'],
                    'init_steps': INIT_STEPS,
                }
                for mid, cfg in MOTOR_CONFIG.items()
            },
        },
        'frames': frames,
    }

    filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"已儲存：{filename}")


if __name__ == '__main__':
    record()
