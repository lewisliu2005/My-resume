"""
visualizer.py — 馬達即時數據視覺化
被 player.py 引用；也可獨立執行讀取 recording_*.json 事後繪圖。
"""
import sys
import math
from datetime import datetime

import logging
import matplotlib
import matplotlib.font_manager as fm

# 只用系統實際存在的字體，避免 findfont 警告
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)

_CANDIDATES = ['Microsoft JhengHei', 'Microsoft YaHei',
               'DFKai-SB', 'Arial Unicode MS']
_available  = {f.name for f in fm.fontManager.ttflist}
_cjk_font   = next((f for f in _CANDIDATES if f in _available), None)

if _cjk_font:
    matplotlib.rcParams['font.family'] = [_cjk_font, 'DejaVu Sans']
else:
    # 沒有 CJK 字體，標題改用英文（在下方定義）
    matplotlib.rcParams['font.family'] = ['DejaVu Sans']

matplotlib.rcParams['axes.unicode_minus'] = False

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# 根據是否有 CJK 字體決定標題文字
_T = {
    'main':  '馬達即時數據'   if _cjk_font else 'Motor Live Data',
    'pos':   '位置追蹤　（虛線 = 目標，實線 = 實際）'
             if _cjk_font else 'Position  (dashed=target  solid=actual)',
    'pos_y': '步數 (0–4095 循環值)' if _cjk_font else 'Steps (0-4095 raw)',
    'load':  '負載監控'        if _cjk_font else 'Load Monitor',
    'load_y':'負載值'          if _cjk_font else 'Load',
    'time':  '時間 (秒)'       if _cjk_font else 'Time (s)',
    'thr':   '門檻'            if _cjk_font else 'Threshold',
}

# 每顆馬達對應顏色
MOTOR_COLORS = {
    1: '#e74c3c',   # 紅
    2: '#3498db',   # 藍
    3: '#2ecc71',   # 綠
    4: '#f39c12',   # 橙
    5: '#9b59b6',   # 紫
    6: '#1abc9c',   # 青
}


