import serial
import time
import sys

class FeetechSTS:
    def __init__(self, port='COM23', baudrate=1000000, servo_id=1):
        self.servo_id = servo_id
        self.ser = None
        
        self.ADDR_TORQUE_ENABLE = 0x28
        self.ADDR_GOAL_POSITION = 0x2A
        self.ADDR_PRESENT_POSITION = 0x38
        
        self.INST_PING = 0x01
        self.INST_READ = 0x02
        self.INST_WRITE = 0x03

        print(f"🔌 正在連接序列埠 {port} (包率 {baudrate})...")
        try:
            self.ser = serial.Serial(port, baudrate, timeout=0.1)
        except serial.SerialException as e:
            print(f"❌ 序列埠開啟失敗！\n錯誤細節: {e}")
            sys.exit()

    def send_packet(self, instruction, parameters):
        if not self.ser: return
        self.ser.reset_input_buffer() 
        length = len(parameters) + 2 
        checksum_sum = self.servo_id + length + instruction + sum(parameters)
        checksum = (~checksum_sum) & 0xFF
        packet = [0xFF, 0xFF, self.servo_id, length, instruction] + parameters + [checksum]
        self.ser.write(bytearray(packet))
        self.ser.flush()

    def ping(self):
        self.send_packet(self.INST_PING, [])
        time.sleep(0.05)
        if self.ser.in_waiting >= 6:
            response = list(self.ser.read(6))
            if response[0] == 0xFF and response[1] == 0xFF and response[2] == self.servo_id:
                return response[4] == 0 
        return False

    def write_byte(self, address, value):
        self.send_packet(self.INST_WRITE, [address, value & 0xFF])

    def write_word(self, address, value):
        val_l = value & 0xFF
        val_h = (value >> 8) & 0xFF
        self.send_packet(self.INST_WRITE, [address, val_l, val_h])

    def read_word(self, address):
        self.send_packet(self.INST_READ, [address, 2])
        time.sleep(0.05)
        if self.ser and self.ser.in_waiting >= 8:
            response = list(self.ser.read(8))
            if response[0] == 0xFF and response[1] == 0xFF:
                val_l = response[5]
                val_h = response[6]
                return (val_h << 8) | val_l
        return None

    def enable_torque(self, enable=True):
        val = 1 if enable else 0
        self.write_byte(self.ADDR_TORQUE_ENABLE, val)
        print(f"-> 扭矩狀態已{'開啟 (鎖定)' if enable else '關閉 (放鬆)'}")

    def set_angle(self, target_output_angle):
        """
        將使用者期望的「減速機輸出軸角度 (0~360度)」
        轉換為「馬達內部數值 (0~12258)」並送出控制指令
        """
        # 1. 軟體極限保護：強制將輸入角度限制在 0 ~ 360 度之間
        # 這樣就絕對不會產生負數，解決了瘋狂倒轉的溢位問題！
        target_output_angle = max(0.0, min(360.0, float(target_output_angle)))
        
        # 2. 減速機轉換公式：
        # 當輸入 360 度時，對應內部數值 12258
        # 當輸入 180 度時，對應內部數值 6129
        internal_pos = int((target_output_angle / 360.0) * 12258)
        
        # 再次確保數值不會超過機構極限 (0 ~ 12258)
        internal_pos = max(0, min(12258, internal_pos))
            
        # 3. 發送指令 (因為必定是正數，直接發送即可)
        self.write_word(self.ADDR_GOAL_POSITION, internal_pos)
        
        return target_output_angle, internal_pos

    def get_position(self):
        pos = self.read_word(self.ADDR_PRESENT_POSITION)
        # 因為我們現在只在正數範圍 (0~12258) 內活動，
        # 就不需要去處理大於 32767 的負數轉換了
        return pos

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

# ================= 主程式執行區塊 =================
if __name__ == '__main__':
    print("\n=======================================")
    print(" ⚙️ 飛特 STS 舵機 (行星減速 3:1 專用版)")
    print("=======================================\n")

    servo = FeetechSTS(port='COM23', baudrate=1000000, servo_id=1)

    if servo.ping():
        print(f"✅ 成功與馬達 (ID: {servo.servo_id}) 建立通訊！\n")
    else:
        print(f"❌ 馬達無回應，請確認線路是否鬆動。")
        servo.close()
        sys.exit()

    try:
        servo.enable_torque(True)
        time.sleep(0.5)
        
        print("-" * 50)
        print("💡 機構限制：由於 3:1 減速機，內部數值對應為 0 ~ 12258")
        print("💡 保護機制：輸入角度已被嚴格限制在 0° ~ 360° 之間")
        
        while True:
            print("-" * 50)
            user_input = input("請輸入【輸出軸】目標角度 (0~360)，或輸入 'q' 離開: ")
            
            if user_input.lower() == 'q':
                break
                
            try:
                # 執行轉動
                safe_angle, internal_pos = servo.set_angle(user_input)
                
                # 如果使用者輸入負數或超過360，會被強制修正，這裡顯示修正後的值
                if float(user_input) != safe_angle:
                     print(f"⚠️ 觸發極限保護！已將角度修正為 {safe_angle}°")
                     
                print(f"🎯 執行轉動至: {safe_angle}° (馬達實際步數: {internal_pos})")
                
                # 給予轉動時間 (轉 12258 步比較久，給予 1.5 秒等待)
                time.sleep(1.5) 
                
                # 讀取結果
                current_pos = servo.get_position()
                if current_pos is not None:
                    # 反向推算回輸出軸角度
                    current_angle = round((current_pos / 12258.0) * 360.0, 1)
                    print(f"📍 實際抵達位置: 約 {current_angle}° (馬達步數: {current_pos})")
                else:
                    print("⚠️ 無法讀取回傳位置")
                    
            except ValueError:
                print("❌ 輸入錯誤！請輸入純數字 (例如: 90 或 180.5)")

    finally:
        print("\n=======================================")
        print("🛑 正在關閉系統...")
        servo.enable_torque(False)
        servo.close()
        print("✅ 程式安全結束。")
        print("=======================================")