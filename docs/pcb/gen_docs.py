#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C210 工程补充图：叠层、布局规则、装配轴测图。
输出 docs/pcb/{stackup,layout_rules,pcb_assembly}.svg。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_pcb as g  # noqa: E402

INK = g.INK
MUTED = g.MUTED
RED = g.RED
BLUE = g.BLUE
GREEN = g.GREEN
ORANGE = "#c46a2b"
AMBER = "#b9770e"
POWER = g.POWER
COPPER = g.COPPER
CREAM = "#fbf8ef"
PANEL = "#fdfbf4"
EDGE = "#b9a57a"
FONT = g.FONT
MONO = g.MONO


def title(svg, w, main, sub):
    svg.rect(26, 26, w - 52, 100, "#efe6d2", EDGE, 1.2, 10)
    svg.text(52, 72, main, size=30, fill=INK, anchor="start", weight="bold",
             letter=1)
    svg.text(52, 104, sub, size=14, fill=MUTED, anchor="start")
    svg.text(w - 52, 72, "REV 1.0 · 2026-11-21", size=12, fill=MUTED,
             anchor="end")


def footer(svg, w, h, note):
    svg.rect(26, h - 96, w - 52, 70, "#efe6d2", EDGE, 1.2, 8)
    svg.text(52, h - 58, note, size=12, fill=MUTED, anchor="start")


# ---------------------------------------------------------------------------
# 叠层
# ---------------------------------------------------------------------------
def render_stackup():
    W = H = 1600
    svg = g.Svg(W, H, CREAM)
    title(svg, W, "PCB STACKUP", "2-layer · 1.0 mm FR-4 · 1 oz copper · "
          "external trace geometry")
    # 3D 叠层块
    x0, x1 = 260, 880
    y0 = 230
    layers = [
        ("Top silkscreen", 10, "#f5f2e8", "white legend"),
        ("Top solder mask", 22, "#0b5d2e", "green LPI"),
        ("Top copper", 40, "#d8b45a", "1 oz / ENIG"),
        ("FR-4 core", 360, "#c8b98f", "0.86 mm core"),
        ("Bottom copper", 40, "#d8b45a", "1 oz"),
        ("Bottom solder mask", 22, "#0b5d2e", "green LPI"),
        ("Bottom silkscreen", 10, "#f5f2e8", "white legend"),
    ]
    # 总厚度 450 px 对应 1.0 mm（示意，铜/mask 有夸大）
    total = sum(l[1] for l in layers)
    y = y0
    layer_mid = []
    for name, th, col, note in layers:
        hh = th / total * 450
        svg.rect(x0, y, x1 - x0, hh, col, "#6b5a35", 1.2, 3)
        svg.line(x0, y, x1, y, "#6b5a35", 0.8)
        layer_mid.append(y + hh / 2)
        y += hh
    # 固定间距标签，避免薄层文字互相压住
    label_y = [250, 282, 314, 470, 620, 652, 684]
    for (name, th, col, note), ly, mid in zip(layers, label_y, layer_mid):
        svg.line(x1, mid, x1 + 18, ly, MUTED, 0.9)
        svg.circle(x1, mid, 2.6, col, "#6b5a35", 0.6)
        svg.text(x1 + 24, ly - 2, name, size=13, fill=INK,
                 anchor="start", weight="bold")
        svg.text(x1 + 24, ly + 13, note, size=10, fill=MUTED,
                 anchor="start")
    # 总厚度标注
    svg.line(x0 - 22, y0, x0 - 22, y, MUTED, 1.4)
    svg.line(x0 - 30, y0, x0 - 14, y0, MUTED, 1.4)
    svg.line(x0 - 30, y, x0 - 14, y, MUTED, 1.4)
    svg.text(x0 - 34, (y0 + y) / 2, "1.0 mm", size=15, fill=INK,
             anchor="end", weight="bold", rotate=-90)
    svg.text(x0, y0 - 18, "Cross-section (not to scale: copper/mask exaggerated)",
             size=12, fill=MUTED, anchor="start")

    # 右侧表格
    tx, ty = 1210, 240
    svg.text(tx, ty, "TRACE WIDTH / CURRENT (1 oz, 10°C rise)", size=15,
             fill=INK, anchor="start", weight="bold")
    rows = [
        ("2.0 mm", "≈ 3.2 A", "heater 2A"),
        ("0.5 mm", "≈ 1.4 A", "3V3 rail"),
        ("0.3 mm", "≈ 1.0 A", "GATE"),
        ("0.25 mm", "≈ 0.9 A", "SCK/SO/CS"),
        ("0.2 mm", "≈ 0.8 A", "T_P/T_N"),
    ]
    yy = ty + 34
    svg.rect(tx, yy, 340, 26, "#e8dfca", "none", 0, 3)
    svg.text(tx + 8, yy + 18, "WIDTH", size=12, fill=INK, weight="bold")
    svg.text(tx + 92, yy + 18, "CURRENT", size=12, fill=INK, weight="bold")
    svg.text(tx + 200, yy + 18, "USE", size=12, fill=INK, weight="bold")
    yy += 26
    for i, (w, i_, use) in enumerate(rows):
        if i % 2 == 0:
            svg.rect(tx, yy, 340, 48, "#f7f1e2", "none", 0, 0)
        svg.text(tx + 8, yy + 20, w, size=13, fill=INK, family=MONO,
                 weight="bold")
        svg.text(tx + 92, yy + 20, i_, size=13, fill=INK, family=MONO)
        svg.text(tx + 200, yy + 20, use, size=9, fill=MUTED)
        svg.text(tx + 200, yy + 36, "", size=9, fill=MUTED)
        yy += 48
    svg.rect(tx, ty + 34, 340, yy - (ty + 34), "none", "#d8c9a9", 0.8)

    # 规则列表
    rules = [
        "Minimum trace / space: 0.2 mm (signal), 0.3 mm (5V), 0.3 mm board edge.",
        "Via: 0.3 mm drill / 0.6 mm pad; thermal via array under Q1 TO-252 tab.",
        "Surface finish: ENIG; solder mask: green LPI; board thickness 1.0 mm.",
        "2-layer, 1 oz copper both sides; bottom layer is the ground plane.",
        "Impedance not controlled; keep T_P/T_N short, paired and away from GATE.",
    ]
    yy = 760
    svg.text(tx - 290, yy, "STACKUP / DRC NOTES", size=15, fill=INK, anchor="start",
             weight="bold")
    for i, r in enumerate(rules):
        svg.circle(tx - 283, yy + 26 + i * 30, 3.2, COPPER, "none", 0)
        svg.text(tx - 270, yy + 31 + i * 30, r, size=11, fill=INK, anchor="start")

    footer(svg, W, H, "Render only — confirm stackup, trace width and current "
           "with the fab's impedance/current calculator before fabrication.")
    svg.save("stackup.svg")


