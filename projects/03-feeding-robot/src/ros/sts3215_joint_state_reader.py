#!/usr/bin/env python3
"""
STS3215 ROS 驅動 — 被動讀取模式
讀取馬達目前位置，轉換成弧度後發布到 /joint_states。
扭矩不開啟，可手動移動馬達並在 RViz 看到對應動作。

使用方式:
  rosrun <your_ros_package> sts3215_joint_state_reader.py _port:=/dev/ttyUSB0

注意: 執行前請先停止 joint_state_publisher，否則兩者會互相干擾:
  rosnode kill /joint_state_publisher
"""

import math
import time
import rospy
import serial
from sensor_msgs.msg import JointState

# ── 馬達對應關節設定 ─────────────────────────────────────────────
# URDF 中有 joint1~joint5，馬達 ID 對應如下
JOINTS = [
    # (joint_name, motor_id, max_steps, zero_raw, direction)
    # direction: +1 = 正轉與 URDF 一致, -1 = 反向
    ('joint1', 1, 12258, 2048, -1),  # 有 3:1 減速機，方向相反
    ('joint2', 2, 12258, 2048, -1),
    ('joint3', 3, 12258, 2048, +1),
    ('joint4', 4, 4096,  2048, -1),  # 無減速機，方向相反
    ('joint5', 5, 4096,  2048, +1),  # 無減速機，方向相反
]

ADDR_PRESENT_POSITION = 0x38
INST_READ = 0x02


def send_packet(ser, motor_id, instruction, params):
    length = len(params) + 2
    cs = (~(motor_id + length + instruction + sum(params))) & 0xFF
    ser.reset_input_buffer()
    ser.write(bytearray([0xFF, 0xFF, motor_id, length, instruction] + params + [cs]))
    ser.flush()


def read_raw_position(ser, motor_id):
    """回傳馬達原始步數，失敗回傳 None。"""
    send_packet(ser, motor_id, INST_READ, [ADDR_PRESENT_POSITION, 2])
    time.sleep(0.012)
    if ser.in_waiting >= 8:
        r = list(ser.read(8))
        if r[0] == 0xFF and r[1] == 0xFF and r[2] == motor_id:
            return (r[6] << 8) | r[5]
    return None


def raw_to_rad(raw, max_steps, zero_raw):
    """將步數轉換為弧度，以 zero_raw 為零點。"""
    return (raw - zero_raw) / max_steps * 2.0 * math.pi


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

    rospy.loginfo("連接成功。開始讀取馬達位置（扭矩未開啟）...")

    # 記錄上一次成功讀到的角度，避免讀取失敗時跳回 0
    last_positions = [0.0] * len(JOINTS)

    rate = rospy.Rate(rate_hz)
    while not rospy.is_shutdown():
        positions = []
        for i, (_, motor_id, max_steps, zero_raw, direction) in enumerate(JOINTS):
            raw = read_raw_position(ser, motor_id)
            if raw is not None:
                rad = raw_to_rad(raw, max_steps, zero_raw) * direction
                last_positions[i] = rad
            else:
                rospy.logwarn_throttle(5.0, f"馬達 ID={motor_id} 讀取失敗，使用上次數值")
                rad = last_positions[i]
            positions.append(rad)

        js = JointState()
        js.header.stamp = rospy.Time.now()
        js.name     = [j[0] for j in JOINTS]
        js.position = positions
        pub.publish(js)

        rate.sleep()

    ser.close()
    rospy.loginfo("序列埠已關閉。")


if __name__ == '__main__':
    main()
