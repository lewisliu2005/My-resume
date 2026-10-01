"""
player.py — 播放錄製的機械手臂動作
使用方式: python player.py recording_YYYYMMDD_HHMMSS.json
"""
import serial
import time
import json
import sys
import glob
import os
import ctypes
import threading
import winsound
from collections import deque

PORT      = 'COM23'
BAUDRATE  = 1000000
READ_WAIT = 0.015
ARRIVE_TIMEOUT     = 8.0
POSITION_TOLERANCE = 25

# 播放速度比例：1.0 = 原速，1.2 = 慢 20%（給馬達更多跟上時間），0.8 = 快 20%
PLAYBACK_SCALE = 1.5

ADDR_TORQUE_ENABLE    = 0x28
ADDR_ACC              = 0x29
ADDR_GOAL_POSITION    = 0x2A
ADDR_PRESENT_POSITION = 0x38
ADDR_PRESENT_LOAD     = 0x3C  # 60：負載暫存器（有號 15-bit，±1000 對應 ±100% 負載）
ADDR_MOVING           = 0x42
INST_WRITE = 0x03
INST_READ  = 0x02

PLAYBACK_ACC = 50   # 播放時的加速度（0=最大，數值越小越平滑）

# ── 扭力保護 + 視覺化設定 ─────────────────────────────────────
LOAD_THRESHOLD = 2000  # 負載保護門檻（0–1000，建議先觀察正常值再設定）
VIZ_INTERVAL   = 5     # 每幾幀做一次讀取（負載檢查 + 畫面更新）

# 減速馬達：GOAL_POSITION 可寫入任意整數（含負值）
# 正常馬達：GOAL_POSITION 只寫 0-4095
MOTOR_CONFIG = {
    1: {'gearbox': True},
    2: {'gearbox': True},
    3: {'gearbox': True},
    4: {'gearbox': False},
    5: {'gearbox': False},
    6: {'gearbox': False},
}
MOTOR_IDS  = list(MOTOR_CONFIG.keys())
INIT_STEPS = 2048


# ─── 低階通訊 ────────────────────────────────────────────────

def _checksum(motor_id, length, instruction, params):
    return (~(motor_id + length + instruction + sum(params))) & 0xFF


def send_packet(ser, motor_id, instruction, params):
    length = len(params) + 2
    cs = _checksum(motor_id, length, instruction, params)
    ser.reset_input_buffer()
    ser.write(bytearray([0xFF, 0xFF, motor_id, length, instruction] + params + [cs]))
    ser.flush()


def read_byte(ser, motor_id, address):
    send_packet(ser, motor_id, INST_READ, [address, 1])
    time.sleep(READ_WAIT)
    if ser.in_waiting >= 7:
        r = list(ser.read(7))
        if r[0] == 0xFF and r[1] == 0xFF and r[2] == motor_id:
            return r[5]
    return None


def read_raw_position(ser, motor_id):
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


def _decode_signed(raw):
    """STS 有號格式：bit15 = 符號位，bit0-14 = 大小。"""
    return -(raw & 0x7FFF) if (raw & 0x8000) else raw


def read_motor_status(ser, motor_id):
    """
    一次讀取 6 bytes（位置 + 速度 + 負載），減少讀取次數。
    回傳 (pos: int|None, load: int|None)。
    封包結構：[FF FF ID LEN ERR POS_L POS_H SPD_L SPD_H LOAD_L LOAD_H CHKSUM]
    """
    send_packet(ser, motor_id, INST_READ, [ADDR_PRESENT_POSITION, 6])
    time.sleep(READ_WAIT)
    if ser.in_waiting >= 12:
        r = list(ser.read(12))
        if r[0] == 0xFF and r[1] == 0xFF and r[2] == motor_id:
            pos  = (r[6] << 8) | r[5]
            load = _decode_signed((r[10] << 8) | r[9])
            return pos, load
    return None, None


def read_all_status(ser):
    """讀取所有馬達的位置和負載，回傳 {motor_id: {'pos', 'load'}}。"""
    return {mid: dict(zip(('pos', 'load'), read_motor_status(ser, mid)))
            for mid in MOTOR_IDS}


