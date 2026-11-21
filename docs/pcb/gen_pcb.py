#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C210 焊笔控制器 PCB 布局/装配渲染生成器。

不是 EDA 输出，而是按 docs/SPEC.md 的网表绘制的工程示意图：
- 42 x 24 mm，2 层，1.0 mm，1 oz
- 顶视图 / 底视图 / 原理图 / 装配轴测图 / 叠层 / 布局规则
- 输出 docs/pcb/*.svg，再由 qlmanage 渲染为 docs/images/*.png

运行：python3 -I docs/pcb/gen_pcb.py
"""
from __future__ import annotations

import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG_DIR = HERE.parent / "images"
IMG_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# 画布 / 坐标
# ---------------------------------------------------------------------------
BOARD_W = 42.0          # mm
BOARD_H = 24.0          # mm
BOARD_T = 1.0           # mm
SCALE = 42.0            # px / mm（板视图）
CANVAS = 2000
OX = (CANVAS - BOARD_W * SCALE) / 2.0
OY = (CANVAS - BOARD_H * SCALE) / 2.0

FONT = "Inter, Helvetica, Arial, sans-serif"
MONO = "SFMono-Regular, Menlo, Consolas, monospace"

# 颜色
BG = "#f3efe4"
INK = "#1d2a30"
MUTED = "#5d6b70"
BOARD = "#0b5d2e"
BOARD_DARK = "#084a25"
EDGE = "#d8b45a"
EDGE_LIGHT = "#f0d48a"
COPPER = "#2f8f5b"
COPPER_LIGHT = "#48b277"
POWER = "#3aa76d"
PAD = "#e3c15c"
PAD_EDGE = "#a8842f"
HOLE = "#151515"
SILK = "#f5f2e8"
SILK_DIM = "#cfe0d2"
IC = "#24282c"
IC_EDGE = "#4a5258"
PASSIVE = "#d9c7a3"
PASSIVE_EDGE = "#a89470"
METAL = "#b9bdc0"
RED = "#c0392b"
GREEN = "#2e7d32"
BLUE = "#2c6fbb"
CREAM = "#fbf8ef"
GRID = "#e7e0d1"


def px(x_mm: float, y_mm: float) -> tuple[float, float]:
    """板坐标（左下原点，y 向上）-> SVG 像素（左上原点，y 向下）。"""
    return OX + x_mm * SCALE, OY + (BOARD_H - y_mm) * SCALE


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Svg:
    def __init__(self, w: int, h: int, bg: str = BG):
        self.w = w
        self.h = h
        self.parts: list[str] = []
        self.rect(0, 0, w, h, bg, rx=0)

    def add(self, s: str) -> None:
        self.parts.append(s)

    def rect(self, x, y, w, h, fill, stroke="none", sw=0, rx=0, opacity=1.0):
        self.add(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'rx="{rx:.2f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'opacity="{opacity}"/>'
        )

    def line(self, x1, y1, x2, y2, stroke, sw=1, opacity=1.0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{d} '
            f'stroke-linecap="round"/>'
        )

    def circle(self, cx, cy, r, fill, stroke="none", sw=0, opacity=1.0):
        self.add(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>'
        )

    def poly(self, pts, fill, stroke="none", sw=0, opacity=1.0):
        p = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        self.add(
            f'<polygon points="{p}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" opacity="{opacity}"/>'
        )

    def path(self, d, fill="none", stroke="none", sw=0, opacity=1.0, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(
            f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'opacity="{opacity}"{da} stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def text(self, x, y, s, size=14, fill=INK, anchor="middle", weight="normal",
             family=FONT, rotate=None, opacity=1.0, letter=0):
        tr = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate else ""
        self.add(
            f'<text x="{x:.2f}" y="{y:.2f}" font-family="{family}" '
            f'font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" opacity="{opacity}" '
            f'letter-spacing="{letter}"{tr}>{esc(s)}</text>'
        )

    def raw(self, s: str) -> None:
        self.add(s)

    def save(self, name: str):
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
            f'height="{self.h}" viewBox="0 0 {self.w} {self.h}">\n'
        )
        body = "\n".join(self.parts)
        (HERE / name).write_text(head + body + "\n</svg>\n", encoding="utf-8")
        print(f"wrote {name}")


# ---------------------------------------------------------------------------
# 基础图元（板坐标）
# ---------------------------------------------------------------------------
def pad_rect(svg: Svg, x, y, w, h, rx=0.15, fill=PAD, stroke=PAD_EDGE, sw=0.15):
    """x,y 是中心（mm），w,h 是尺寸（mm）。"""
    cx, cy = px(x, y)
    svg.rect(cx - w * SCALE / 2, cy - h * SCALE / 2,
             w * SCALE, h * SCALE, fill, stroke, sw, rx * SCALE)


def through_pad(svg: Svg, x, y, r=0.8, drill=0.4, fill=PAD):
    cx, cy = px(x, y)
    svg.circle(cx, cy, r * SCALE, fill, PAD_EDGE, 0.5)
    svg.circle(cx, cy, drill * SCALE, HOLE)


def via(svg: Svg, x, y, r=0.3, drill=0.15):
    cx, cy = px(x, y)
    svg.circle(cx, cy, r * SCALE, PAD, PAD_EDGE, 0.4)
    svg.circle(cx, cy, drill * SCALE, HOLE)


def trace(svg: Svg, pts, width=0.25, color=COPPER, opacity=0.95, outline=True):
    if len(pts) < 2:
        return
    pp = [px(x, y) for x, y in pts]
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pp)
    if outline:
        svg.path(d, stroke="#0a3d1d", sw=width * SCALE + 2.0, opacity=0.55)
    svg.path(d, stroke=color, sw=width * SCALE, opacity=opacity)


def silk_line(svg: Svg, pts, width=0.18, color=SILK, opacity=0.9):
    pp = [px(x, y) for x, y in pts]
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pp)
    svg.path(d, stroke=color, sw=width * SCALE, opacity=opacity)


def silk_text(svg: Svg, x, y, s, size=13, color=SILK, anchor="middle",
              weight="normal", rotate=None, opacity=0.95):
    cx, cy = px(x, y)
    svg.text(cx, cy, s, size=size, fill=color, anchor=anchor,
             weight=weight, rotate=rotate, opacity=opacity)


def leader(svg: Svg, x1, y1, x2, y2, color=SILK_DIM, width=0.08):
    silk_line(svg, [(x1, y1), (x2, y2)], width=width, color=color, opacity=0.8)


# ---------------------------------------------------------------------------
# 封装绘制
# ---------------------------------------------------------------------------
def passive(svg: Svg, c, side="top"):
    """两脚贴片：0603/0805/1812/SMA/LED0805。"""
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    rot = c.get("rot", 0)
    if rot == 90:
        w, h = h, w
    kind = c.get("kind", "0603")
    if kind == "1812":
        pw, ph = 0.8, h
    elif kind in ("0805", "led0805"):
        pw, ph = 0.5, h
    elif kind == "SMA":
        pw, ph = 1.0, h
    else:
        pw, ph = 0.42, h
    # 两端的焊盘
    pad_rect(svg, x - w / 2 + pw / 2, y, pw, ph, rx=0.08)
    pad_rect(svg, x + w / 2 - pw / 2, y, pw, ph, rx=0.08)
    # 本体
    cx, cy = px(x, y)
    body_w = (w - 2 * pw + 0.15) * SCALE
    body_h = h * SCALE
    fill = PASSIVE
    if kind == "led0805":
        fill = RED
    elif kind == "SMA":
        fill = "#2b2b2b"
    svg.rect(cx - body_w / 2, cy - body_h / 2, body_w, body_h,
             fill, PASSIVE_EDGE if kind != "SMA" else "#555", 0.5, 0.06 * SCALE)
    if kind == "SMA":
        # 二极管色带
        svg.rect(cx + body_w * 0.28, cy - body_h / 2, body_w * 0.12, body_h,
                 "#d9d9d9", "none", 0, 0)
    if kind == "led0805":
        svg.circle(cx, cy, 0.18 * SCALE, "#ffdddd", "none", 0)
    label(svg, c)


def sot23(svg: Svg, c):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    for dx in (-0.95, 0.0, 0.95):
        pad_rect(svg, x + dx, y - h / 2 + 0.25, 0.5, 0.55, rx=0.06)
    cx, cy = px(x, y + 0.15)
    svg.rect(cx - w * SCALE / 2, cy - h * SCALE / 2 + 0.2 * SCALE,
             w * SCALE, h * SCALE * 0.75, IC, IC_EDGE, 0.5, 0.05 * SCALE)
    label(svg, c)


def elec(svg: Svg, c):
    """SMD 电解电容：竖直两脚，圆形本体 + 极性标记。"""
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    # 焊盘在上下两端
    pad_rect(svg, x, y - h / 2 + 0.65, 1.8, 1.2, rx=0.08)
    pad_rect(svg, x, y + h / 2 - 0.65, 1.8, 1.2, rx=0.08)
    cx, cy = px(x, y)
    r = (w / 2 - 0.05) * SCALE
    svg.circle(cx, cy, r, "#2e4f8a", "#1b2f55", 1.0)
    # 顶部银色圆面
    svg.circle(cx, cy, r * 0.78, "#b9c2cc", "#6f7a86", 0.8)
    # 负极侧的深色月牙/色带
    svg.path(
        f"M {cx - r*0.78:.2f} {cy + r*0.30:.2f} "
        f"A {r*0.78:.2f} {r*0.78:.2f} 0 0 1 {cx + r*0.78:.2f} {cy + r*0.30:.2f} "
        f"L {cx + r*0.55:.2f} {cy + r*0.55:.2f} "
        f"A {r*0.55:.2f} {r*0.55:.2f} 0 0 0 {cx - r*0.55:.2f} {cy + r*0.55:.2f} Z",
        fill="#1b2f55", opacity=0.9,
    )
    # 正极 "+"
    svg.line(cx - 0.55 * SCALE, cy - 0.85 * SCALE,
             cx - 0.05 * SCALE, cy - 0.85 * SCALE, "#ffffff", 2.2)
    svg.line(cx - 0.30 * SCALE, cy - 1.10 * SCALE,
             cx - 0.30 * SCALE, cy - 0.60 * SCALE, "#ffffff", 2.2)
    svg.text(cx, cy + 0.15 * SCALE, "C1", size=14, fill="#ffffff",
             weight="bold")
    svg.text(cx, cy + 0.55 * SCALE, "100µF", size=11, fill="#dfe9f5")


def slide_switch(svg: Svg, c):
    """5V/3A 滑动开关：两端焊盘 + 黑色本体 + 小拨钮。"""
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    pad_rect(svg, x - w / 2 + 0.65, y, 1.3, h * 0.78, rx=0.08)
    pad_rect(svg, x + w / 2 - 0.65, y, 1.3, h * 0.78, rx=0.08)
    cx, cy = px(x, y)
    svg.rect(cx - (w - 1.6) * SCALE / 2, cy - h * SCALE * 0.40,
             (w - 1.6) * SCALE, h * SCALE * 0.80, "#202020", "#555", 0.8,
             0.08 * SCALE)
    # 拨钮
    svg.rect(cx - 1.25 * SCALE, cy - 0.55 * SCALE,
             2.5 * SCALE, 1.1 * SCALE, "#b9bdc0", "#666", 0.6, 0.08 * SCALE)
    svg.text(cx, cy - 0.12 * SCALE, "SW1", size=13, fill="#ffffff",
             weight="bold")
    svg.text(cx, cy + 0.40 * SCALE, "5V 3A", size=10, fill="#cfcfcf")


def sot223(svg: Svg, c):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    # 三个小脚 + 大焊盘（tab）
    for dy in (-1.0, 0.0, 1.0):
        pad_rect(svg, x - w / 2 + 0.5, y + dy, 0.9, 0.6, rx=0.06)
    pad_rect(svg, x + w / 2 - 1.2, y, 2.2, h * 0.8, rx=0.08)
    cx, cy = px(x, y)
    svg.rect(cx - w * SCALE / 2 + 0.9 * SCALE, cy - h * SCALE / 2,
             w * SCALE - 1.8 * SCALE, h * SCALE, IC, IC_EDGE, 0.5, 0.05 * SCALE)
    label(svg, c)


def soic(svg: Svg, c, npins: int):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    # 长边在上下；pins 沿左右均分。这里 SOIC-8/16 都按“左右各一半”画。
    n = npins // 2
    pitch = (w - 1.0) / (n - 1) if n > 1 else 0
    for i in range(n):
        px_ = x - (w - 1.0) / 2 + i * pitch
        pad_rect(svg, px_, y - h / 2 + 0.3, 0.45, 0.55, rx=0.05)
        pad_rect(svg, px_, y + h / 2 - 0.3, 0.45, 0.55, rx=0.05)
    cx, cy = px(x, y)
    svg.rect(cx - (w - 0.7) * SCALE / 2, cy - (h - 0.6) * SCALE / 2,
             (w - 0.7) * SCALE, (h - 0.6) * SCALE, IC, IC_EDGE, 0.6, 0.08 * SCALE)
    # pin 1 圆点
    svg.circle(cx - (w - 1.3) * SCALE / 2, cy + (h - 1.2) * SCALE / 2,
               0.16 * SCALE, SILK)
    label(svg, c)


def to252(svg: Svg, c):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    # 三个引脚在左侧，tab 在右侧
    for dy in (-1.0, 0.0, 1.0):
        pad_rect(svg, x - w / 2 + 0.55, y + dy, 0.9, 0.65, rx=0.06)
    pad_rect(svg, x + w / 2 - 1.6, y, 3.0, h * 0.92, rx=0.08)
    cx, cy = px(x, y)
    svg.rect(cx - (w - 1.5) * SCALE / 2, cy - (h - 0.5) * SCALE / 2,
             (w - 1.5) * SCALE, (h - 0.5) * SCALE, IC, IC_EDGE, 0.6, 0.08 * SCALE)
    # 金属 tab 的高光
    svg.rect(cx + w * SCALE * 0.18, cy - h * SCALE * 0.38,
             w * SCALE * 0.26, h * SCALE * 0.76, METAL, "#777", 0.5, 0.06 * SCALE)
    label(svg, c)


def usb_c(svg: Svg, c):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    # 16 个细 pad 沿下边缘（板坐标 y 的下侧）
    n = 16
    span = w * 0.72
    for i in range(n):
        xx = x - span / 2 + span * i / (n - 1)
        pad_rect(svg, xx, y - h / 2 + 0.55, 0.28, 1.0, rx=0.04)
    # 4 个壳脚
    for dx in (-w * 0.38, -w * 0.18, w * 0.18, w * 0.38):
        pad_rect(svg, x + dx, y + h / 2 - 0.7, 0.9, 1.1, rx=0.08)
    cx, cy = px(x, y)
    # 连接器外壳：向板外延伸
    svg.rect(cx - w * SCALE / 2 - 0.8 * SCALE, cy - h * SCALE / 2,
             w * SCALE + 0.8 * SCALE, h * SCALE, "#d9d5c8", "#7a7568", 0.8, 0.15 * SCALE)
    svg.rect(cx - w * SCALE / 2 - 0.5 * SCALE, cy - h * SCALE * 0.28,
             w * SCALE * 0.9, h * SCALE * 0.56, "#2a2a2a", "none", 0, 0.1 * SCALE)
    svg.rect(cx - w * SCALE / 2 - 0.2 * SCALE, cy - h * SCALE * 0.16,
             w * SCALE * 0.5, h * SCALE * 0.32, "#b9b9b9", "none", 0, 0.05 * SCALE)
    label(svg, c)


def jst_xh(svg: Svg, c):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    # 两个大焊盘
    pad_rect(svg, x - w * 0.22, y, 1.2, 1.4, rx=0.08)
    pad_rect(svg, x + w * 0.22, y, 1.2, 1.4, rx=0.08)
    cx, cy = px(x, y)
    svg.rect(cx - w * SCALE / 2, cy - h * SCALE / 2,
             w * SCALE, h * SCALE, "#efe9da", "#8c8474", 0.8, 0.2 * SCALE)
    for dx in (-0.9, 0.9):
        svg.rect(cx + dx * SCALE - 0.42 * SCALE, cy - 0.4 * SCALE,
                 0.84 * SCALE, 0.8 * SCALE, "#f7f2e6", "#6f6a5e", 0.5, 0.08 * SCALE)
    label(svg, c)


def header(svg: Svg, c, npins: int):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    # 排针：圆形焊盘 + 方孔
    for i in range(npins):
        xx = x - (w - 2.54) / 2 + i * 2.54
        through_pad(svg, xx, y, r=0.85, drill=0.5)
    cx, cy = px(x, y)
    svg.rect(cx - w * SCALE / 2, cy - h * SCALE / 2,
             w * SCALE, h * SCALE, "#1f1f1f", "none", 0, 0.12 * SCALE, 0.55)
    # 每针的塑料方口
    for i in range(npins):
        xx = x - (w - 2.54) / 2 + i * 2.54
        cx2, cy2 = px(xx, y)
        svg.rect(cx2 - 1.15 * SCALE, cy2 - 1.15 * SCALE,
                 2.3 * SCALE, 2.3 * SCALE, "none", "#9a9a9a", 0.6, 0.05 * SCALE)
    label(svg, c)


def tact(svg: Svg, c):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    for dx in (-w * 0.32, w * 0.32):
        for dy in (-h * 0.32, h * 0.32):
            pad_rect(svg, x + dx, y + dy, 0.8, 0.8, rx=0.06)
    cx, cy = px(x, y)
    svg.rect(cx - w * SCALE * 0.38, cy - h * SCALE * 0.38,
             w * SCALE * 0.76, h * SCALE * 0.76, "#2d2d2d", "#555", 0.8, 0.1 * SCALE)
    svg.circle(cx, cy, 0.8 * SCALE, "#8a8a8a", "#555", 0.6)
    label(svg, c)


def led3mm(svg: Svg, c):
    x, y, w, h = c["x"], c["y"], c["w"], c["h"]
    through_pad(svg, x - 0.9, y, r=0.7, drill=0.35)
    through_pad(svg, x + 0.9, y, r=0.7, drill=0.35)
    cx, cy = px(x, y)
    svg.circle(cx, cy, 1.45 * SCALE, GREEN if c.get("color") == "green" else RED,
               "#6b1f18", 0.8)
    svg.circle(cx - 0.35 * SCALE, cy - 0.35 * SCALE, 0.3 * SCALE, "#ffffff", "none", 0,
               0.35)
    label(svg, c)


def testpoint(svg: Svg, c):
    x, y = c["x"], c["y"]
    through_pad(svg, x, y, r=0.75, drill=0.35)
    label(svg, c)


def mounting_hole(svg: Svg, x, y):
    cx, cy = px(x, y)
    svg.circle(cx, cy, 1.7 * SCALE, PAD, PAD_EDGE, 0.6)
    svg.circle(cx, cy, 1.1 * SCALE, HOLE)
    svg.circle(cx, cy, 1.35 * SCALE, "none", "#6b6b6b", 0.4, 0.4)


def label(svg: Svg, c):
    """元件位号/值：默认上方位号、下方值；可用 lx/ly/lanchor 覆盖。"""
    x, y = c["x"], c["y"]
    w, h = c["w"], c["h"]
    if c.get("nolabel"):
        return
    lx = c.get("lx", x)
    ly = c.get("ly", y - h / 2 - 0.45)
    anchor = c.get("lanchor", "middle")
    size = c.get("lsize", 11)
    silk_text(svg, lx, ly, c["ref"], size=size, anchor=anchor,
              weight="bold" if c.get("big") else "normal")
    if c.get("show_value", c.get("big", False)):
        vy = c.get("vy", y + h / 2 + 0.6)
        silk_text(svg, c.get("vx", lx), vy, c["value"], size=max(9, size - 1),
                  anchor=anchor, color=SILK_DIM)


# ---------------------------------------------------------------------------
# 元件表
# ---------------------------------------------------------------------------
TOP = [
    # 电源/输入
    dict(ref="J1", value="USB-C 16P", kind="usb", x=4.5, y=12.0, w=9.0, h=7.4,
         big=True, lx=4.5, ly=16.3, show_value=True, lsize=12),
    dict(ref="F1", value="3A PTC", kind="1812", x=12.25, y=19.1, w=4.5, h=3.2,
         big=True, lsize=12),
    dict(ref="SW1", value="5V 3A", kind="switch", x=19.85, y=21.55, w=8.7, h=3.5,
         nolabel=True),
    dict(ref="D1", value="SMAJ5.0A", kind="SMA", x=12.15, y=14.3, w=4.3, h=2.6,
         lsize=11),
    dict(ref="C1", value="100µF", kind="elec", x=18.15, y=15.65, w=6.3, h=6.3,
         nolabel=True),
    dict(ref="C2", value="10µF", kind="0805", x=22.8, y=17.625, w=2.0, h=1.25),
    dict(ref="C3", value="0.1µF", kind="0603", x=22.6, y=15.9, w=1.6, h=0.8),
    # 模拟/开关
    dict(ref="U2", value="74HCT4053", kind="soic16", x=30.0, y=14.0, w=10.0, h=4.0,
         big=True, lsize=12),
    dict(ref="U1", value="MAX31855", kind="soic8", x=15.0, y=9.5, w=5.0, h=4.0,
         big=True, lsize=11),
    dict(ref="C11", value="0.1µF", kind="0603", x=12.0, y=12.2, w=1.6, h=0.8),
    dict(ref="R7", value="1M", kind="0603", x=13.3, y=4.9, w=1.6, h=0.8),
    dict(ref="R8", value="1M", kind="0603", x=13.3, y=3.4, w=1.6, h=0.8),
    dict(ref="R9", value="1k", kind="0603", x=15.3, y=4.9, w=1.6, h=0.8),
    dict(ref="R10", value="1k", kind="0603", x=15.3, y=3.4, w=1.6, h=0.8),
    dict(ref="D3", value="BAT54S", kind="sot23", x=11.0, y=2.75, w=3.0, h=1.5),
    dict(ref="D4", value="BAT54S", kind="sot23", x=11.0, y=4.75, w=3.0, h=1.5),
    dict(ref="C8", value="100nF", kind="0603", x=17.4, y=2.4, w=1.6, h=0.8),
    dict(ref="C9", value="10nF", kind="0603", x=13.8, y=2.4, w=1.6, h=0.8),
    dict(ref="C10", value="10nF", kind="0603", x=15.6, y=2.4, w=1.6, h=0.8),
    dict(ref="R13", value="10k", kind="0603", x=10.3, y=6.4, w=1.6, h=0.8),
    dict(ref="R17", value="10k", kind="0603", x=10.3, y=7.9, w=1.6, h=0.8),
    dict(ref="R5", value="100Ω", kind="0603", x=36.3, y=12.9, w=1.6, h=0.8),
    dict(ref="R6", value="10k", kind="0603", x=36.3, y=11.4, w=1.6, h=0.8),
    # 加热功率级
    dict(ref="Q1", value="AOD4184", kind="to252", x=22.3, y=6.05, w=6.6, h=6.1,
         big=True, lsize=12),
    dict(ref="D2", value="SS34", kind="SMA", x=21.65, y=11.1, w=4.3, h=2.6,
         lsize=11),
    dict(ref="R3", value="100Ω", kind="0603", x=17.8, y=6.4, w=1.6, h=0.8),
    dict(ref="R4", value="1k", kind="0603", x=17.8, y=4.9, w=1.6, h=0.8),
    dict(ref="J2", value="C210", kind="jst", x=38.35, y=6.9, w=7.3, h=5.8,
         big=True, lsize=12),
    dict(ref="J4", value="KSD", kind="header2", x=38.04, y=18.27, w=5.08, h=2.54,
         big=True, lsize=11),
    # 测试点
    dict(ref="TP1", value="+5V", kind="tp", x=32.0, y=20.6, w=1.5, h=1.5,
         lsize=10, ly=21.9),
    dict(ref="TP2", value="+3V3", kind="tp", x=34.2, y=20.6, w=1.5, h=1.5,
         lsize=10, ly=21.9),
    dict(ref="TP3", value="GND", kind="tp", x=36.4, y=20.6, w=1.5, h=1.5,
         lsize=10, ly=21.9),
    dict(ref="TP4", value="GATE", kind="tp", x=10.0, y=10.9, w=1.5, h=1.5,
         lsize=10, ly=12.2),
    dict(ref="TP5", value="T+", kind="tp", x=8.0, y=2.0, w=1.5, h=1.5,
         lsize=10, ly=0.9),
    dict(ref="TP6", value="T-", kind="tp", x=20.0, y=1.5, w=1.5, h=1.5,
         lsize=10, ly=0.4),
]

BOTTOM = [
    dict(ref="U3", value="AMS1117-3.3", kind="sot223", x=31.25, y=6.75, w=6.5, h=3.5,
         big=True, lsize=11),
    dict(ref="C4", value="10µF", kind="0805", x=26.5, y=5.625, w=2.0, h=1.25),
    dict(ref="C5", value="10µF", kind="0805", x=26.5, y=7.625, w=2.0, h=1.25),
    dict(ref="C6", value="0.1µF", kind="0603", x=26.3, y=9.2, w=1.6, h=0.8),
    dict(ref="U4", value="STC8G1K08A", kind="soic8", x=6.5, y=6.0, w=5.0, h=4.0,
         big=True, lsize=10),
    dict(ref="C12", value="0.1µF", kind="0603", x=10.3, y=4.4, w=1.6, h=0.8),
    dict(ref="C13", value="10µF", kind="0805", x=10.5, y=5.75, w=2.0, h=1.25),
    dict(ref="LED1", value="红色", kind="led0805", x=22.0, y=2.6, w=2.0, h=1.25),
    dict(ref="R14", value="330Ω", kind="0603", x=24.2, y=2.4, w=1.6, h=0.8),
    dict(ref="SW2", value="KEY", kind="tact", x=13.0, y=13.0, w=6.0, h=6.0,
         big=True, lsize=11),
    dict(ref="R15", value="10k", kind="0603", x=11.3, y=17.4, w=1.6, h=0.8),
    dict(ref="C14", value="100nF", kind="0603", x=11.3, y=18.9, w=1.6, h=0.8),
    dict(ref="J3", value="ISP", kind="header4", x=13.08, y=1.77, w=10.16, h=2.54,
         big=True, lsize=11),
    dict(ref="LED2", value="绿色", kind="led3", x=2.5, y=18.0, w=3.0, h=3.0,
         color="green", lsize=10, ly=19.6),
    dict(ref="R16", value="1k", kind="0603", x=5.5, y=18.0, w=1.6, h=0.8,
         ly=19.3),
    dict(ref="R1", value="5.1k", kind="0603", x=7.0, y=20.0, w=1.6, h=0.8),
    dict(ref="R2", value="5.1k", kind="0603", x=7.0, y=21.2, w=1.6, h=0.8),
    dict(ref="C7", value="0.1µF", kind="0603", x=33.0, y=10.5, w=1.6, h=0.8),
]


def draw_component(svg: Svg, c, side="top", mirror=False):
    if mirror:
        c = dict(c)
        c["x"] = BOARD_W - c["x"]
    kind = c.get("kind", "0603")
    if kind in ("0603", "0805", "1812", "SMA", "led0805"):
        passive(svg, c, side)
    elif kind == "elec":
        elec(svg, c)
    elif kind == "switch":
        slide_switch(svg, c)
    elif kind == "sot23":
        sot23(svg, c)
    elif kind == "sot223":
        sot223(svg, c)
    elif kind == "soic8":
        soic(svg, c, 8)
    elif kind == "soic16":
        soic(svg, c, 16)
    elif kind == "to252":
        to252(svg, c)
    elif kind == "usb":
        usb_c(svg, c)
    elif kind == "jst":
        jst_xh(svg, c)
    elif kind == "header2":
        header(svg, c, 2)
    elif kind == "header4":
        header(svg, c, 4)
    elif kind == "tact":
        tact(svg, c)
    elif kind == "led3":
        led3mm(svg, c)
    elif kind == "tp":
        testpoint(svg, c)
    else:
        pad_rect(svg, c["x"], c["y"], c["w"], c["h"], rx=0.1)
        label(svg, c)


# ---------------------------------------------------------------------------
# 顶视图
# ---------------------------------------------------------------------------
def board_outline(svg: Svg, mirror=False):
    x = OX
    y = OY
    w = BOARD_W * SCALE
    h = BOARD_H * SCALE
    svg.rect(x, y, w, h, BOARD, EDGE, 3.0, 0.35 * SCALE)
    svg.rect(x + 2, y + 2, w - 4, h - 4, "none", EDGE_LIGHT, 0.8, 0.35 * SCALE, 0.5)


def draw_grid(svg: Svg):
    """板内浅网格，5mm 一格。"""
    for gx in range(0, int(BOARD_W) + 1, 5):
        x, _ = px(gx, 0)
        svg.line(x, OY, x, OY + BOARD_H * SCALE, "#1b6a3a", 0.6, 0.25)
    for gy in range(0, int(BOARD_H) + 1, 5):
        _, y = px(0, gy)
        svg.line(OX, y, OX + BOARD_W * SCALE, y, "#1b6a3a", 0.6, 0.25)


def title_block(svg: Svg, title: str, subtitle: str, view: str):
    # 顶部标题
    svg.rect(OX, 40, BOARD_W * SCALE, 120, CREAM, EDGE, 1.5, 10)
    svg.text(OX + 22, 82, title, size=30, fill=INK, anchor="start", weight="bold",
             letter=1)
    svg.text(OX + 22, 112, subtitle, size=15, fill=MUTED, anchor="start")
    svg.text(OX + BOARD_W * SCALE - 22, 82, view, size=20, fill=INK,
             anchor="end", weight="bold")
    svg.text(OX + BOARD_W * SCALE - 22, 112,
             "REV 1.0  ·  2026-11-21  ·  ZCode", size=12, fill=MUTED,
             anchor="end")
    # 底部图例
    ly = OY + BOARD_H * SCALE + 34
    svg.rect(OX, ly, BOARD_W * SCALE, 210, CREAM, EDGE, 1.2, 8)
    svg.text(OX + 18, ly + 28, "LEGEND / NOTES", size=14, fill=INK,
             anchor="start", weight="bold", letter=1)
    items = [
        (COPPER, "Top copper trace"),
        (POWER, "5V / 2A power trace"),
        (PAD, "ENIG pad / via"),
        (SILK, "Silkscreen"),
        (IC, "IC / connector body"),
    ]
    for i, (col, txt) in enumerate(items):
        bx = OX + 18 + (i % 3) * 250
        by = ly + 56 + (i // 3) * 32
        svg.rect(bx, by - 10, 26, 14, col, PAD_EDGE if col == PAD else "none",
                 0.5, 3)
        svg.text(bx + 36, by + 1, txt, size=12, fill=MUTED, anchor="start")
    svg.text(OX + 18, ly + 158,
             "2-layer · 1.0 mm FR-4 · 1 oz copper · min trace/space 0.2 mm · "
             "via 0.3/0.6 mm", size=12, fill=MUTED, anchor="start")
    svg.text(OX + 18, ly + 182,
             "Render only — footprints are approximate. Verify with KiCad / "
             "LCEDA DRC before fabrication.", size=12, fill=RED, anchor="start")


def dimension(svg: Svg, x1, y1, x2, y2, text_s, offset=0.0):
    p1 = px(x1, y1)
    p2 = px(x2, y2)
    svg.line(p1[0], p1[1], p2[0], p2[1], MUTED, 0.8, 0.8)
    # 端部小刻度
    if abs(y2 - y1) < 0.01:
        for p in (p1, p2):
            svg.line(p[0], p[1] - 5, p[0], p[1] + 5, MUTED, 0.8, 0.8)
    else:
        for p in (p1, p2):
            svg.line(p[0] - 5, p[1], p[0] + 5, p[1], MUTED, 0.8, 0.8)
    mx = (p1[0] + p2[0]) / 2
    my = (p1[1] + p2[1]) / 2
    svg.text(mx, my - 6 + offset, text_s, size=12, fill=MUTED)


def scale_bar(svg: Svg, x_mm=0.0, y_mm=0.0, length_mm=10):
    x, y = px(x_mm, y_mm)
    svg.line(x, y, x + length_mm * SCALE, y, INK, 2.5)
    for i in range(0, length_mm + 1, 5):
        xx = x + i * SCALE
        svg.line(xx, y - 5, xx, y + 5, INK, 1.5)
    svg.text(x + length_mm * SCALE / 2, y - 10, f"{length_mm} mm", size=12,
             fill=INK)


def render_top():
    svg = Svg(CANVAS, CANVAS)
    draw_grid(svg)
    board_outline(svg)

    # ---- 走线（先画，元件盖住端点） ----
    # USB-C VBUS -> F1 -> SW1
    trace(svg, [(8.2, 10.5), (10.0, 10.5), (10.0, 19.1), (10.0, 19.1)], 2.0, POWER)
    trace(svg, [(8.2, 13.5), (9.0, 13.5), (9.0, 18.2), (10.0, 18.2)], 1.6, POWER)
    trace(svg, [(14.5, 19.1), (15.5, 19.1), (15.5, 20.9)], 2.0, POWER)
    # SW1 -> +5V 节点 / C1 / J4
    trace(svg, [(24.2, 20.9), (25.5, 20.9), (25.5, 18.4), (35.5, 18.4)], 2.0, POWER)
    trace(svg, [(18.15, 18.15), (18.15, 18.4)], 2.0, POWER)
    trace(svg, [(18.15, 13.15), (18.15, 9.8), (19.0, 9.8), (19.0, 8.7)], 2.0, POWER)
    trace(svg, [(18.15, 13.15), (21.0, 13.15), (21.0, 10.5), (22.0, 10.5),
                (22.0, 9.2)], 2.0, POWER)
    # J4 pin2 -> J2 pin1 (HEAT_P) 与 4053 X0
    trace(svg, [(35.5, 17.5), (33.5, 17.5), (33.5, 8.8), (35.7, 8.8)], 2.0, POWER)
    trace(svg, [(35.7, 8.8), (35.7, 5.6), (34.8, 5.6)], 2.0, POWER)
    trace(svg, [(30.0, 12.0), (30.0, 9.2), (31.5, 9.2), (31.5, 8.8)], 1.2, POWER)
    # J2 pin2 -> Q1 drain (HEAT_N)
    trace(svg, [(34.8, 8.2), (32.0, 8.2), (32.0, 7.2), (25.6, 7.2)], 2.0, POWER)
    # Q1 source -> GND（用铺铜/短走线示意）
    trace(svg, [(22.0, 3.0), (22.0, 1.8), (18.0, 1.8), (18.0, 2.4)], 1.5, COPPER)
    # 3.3V 从 LDO（底面）经 via 到 U1/U4，仅示意
    trace(svg, [(26.5, 9.5), (20.5, 9.5), (20.5, 12.0), (17.8, 12.0)], 0.5, COPPER_LIGHT)
    trace(svg, [(26.5, 9.5), (26.5, 15.0), (23.0, 15.0)], 0.5, COPPER_LIGHT)
    # 模拟差分对（短、成对）
    trace(svg, [(17.0, 9.5), (18.2, 9.5), (18.2, 8.4), (20.0, 8.4),
                (20.0, 10.5), (19.5, 10.5)], 0.2, "#d9a441")
    trace(svg, [(17.0, 8.2), (18.8, 8.2), (18.8, 7.8), (20.4, 7.8),
                (20.4, 10.0), (19.5, 10.0)], 0.2, "#d9a441")
    # GATE
    trace(svg, [(9.0, 10.9), (9.0, 6.4), (17.0, 6.4)], 0.3, "#c46a2b")
    # SCK/SO/CS 从 U1 到 MCU（经 via，示意）
    trace(svg, [(15.0, 11.5), (15.0, 14.0), (10.0, 14.0)], 0.25, COPPER)
    trace(svg, [(16.0, 11.5), (16.0, 13.0), (10.5, 13.0)], 0.25, COPPER)
    trace(svg, [(17.0, 11.0), (17.0, 13.6), (11.0, 13.6)], 0.25, COPPER)

    # ---- 过孔 ----
    for v in [(10.0, 10.5), (10.0, 19.1), (18.15, 18.4), (18.15, 12.5),
              (33.5, 17.5), (35.7, 8.8), (32.0, 7.2), (25.6, 7.2),
              (9.0, 6.4), (10.0, 14.0), (10.5, 13.0), (11.0, 13.6),
              (20.5, 12.0), (26.5, 15.0)]:
        via(svg, *v)

    # ---- 元件 ----
    for c in TOP:
        draw_component(svg, c, "top")

    # 丝印网络名
    silk_text(svg, 6.0, 9.2, "+5V", size=12, weight="bold")
    silk_text(svg, 23.4, 12.9, "+3V3", size=12, weight="bold")
    silk_text(svg, 35.8, 15.2, "HEAT+", size=11, weight="bold", rotate=-90)
    silk_text(svg, 33.0, 6.2, "HEAT-", size=11, weight="bold")
    silk_text(svg, 13.0, 10.6, "T+", size=11, weight="bold")
    silk_text(svg, 13.0, 8.0, "T-", size=11, weight="bold")
    silk_text(svg, 15.0, 6.9, "GATE", size=10, weight="bold")
    silk_text(svg, 12.5, 0.8, "ISP", size=10, weight="bold")
    silk_text(svg, 5.0, 4.6, "LED", size=10, weight="bold")
    silk_text(svg, 13.0, 17.9, "KEY", size=10, weight="bold")
    silk_text(svg, 18.6, 6.6, "Q1", size=10, weight="bold")

    # 星形地标记（C1 负极）
    sx, sy = px(18.15, 13.15)
    svg.circle(sx, sy, 7, "none", "#fff08a", 2.0)
    svg.text(sx + 12, sy + 4, "STAR GND", size=9, fill="#fff08a", anchor="start")

    # 安装孔
    for (mx, my) in [(2.0, 2.0), (40.0, 2.0), (2.0, 22.0), (40.0, 22.0)]:
        mounting_hole(svg, mx, my)

    # 尺寸/比例尺
    dimension(svg, 0, 24.9, 42, 24.9, "42 mm")
    dimension(svg, -1.1, 0, -1.1, 24, "24 mm")
    scale_bar(svg, 0.5, 1.0, 10)
    title_block(svg, "C210 PEN CONTROLLER", "Top view · 42 × 24 mm · 2-layer · 1.0 mm · 1 oz",
                "TOP VIEW")
    svg.save("pcb_top.svg")


def mirror_pts(pts):
    return [(BOARD_W - x, y) for x, y in pts]


def thermal_pad(svg: Svg, x, y, r=0.8, drill=0.4):
    """底面热焊盘：金盘 + 间隙环 + 4 根铜辐条。"""
    cx, cy = px(x, y)
    # 间隙环（阻焊/基材色）
    svg.circle(cx, cy, (r + 0.45) * SCALE, BOARD_DARK, "none", 0)
    # 4 根辐条
    for ang in (0, 90, 180, 270):
        a = math.radians(ang)
        x1 = cx + math.cos(a) * r * SCALE
        y1 = cy + math.sin(a) * r * SCALE
        x2 = cx + math.cos(a) * (r + 0.85) * SCALE
        y2 = cy + math.sin(a) * (r + 0.85) * SCALE
        svg.line(x1, y1, x2, y2, "#2f8f5b", 0.28 * SCALE, 0.95)
    # 金盘 + 孔
    through_pad(svg, x, y, r=r, drill=drill)


def render_bottom():
    svg = Svg(CANVAS, CANVAS)
    draw_grid(svg)

    # 底面铺铜：整板 + 阴影线
    x0, y0 = px(0, BOARD_H)
    w = BOARD_W * SCALE
    h = BOARD_H * SCALE
    svg.raw(
        '<defs>'
        f'<clipPath id="bclip"><rect x="{x0:.2f}" y="{y0:.2f}" '
        f'width="{w:.2f}" height="{h:.2f}" rx="{0.35*SCALE:.2f}"/></clipPath>'
        '<pattern id="bhatch" width="14" height="14" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)">'
        '<line x1="0" y1="0" x2="0" y2="14" stroke="#2a7a45" stroke-width="1.1" '
        'opacity="0.55"/></pattern>'
        '</defs>'
    )
    board_outline(svg)
    svg.rect(x0 + 0.25 * SCALE, y0 + 0.25 * SCALE, w - 0.5 * SCALE,
             h - 0.5 * SCALE, "#1f6b3a", "none", 0, 0.35 * SCALE)
    svg.raw(
        f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'rx="{0.35*SCALE:.2f}" fill="url(#bhatch)" clip-path="url(#bclip)"/>'
    )

    # 模拟地岛（底面坐标，镜像后 x=42-x）
    island = [(3.2, 0.8), (21.8, 0.8), (21.8, 13.6), (18.15, 13.6),
              (18.15, 15.0), (9.5, 15.0), (9.5, 8.2), (3.2, 8.2)]
    # 先在板坐标画，再镜像
    mir = [(BOARD_W - x, y) for x, y in island]
    pts = [px(x, y) for x, y in mir]
    svg.poly(pts, "#227a45", "#062e16", 4.0)
    # 单点连接颈（星形地）
    neck = [(17.7, 13.6), (18.6, 13.6), (18.6, 15.0), (17.7, 15.0)]
    neck = [(BOARD_W - x, y) for x, y in neck]
    svg.poly([px(x, y) for x, y in neck], "#227a45", "#f0d48a", 1.2)

    # 底面走线（镜像）
    traces = [
        ([(31.25, 6.75), (28.0, 6.75), (28.0, 10.0), (25.5, 10.0)], 0.5, COPPER_LIGHT),
        ([(31.25, 6.75), (34.0, 6.75), (34.0, 9.0)], 0.5, COPPER_LIGHT),
        ([(26.5, 5.625), (25.0, 5.625), (25.0, 3.0)], 0.6, COPPER_LIGHT),
        ([(26.5, 7.625), (24.0, 7.625), (24.0, 10.0)], 0.5, COPPER_LIGHT),
        ([(6.5, 8.0), (6.5, 10.0), (10.0, 10.0)], 0.25, COPPER),
        ([(6.5, 4.0), (6.5, 3.0), (10.5, 3.0)], 0.25, COPPER),
        ([(9.0, 6.0), (10.5, 6.0)], 0.25, COPPER),
        ([(4.0, 4.0), (4.0, 2.625)], 0.25, COPPER),
        ([(6.3, 2.4), (6.3, 4.0)], 0.25, COPPER),
        ([(13.0, 10.0), (13.0, 8.0)], 0.25, COPPER),
        ([(13.0, 16.0), (13.0, 19.0)], 0.25, COPPER),
        ([(11.3, 17.4), (11.3, 16.0)], 0.25, COPPER),
        ([(13.08, 3.04), (13.08, 4.5)], 0.25, COPPER),
        ([(17.0, 3.04), (17.0, 5.0)], 0.25, COPPER),
    ]
    for pts_mm, width, color in traces:
        trace(svg, mirror_pts(pts_mm), width, color, opacity=0.85)

    # 过孔（底面）
    for v in [(25.0, 3.0), (24.0, 10.0), (10.0, 10.0), (10.5, 6.0),
              (10.5, 3.0), (6.3, 4.0), (13.0, 8.0), (13.0, 19.0),
              (11.3, 16.0), (13.08, 4.5), (17.0, 5.0), (18.15, 13.6)]:
        via(svg, BOARD_W - v[0], v[1])

    # 热焊盘（底面）
    for (x, y) in [(4.5 - 3.4, 12.0 - 3.0), (4.5 + 3.4, 12.0 - 3.0),
                   (4.5 - 3.4, 12.0 + 3.0), (4.5 + 3.4, 12.0 + 3.0),
                   (38.35 - 2.5, 6.9), (38.35 + 2.5, 6.9),
                   (38.04 - 1.27, 18.27), (38.04 + 1.27, 18.27),
                   (13.08 - 3.81, 1.77), (13.08 - 1.27, 1.77),
                   (13.08 + 1.27, 1.77), (13.08 + 3.81, 1.77),
                   (13.0 - 2.0, 13.0 - 2.0), (13.0 + 2.0, 13.0 - 2.0),
                   (13.0 - 2.0, 13.0 + 2.0), (13.0 + 2.0, 13.0 + 2.0),
                   (32.0, 20.6), (34.2, 20.6), (36.4, 20.6),
                   (10.0, 10.9), (8.0, 2.0), (20.0, 1.5)]:
        thermal_pad(svg, BOARD_W - x, y)

    # 安装孔（底面）
    for (mx, my) in [(2.0, 2.0), (40.0, 2.0), (2.0, 22.0), (40.0, 22.0)]:
        cx, cy = px(BOARD_W - mx, my)
        svg.circle(cx, cy, 1.7 * SCALE, PAD, PAD_EDGE, 0.6)
        svg.circle(cx, cy, 1.1 * SCALE, HOLE)

    # 底面元件（镜像）
    for c in BOTTOM:
        draw_component(svg, c, "bottom", mirror=True)

    # 丝印/标识（镜像位置，文字正向）
    silk_text(svg, BOARD_W - 24.0, 11.0, "POWER GND", size=13, weight="bold")
    silk_text(svg, BOARD_W - 12.0, 4.2, "ANALOG GND", size=13, weight="bold")
    silk_text(svg, BOARD_W - 23.5, 14.3, "STAR @ C1-", size=11, weight="bold")
    silk_text(svg, BOARD_W - 21.0, 23.0, "BOTTOM VIEW (MIRRORED)", size=13,
              color="#ffe9a8", weight="bold")
    silk_text(svg, BOARD_W - 8.0, 0.9, "J2 pin1=HEAT+ / pin2=HEAT-", size=9)

    # 尺寸/比例尺
    dimension(svg, 0, 24.9, 42, 24.9, "42 mm")
    dimension(svg, -1.1, 0, -1.1, 24, "24 mm")
    scale_bar(svg, 0.5, 1.0, 10)

    # 标题/图例
    title_block(svg, "C210 PEN CONTROLLER",
                "Bottom view (mirrored) · ground plane + bottom components",
                "BOTTOM VIEW")
    # 覆盖图例中的顶层色块为底面语义
    ly = OY + BOARD_H * SCALE + 34
    svg.rect(OX, ly, BOARD_W * SCALE, 210, CREAM, EDGE, 1.2, 8)
    svg.text(OX + 18, ly + 28, "BOTTOM LEGEND / NOTES", size=14, fill=INK,
             anchor="start", weight="bold", letter=1)
    bits = [
        ("#1f6b3a", "POWER GND pour"),
        ("#227a45", "ANALOG GND island"),
        ("#f0d48a", "star neck @ C1-"),
        ("#2f8f5b", "bottom trace"),
        (PAD, "THT pad / thermal relief"),
        ("#24282c", "bottom component"),
    ]
    for i, (col, txt) in enumerate(bits):
        bx = OX + 18 + (i % 3) * 250
        by = ly + 56 + (i // 3) * 32
        svg.rect(bx, by - 10, 26, 14, col, PAD_EDGE if col == PAD else "none",
                 0.5, 3)
        svg.text(bx + 36, by + 1, txt, size=12, fill=MUTED, anchor="start")
    svg.text(OX + 18, ly + 158,
             "Mirrored left-right. Bottom components: U3/U4, SW2, J3, LED1/LED2, "
             "R14/R15/R16, C12/C13/C14.", size=12, fill=MUTED, anchor="start")
    svg.text(OX + 18, ly + 182,
             "Single-point star ground at C1 negative; heater current must not "
             "flow through U1 analog ground.", size=12, fill=MUTED, anchor="start")
    svg.save("pcb_bottom.svg")


# ---------------------------------------------------------------------------
# 系统原理图（网络标签 + 元件表）
# ---------------------------------------------------------------------------
def render_schematic():
    W, H = 2400, 1600
    svg = Svg(W, H, "#fbf8ef")
    svg.rect(26, 26, W - 52, H - 52, "none", "#b9a57a", 2.0, 10)
    svg.rect(26, 26, W - 52, 92, "#efe6d2", "#b9a57a", 1.2, 10)
    svg.text(52, 70, "C210 PEN CONTROLLER", size=32, fill=INK,
             anchor="start", weight="bold", letter=1)
    svg.text(52, 98, "System schematic / net-label view · STC8G1K08A-8PIN · "
             "5V/3A USB-C · JBC C210 · MAX31855", size=15, fill=MUTED,
             anchor="start")
    svg.text(W - 52, 70, "SCHEMATIC", size=24, fill=INK, anchor="end",
             weight="bold")
    svg.text(W - 52, 98, "REV 1.0 · 2026-11-21 · ZCode", size=12, fill=MUTED,
             anchor="end")

    def block(x, y, w, h, title, color="#c9b98a"):
        svg.rect(x, y, w, h, "#fdfbf4", color, 1.4, 8)
        svg.rect(x, y, w, 34, "#efe6d2", color, 1.4, 8)
        svg.rect(x, y + 20, w, 14, "#efe6d2", "none", 0, 0)
        svg.text(x + 14, y + 23, title, size=17, fill=INK, anchor="start",
                 weight="bold", letter=0.5)

    def table(x, y, rows, widths=(90, 150, 420), row_h=27, header=None,
              font=13):
        cy = y
        if header:
            svg.rect(x, cy, sum(widths), row_h, "#e8dfca", "none", 0, 3)
            cx = x
            for i, htxt in enumerate(header):
                svg.text(cx + 7, cy + row_h - 8, htxt, size=font, fill=INK,
                         anchor="start", weight="bold")
                cx += widths[i]
            cy += row_h
        for idx, row in enumerate(rows):
            if idx % 2 == 0:
                svg.rect(x, cy, sum(widths), row_h, "#f7f1e2", "none", 0, 0)
            cx = x
            for i, txt in enumerate(row):
                svg.text(cx + 7, cy + row_h - 8, txt, size=font, fill=INK,
                         anchor="start",
                         family=MONO if i >= 2 else FONT,
                         weight="bold" if i == 0 else "normal")
                cx += widths[i]
            cy += row_h
        svg.rect(x, y, sum(widths), cy - y, "none", "#d8c9a9", 0.8)
        return cy

    def net(x, y, label, color=BLUE):
        w = max(60, len(label) * 9 + 18)
        svg.rect(x, y - 13, w, 26, "#ffffff", color, 1.2, 5)
        svg.text(x + 9, y + 5, label, size=14, fill=color, anchor="start",
                 family=MONO, weight="bold")

    def arrow(x1, y1, x2, y2, color=COPPER, w=3.0):
        svg.line(x1, y1, x2, y2, color, w)
        ang = math.atan2(y2 - y1, x2 - x1)
        for da in (math.radians(25), -math.radians(25)):
            xa = x2 - 12 * math.cos(ang + da)
            ya = y2 - 12 * math.sin(ang + da)
            svg.line(x2, y2, xa, ya, color, w)

    # 1. USB-C 输入
    block(40, 140, 700, 400, "1 · USB-C 5V/3A INPUT & PROTECTION")
    table(58, 188, [
        ("J1", "USB-C 16P", "VBUS→F1; CC1→R1 5.1k→GND; CC2→R2 5.1k→GND"),
        ("F1", "PTC 3A", "VBUS→F1→SW1; hold 3A / trip 6A"),
        ("SW1", "5V 3A", "F1→SW1→+5V"),
        ("D1", "SMAJ5.0A", "+5V→GND TVS"),
        ("C1", "100µF", "+5V→GND bulk"),
        ("C2", "10µF", "+5V→GND"),
        ("C3", "0.1µF", "+5V→GND"),
        ("R1/R2", "5.1k", "CC1/CC2→GND (5V sink)"),
    ], widths=(80, 120, 470), header=("REF", "VALUE", "CONNECTION"))
    net(520, 360, "+5V", RED)
    net(58, 500, "GND", MUTED)

    # 2. LDO
    block(770, 140, 420, 300, "2 · 3.3V LDO")
    table(788, 188, [
        ("U3", "AMS1117-3.3", "IN=+5V; OUT=+3V3; GND; tab=OUT"),
        ("C4", "10µF", "+5V→GND"),
        ("C5", "10µF", "+3V3→GND"),
        ("C6", "0.1µF", "+3V3→GND"),
    ], widths=(80, 130, 180), header=("REF", "VALUE", "CONNECTION"))
    net(930, 400, "+3V3", BLUE)

    # 3. 加热 + 4053
    block(1220, 140, 1140, 560, "3 · HEATER POWER STAGE & 74HCT4053 ISOLATION")
    table(1240, 188, [
        ("F2", "KSD9700 400°C", "+5V→F2→J4 pin1 (NC, series in heater)"),
        ("J4", "2-pin 2.54", "pin1=+5V via F2; pin2=HEAT_P"),
        ("J2", "JST XH 2p", "pin1=HEAT_P; pin2=HEAT_N (C210 head)"),
        ("Q1", "AOD4184", "D=HEAT_N; S=GND; G=R3 100Ω←P5.4"),
        ("R3", "100Ω", "P5.4→Q1 gate"),
        ("R4", "1k", "Q1 gate→GND (power-up off)"),
        ("D2", "SS34", "A=HEAT_N; K=HEAT_P (freewheel)"),
        ("U2", "74HCT4053", "X0=HEAT_P; Y0=HEAT_N; X→R9 1k→T_P; Y→R10 1k→T_N"),
        ("R5/R6", "100Ω/10k", "P5.4→R5→INH; INH→R6→GND"),
        ("R9/R10", "1k", "U2 X/Y→T_P/T_N (series, after switch)"),
    ], widths=(80, 160, 400), header=("REF", "VALUE", "CONNECTION"))
    net(1240, 500, "HEAT_P", RED)
    net(1370, 500, "HEAT_N", RED)
    net(1500, 500, "GATE", "#c46a2b")
    net(1610, 500, "INH", "#8e44ad")
    net(1710, 500, "T_P", "#b9770e")
    net(1810, 500, "T_N", "#b9770e")
    net(2050, 500, "+5V", RED)
    net(2140, 500, "GND", MUTED)
    arrow(1240, 620, 2340, 620, POWER, 4)
    svg.text(1790, 610, "+5V → F2 → J4 → HEAT_P → C210 → HEAT_N → Q1 → GND",
             size=13, fill=INK, anchor="middle")

    # 4. 传感器前端
    block(40, 570, 1140, 460, "4 · MAX31855 SENSOR FRONT-END")
    table(58, 618, [
        ("U1", "MAX31855", "T+=T_P; T-=T_N; VCC=+3V3; SCK/SO/CS→MCU"),
        ("R7/R8", "1M", "T_P/T_N→GND (bias)"),
        ("C8", "100nF", "T_P–T_N differential filter"),
        ("C9/C10", "10nF", "T_P/T_N→GND common-mode filter"),
        ("D3/D4", "BAT54S", "T_P/T_N clamp: pin3=signal; pin1=GND; pin2=+3V3"),
        ("C11", "0.1µF", "U1 VCC→GND"),
        ("R13", "10k", "CS→+3V3"),
        ("R17", "10k", "SO→GND (absent chip reads 0)"),
    ], widths=(80, 120, 420), header=("REF", "VALUE", "CONNECTION"))
    net(700, 760, "T_P", "#b9770e")
    net(790, 760, "T_N", "#b9770e")
    net(880, 760, "SCK", GREEN)
    net(960, 760, "SO", GREEN)
    net(1030, 760, "CS", GREEN)
    net(700, 900, "+3V3", BLUE)
    net(790, 900, "GND", MUTED)
    svg.text(58, 990, "关键：加热关断时 4053 把约 5V 共模送到 T+/T-；"
             "1k 串联 + BAT54S 钳位到 3V3/GND，保护 MAX31855 输入。",
             size=13, fill=RED, anchor="start")

    # 5. MCU / UI
    block(1220, 730, 1140, 670, "5 · MCU / BUTTON / LED / ISP")
    table(1240, 778, [
        ("U4", "STC8G1K08A", "1=P5.4 2=VCC 3=P5.5 4=GND 5=P3.0 6=P3.1 7=P3.2 8=P3.3"),
        ("P3.0", "SCK", "→MAX31855 SCK / ISP RX"),
        ("P3.1", "SO", "←MAX31855 SO / ISP TX"),
        ("P3.2", "CS", "→MAX31855 CS (R13 10k↑)"),
        ("P3.3", "KEY", "SW2→GND; R15 10k↑; C14 100nF→GND"),
        ("P5.4", "GATE/INH", "R3→Q1 gate; R5→U2 INH; R4 1k↓"),
        ("P5.5", "LED", "R14 330Ω→LED1→GND"),
        ("J3", "ISP 4pin", "1=+3V3 2=GND 3=P3.0 4=P3.1"),
        ("LED2", "green", "+3V3→R16 1k→LED2→GND"),
        ("C12/C13", "0.1µF/10µF", "U4 VCC→GND"),
    ], widths=(90, 140, 500), header=("REF/PIN", "SIGNAL", "CONNECTION"))
    net(1240, 1120, "SCK", GREEN)
    net(1320, 1120, "SO", GREEN)
    net(1400, 1120, "CS", GREEN)
    net(1480, 1120, "KEY", "#8e44ad")
    net(1570, 1120, "GATE", "#c46a2b")
    net(1670, 1120, "LED", RED)
    net(1770, 1120, "+3V3", BLUE)
    net(1870, 1120, "GND", MUTED)

    # 互连箭头
    arrow(700, 300, 770, 300, POWER, 4)
    svg.text(735, 288, "+5V", size=12, fill=RED, anchor="middle")
    arrow(740, 480, 1240, 480, POWER, 4)
    svg.text(990, 468, "+5V (heater)", size=12, fill=RED, anchor="middle")
    arrow(1080, 400, 1080, 570, COPPER, 3)
    svg.text(1092, 485, "+3V3", size=12, fill=BLUE, anchor="start")
    arrow(900, 400, 1220, 760, COPPER, 3)
    svg.text(1055, 590, "+3V3", size=12, fill=BLUE, anchor="middle")
    arrow(1140, 700, 1220, 830, "#b9770e", 3)
    svg.text(1180, 760, "T_P/T_N", size=11, fill="#b9770e", anchor="start")
    arrow(1220, 900, 1140, 900, GREEN, 3)
    svg.text(1180, 888, "SCK/SO/CS", size=11, fill=GREEN, anchor="middle")
    arrow(1220, 1000, 1140, 1000, "#c46a2b", 3)
    svg.text(1180, 988, "GATE", size=11, fill="#c46a2b", anchor="middle")

    # 关键网络 / 说明
    svg.rect(40, 1060, 1140, 340, "#fdfbf4", "#c9b98a", 1.4, 8)
    svg.text(58, 1094, "KEY NETS & DESIGN NOTES", size=17, fill=INK,
             anchor="start", weight="bold")
    notes = [
        "+5V: J1 VBUS→F1→SW1→F2→J4/J2/Q1; 2A path ≥2mm, star ground at C1-.",
        "+3V3: U3 AMS1117-3.3→U1/U4/UI; U2 74HCT4053 stays on +5V.",
        "HEAT_P/HEAT_N: C210 heater + thermocouple series; D2 freewheel; F2 400°C NC.",
        "T_P/T_N: 4053 X/Y→R9/R10 1k→MAX31855; BAT54S clamp to 3V3/GND; 1M bias.",
        "GATE/INH: P5.4 high = heater on = 4053 inhibited; R4 1k gate pulldown.",
        "FAULT: sensor fault bits, T>420°C, >100°C/cycle jump, 10 cycles full duty & T<100°C.",
        "LED: <300°C 2Hz; 300–400°C solid; >400°C 5Hz + heater off; FAULT 5Hz.",
        "ISP: P3.0/P3.1 shared with MAX31855; CS high + R17 SO pulldown; no jumper needed.",
    ]
    for i, t in enumerate(notes):
        svg.circle(66, 1124 + i * 33, 3.5, COPPER, "none", 0)
        svg.text(82, 1129 + i * 33, t, size=13, fill=INK, anchor="start")

    svg.rect(26, 1470, W - 52, 78, "#efe6d2", "#b9a57a", 1.2, 8)
    svg.text(52, 1502, "Pin-level netlist: see PCB_DESIGN.md §4. "
             "Footprints/placement: PCB_RENDER_NOTES.md.",
             size=13, fill=MUTED, anchor="start")
    svg.text(W - 52, 1502, "Render only — verify with KiCad / LCEDA DRC before fabrication.",
             size=13, fill=RED, anchor="end")

    svg.save("schematic.svg")


if __name__ == "__main__":
    render_top()
    render_bottom()
    render_schematic()
