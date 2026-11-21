#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 build/pid_step.csv 生成 PID 阶跃响应 SVG（纯标准库）。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "build" / "pid_step.csv"
OUT = ROOT / "docs" / "pcb" / "pid_step.svg"

W, H = 1800, 1100
L, R, T, B = 150, 120, 100, 140
PW, PH = W - L - R, H - T - B
INK = "#1d2a30"
MUTED = "#5d6b70"
GRID = "#e0d8c8"
BG = "#fbf8ef"
BLUE = "#2c6fbb"
RED = "#c0392b"
GREEN = "#2e7d32"

rows = []
for line in CSV.read_text().splitlines()[1:]:
    p = line.split(",")
    if len(p) >= 4:
        rows.append((float(p[0]), float(p[1]), float(p[2]), float(p[3])))
if not rows:
    raise SystemExit("empty csv")
tmax = rows[-1][0]
ymin, ymax = 0, 450
dmin, dmax = 0, 1


def x(t):
    return L + t / tmax * PW


def y(v):
    return T + (1 - (v - ymin) / (ymax - ymin)) * PH


def yd(v):
    return T + (1 - (v - dmin) / (dmax - dmin)) * PH


parts = []
parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
parts.append(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
parts.append(f'<text x="{L}" y="52" font-family="Inter, Helvetica, Arial" font-size="30" font-weight="bold" fill="{INK}">PID step response · 25 → 380 °C · 1 Hz control</text>')
parts.append(f'<text x="{L}" y="78" font-family="Inter, Helvetica, Arial" font-size="15" fill="{MUTED}">Plant: T[k+1] = T[k] + duty·78.7 − (T[k]−25)·0.086 · Kp=0.006 Ki=0.0015 Kd=0.030 FF=0.39</text>')

# grid
for v in range(0, 451, 50):
    yy = y(v)
    parts.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{L+PW}" y2="{yy:.1f}" stroke="{GRID}" stroke-width="1"/>')
    parts.append(f'<text x="{L-12}" y="{yy+5:.1f}" font-family="Inter, Helvetica, Arial" font-size="13" fill="{MUTED}" text-anchor="end">{v}</text>')
for t in range(0, int(tmax) + 1, 20):
    xx = x(t)
    parts.append(f'<line x1="{xx:.1f}" y1="{T}" x2="{xx:.1f}" y2="{T+PH}" stroke="{GRID}" stroke-width="1"/>')
    parts.append(f'<text x="{xx:.1f}" y="{T+PH+24}" font-family="Inter, Helvetica, Arial" font-size="13" fill="{MUTED}" text-anchor="middle">{t}</text>')

# axes
parts.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+PH}" stroke="{INK}" stroke-width="2"/>')
parts.append(f'<line x1="{L}" y1="{T+PH}" x2="{L+PW}" y2="{T+PH}" stroke="{INK}" stroke-width="2"/>')
parts.append(f'<text x="{L+PW/2}" y="{H-40}" font-family="Inter, Helvetica, Arial" font-size="16" fill="{INK}" text-anchor="middle">time (s)</text>')
parts.append(f'<text x="40" y="{T+PH/2}" font-family="Inter, Helvetica, Arial" font-size="16" fill="{INK}" text-anchor="middle" transform="rotate(-90 40 {T+PH/2})">temperature (°C)</text>')

# setpoint
yy = y(380)
parts.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{L+PW}" y2="{yy:.1f}" stroke="{RED}" stroke-width="2" stroke-dasharray="8 6" opacity="0.8"/>')
parts.append(f'<text x="{L+PW-8}" y="{yy-8:.1f}" font-family="Inter, Helvetica, Arial" font-size="12" fill="{RED}" text-anchor="end">setpoint 380 °C</text>')

# temperature curve
d = "M " + " L ".join(f"{x(t):.1f} {y(v):.1f}" for t, v, _, _ in rows)
parts.append(f'<path d="{d}" fill="none" stroke="{BLUE}" stroke-width="3"/>')
# duty curve (secondary, scaled)
d2 = "M " + " L ".join(f"{x(t):.1f} {yd(v):.1f}" for t, _, _, v in rows)
parts.append(f'<path d="{d2}" fill="none" stroke="{GREEN}" stroke-width="1.8" opacity="0.65"/>')

# legend
parts.append(f'<line x1="{L+20}" y1="{T+26}" x2="{L+60}" y2="{T+26}" stroke="{BLUE}" stroke-width="3"/>')
parts.append(f'<text x="{L+68}" y="{T+31}" font-family="Inter, Helvetica, Arial" font-size="14" fill="{INK}">temperature</text>')
parts.append(f'<line x1="{L+20}" y1="{T+50}" x2="{L+60}" y2="{T+50}" stroke="{GREEN}" stroke-width="2"/>')
parts.append(f'<text x="{L+68}" y="{T+55}" font-family="Inter, Helvetica, Arial" font-size="14" fill="{INK}">duty (0..1, scaled)</text>')
parts.append(f'<text x="{L+20}" y="{T+86}" font-family="Inter, Helvetica, Arial" font-size="14" fill="{MUTED}">peak 391.0 °C · overshoot 2.9 % · settle 46 s · steady-state error 0.000 °C</text>')

parts.append('</svg>')
OUT.write_text("\n".join(parts), encoding="utf-8")
print(f"wrote {OUT}")