def check_overload_from_status(status):
    """從已讀取的 status 中找出第一個超載馬達，回傳 (overloaded, mid, load)。"""
    for mid, s in status.items():
        load = s.get('load')
        if load is not None and abs(load) > LOAD_THRESHOLD:
            return True, mid, load
    return False, None, None


# ── ANSI 視覺化 ───────────────────────────────────────────────

_DASH_LINES = 11   # dashboard 固定佔用行數（用於游標上移重繪）


def _enable_ansi():
    """在 Windows 終端機啟用 ANSI/VT100 跳脫碼支援。"""
    if sys.platform == 'win32':
        try:
            kernel32 = ctypes.windll.kernel32
            # ENABLE_PROCESSED_OUTPUT|WRAP_AT_EOL|VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def _err_str(target, pos, is_gearbox):
    """計算目標與實際的步數誤差（考慮 gearbox 的 mod 4096 環繞）。"""
    if target is None or pos is None:
        return '  N/A '
    raw_target = target % 4096 if is_gearbox else target
    err = pos - raw_target
    if is_gearbox:
        if err >  2048: err -= 4096
        if err < -2048: err += 4096
    return f'{err:+6d}'


def print_dashboard(targets, status, frame_num, total, fps, first_call):
    """
    以 ANSI 跳脫碼就地更新馬達數據表格。
    targets : {mid_str: absolute_steps}
    status  : {mid: {'pos': int|None, 'load': int|None}}
    first_call : True 表示第一次印出，不需上移游標。
    """
    W = '─' * 54
    rows = [
        f'{W}',
        f'  ID │  目標(abs) │  實際(raw) │  誤差  │  負載  ',
        f'{W}',
    ]
    for mid in MOTOR_IDS:
        t   = targets.get(str(mid))
        s   = status.get(mid, {})
        pos = s.get('pos')
        ld  = s.get('load')
        is_gb = MOTOR_CONFIG[mid]['gearbox']

        t_s  = f'{t:10d}' if t   is not None else '      N/A '
        p_s  = f'{pos:10d}' if pos is not None else '      N/A '
        e_s  = _err_str(t, pos, is_gb)
        l_s  = f'{ld:+6d}' if ld  is not None else '  N/A '
        rows.append(f'  {mid}  │ {t_s} │ {p_s} │ {e_s} │ {l_s}  ')

    rows += [
        f'{W}',
        f'  幀：{frame_num}/{total}  FPS: {fps:.1f}  '
        f'速度: {PLAYBACK_SCALE}x  負載門檻: {LOAD_THRESHOLD}  ',
    ]

    if not first_call:
        sys.stdout.write(f'\x1b[{_DASH_LINES}A')   # 游標上移

    for row in rows:
        sys.stdout.write(f'\r{row}\x1b[0K\n')      # 覆寫並清除行尾殘留字元
    sys.stdout.flush()


def _alarm_beep():
    """警報音執行緒：三段高低交替急促蜂鳴。"""
    for _ in range(3):
        winsound.Beep(2500, 250)   # 高音
        winsound.Beep(1000, 250)   # 低音
    winsound.Beep(2500, 800)       # 最後一聲長音


def emergency_stop(ser, reason: str):
    """
    緊急停止：
      1. 立即切斷所有馬達扭矩（優先執行）
      2. 在背景執行緒發出警報音（不阻塞主流程）
    """
    for mid in MOTOR_IDS:
        set_torque(ser, mid, False)

    print(f"\n緊急停止：{reason}")
    print("所有馬達扭矩已切斷。")

    t = threading.Thread(target=_alarm_beep, daemon=True)
    t.start()
    t.join()   # 等警報播完再繼續（確保使用者聽到）


def encode_goal(steps):
    """
    將絕對步數編碼為 SCS 協定的 GOAL_POSITION 格式。
    STS 協定：正值直接使用，負值用 bit 15 當符號位。
      正值：0x0000 ~ 0x7FFF
      負值：-1 → 0x8001, -200 → 0x80C8, ...
    """
    if steps < 0:
        return ((-steps) & 0x7FFF) | 0x8000
    return steps & 0x7FFF


