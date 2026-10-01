# ① 虛擬重機械考照測驗
**Virtual Excavator Licensing Simulator**

> 國立虎尾科技大學 資訊工程系 · 行動運算與人機介面實驗室　|　2022/12 – 2023/12，後續延伸為 115 年度國科會大專學生研究計畫

[← 回到首頁](../../README.md)

<p align="center">
  <img src="images/operation.jpg" width="48%" alt="實際操作">
  <img src="images/vr-operation.jpg" width="48%" alt="VR 操作">
</p>

## 🏆 成果

| 成果 | 說明 |
|:---|:---|
| 🥇 2025 第30屆 大專校院資訊應用服務創新競賽 | **資訊應用組 第一名** |
| 🥇 2025 第30屆 大專校院資訊應用服務創新競賽 | **勞工保障及保險智慧服務組 第一名** |
| 🔬 115 年度 國科會大專學生研究計畫 | 運用虛擬模擬技術建置挖土機操作考照系統並分析其訓練成效（115-2813-C-150-018-E，2026/07 – 2027/02，學生主持人） |
| 📡 2025 行動通訊實務競賽 | 入圍（團隊「掘掘動心」） |
| 🏡 2024 智在家鄉 聯發科技數位社會創新競賽 | 入圍（團隊「挖到你心坎」） |

## 💡 動機

根據勞動部統計，挖掘機證照合格率從 **109 年的 81%** 一路降到 **112 年的 50%**。考生缺乏實機練習的場地與機具、補習費用高昂，初學者直接上實機又有工安風險。

<p align="center"><img src="images/pass-rate.jpg" width="70%" alt="歷年挖土機證照合格率"></p>

我們想做的是：**在室內就能反覆練習、又有臨場感的考照模擬器**，降低學習門檻，也吸引更多人投入營建機械領域。

## 🧩 系統架構

```mermaid
flowchart LR
    subgraph HW["自製操作台（硬體）"]
        J["二軸搖桿 ×2<br/>大臂 / 小臂 / 挖斗 / 迴轉"]
        P["腳踏板<br/>可變電阻 + 3D 列印件"]
        E["ESP32<br/>（整合於自製 PCB）"]
        J --> E
        P --> E
    end
    E -- "Wi-Fi · UDP" --> U
    subgraph SW["電腦端（Unity）"]
        U["UDP 接收<br/>C# System.Net.Sockets"]
        PH["物理引擎<br/>Rigidbody / Collider / Joints"]
        UI["考場與 UI<br/>Menu · 三種測驗 · 計時 · 違規計數"]
        U --> PH --> UI
    end
    UI --> VR["螢幕 / VR 頭盔"]
```

<p align="center"><img src="images/architecture.jpg" width="70%" alt="系統架構圖"></p>

## 🔧 硬體設計

- **操作台框架**：以鋁擠型為主體，搭配 3D 列印的搖桿座連接件，可快速拆裝。
- **操控輸入**：二軸搖桿控制大臂、小臂、挖斗與迴轉；挖掘機的行走方式特殊，因此用 **可變電阻 + 自行繪製的 3D 列印件** 做出擬真腳踏板。
- **自製 PCB**：初期大量杜邦線導致接觸不良、訊號不穩，重新設計專屬 PCB 把 ESP32 直接整合上板並改用插拔式接頭，再用 SketchUp 設計外殼收納，大幅提升穩定度與耐用度。

<p align="center">
  <img src="images/hardware-overview.jpg" width="32%" alt="操作台">
  <img src="images/pedal.jpg" width="32%" alt="腳踏板">
  <img src="images/joystick-mount-cad.jpg" width="24%" alt="搖桿座 3D 模型">
</p>
<p align="center">
  <img src="images/pcb-layout.jpg" width="28%" alt="PCB Layout">
  <img src="images/pcb-enclosure.jpg" width="36%" alt="PCB 與外殼">
  <img src="images/frame-cad.jpg" width="26%" alt="框架 3D 圖">
</p>

## 🎮 軟體設計

- **3D 建模**：Blender 建立挖掘機模型、SketchUp 依勞動部術科測試參考資料建立 1:1 考場。
- **物理模擬**：Rigidbody 賦予質量、重力與阻力；Collider 判定挖斗與地面接觸；Hinge / Configurable Joint 建立大臂、小臂、挖斗連動與作動限制。
- **即時通訊**：Unity 端以 UDP 接收 ESP32 封包，把搖桿操作即時轉為機具動作。
- **使用者介面**：
  - **Menu**：即時顯示 Wi-Fi 連線狀態，確認軟硬體通訊正常
  - **Select Mode**：三種模擬考場（First / Second / Third test）
  - **測驗畫面**：5 分鐘倒數計時、即時記錄 **違規次數**，可 Reset 重來或返回選單
  - 支援 **VR** 沉浸式操作

<p align="center">
  <img src="images/blender-model.jpg" width="48%" alt="Blender 模型">
  <img src="images/sketchup-site.jpg" width="48%" alt="SketchUp 考場">
</p>
<p align="center">
  <img src="images/unity-excavator.jpg" width="48%" alt="Unity 挖掘機">
  <img src="images/unity-site.jpg" width="40%" alt="Unity 考場">
</p>
<p align="center">
  <img src="images/ui-menu.jpg" width="32%" alt="Menu">
  <img src="images/ui-select.jpg" width="32%" alt="Select Mode">
  <img src="images/ui-test1.jpg" width="32%" alt="First test">
</p>

## 🌱 推廣與回饋

作品曾在多個展場讓 **沒有挖掘機駕駛經驗的一般民眾** 與國小學童實際試玩。比賽中也得到評審的改良建議，在教授與學長指導下逐步改良至第二代。

## 🛠️ 技術關鍵字

`Unity` `C#` `ESP32` `Wi-Fi` `UDP` `Blender` `SketchUp` `PCB 設計` `3D 列印` `鋁擠型機構` `VR` `物理引擎`
