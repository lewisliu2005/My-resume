<div align="center">

# 劉宗修 · Tsung-Hsiu Liu

**國立虎尾科技大學 資訊工程系**　|　行動運算與人機介面實驗室（指導教授：陳國益 教授）

嵌入式系統 × 機器人 × 虛擬實境 — 把軟體做進真實世界的硬體裡

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![C#](https://img.shields.io/badge/C%23-512BD4?logo=dotnet&logoColor=white)
![C/C++](https://img.shields.io/badge/C%2FC%2B%2B-00599C?logo=cplusplus&logoColor=white)
![Unity](https://img.shields.io/badge/Unity-000000?logo=unity&logoColor=white)
![ROS](https://img.shields.io/badge/ROS-22314E?logo=ros&logoColor=white)
![ESP32](https://img.shields.io/badge/ESP32-E7352C?logo=espressif&logoColor=white)
![Raspberry Pi RP2350](https://img.shields.io/badge/RP2350-A22846?logo=raspberrypi&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLO-00FFFF?logo=yolo&logoColor=black)
![Blender](https://img.shields.io/badge/Blender-F5792A?logo=blender&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black)

</div>

---

## 📌 一頁看懂

| 🏆 全國競賽獲獎 / 入圍 | 🥇 全國第一名 | 🔬 國科會大專生計畫 | 🛠️ 專題實作 | 📜 證照 |
|:---:|:---:|:---:|:---:|:---:|
| **15** 項 | **2** 座（雙料冠軍） | **1** 件（學生主持人） | **3** 項 | **6** 張 |

- 🥇 **2025 第30屆 大專校院資訊應用服務創新競賽（InnoServe）雙料冠軍** — 以「虛擬重機械考照測驗」同時拿下 *資訊應用組* 與 *勞工保障及保險智慧服務組* 第一名
- 🔬 **115 年度 國科會大專學生研究計畫**（115-2813-C-150-018-E）— 運用虛擬模擬技術建置挖土機操作考照系統並分析其訓練成效
- 🏅 **第25屆 旺宏金矽獎 半導體設計與應用大賽 優勝獎** — 仿生機器魚用於池釣訓練
- 🏅 **2026 教育部 跨域智慧晶片設計應用創新專題實作競賽 佳作**
- 📚 112 學年度第一學期 **書卷獎**；微積分會考全年級第 7 名

---

## 🛠️ 專題作品

<table>
<tr>
<td width="34%" valign="top">
<a href="projects/01-excavator-simulator/"><img src="projects/01-excavator-simulator/images/operation.jpg" alt="虛擬重機械考照測驗"></a>
</td>
<td valign="top">

### [① 虛擬重機械考照測驗](projects/01-excavator-simulator/)
**Virtual Excavator Licensing Simulator**　·　2022/12 – 2023/12（持續延伸為國科會計畫）

挖掘機證照合格率從 109 年的 81% 降到 112 年的 50%。我們用 **Unity + ESP32** 打造室內可練習的高擬真挖掘機考照模擬器：自製鋁擠型操作台、3D 列印搖桿座與腳踏板、自行設計 PCB，透過 **Wi-Fi UDP** 即時驅動 Unity 物理引擎中的虛擬挖掘機，並依勞動部術科考場建置三種測驗關卡、支援 VR。

`Unity` `C#` `ESP32` `UDP` `Blender` `SketchUp` `PCB 設計` `3D 列印` `VR`

🥇 InnoServe 2025 資訊應用組 第一名　🥇 勞工保障及保險智慧服務組 第一名　🔬 國科會大專生計畫

</td>
</tr>
<tr>
<td width="34%" valign="top">
<a href="projects/02-bionic-robotic-fish/"><img src="projects/02-bionic-robotic-fish/images/pool-fishing.jpg" alt="仿生機器魚"></a>
</td>
<td valign="top">

### [② 仿生機器魚](projects/02-bionic-robotic-fish/)
**Bionic Robotic Fish for Pond Fishing**　·　2024/02 – 2025/11

模擬真實魚類行為的室內釣魚機器魚。**RP2350** 主控 + 433 MHz 水下無線通訊 + 九軸 IMU，上位機以 **YOLOv11（mAP@50 = 99.5%）** 定位機器魚、單應性矩陣轉換座標，再由 **ROS + PID + 狀態機** 完成巡游與追餌。

**我的負責：** 串口伺服馬達控制與 **半雙工通訊驅動電路設計**（SN74LVC1G125/126 將 UART RX/TX 合併為單線半雙工）。

`RP2350` `ROS Noetic` `YOLOv11` `PID` `SX1278 433MHz` `PCB 設計`

🏅 旺宏金矽獎 優勝　🏅 InnoServe 2025 佳作

</td>
</tr>
<tr>
<td width="34%" valign="top">
<a href="projects/03-feeding-robot/"><img src="projects/03-feeding-robot/images/arm.jpg" alt="餵飯機器人"></a>
</td>
<td valign="top">

### [③ 餵飯機器人](projects/03-feeding-robot/)　*（研發中，含完整原始碼）*
**Assistive Feeding Robot Arm**　·　2025/11 – 迄今

家母長年從事居家托育，餵食時段常無法同時照顧其他孩子 — 這是我做這個專題的起點。六軸機械手臂分兩階段：**示教錄製／回放** 完成固定的挖取動作；**YOLO 嘴部偵測 + 深度相機 + ROS MoveIt** 動態送食。我從零實作 Feetech SCS 協定驅動、多圈位置追蹤、負載過載緊急停止，以及 ROS 節點。

`Python` `pyserial` `RS-485` `ROS` `MoveIt` `RViz` `YOLO` `matplotlib`

📂 [查看原始碼](projects/03-feeding-robot/src/)

</td>
</tr>
</table>

---

## 🏆 競賽與榮譽

> 完整列表與獎狀請見 👉 [awards/](awards/)

| 時間 | 競賽 | 作品 | 名次 |
|:---|:---|:---|:---:|
| 2025/11 | 第30屆 大專校院資訊應用服務創新競賽 · 資訊應用組 | 虛擬重機械考照測驗 | 🥇 **第一名** |
| 2025/11 | 第30屆 大專校院資訊應用服務創新競賽 · 勞工保障及保險智慧服務組 | 虛擬重機械考照測驗 | 🥇 **第一名** |
| 2025/11 | 第30屆 大專校院資訊應用服務創新競賽 · 友達智慧場域與 ESG 應用組 | 代訓練模型之群養寵物飲水照護系統 | 🥈 **第二名** |
| 2024/11 | 第29屆 大專校院資訊應用服務創新競賽 · 資訊應用組 | 智慧生活中的 AI 交互式虛擬角色設計與應用 | 🥉 **第三名** |
| 2025/07 | 第25屆 旺宏金矽獎 半導體設計與應用大賽 · 應用組 | 仿生機器魚用於池釣訓練 | **優勝獎** |
| 2026/08 | 2026 教育部 跨域智慧晶片設計應用創新專題實作競賽 | — | 佳作 |
| 2025/11 | 第30屆 大專校院資訊應用服務創新競賽 · 資訊應用組 | 可以與人互動的仿生機器魚 | 佳作 |
| 2024/11 | 第29屆 大專校院資訊應用服務創新競賽 · 資訊應用組 | 智能排球教練：AI 即時發球姿勢檢測與學習系統 | 佳作 |
| 2025/12 | 2025 行動通訊實務競賽 · 智慧數位應用 | 掘掘動心（虛擬挖掘機） | 入圍 |
| 2025/11 | 2025 全國大專院校產學創新實作競賽 | AI VTuber 互動式系統 | 入圍 |
| 2024/10 | 2024 中華電信 5G 創新應用大賽 | 融合 AI 語音模型與 IoT 之虛擬助手 | 入圍 |
| 2024/07 | 2024 智在家鄉 聯發科技數位社會創新競賽 | 挖到你心坎 | 入圍 |
| 2025/04 | 第22屆 育秀盃創意獎 | — | 入圍 |
| 2026/04 | 第23屆 育秀盃創意獎 | — | 入圍 |
| 2024/02 | 112 學年度第一學期 資訊工程系 | — | 書卷獎 |

---

## 🧰 技術能力

| 領域 | 技術 |
|:---|:---|
| **程式語言** | Python、C#、C / C++（MCU 韌體） |
| **嵌入式 / 硬體** | ESP32、RP2350、Feetech STS / SC 串口伺服馬達、RS-485 / UART 半雙工、PCB 設計、IMU、433 MHz LoRa 模組 |
| **機器人** | ROS 1 (Noetic)、MoveIt、RViz、PID 控制、狀態機、示教錄製回放 |
| **電腦視覺 / AI** | YOLOv11、OpenCV、資料增強、單應性透視轉換 |
| **3D / 虛擬實境** | Unity（物理引擎、VR）、Blender、SketchUp、3D 列印 |
| **通訊 / 系統** | UDP Socket、Wi-Fi、Linux 系統管理 |

## 📜 證照

| 證照 | 級別 |
|:---|:---:|
| 電腦硬體裝修 技術士 | 乙級 / 丙級 |
| 室內配線 技術士 | 乙級 / 丙級 |
| 工業電子 技術士 | 丙級 |
| Linux System Administration | 專業級 |

## 🎓 學歷與經歷

- **國立虎尾科技大學 資訊工程系**（2023/09 – 迄今）— 大一上即加入行動運算與人機介面實驗室
- **國立大湖高級農工職業學校 電機科**（2020/09 – 2023/06）— 高三參加工科賽後開始對程式設計產生濃厚興趣
- **115 年度 國科會大專學生研究計畫** 學生主持人（2026/07 – 2027/02）
- **日本高知工科大學** 交流研習（2025/07）
- 第十四屆 數理科學營 研習（112 學年度）

---

## 🔭 研究興趣與讀書計畫

1. **嵌入式智慧影像分析** — 把 AI 影像辨識下放到邊緣裝置，研究模型輕量化與最佳化，讓服務型機器人在有限算力下仍能即時反應（正是餵飯機器人需要的能力）。
2. **影像辨識與機器學習** — 延續專題中使用的 YOLO、OpenCV，深入物件偵測與姿態估測。
3. **混合實境（MR）** — 從挖掘機 VR 模擬器延伸，探索虛擬與真實物件互動的訓練系統。

---

<div align="center">

🐙 [github.com/lewisliu2005](https://github.com/lewisliu2005)

</div>
