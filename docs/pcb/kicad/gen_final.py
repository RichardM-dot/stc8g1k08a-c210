#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终 A3 KiCad 原理图：使用 c210.kicad_sym 自定义符号 + A3 图框。

输出：
  docs/pcb/kicad/c210.kicad_sch
  docs/pcb/kicad/c210_schematic.pdf / .svg / .net / .erc
  docs/images/c210_schematic_v2.png + q1..q4
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
PCB = HERE.parent
PROJECT = PCB.parent
sys.path.insert(0, str(PCB))

import gen_kicad_sch as g  # noqa: E402
from kiutils.symbol import SymbolLib  # noqa: E402

# 自定义符号库
g.LIB._cache["c210"] = SymbolLib.from_file(str(HERE / "c210.kicad_sym"))
# BAT54S 只显示引脚号，隐藏 A1/common/K2 名称，减少块内文字拥挤
for _sym in g.LIB._cache["c210"].symbols:
    if _sym.entryName == "BAT54S":
        _sym.pinNamesHide = True

KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
SCH = HERE / "c210_schematic_v2.kicad_sch"
WKS = HERE / "c210.kicad_wks"


def build():
    b = g.Builder()
    b.sch.paper = g.PageSettings(paperSize="A3")

    # 图框
    b.block(15, 15, 140, 105, "1  USB-C 5V/3A INPUT")
    b.block(15, 110, 140, 160, "2  3.3V LDO")
    b.block(15, 165, 140, 270, "3  MAX31855 FRONT-END")
    b.block(150, 15, 275, 130, "4  MCU / KEY / LED / ISP")
    b.block(150, 135, 275, 215, "5  74HCT4053 ISOLATION")
    b.block(285, 15, 410, 160, "6  HEATER POWER")
    b.block(285, 165, 410, 228, "NOTES")
    b.block(150, 220, 230, 270, "SYSTEM BLOCK")

    # ---------------- 1. USB-C ----------------
    j1 = b.add("Connector", "USB_C_Receptacle_USB2.0_16P", "J1",
               "USB-C 16P", 45, 55, value_dx=0, value_dy=14,
               ref_dx=0, ref_dy=-14)
    b.stub(j1, "A4", "VBUS")
    b.stub(j1, "A5", "CC1")
    b.stub(j1, "B5", "CC2")
    b.stub(j1, "A1", "GND")
    b.stub(j1, "SH", "GND")
    for p in ("A6", "B6", "A7", "B7", "A8", "B8"):
        b.stub(j1, p, "", nc=True)

    f1 = b.add("Device", "Polyfuse", "F1", "3A PTC", 95, 28,
               value_dx=8, value_dy=0, ref_dx=-8, ref_dy=0)
    b.stub(f1, "1", "VBUS")
    b.stub(f1, "2", "+5V_SW")
    sw1 = b.add("Switch", "SW_SPST", "SW1", "5V 3A", 122, 28,
                value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(sw1, "1", "+5V_SW")
    b.stub(sw1, "2", "+5V")
    d1 = b.add("Device", "D_TVS", "D1", "SMAJ5.0A", 95, 60,
               value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(d1, "1", "+5V")
    b.stub(d1, "2", "GND")

    c1 = b.add("Device", "C_Polarized", "C1", "100µF", 50, 90,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c1, "1", "+5V")
    b.stub(c1, "2", "GND")
    c2 = b.add("Device", "C", "C2", "10µF", 75, 90,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c2, "1", "+5V")
    b.stub(c2, "2", "GND")
    c3 = b.add("Device", "C", "C3", "0.1µF", 100, 90,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c3, "1", "+5V")
    b.stub(c3, "2", "GND")
    r1 = b.add("Device", "R", "R1", "5.1k", 110, 72,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r1, "1", "CC1")
    b.stub(r1, "2", "GND")
    r2 = b.add("Device", "R", "R2", "5.1k", 125, 90,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r2, "1", "CC2")
    b.stub(r2, "2", "GND")

    # ---------------- 2. LDO ----------------
    u3 = b.add("c210", "AMS1117-3.3", "U3", "AMS1117-3.3", 50, 135,
               value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(u3, "3", "+5V")
    b.stub(u3, "2", "+3V3")
    b.stub(u3, "1", "GND")
    c4 = b.add("Device", "C", "C4", "10µF", 85, 135,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c4, "1", "+5V")
    b.stub(c4, "2", "GND")
    c5 = b.add("Device", "C", "C5", "10µF", 110, 135,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c5, "1", "+3V3")
    b.stub(c5, "2", "GND")
    c6 = b.add("Device", "C", "C6", "0.1µF", 130, 135,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c6, "1", "+3V3")
    b.stub(c6, "2", "GND")

    # ---------------- 3. MAX31855 ----------------
    u1 = b.add("c210", "MAX31855", "U1", "MAX31855", 90, 215,
               value_dx=0, value_dy=-8, ref_dx=0, ref_dy=8)
    b.stub(u1, "1", "GND")
    b.stub(u1, "2", "T_N")
    b.stub(u1, "3", "T_P")
    b.stub(u1, "4", "+3V3")
    b.stub(u1, "5", "SCK")
    b.stub(u1, "6", "CS")
    b.stub(u1, "7", "SO")
    b.stub(u1, "8", "", nc=True)

    r7 = b.add("Device", "R", "R7", "1M", 75, 195,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r7, "1", "T_P")
    b.stub(r7, "2", "GND")
    r8 = b.add("Device", "R", "R8", "1M", 75, 240,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r8, "1", "T_N")
    b.stub(r8, "2", "GND")
    c8 = b.add("Device", "C", "C8", "100nF", 60, 215,
               value_dx=-6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c8, "1", "T_P")
    b.stub(c8, "2", "T_N")
    c9 = b.add("Device", "C", "C9", "10nF", 55, 185,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c9, "1", "T_P")
    b.stub(c9, "2", "GND")
    c10 = b.add("Device", "C", "C10", "10nF", 55, 250,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c10, "1", "T_N")
    b.stub(c10, "2", "GND")
    d3 = b.add("c210", "BAT54S", "D3", "BAT54S", 30, 190,
               value_dx=0, value_dy=14, ref_dx=0, ref_dy=18)
    b.stub(d3, "1", "GND")
    b.stub(d3, "2", "+3V3")
    b.stub(d3, "3", "T_P")
    d4 = b.add("c210", "BAT54S", "D4", "BAT54S", 30, 245,
               value_dx=0, value_dy=14, ref_dx=0, ref_dy=18)
    b.stub(d4, "1", "GND")
    b.stub(d4, "2", "+3V3")
    b.stub(d4, "3", "T_N")
    c11 = b.add("Device", "C", "C11", "0.1µF", 120, 185,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c11, "1", "+3V3")
    b.stub(c11, "2", "GND")
    r13 = b.add("Device", "R", "R13", "10k", 120, 215,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r13, "1", "+3V3")
    b.stub(r13, "2", "CS")
    r17 = b.add("Device", "R", "R17", "10k", 120, 245,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r17, "1", "SO")
    b.stub(r17, "2", "GND")

    # ---------------- 4. MCU ----------------
    u4 = b.add("c210", "STC8G1K08A-8PIN", "U4", "STC8G1K08A-8PIN",
               225, 70, value_dx=0, value_dy=-8, ref_dx=0, ref_dy=8)
    b.stub(u4, "1", "GATE")
    b.stub(u4, "2", "+3V3", length=12.7)
    b.stub(u4, "3", "LED")
    b.stub(u4, "4", "GND", length=19.05)
    b.stub(u4, "5", "SCK")
    b.stub(u4, "6", "SO")
    b.stub(u4, "7", "CS")
    b.stub(u4, "8", "KEY")

    sw2 = b.add("Switch", "SW_Push", "SW2", "KEY", 180, 100,
                value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(sw2, "1", "KEY")
    b.stub(sw2, "2", "GND")
    r15 = b.add("Device", "R", "R15", "10k", 155, 85,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r15, "1", "+3V3")
    b.stub(r15, "2", "KEY")
    c14 = b.add("Device", "C", "C14", "100nF", 155, 115,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c14, "1", "KEY")
    b.stub(c14, "2", "GND")
    led1 = b.add("Device", "LED", "LED1", "red", 262, 90,
                 value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(led1, "1", "GND")
    b.stub(led1, "2", "LED_A")
    r14 = b.add("Device", "R", "R14", "330Ω", 250, 90,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r14, "1", "LED")
    b.stub(r14, "2", "LED_A")
    j3 = b.add("Connector", "Conn_01x04_Pin", "J3", "ISP", 175, 122,
               value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(j3, "1", "+3V3")
    b.stub(j3, "2", "GND")
    b.stub(j3, "3", "SCK")
    b.stub(j3, "4", "SO")
    led2 = b.add("Device", "LED", "LED2", "green", 260, 118,
                 value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(led2, "1", "GND")
    b.stub(led2, "2", "LED2_A")
    r16 = b.add("Device", "R", "R16", "1k", 245, 118,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r16, "1", "+3V3")
    b.stub(r16, "2", "LED2_A")
    c12 = b.add("Device", "C", "C12", "0.1µF", 180, 30,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c12, "1", "+3V3")
    b.stub(c12, "2", "GND")
    c13 = b.add("Device", "C", "C13", "10µF", 200, 30,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c13, "1", "+3V3")
    b.stub(c13, "2", "GND")

    # ---------------- 5. 4053 ----------------
    u2 = b.add("c210", "74HCT4053", "U2", "74HCT4053", 210, 175,
               value_dx=0, value_dy=-9, ref_dx=0, ref_dy=9)
    b.stub(u2, "1", "GND")
    b.stub(u2, "2", "HEAT_N")
    b.stub(u2, "3", "GND")
    b.stub(u2, "4", "GND")
    b.stub(u2, "5", "GND")
    b.stub(u2, "6", "INH")
    b.stub(u2, "7", "GND")
    b.stub(u2, "8", "GND")
    b.stub(u2, "9", "GND")
    b.stub(u2, "10", "GND")
    b.stub(u2, "11", "GND")
    b.stub(u2, "12", "HEAT_P")
    b.stub(u2, "13", "GND")
    b.stub(u2, "14", "SW_X")
    b.stub(u2, "15", "SW_Y")
    b.stub(u2, "16", "+5V")
    r9 = b.add("Device", "R", "R9", "1k", 170, 155,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r9, "1", "SW_X")
    b.stub(r9, "2", "T_P")
    r10 = b.add("Device", "R", "R10", "1k", 170, 195,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r10, "1", "SW_Y")
    b.stub(r10, "2", "T_N")
    r5 = b.add("Device", "R", "R5", "100Ω", 155, 160,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r5, "1", "GATE")
    b.stub(r5, "2", "INH")
    r6 = b.add("Device", "R", "R6", "10k", 155, 200,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r6, "1", "INH")
    b.stub(r6, "2", "GND")
    c7 = b.add("Device", "C", "C7", "0.1µF", 245, 155,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c7, "1", "+5V")
    b.stub(c7, "2", "GND")

    # ---------------- 6. 加热 ----------------
    f2 = b.add("c210", "KSD9700", "F2", "KSD9700 400°C NC", 300, 35,
               value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(f2, "1", "+5V")
    b.stub(f2, "2", "HEAT_F2")
    j4 = b.add("Connector", "Conn_01x02_Pin", "J4", "2-pin", 335, 35,
               value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(j4, "1", "HEAT_F2")
    b.stub(j4, "2", "HEAT_P")
    j2 = b.add("Connector", "Conn_01x02_Pin", "J2", "C210 JST", 378, 35,
               value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(j2, "1", "HEAT_P")
    b.stub(j2, "2", "HEAT_N")
    q1 = b.add("c210", "AOD4184", "Q1", "AOD4184", 380, 95,
               value_dx=8, value_dy=0, ref_dx=-8, ref_dy=0)
    b.stub(q1, "1", "Q1_G")
    b.stub(q1, "2", "HEAT_N")
    b.stub(q1, "3", "GND")
    d2 = b.add("Device", "D_Schottky", "D2", "SS34", 345, 85,
               value_dx=0, value_dy=-7, ref_dx=0, ref_dy=7)
    b.stub(d2, "1", "HEAT_P")
    b.stub(d2, "2", "HEAT_N")
    r3 = b.add("Device", "R", "R3", "100Ω", 330, 110,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r3, "1", "GATE")
    b.stub(r3, "2", "Q1_G")
    r4 = b.add("Device", "R", "R4", "1k", 310, 120,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r4, "1", "Q1_G")
    b.stub(r4, "2", "GND")

    # ---------------- 说明 ----------------
    b.text("C210 tip: heater + thermocouple series; J2 pin1=HEAT+, pin2=HEAT-.",
           292, 140, 1.5)
    b.text("F2 KSD9700 400°C NC is in the heater harness, close to the handle.",
           292, 147, 1.5)
    b.text("LED: <300°C 2Hz; 300-400°C solid; >400°C 5Hz + heater off; FAULT 5Hz.",
           292, 180, 1.5)
    b.text("Safety: F1 3A PTC; F2 400°C NC; D2 SS34; R4 1k gate pulldown; watchdog.",
           292, 188, 1.5)
    b.text("Firmware: 1Hz; 120ms measure / 800ms max duty;",
           292, 196, 1.48)
    b.text("  PID Kp=0.006 Ki=0.0015 Kd=0.030 FF=0.39",
           292, 203, 1.45)
    b.text("ISP: J3 1=+3V3 2=GND 3=P3.0/SCK 4=P3.1/SO; no USB-TTL VCC.",
           292, 211, 1.45)

    # 系统框图（文字流程，填满 middle-bottom）
    b.text("USB-C -> F1/SW1 -> +5V", 153, 232, 1.5)
    b.text("+5V -> U3 -> +3V3", 153, 240, 1.5)
    b.text("+5V -> F2 -> J4/J2 -> Q1", 153, 248, 1.5)
    b.text("J2 -> U2 -> R9/R10 -> U1 -> U4", 153, 256, 1.45)
    b.text("U4 -> Q1 / U2 / LED / KEY", 153, 264, 1.45)

    # PWR flags
    b.pwr_flag("+5V", 395, 218)
    b.pwr_flag("GND", 395, 228)

    b.sch.to_file(str(SCH))
    print("wrote", SCH)


def export():
    for args in [
        ["sch", "export", "pdf", "--drawing-sheet", str(WKS), "-o",
         str(HERE / "c210_schematic_v2.pdf"), str(SCH)],
        ["sch", "export", "svg", "--drawing-sheet", str(WKS), "-o",
         str(HERE), str(SCH)],
        ["sch", "export", "netlist", "-o",
         str(HERE / "c210_schematic_v2.net"), str(SCH)],
        ["sch", "erc", "-o", str(HERE / "c210_schematic_v2.erc"),
         "--severity-all", "--format", "report", str(SCH)],
    ]:
        cmd = [KICAD_CLI] + args
        print("+", " ".join(cmd))
        p = subprocess.run(cmd, text=True, capture_output=True)
        print((p.stdout or "")[-1500:])
        print((p.stderr or "")[-800:])


if __name__ == "__main__":
    build()
    export()
