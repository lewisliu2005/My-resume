#!/usr/bin/env python3
"""
STS3215 ROS 驅動
- 持續讀取馬達位置並發布到 /joint_states
- 訂閱 /execute_trajectory/goal，依 MoveIt 規劃的離散路徑點驅動馬達

馬達區分：
  有減速機 (joint1-3)：3:1 減速，max_steps=12258，需圈數追蹤
  無減速機 (joint4-5)：直接驅動，max_steps=4096

使用方式:
  rosrun <your_ros_package> sts3215_moveit_driver.py _port:=/dev/ttyUSB0
"""

import math
import time
import threading
import rospy
import serial
from sensor_msgs.msg import JointState
from moveit_msgs.msg import ExecuteTrajectoryActionGoal

# ── 馬達對應關節設定 ─────────────────────────────────────────────
# (joint_name, motor_id, max_steps, zero_raw, direction, gearbox)
# gearbox=True  → 3:1 減速機，max_steps ≈ 4096 × 3 = 12258（多圈追蹤）
# gearbox=False → 無減速機，  max_steps = 4096（單圈 0-4095）
JOINTS = [
    ('joint1', 1, 12258, 2048, -1, True),
    ('joint2', 2, 12258, 2048, -1, True),
    ('joint3', 3, 12258, 2048, +1, True),
    ('joint4', 4, 4096,  2048, -1, False),
    ('joint5', 5, 4096,  2048, +1, False),
]

JOINT_CONFIG = {name: (mid, max_steps, zero_raw, direction, gearbox)
                for (name, mid, max_steps, zero_raw, direction, gearbox) in JOINTS}
MOTOR_IDS    = [mid for (_, mid, _, _, _, _) in JOINTS]

ADDR_TORQUE_ENABLE    = 0x28
ADDR_ACC              = 0x29
ADDR_GOAL_POSITION    = 0x2A
ADDR_PRESENT_POSITION = 0x38
ADDR_MOVING           = 0x42
INST_READ  = 0x02
INST_WRITE = 0x03

WRAP_THRESHOLD = 2048   # 超過此跳變視為跨圈
ARRIVE_TIMEOUT = 8.0    # 等待到位逾時（秒）
PLAYBACK_ACC   = 50     # 執行軌跡時的加速度
INIT_STEPS     = 2048   # 初始（零點）位置


# ── 圈數追蹤器（僅有減速機的馬達需要）──────────────────────────
class RevolutionTracker:
    """將 0-4095 的原始值擴展為多圈絕對位置。"""

    def __init__(self, motor_ids):
        self._revs     = {mid: 0    for mid in motor_ids}
        self._last_raw = {mid: None for mid in motor_ids}

    def update(self, motor_id, raw):
        if raw is None:
            return None
        last = self._last_raw[motor_id]
        if last is not None:
            delta = raw - last
            if delta < -WRAP_THRESHOLD:
                self._revs[motor_id] += 1
            elif delta > WRAP_THRESHOLD:
                self._revs[motor_id] -= 1
        self._last_raw[motor_id] = raw
        return self._revs[motor_id] * 4096 + raw


# ── 低階通訊（需持 lock）────────────────────────────────────────
def _send(ser, motor_id, instruction, params):
    length = len(params) + 2
    cs = (~(motor_id + length + instruction + sum(params))) & 0xFF
    ser.reset_input_buffer()
    ser.write(bytearray([0xFF, 0xFF, motor_id, length, instruction] + params + [cs]))
    ser.flush()


def read_raw(ser, lock, motor_id):
    with lock:
        _send(ser, motor_id, INST_READ, [ADDR_PRESENT_POSITION, 2])
        time.sleep(0.012)
        r = list(ser.read(ser.in_waiting)) if ser.in_waiting >= 8 else []
    if len(r) >= 8 and r[0] == 0xFF and r[1] == 0xFF and r[2] == motor_id:
        return (r[6] << 8) | r[5]
    return None


def read_moving(ser, lock, motor_id):
    with lock:
        _send(ser, motor_id, INST_READ, [ADDR_MOVING, 1])
        time.sleep(0.012)
        r = list(ser.read(ser.in_waiting)) if ser.in_waiting >= 7 else []
    if len(r) >= 7 and r[0] == 0xFF and r[1] == 0xFF and r[2] == motor_id:
        return r[5]
    return None