# ---------------------------------------------------------------------------
# 布局规则
# ---------------------------------------------------------------------------
def render_rules():
    W = H = 1600
    svg = g.Svg(W, H, CREAM)
    title(svg, W, "PCB LAYOUT RULES", "42 × 24 mm · 2-layer · 1.0 mm · "
          "star ground · analog/digital separation")
    # 左侧 mini 板图
    bx, by = 70, 190
    bw, bh = 700, 400
    svg.rect(bx, by, bw, bh, "#0b5d2e", EDGE, 2.0, 12)
    # 功率区 / 模拟区
    svg.rect(bx + 20, by + 20, 300, bh - 40, "none", "#ffd54f", 2.0, 8,
             0.75, )
    svg.text(bx + 34, by + 48, "POWER / HEATER", size=14, fill="#ffe9a8",
             anchor="start", weight="bold")
    svg.rect(bx + 360, by + 20, 300, bh - 40, "none", "#a5d6a7", 2.0, 8)
    svg.text(bx + 374, by + 48, "ANALOG / MCU", size=14, fill="#c8e6c9",
             anchor="start", weight="bold")
    # 星形地
    svg.circle(bx + 360, by + bh - 50, 8, "#fff08a", "none", 0)
    svg.text(bx + 380, by + bh - 46, "STAR GND @ C1-", size=11, fill="#fff08a",
             anchor="start")
    # 5V 粗线
    svg.line(bx + 30, by + 90, bx + 680, by + 90, "#3aa76d", 18, 0.9)
    svg.line(bx + 30, by + 130, bx + 320, by + 130, "#3aa76d", 10, 0.8)
    # 模拟差分对
    svg.line(bx + 420, by + 110, bx + 620, by + 110, "#d9a441", 3)
    svg.line(bx + 420, by + 122, bx + 620, by + 122, "#d9a441", 3)
    svg.text(bx + 430, by + 100, "T_P/T_N paired", size=10, fill="#ffe0a3",
             anchor="start")
    # 散热过孔
    for i in range(3):
        for j in range(2):
            svg.circle(bx + 220 + i * 18, by + 300 + j * 18, 4, "#e3c15c",
                       "#a8842f", 1)
    svg.text(bx + 250, by + 312, "thermal vias under Q1", size=10,
             fill="#ffe9a8", anchor="start")
    # 图例
    svg.text(bx, by + bh + 28, "Mini floorplan: power left / analog right; "
             "single-point star at C1 negative.", size=12, fill=MUTED,
             anchor="start")

    # 右侧规则表
    tx, ty = 820, 190
    rules = [
        ("5V / 2A", "Trace ≥2.0 mm; VBUS→F1→SW1→J4/J2/Q1; copper pour on Q1 "
                    "drain/source; thermal vias under TO-252 tab."),
        ("3.3V", "0.5 mm; U3→U1/U4/UI; keep away from heater return."),
        ("GATE", "0.3 mm; route away from T_P/T_N; R3 100Ω at Q1, R4 1k pulldown."),
        ("T_P / T_N", "0.2 mm, short, paired; 4053 close to J2/U1; BAT54S at U1; "
                      "do not cross GATE or 5V switching node."),
        ("GND", "Bottom ground plane; power GND / analog GND split; single-point "
                "neck at C1 negative; no heater current through U1 ground."),
        ("Clearance", "0.2 mm min; 0.3 mm at board edge; 0.3 mm around 5V; "
                      "0.5 mm around Q1 tab/heat."),
        ("Vias", "0.3/0.6 mm; stitching vias around board edge; thermal via "
                 "array under Q1; avoid via-in-pad unless filled."),
        ("Placement", "MAX31855/U2 away from Q1 and 5V path; F1/D1 near USB-C; "
                      "CC resistors at connector; LDO away from heat."),
        ("Silkscreen", "+5V, +3V3, HEAT+, HEAT-, T+, T-, GATE, ISP, LED, KEY; "
                       "pin-1 dot; polarity marks; no text on pads."),
        ("Safety", "F1 3A PTC; F2 400°C NC in heater; D2 freewheel; R4 1k gate "
                   "pulldown; R6 10k INH pulldown; watchdog; fused/limited bench "
                   "supply for first power-up."),
    ]
    yy = ty
    for i, (name, text) in enumerate(rules):
        svg.rect(tx, yy, 700, 82, "#fdfbf4", "#d8c9a9", 1.0, 6)
        svg.text(tx + 14, yy + 24, name, size=14, fill=INK, anchor="start",
                 weight="bold")
        # 简单换行
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            if len(cur) + len(w) + 1 > 72:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            lines.append(cur)
        for j, line in enumerate(lines[:3]):
            svg.text(tx + 14, yy + 44 + j * 16, line, size=11, fill=MUTED,
                     anchor="start")
        yy += 90

    footer(svg, W, H, "Render only — run DRC and confirm creepage/clearance "
           "against the actual enclosure and connector footprints.")
    svg.save("layout_rules.svg")