def set_position(ser, motor_id, steps):
    """精確定位用（含 10ms 延遲，給 move_and_wait 使用）"""
    encoded = encode_goal(steps)
    send_packet(ser, motor_id, INST_WRITE,
                [ADDR_GOAL_POSITION, encoded & 0xFF, (encoded >> 8) & 0xFF])
    time.sleep(0.01)


def set_position_stream(ser, motor_id, steps, acc=PLAYBACK_ACC):
    """
    串流播放用，無等待延遲。
    同時寫入 ACC + GOAL_POSITION + GOAL_TIME(0) + GOAL_SPEED(0)，
    對應 SDK 的 WritePosEx(id, position, speed=0, acc)。
    speed=0 表示最大速度，讓馬達在幀間連續移動不停頓。
    """
    encoded = encode_goal(steps)
    send_packet(ser, motor_id, INST_WRITE, [
        ADDR_ACC,
        acc,
        encoded & 0xFF, (encoded >> 8) & 0xFF,  # GOAL_POSITION
        0, 0,                                     # GOAL_TIME = 0
        0, 0,                                     # GOAL_SPEED = 0 (最大)
    ])


# ─── 到達判斷 ────────────────────────────────────────────────

def _arrived(raw_pos, absolute_target, is_gearbox, tolerance):
    """
    判斷馬達是否到達目標位置。

    減速馬達：
      PRESENT_POSITION 永遠是 0-4095（循環），
      需將絕對目標 mod 4096 後比較（Python 的 % 對負值也正確）。
      例：target=-196 → raw_target=3900；target=4196 → raw_target=100

    正常馬達：
      直接比較 raw_pos 與 target。
    """
    if raw_pos is None:
        return False

    if is_gearbox:
        raw_target = absolute_target % 4096      # Python % 對負數也正確
        diff = abs(raw_pos - raw_target)
        diff = min(diff, 4096 - diff)            # 取環繞後的較短距離
    else:
        diff = abs(raw_pos - absolute_target)

    return diff <= tolerance


def _all_stopped(ser, motor_ids):
    for mid in motor_ids:
        m = read_byte(ser, mid, ADDR_MOVING)
        if m is None or m != 0:
            return False
    return True


def move_and_wait(ser, targets: dict, label: str = "") -> bool:
    """
    targets: {motor_id (int): absolute_steps (int)}
    對減速馬達，steps 可為任意整數（含負值）。
    對正常馬達，steps 為 0-4095。
    """
    # 1. 送出所有目標位置
    for mid, steps in targets.items():
        set_position(ser, mid, steps)

    # 2. 給馬達啟動時間
    time.sleep(0.08)

    # 3. 等待全部 MOVING = 0
    deadline = time.time() + ARRIVE_TIMEOUT
    while time.time() < deadline:
        if _all_stopped(ser, list(targets.keys())):
            break
        time.sleep(0.05)
    else:
        print(f"\n  警告：{label} 逾時！各馬達狀態：")
        for mid, target in targets.items():
            raw = read_raw_position(ser, mid)
            print(f"    馬達 {mid}: 目標={target}  原始讀值={raw}")
        return False

    # 4. 確認位置
    all_ok = True
    for mid, target in targets.items():
        is_gearbox = MOTOR_CONFIG[mid]['gearbox']
        raw = read_raw_position(ser, mid)
        if not _arrived(raw, target, is_gearbox, POSITION_TOLERANCE):
            raw_target = target % 4096 if is_gearbox else target
            print(f"  警告：馬達 {mid} 未精確到位 "
                  f"(目標={target}, 對應原始={raw_target}, 實際原始={raw})")
            all_ok = False
    return all_ok


# ─── 主流程 ─────────────────────────────────────────────────

def select_json():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    files = sorted(glob.glob('recording_*.json'))
    if not files:
        print("找不到任何 recording_*.json，請先執行 recorder.py。")
        sys.exit(1)

    print("請選擇要播放的錄製檔：")
    for i, f in enumerate(files):
        print(f"  [{i+1}] {f}  ({os.path.getsize(f)//1024} KB)")

    while True:
        try:
            idx = int(input("輸入編號：")) - 1
            if 0 <= idx < len(files):
                return files[idx]
        except ValueError:
            pass
        print("請輸入有效編號。")