def set_torque(ser, lock, motor_id, enable):
    with lock:
        _send(ser, motor_id, INST_WRITE, [ADDR_TORQUE_ENABLE, 1 if enable else 0])
    time.sleep(0.02)


def encode_goal(steps):
    """STS3215 位置指令：負數用 bit15=1 + 補數表示。"""
    if steps < 0:
        return ((-steps) & 0x7FFF) | 0x8000
    return steps & 0x7FFF


def set_position(ser, lock, motor_id, steps):
    """送出目標位置（單次，不寫 ACC/SPEED，用於關機回原點）。"""
    encoded = encode_goal(steps)
    with lock:
        _send(ser, motor_id, INST_WRITE,
              [ADDR_GOAL_POSITION, encoded & 0xFF, (encoded >> 8) & 0xFF])
    time.sleep(0.01)


def set_position_stream(ser, lock, motor_id, steps):
    """連續寫入 ACC + GOAL_POSITION + GOAL_TIME + GOAL_SPEED（GOAL_TIME=0 即最大速度）。"""
    encoded = encode_goal(steps)
    with lock:
        _send(ser, motor_id, INST_WRITE, [
            ADDR_ACC,  PLAYBACK_ACC,
            encoded & 0xFF, (encoded >> 8) & 0xFF,  # GOAL_POSITION
            0, 0,                                    # GOAL_TIME = 0
            0, 0,                                    # GOAL_SPEED = 0
        ])


# ── 角度轉換 ─────────────────────────────────────────────────────
def raw_to_rad(absolute, max_steps, zero_raw, direction):
    return (absolute - zero_raw) / max_steps * 2.0 * math.pi * direction


def rad_to_steps(rad, max_steps, zero_raw, direction):
    """
    弧度 → 馬達步數。
    有減速機：max_steps=12258，結果可超出 0-4095 範圍（多圈）。
    無減速機：max_steps=4096，結果在 0-4095 範圍內。
    """
    return int(rad * direction / (2.0 * math.pi) * max_steps + zero_raw)


# ── 關機序列 ─────────────────────────────────────────────────────
def return_to_home(ser, lock):
    """啟動扭矩 → 回歸初始位置 → 停止激磁。"""
    rospy.loginfo("關閉中：啟動扭矩...")
    for mid in MOTOR_IDS:
        set_torque(ser, lock, mid, True)
    time.sleep(0.3)

    rospy.loginfo(f"關閉中：移動至初始位置（{INIT_STEPS} steps）...")
    for mid in MOTOR_IDS:
        set_position(ser, lock, mid, INIT_STEPS)
    time.sleep(0.1)

    deadline = time.time() + ARRIVE_TIMEOUT
    while time.time() < deadline:
        if all(read_moving(ser, lock, mid) == 0 for mid in MOTOR_IDS):
            break
        time.sleep(0.05)
    else:
        rospy.logwarn("回原點等待逾時。")

    for mid in MOTOR_IDS:
        set_torque(ser, lock, mid, False)
    time.sleep(0.2)
    rospy.loginfo("已回到初始位置，激磁已關閉。")