# ---------------------------------------------------------------------------
# 装配轴测图
# ---------------------------------------------------------------------------
def render_assembly():
    W = H = 2000
    svg = g.Svg(W, H, CREAM)
    title(svg, W, "PCB ASSEMBLY (ISOMETRIC)", "42 × 24 mm · top-side components · non-structural illustration")
    S = 19.0
    CX, CY = 1000, 980

    def iso(x, y, z):
        px = CX + (x - y) * 0.866 * S
        py = CY + (x + y) * 0.5 * S - z * S
        return px, py

    def face(pts, fill, stroke="#1b2f22", sw=1.0, opacity=1.0):
        svg.poly([iso(x, y, z) for x, y, z in pts], fill, stroke, sw, opacity)

    def iso_box(x, y, w, h, z0, z1, fill, top=None, stroke="#1b2f22"):
        x0, x1 = x - w / 2, x + w / 2
        y0, y1 = y - h / 2, y + h / 2
        # 侧面（先画）
        face([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
             "#7a6a4a", stroke)
        face([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
             "#8a7650", stroke)
        # 顶面
        face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
             top or fill, stroke)
        # 顶面轮廓高光
        face([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
             "none", "#ffffff", 1.2, 0.35)

    # 板子：3D 板厚 1.0mm
    face([(0, 0, 0), (42, 0, 0), (42, 24, 0), (0, 24, 0)], "#0b5d2e", EDGE, 2.0)
    face([(0, 0, 1), (42, 0, 1), (42, 24, 1), (0, 24, 1)], "#146b35", "#6b5a35", 1.4)
    face([(0, 0, 0), (42, 0, 0), (42, 0, 1), (0, 0, 1)], "#0a4a24", "#6b5a35", 1.0)
    face([(42, 0, 0), (42, 24, 0), (42, 24, 1), (42, 0, 1)], "#093f1f", "#6b5a35", 1.0)

    # 主要顶面器件（x,y,w,h,height,color）
    parts = [
        ("J1 USB-C", 4.5, 12.0, 9.0, 7.4, 3.2, "#d9d5c8"),
        ("F1", 12.25, 19.1, 4.5, 3.2, 2.2, "#d9c7a3"),
        ("SW1", 19.85, 21.55, 8.7, 3.5, 3.0, "#202020"),
        ("C1 100µF", 18.15, 15.65, 6.3, 6.3, 6.0, "#2e4f8a"),
        ("U2 4053", 30.0, 14.0, 10.0, 4.0, 1.6, "#24282c"),
        ("U1 MAX31855", 15.0, 9.5, 5.0, 4.0, 1.6, "#24282c"),
        ("Q1 TO-252", 22.3, 6.05, 6.6, 6.1, 2.3, "#24282c"),
        ("J2 C210", 38.35, 6.9, 7.3, 5.8, 6.0, "#efe9da"),
        ("J4 KSD", 38.04, 18.27, 5.08, 2.54, 2.5, "#1f1f1f"),
    ]
    # 按 (x+y) 从远到近绘制，保证近处元件盖住远处元件
    for name, x, y, w, h, hh, col in sorted(parts, key=lambda p: p[1] + p[2]):
        iso_box(x, y, w, h, 1.0, 1.0 + hh, col)
    # 引线标注
    labels = [
        ("J1 USB-C", 4.5, 12.0, 3.2, 690, 1080),
        ("C1 100µF", 18.15, 15.65, 6.0, 760, 900),
        ("SW1", 19.85, 21.55, 3.0, 1080, 860),
        ("U2 74HCT4053", 30.0, 14.0, 1.6, 1420, 1040),
        ("Q1 AOD4184", 22.3, 6.05, 2.3, 1150, 1460),
        ("J2 C210", 38.35, 6.9, 6.0, 1580, 1480),
        ("U1 MAX31855", 15.0, 9.5, 1.6, 700, 1280),
    ]
    for name, x, y, z, tx, ty in labels:
        px, py = iso(x, y, z)
        svg.line(px, py, tx, ty, MUTED, 1.0)
        svg.circle(px, py, 3.0, "#ffffff", MUTED, 0.8)
        svg.text(tx, ty - 8, name, size=13, fill=INK, anchor="middle",
                 weight="bold")
    # 图例 / 说明
    svg.rect(70, 1560, 1860, 290, PANEL, EDGE, 1.2, 8)
    svg.text(94, 1598, "ASSEMBLY NOTES", size=17, fill=INK, anchor="start",
             weight="bold")
    notes = [
        "Top side: J1 USB-C (left edge), F1/SW1, C1, U2 74HCT4053, U1 MAX31855, "
        "Q1 TO-252, J2/J4 (right edge).",
        "Bottom side: U3 AMS1117-3.3, U4 STC8G1K08A, SW2 key, J3 ISP, "
        "LED1/LED2, R1/R2, R14/R15/R16, C7, C12/C13/C14.",
        "Q1 TO-252 tab is soldered to a copper pour with a thermal via array; "
        "D2 SS34 is the heater freewheel diode.",
        "F2 KSD9700 400°C NC is in the heater harness, not on the PCB; "
        "keep it close to the handle.",
        "This is a non-structural illustration, not a mechanical envelope; "
        "check connector heights and enclosure clearance before assembly.",
    ]
    for i, t in enumerate(notes):
        svg.circle(102, 1628 + i * 38, 3.5, COPPER, "none", 0)
        svg.text(118, 1633 + i * 38, t, size=12, fill=INK, anchor="start")

    footer(svg, W, H, "Render only — heights are approximate. Verify with the "
           "actual connector/enclosure 3D models before fabrication.")
    svg.save("pcb_assembly.svg")


if __name__ == "__main__":
    render_stackup()
    render_rules()
    render_assembly()