class Visualizer:
    """
    即時馬達數據圖表。

    版面：
      上半 — 位置追蹤（目標虛線、實際實線）
      下半 — 負載監控（含 ±LOAD_THRESHOLD 警戒線）
    """

    def __init__(self, motor_ids, motor_config, load_threshold=1000):
        self.motor_ids      = motor_ids
        self.motor_config   = motor_config
        self.load_threshold = load_threshold

        # 資料緩衝
        self.times = []
        self.buf   = {mid: {'target': [], 'actual': [], 'load': []}
                      for mid in motor_ids}

        self._build_figure()

    # ─── 初始化 ──────────────────────────────────────────────

    def _build_figure(self):
        plt.ion()
        self.fig = plt.figure(figsize=(14, 7))
        self.fig.suptitle(_T['main'], fontsize=13, fontweight='bold')

        gs = gridspec.GridSpec(2, 1, figure=self.fig, hspace=0.45)
        self.ax_pos  = self.fig.add_subplot(gs[0])
        self.ax_load = self.fig.add_subplot(gs[1])

        # 位置圖
        self.ax_pos.set_title(_T['pos'])
        self.ax_pos.set_xlabel(_T['time'])
        self.ax_pos.set_ylabel(_T['pos_y'])
        self.ax_pos.set_ylim(-50, 4150)
        self.ax_pos.grid(True, alpha=0.25)

        # 負載圖
        self.ax_load.set_title(_T['load'])
        self.ax_load.set_xlabel(_T['time'])
        self.ax_load.set_ylabel(_T['load_y'])
        self.ax_load.axhline(0, color='black', linewidth=0.6, zorder=0)
        self.ax_load.grid(True, alpha=0.25)

        # 警戒線
        for sign in (+1, -1):
            self.ax_load.axhline(sign * self.load_threshold,
                                 color='red', linewidth=1, linestyle='--',
                                 alpha=0.6, zorder=1)
        self.ax_load.text(0.01, self.load_threshold * 1.03,
                          f'{_T["thr"]} ±{self.load_threshold}',
                          transform=self.ax_load.get_yaxis_transform(),
                          color='red', fontsize=8)

        # 建立折線物件
        self._lines_t = {}   # target
        self._lines_a = {}   # actual
        self._lines_l = {}   # load

        for mid in self.motor_ids:
            c     = MOTOR_COLORS.get(mid, '#555555')
            label = f'M{mid}'
            self._lines_t[mid], = self.ax_pos.plot(
                [], [], '--', color=c, linewidth=1,   alpha=0.55, label=f'{label} 目標')
            self._lines_a[mid], = self.ax_pos.plot(
                [], [], '-',  color=c, linewidth=1.6, alpha=0.9,  label=f'{label} 實際')
            self._lines_l[mid], = self.ax_load.plot(
                [], [], '-',  color=c, linewidth=1.4, alpha=0.85, label=label)

        self.ax_pos.legend(loc='upper left',  fontsize=7,  ncol=4,
                           framealpha=0.6)
        self.ax_load.legend(loc='upper left', fontsize=8,  ncol=3,
                            framealpha=0.6)

        self.fig.canvas.draw()
        plt.pause(0.02)

    # ─── 即時更新 ────────────────────────────────────────────

    def update(self, time_sec, targets, status):
        """
        time_sec : 播放經過秒數
        targets  : {mid_str: absolute_steps}  （當前幀目標）
        status   : {mid: {'pos': int|None, 'load': int|None}}
        """
        self.times.append(time_sec)
        ts = self.times

        for mid in self.motor_ids:
            t    = targets.get(str(mid))
            s    = status.get(mid, {})
            pos  = s.get('pos')
            load = s.get('load')

            self.buf[mid]['target'].append(t)
            self.buf[mid]['actual'].append(pos)
            self.buf[mid]['load'].append(load)

            # 目標對 gearbox 馬達取 mod 4096 以便和 raw 讀值同尺度比較
            is_gb  = self.motor_config.get(mid, {}).get('gearbox', False)
            t_plot = [(v % 4096 if is_gb else v) if v is not None else math.nan
                      for v in self.buf[mid]['target']]
            a_plot = [v if v is not None else math.nan
                      for v in self.buf[mid]['actual']]
            l_plot = [v if v is not None else math.nan
                      for v in self.buf[mid]['load']]

            self._lines_t[mid].set_data(ts, t_plot)
            self._lines_a[mid].set_data(ts, a_plot)
            self._lines_l[mid].set_data(ts, l_plot)

        # 自動縮放 X 軸，Y 軸固定（位置）或自動（負載）
        self.ax_pos.set_xlim(0, max(ts) + 0.5)
        self.ax_load.relim()
        self.ax_load.autoscale_view(scalex=True, scaley=True)
        self.ax_load.set_xlim(0, max(ts) + 0.5)

        self.fig.canvas.flush_events()
        plt.pause(0.001)

    # ─── 儲存 ────────────────────────────────────────────────

    def save(self, filename=None):
        """儲存圖表為 PNG，回傳檔案名稱。"""
        if filename is None:
            filename = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.ioff()
        self.fig.canvas.draw()
        self.fig.savefig(filename, dpi=150, bbox_inches='tight')
        plt.ion()
        print(f"圖表已儲存：{filename}")
        return filename

    def close(self):
        plt.ioff()
        plt.close(self.fig)


# ─── 獨立執行：讀 JSON 事後繪圖 ──────────────────────────────

if __name__ == '__main__':
    import json, glob, os

    files = sorted(glob.glob('recording_*.json'))
    if not files:
        print("找不到 recording_*.json")
        sys.exit(1)

    for i, f in enumerate(files):
        print(f"  [{i+1}] {f}")
    idx = int(input("選擇編號：")) - 1
    path = files[idx]

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    motor_cfg = {int(k): v for k, v in data['metadata']['motor_config'].items()}
    motor_ids = sorted(motor_cfg.keys())
    frames    = data['frames']

    # 使用和 player 相同的 LOAD_THRESHOLD（若 JSON 無記錄則給預設值）
    threshold = 1000

    viz = Visualizer(motor_ids, motor_cfg, load_threshold=threshold)

    print(f"繪製 {len(frames)} 幀...")
    for frame in frames:
        targets = {mid_str: m['steps']
                   for mid_str, m in frame['motors'].items()
                   if m['steps'] is not None}
        status  = {int(mid_str): {'pos':  m.get('raw_steps'),
                                   'load': None}
                   for mid_str, m in frame['motors'].items()}
        viz.update(frame['time'], targets, status)

    out = viz.save()
    print(f"已儲存 {out}")
    plt.ioff()
    plt.show(block=True)