# ── 軌跡執行器 ───────────────────────────────────────────────────
class TrajectoryRunner:
    """非同步執行 /execute_trajectory/goal 中的離散路徑點。"""

    def __init__(self, ser, lock):
        self.ser   = ser
        self.lock  = lock
        self._busy = threading.Lock()

    def on_goal(self, msg):
        """訂閱回呼：非阻塞地提交新軌跡，若上一條尚未完成則捨棄。"""
        if not self._busy.acquire(blocking=False):
            rospy.logwarn("上一條軌跡尚未完成，忽略新 goal")
            return
        t = threading.Thread(target=self._execute, args=(msg,), daemon=True)
        t.start()

    def _execute(self, msg):
        try:
            jt          = msg.goal.trajectory.joint_trajectory
            joint_names = jt.joint_names
            points      = jt.points

            if not points:
                rospy.logwarn("收到空軌跡，忽略")
                return

            rospy.loginfo(f"開始執行軌跡：{len(points)} 個路徑點  關節={joint_names}")

            # 開啟扭矩
            for mid in MOTOR_IDS:
                set_torque(self.ser, self.lock, mid, True)
            time.sleep(0.1)

            start = rospy.Time.now()
            for idx, point in enumerate(points):
                wait = (start + point.time_from_start - rospy.Time.now()).to_sec()
                if wait > 0:
                    rospy.sleep(wait)

                for name, rad in zip(joint_names, point.positions):
                    if name not in JOINT_CONFIG:
                        continue
                    mid, max_steps, zero_raw, direction, gearbox = JOINT_CONFIG[name]
                    steps = rad_to_steps(rad, max_steps, zero_raw, direction)
                    set_position_stream(self.ser, self.lock, mid, steps)
                    rospy.logdebug(
                        f"  [{idx}] {name}(id={mid},"
                        f"{'減速' if gearbox else '直驅'}) "
                        f"rad={rad:.3f} → steps={steps}"
                    )

            # 等待最後一個點到位
            active_ids = [JOINT_CONFIG[n][0] for n in joint_names if n in JOINT_CONFIG]
            deadline   = time.time() + ARRIVE_TIMEOUT
            while time.time() < deadline:
                if all(read_moving(self.ser, self.lock, mid) == 0 for mid in active_ids):
                    break
                time.sleep(0.05)
            else:
                rospy.logwarn("等待到位逾時")

            rospy.loginfo("軌跡執行完成")

        except Exception as e:
            rospy.logerr(f"軌跡執行錯誤：{e}")
        finally:
            self._busy.release()


# ── 主程式 ───────────────────────────────────────────────────────
def main():
    rospy.init_node('sts3215_driver')

    port     = rospy.get_param('~port',     '/dev/ttyACM0')
    baudrate = rospy.get_param('~baudrate', 1000000)
    rate_hz  = rospy.get_param('~rate',     20)

    pub = rospy.Publisher('/joint_states', JointState, queue_size=10)

    rospy.loginfo(f"開啟序列埠 {port} @ {baudrate} bps ...")
    try:
        ser = serial.Serial(port, baudrate, timeout=0.1)
    except serial.SerialException as e:
        rospy.logerr(f"序列埠開啟失敗: {e}")
        return

    lock   = threading.Lock()
    rospy.on_shutdown(lambda: return_to_home(ser, lock))
    runner = TrajectoryRunner(ser, lock)

    rospy.Subscriber('/execute_trajectory/goal', ExecuteTrajectoryActionGoal, runner.on_goal)
    rospy.loginfo("已訂閱 /execute_trajectory/goal")

    # 有減速機的馬達需要圈數追蹤（讀取時用絕對位置換算弧度）
    gearbox_ids = [mid for (_, mid, _, _, _, gb) in JOINTS if gb]
    tracker     = RevolutionTracker(gearbox_ids)
    last_pos    = [0.0] * len(JOINTS)

    rospy.loginfo("驅動啟動（扭矩未開啟，可手動移動）")

    rate = rospy.Rate(rate_hz)
    while not rospy.is_shutdown():
        positions = []
        for i, (_, motor_id, max_steps, zero_raw, direction, gearbox) in enumerate(JOINTS):
            raw      = read_raw(ser, lock, motor_id)
            # 有減速機：用多圈絕對值；無減速機：直接用原始值
            absolute = tracker.update(motor_id, raw) if gearbox else raw

            if absolute is not None:
                rad = raw_to_rad(absolute, max_steps, zero_raw, direction)
                last_pos[i] = rad
            else:
                rospy.logwarn_throttle(5.0, f"馬達 ID={motor_id} 讀取失敗，使用上次數值")
                rad = last_pos[i]
            positions.append(rad)

        js = JointState()
        js.header.stamp = rospy.Time.now()
        js.name         = [j[0] for j in JOINTS]
        js.position     = positions
        pub.publish(js)

        rate.sleep()

    ser.close()
    rospy.loginfo("序列埠已關閉。")


if __name__ == '__main__':
    main()