def play():
    json_path = select_json()

    print(f"\n載入錄製檔：{json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    frames = data['frames']
    total  = len(frames)
    print(f"共 {total} 幀，錄製時長 {data['metadata']['duration_sec']} 秒\n")

    print(f"開啟序列埠 {PORT} ...")
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=0.1)
    except serial.SerialException as e:
        print(f"序列埠開啟失敗：{e}")
        sys.exit(1)

    try:
        print("啟用所有馬達扭矩...")
        for mid in MOTOR_IDS:
            set_torque(ser, mid, True)
        time.sleep(0.3)

        # ── [1/3] 移動到初始位置 ──
        print("\n[1/3] 移動到初始位置 (steps=2048)...")
        init_targets = {mid: INIT_STEPS for mid in MOTOR_IDS}
        ok = move_and_wait(ser, init_targets, label="初始位置")
        if ok:
            print("      已到達初始位置。")
        input("\n按下 Enter 開始播放...")

        # ── [2/3] 串流播放 ──
        from visualizer import Visualizer

        recorded_hz = data['metadata'].get('sample_rate_hz', '?')
        print(f"\n[2/3] 開始播放 {total} 幀（錄製 FPS: {recorded_hz}，速度比例: {PLAYBACK_SCALE}x）")

        _enable_ansi()
        viz = Visualizer(MOTOR_IDS, MOTOR_CONFIG, load_threshold=LOAD_THRESHOLD)

        playback_start = time.time()
        fps_window     = deque(maxlen=20)
        viz_targets    = {}
        viz_status     = {mid: {'pos': None, 'load': None} for mid in MOTOR_IDS}
        viz_first      = True
        triggered      = False

        for i, frame in enumerate(frames):
            viz_targets = {mid_str: motor['steps']
                          for mid_str, motor in frame['motors'].items()
                          if motor['steps'] is not None}

            # ── 每 VIZ_INTERVAL 幀：讀取狀態、檢查負載、更新 dashboard + 圖表 ──
            if i % VIZ_INTERVAL == 0:
                viz_status = read_all_status(ser)
                overloaded, bad_mid, load_val = check_overload_from_status(viz_status)

                fps_now = ((len(fps_window) - 1) / (fps_window[-1] - fps_window[0])
                           if len(fps_window) >= 2 else 0.0)

                print_dashboard(viz_targets, viz_status, i + 1, total, fps_now, viz_first)
                viz.update(round(time.time() - playback_start, 3), viz_targets, viz_status)
                viz_first = False

                if overloaded:
                    emergency_stop(ser, f"馬達 {bad_mid} 負載過高（{load_val} > {LOAD_THRESHOLD}）")
                    triggered = True
                    break

            # 依照錄製時間戳決定送出時機
            target_send_time = playback_start + frame['time'] * PLAYBACK_SCALE
            wait = target_send_time - time.time()
            if wait > 0:
                time.sleep(wait)

            # 連續送出所有馬達指令
            for mid_str, motor in frame['motors'].items():
                if motor['steps'] is not None:
                    set_position_stream(ser, int(mid_str), motor['steps'])

            # 滾動 FPS
            fps_window.append(time.time())

        final_fps = ((len(fps_window) - 1) / (fps_window[-1] - fps_window[0])
                     if len(fps_window) >= 2 else 0.0)

        if triggered:
            print("\n已中止播放，所有馬達立即放鬆。")
        else:
            print_dashboard(viz_targets, viz_status, total, total, final_fps, viz_first)
            print("\n      播放完成。")

        viz.save()
        viz.close()

        # ── [3/3] 回到初始位置 ──
        print("\n[3/3] 回到初始位置...")
        ok = move_and_wait(ser, init_targets, label="回到初始位置")
        if ok:
            print("      已回到初始位置。")

    finally:
        print("\n關閉所有馬達扭矩...")
        for mid in MOTOR_IDS:
            set_torque(ser, mid, False)
        time.sleep(0.2)
        ser.close()
        print(f"已釋放序列埠 {PORT}，程式結束。")


if __name__ == '__main__':
    play()
