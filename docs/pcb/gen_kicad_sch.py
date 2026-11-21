#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 C210 焊笔控制器的 KiCad 原理图（.kicad_sch）。

- 使用 KiCad 官方符号库：R/C/D/LED/FET/4053/MAX31855/STC8G/AMS1117/USB-C/连接器
- 每个引脚用短导线 + 网络标签/电源符号连接（net-label 风格）
- 生成后用 kicad-cli 导出 PDF/SVG，并导出网表做连接校验
- 输出：docs/pcb/c210_schematic.kicad_sch

运行：
  /tmp/kicadpy/bin/python docs/pcb/gen_kicad_sch.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from kiutils.schematic import Schematic
from kiutils.symbol import SymbolLib
from kiutils.items.common import (
    PageSettings, TitleBlock, Property, Position, Effects, Stroke, Font,
    Justify, ColorRGBA, Fill,
)
from kiutils.items.schitems import (
    SchematicSymbol, Connection, LocalLabel, NoConnect, Rectangle, Text,
    SymbolProjectInstance, SymbolProjectPath,
)

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
SYMBOL_DIR = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
SCH_PATH = HERE / "c210_schematic.kicad_sch"

PROJECT_NAME = "c210"
LAYOUT_SCALE = 1.0   # A2 页面；手动布局，避免缩放后符号/标签重叠


# ---------------------------------------------------------------------------
# 符号库
# ---------------------------------------------------------------------------
class Lib:
    def __init__(self):
        self._cache: dict[str, SymbolLib] = {}

    def get(self, libname: str, entry: str):
        if libname not in self._cache:
            self._cache[libname] = SymbolLib.from_file(
                str(SYMBOL_DIR / f"{libname}.kicad_sym")
            )
        for s in self._cache[libname].symbols:
            if s.entryName == entry:
                return deepcopy(s)
        raise KeyError(f"{libname}:{entry} not found")

    def pins(self, libname: str, entry: str):
        """返回 {pin_number: (x_mm, y_mm, angle, name)}，优先 style 1。"""
        sym = self.get(libname, entry)
        out = {}
        for unit in sym.units:
            for p in unit.pins:
                # style 1 优先；EPAD 等 style 0 的引脚只在没有同号时加入
                key = str(p.number)
                if key not in out or unit.styleId == 1:
                    out[key] = (p.position.X, p.position.Y,
                                float(p.position.angle or 0), p.name or "")
        return out


LIB = Lib()


# ---------------------------------------------------------------------------
# 构建器
# ---------------------------------------------------------------------------
class Builder:
    def __init__(self):
        self.sch = Schematic.create_new()
        self.sch.uuid = str(uuid4())
        self.sch.paper = PageSettings(paperSize="A2")
        self.sch.titleBlock = TitleBlock(
            title="C210 SOLDERING PEN CONTROLLER",
            date="2026-11-21",
            revision="1.0",
            company="ZCode / STC8G1K08A + MAX31855 + 74HCT4053",
            comments={
                1: "USB-C 5V/3A - JBC C210 - MAX31855 - no display",
                2: "Firmware: stc8g1k08a-c210 / SDCC -mmcs51",
                3: "Sheet 1/1",
            },
        )
        self._lib_ids: set[str] = set()
        self._pwr = 0
        self._parts: dict[str, dict] = {}

    # -- 库符号缓存 -----------------------------------------------------
    def _add_lib_symbol(self, libname: str, entry: str):
        lib_id = f"{libname}:{entry}"
        if lib_id in self._lib_ids:
            return
        sym = LIB.get(libname, entry)
        sym.libraryNickname = libname
        sym.entryName = entry
        self.sch.libSymbols.append(sym)
        self._lib_ids.add(lib_id)

    # -- 属性 -----------------------------------------------------------
    @staticmethod
    def _prop(key: str, value: str, x: float, y: float, angle: float = 0,
              hide: bool = False, size: float = 1.8) -> Property:
        return Property(
            key=key, value=value, id=0,
            position=Position(x, y, angle),
            effects=Effects(font=Font(height=size, width=size), hide=hide),
        )

    # -- 放置元件 -------------------------------------------------------
    def add(self, libname: str, entry: str, ref: str, value: str,
            x: float, y: float, unit: int = 1, footprint: str = "",
            hide_value: bool = False, hide_ref: bool = False,
            value_dx: float = 2.5, value_dy: float = 3.8,
            ref_dx: float = 2.5, ref_dy: float = -2.5) -> dict:
        # A2 布局坐标缩放到 A3，并吸附到 1.27 mm 网格
        x = round((x * LAYOUT_SCALE) / 1.27) * 1.27
        y = round((y * LAYOUT_SCALE) / 1.27) * 1.27
        self._add_lib_symbol(libname, entry)
        pins = LIB.pins(libname, entry)
        pin_uuids = {num: str(uuid4()) for num in pins}
        props = [
            self._prop("Reference", ref, x + ref_dx, y + ref_dy,
                       hide=hide_ref),
            self._prop("Value", value, x + value_dx, y + value_dy,
                       hide=hide_value),
            self._prop("Footprint", footprint, x, y, hide=True),
            self._prop("Datasheet", "~", x, y, hide=True),
        ]
        inst = SchematicSymbol(
            libraryNickname=libname, entryName=entry, libName=None,
            position=Position(x, y, 0), unit=unit, inBom=True,
            onBoard=True, properties=props, pins=pin_uuids,
            instances=[SymbolProjectInstance(
                name=PROJECT_NAME,
                paths=[SymbolProjectPath(
                    sheetInstancePath=f"/{self.sch.uuid}",
                    reference=ref, unit=unit,
                )],
            )],
        )
        self.sch.schematicSymbols.append(inst)
        part = {
            "ref": ref, "value": value, "lib": libname, "entry": entry,
            "x": x, "y": y, "unit": unit, "pins": pins,
            "pin_uuids": pin_uuids, "inst": inst,
        }
        self._parts[ref] = part
        return part

    # -- 引脚绝对坐标 / 外方向 -----------------------------------------
    @staticmethod
    def pin_xy(part: dict, pin: str) -> tuple[float, float, float]:
        lx, ly, pang, _ = part["pins"][str(pin)]
        # 只支持 angle=0 的放置；符号库 y 向上，原理图 y 向下
        return part["x"] + lx, part["y"] - ly, pang

    @staticmethod
    def outward(pin_angle: float) -> tuple[int, int]:
        # 引脚 angle 指向符号内部；外向是反方向（schematics y 向下）
        a = int(round(pin_angle)) % 360
        return {
            0: (-1, 0),      # 引脚在左，向外左
            180: (1, 0),     # 引脚在右，向外右
            90: (0, 1),      # 引脚在下，向外下
            270: (0, -1),    # 引脚在上，向外上
        }.get(a, (0, 0))

    # -- 导线 / 标签 ----------------------------------------------------
    def wire(self, pts):
        self.sch.graphicalItems.append(Connection(
            type="wire",
            points=[Position(x, y, 0) for x, y in pts],
            stroke=Stroke(width=0.0),
            uuid=str(uuid4()),
        ))

    def label(self, net: str, x: float, y: float, angle: float = 0,
              justify: str = "left"):
        self.sch.labels.append(LocalLabel(
            text=net,
            position=Position(x, y, angle),
            effects=Effects(
                font=Font(height=1.8, width=1.8),
                justify=Justify(horizontally=justify),
            ),
            uuid=str(uuid4()),
        ))

    def power(self, net: str, x: float, y: float):
        self._pwr += 1
        ref = f"#PWR{self._pwr:03d}"
        entry = net  # +5V / +3V3 / GND
        self._add_lib_symbol("power", entry)
        pins = LIB.pins("power", entry)
        pin_uuids = {num: str(uuid4()) for num in pins}
        # 电源符号的值文本位置：+5V/+3V3 在上，GND 在下
        vy = y - 4.6 if entry != "GND" else y + 4.6
        props = [
            self._prop("Reference", ref, x + 1.0, y - 1.0, hide=True),
            self._prop("Value", net, x, vy, hide=False, size=1.8),
            self._prop("Footprint", "", x, y, hide=True),
            self._prop("Datasheet", "~", x, y, hide=True),
        ]
        inst = SchematicSymbol(
            libraryNickname="power", entryName=entry, libName=None,
            position=Position(x, y, 0), unit=1, inBom=False,
            onBoard=False, properties=props, pins=pin_uuids,
            instances=[SymbolProjectInstance(
                name=PROJECT_NAME,
                paths=[SymbolProjectPath(
                    sheetInstancePath=f"/{self.sch.uuid}",
                    reference=ref, unit=1,
                )],
            )],
        )
        self.sch.schematicSymbols.append(inst)

    def pwr_flag(self, net: str, x: float, y: float):
        """PWR_FLAG + 电源符号，消除 ERC power_pin_not_driven。"""
        x = round((x * LAYOUT_SCALE) / 1.27) * 1.27
        y = round((y * LAYOUT_SCALE) / 1.27) * 1.27
        self._flag = getattr(self, "_flag", 0) + 1
        ref = f"#FLG{self._flag:03d}"
        self._add_lib_symbol("power", "PWR_FLAG")
        pins = LIB.pins("power", "PWR_FLAG")
        pin_uuids = {num: str(uuid4()) for num in pins}
        props = [
            self._prop("Reference", ref, x + 1.0, y - 1.0, hide=True),
            self._prop("Value", "PWR_FLAG", x, y - 4.0, hide=True),
            self._prop("Footprint", "", x, y, hide=True),
            self._prop("Datasheet", "~", x, y, hide=True),
        ]
        inst = SchematicSymbol(
            libraryNickname="power", entryName="PWR_FLAG", libName=None,
            position=Position(x, y, 0), unit=1, inBom=False,
            onBoard=False, properties=props, pins=pin_uuids,
            instances=[SymbolProjectInstance(
                name=PROJECT_NAME,
                paths=[SymbolProjectPath(
                    sheetInstancePath=f"/{self.sch.uuid}",
                    reference=ref, unit=1,
                )],
            )],
        )
        self.sch.schematicSymbols.append(inst)
        self.wire([(x, y), (x + 7.62, y)])
        self.power(net, x + 7.62, y)

    def stub(self, part: dict, pin: str, net: str, length: float = 6.35,
             nc: bool = False, force_dir: tuple[int, int] | None = None):
        px, py, pang = self.pin_xy(part, pin)
        if nc:
            self.sch.noConnects.append(NoConnect(
                position=Position(px, py, 0), uuid=str(uuid4())))
            return px, py
        dx, dy = force_dir if force_dir else self.outward(pang)
        ex, ey = px + dx * length, py + dy * length
        self.wire([(px, py), (ex, ey)])
        if net in ("+5V", "+3V3", "GND"):
            self.power(net, ex, ey)
        else:
            if dx < 0:
                self.label(net, ex, ey, justify="right")
            else:
                self.label(net, ex, ey, justify="left")
        return ex, ey

    # -- 图框 / 文字 ----------------------------------------------------
    def block(self, x1, y1, x2, y2, title: str):
        x1 *= LAYOUT_SCALE; y1 *= LAYOUT_SCALE
        x2 *= LAYOUT_SCALE; y2 *= LAYOUT_SCALE
        self.sch.shapes.append(Rectangle(
            start=Position(x1, y1, 0),
            end=Position(x2, y2, 0),
            stroke=Stroke(width=0.18, type="solid",
                          color=ColorRGBA(R=140, G=45, B=45, A=1)),
            fill=Fill(type="none"),
            uuid=str(uuid4()),
        ))
        self.sch.texts.append(Text(
            text=title,
            position=Position(x1 + 2.0, y1 + 5.0, 0),
            effects=Effects(
                font=Font(height=3.0, width=3.0, bold=True,
                          color=ColorRGBA(R=140, G=45, B=45, A=1)),
                justify=Justify(horizontally="left", vertically="bottom"),
            ),
            uuid=str(uuid4()),
        ))

    def text(self, s: str, x: float, y: float, size: float = 1.8,
             color=(30, 30, 30)):
        x *= LAYOUT_SCALE; y *= LAYOUT_SCALE
        size = max(size, 1.7)
        self.sch.texts.append(Text(
            text=s, position=Position(x, y, 0),
            effects=Effects(font=Font(height=size, width=size,
                                      color=ColorRGBA(R=color[0], G=color[1],
                                                      B=color[2], A=1))),
            uuid=str(uuid4()),
        ))

    def save(self):
        self.sch.to_file(str(SCH_PATH))
        print(f"wrote {SCH_PATH}")


# ---------------------------------------------------------------------------
# 具体电路
# ---------------------------------------------------------------------------
def build():
    b = Builder()

    # 图框（先画，元件在上层）
    b.block(20, 20, 215, 150, "1  USB-C 5V/3A INPUT & PROTECTION")
    b.block(20, 158, 215, 238, "2  3.3V LDO")
    b.block(20, 246, 215, 405, "3  MAX31855 SENSOR FRONT-END")
    b.block(235, 20, 425, 190, "4  MCU / BUTTON / LED / ISP")
    b.block(235, 198, 425, 320, "5  74HCT4053 ISOLATION")
    b.block(435, 20, 585, 210, "6  HEATER POWER STAGE")
    b.block(435, 220, 585, 370, "NOTES")
    b.pwr_flag("+5V", 195, 60)
    # +3V3 由 U3 VO 直接驱动，不需要 PWR_FLAG
    b.pwr_flag("GND", 195, 90)

    # ---------------- 1. USB-C ----------------
    j1 = b.add("Connector", "USB_C_Receptacle_USB2.0_16P", "J1",
               "USB-C 16P", 70, 68, value_dx=0, value_dy=14,
               ref_dx=0, ref_dy=-14)
    b.stub(j1, "A4", "VBUS")       # 所有 VBUS 堆叠脚
    b.stub(j1, "A5", "CC1")
    b.stub(j1, "B5", "CC2")
    b.stub(j1, "A1", "GND")
    b.stub(j1, "SH", "GND")
    for p in ("A6", "B6", "A7", "B7", "A8", "B8"):
        b.stub(j1, p, "", nc=True)

    f1 = b.add("Device", "Polyfuse", "F1", "3A PTC", 140, 42,
               value_dx=9, value_dy=0, ref_dx=-9, ref_dy=0)
    b.stub(f1, "1", "VBUS")
    b.stub(f1, "2", "+5V_SW")

    sw1 = b.add("Switch", "SW_SPST", "SW1", "5V 3A", 185, 42,
                value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(sw1, "1", "+5V_SW")
    b.stub(sw1, "2", "+5V")

    d1 = b.add("Device", "D_TVS", "D1", "SMAJ5.0A", 140, 80,
               value_dx=0, value_dy=-7, ref_dx=0, ref_dy=7)
    b.stub(d1, "1", "+5V")
    b.stub(d1, "2", "GND")

    c1 = b.add("Device", "C_Polarized", "C1", "100µF", 95, 112,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c1, "1", "+5V")
    b.stub(c1, "2", "GND")
    c2 = b.add("Device", "C", "C2", "10µF", 125, 112,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c2, "1", "+5V")
    b.stub(c2, "2", "GND")
    c3 = b.add("Device", "C", "C3", "0.1µF", 155, 112,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c3, "1", "+5V")
    b.stub(c3, "2", "GND")

    r1 = b.add("Device", "R", "R1", "5.1k", 165, 138,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r1, "1", "CC1")
    b.stub(r1, "2", "GND")
    r2 = b.add("Device", "R", "R2", "5.1k", 185, 138,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r2, "1", "CC2")
    b.stub(r2, "2", "GND")

    # ---------------- 2. LDO ----------------
    u3 = b.add("Regulator_Linear", "AP1117-15", "U3", "AMS1117-3.3",
               80, 195, value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(u3, "3", "+5V")
    b.stub(u3, "2", "+3V3")
    b.stub(u3, "1", "GND")
    c4 = b.add("Device", "C", "C4", "10µF", 135, 195,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c4, "1", "+5V")
    b.stub(c4, "2", "GND")
    c5 = b.add("Device", "C", "C5", "10µF", 165, 195,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c5, "1", "+3V3")
    b.stub(c5, "2", "GND")
    c6 = b.add("Device", "C", "C6", "0.1µF", 195, 195,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c6, "1", "+3V3")
    b.stub(c6, "2", "GND")

    # ---------------- 3. MAX31855 ----------------
    u1 = b.add("Sensor_Temperature", "MAX31855KASA", "U1", "MAX31855",
               125, 330, value_dx=0, value_dy=-8, ref_dx=0, ref_dy=8)
    b.stub(u1, "1", "GND")
    b.stub(u1, "2", "T_N")
    b.stub(u1, "3", "T_P")
    b.stub(u1, "4", "+3V3")
    b.stub(u1, "5", "SCK")
    b.stub(u1, "6", "CS")
    b.stub(u1, "7", "SO")
    b.stub(u1, "8", "", nc=True)

    r7 = b.add("Device", "R", "R7", "1M", 75, 300,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r7, "1", "T_P")
    b.stub(r7, "2", "GND")
    r8 = b.add("Device", "R", "R8", "1M", 75, 360,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r8, "1", "T_N")
    b.stub(r8, "2", "GND")
    c8 = b.add("Device", "C", "C8", "100nF", 105, 330,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c8, "1", "T_P")
    b.stub(c8, "2", "T_N")
    c9 = b.add("Device", "C", "C9", "10nF", 45, 315,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c9, "1", "T_P")
    b.stub(c9, "2", "GND")
    c10 = b.add("Device", "C", "C10", "10nF", 45, 345,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c10, "1", "T_N")
    b.stub(c10, "2", "GND")
    d3 = b.add("Device", "D_Schottky_Dual_Series_ACK", "D3", "BAT54S",
               45, 270, value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(d3, "1", "GND")
    b.stub(d3, "2", "T_P")
    b.stub(d3, "3", "+3V3")
    d4 = b.add("Device", "D_Schottky_Dual_Series_ACK", "D4", "BAT54S",
               45, 385, value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(d4, "1", "GND")
    b.stub(d4, "2", "T_N")
    b.stub(d4, "3", "+3V3")
    c11 = b.add("Device", "C", "C11", "0.1µF", 165, 290,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c11, "1", "+3V3")
    b.stub(c11, "2", "GND")
    r13 = b.add("Device", "R", "R13", "10k", 165, 345,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r13, "1", "+3V3")
    b.stub(r13, "2", "CS")
    r17 = b.add("Device", "R", "R17", "10k", 165, 380,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r17, "1", "SO")
    b.stub(r17, "2", "GND")

    # ---------------- 4. MCU / UI ----------------
    u4 = b.add("MCU_STC", "STC8G1K08A-36I-DFN8", "U4", "STC8G1K08A-8PIN",
               335, 100, value_dx=0, value_dy=-8, ref_dx=0, ref_dy=8)
    b.stub(u4, "1", "GATE")
    b.stub(u4, "2", "+3V3")
    b.stub(u4, "3", "LED")
    b.stub(u4, "4", "GND")
    b.stub(u4, "5", "SCK")
    b.stub(u4, "6", "SO")
    b.stub(u4, "7", "CS")
    b.stub(u4, "8", "KEY")
    b.stub(u4, "9", "", nc=True)   # DFN EPAD；SOP8 无此脚

    sw2 = b.add("Switch", "SW_Push", "SW2", "KEY", 285, 150,
                value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(sw2, "1", "KEY")
    b.stub(sw2, "2", "GND")
    r15 = b.add("Device", "R", "R15", "10k", 270, 135,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r15, "1", "+3V3")
    b.stub(r15, "2", "KEY")
    c14 = b.add("Device", "C", "C14", "100nF", 270, 165,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c14, "1", "KEY")
    b.stub(c14, "2", "GND")

    led1 = b.add("Device", "LED", "LED1", "red", 395, 130,
                 value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(led1, "1", "GND")
    b.stub(led1, "2", "LED_A")
    r14 = b.add("Device", "R", "R14", "330Ω", 370, 130,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r14, "1", "LED")
    b.stub(r14, "2", "LED_A")

    j3 = b.add("Connector", "Conn_01x04_Pin", "J3", "ISP", 285, 180,
               value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(j3, "1", "+3V3")
    b.stub(j3, "2", "GND")
    b.stub(j3, "3", "SCK")
    b.stub(j3, "4", "SO")

    led2 = b.add("Device", "LED", "LED2", "green", 420, 165,
                 value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(led2, "1", "GND")
    b.stub(led2, "2", "LED2_A")
    r16 = b.add("Device", "R", "R16", "1k", 395, 165,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r16, "1", "+3V3")
    b.stub(r16, "2", "LED2_A")

    c12 = b.add("Device", "C", "C12", "0.1µF", 290, 65,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c12, "1", "+3V3")
    b.stub(c12, "2", "GND")
    c13 = b.add("Device", "C", "C13", "10µF", 320, 65,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c13, "1", "+3V3")
    b.stub(c13, "2", "GND")

    # ---------------- 5. 4053 ----------------
    u2 = b.add("Analog_Switch", "CD4053B", "U2", "74HCT4053",
               340, 260, value_dx=0, value_dy=-9, ref_dx=0, ref_dy=9)
    # X/Y 通道
    b.stub(u2, "12", "HEAT_P")   # A0
    b.stub(u2, "13", "GND")      # A1
    b.stub(u2, "14", "SW_X")     # A
    b.stub(u2, "2", "HEAT_N")    # B0
    b.stub(u2, "1", "GND")       # B1
    b.stub(u2, "15", "SW_Y")     # B
    # Z 通道接地
    b.stub(u2, "5", "GND")
    b.stub(u2, "3", "GND")
    b.stub(u2, "4", "GND")
    # 控制/电源
    b.stub(u2, "6", "INH")
    b.stub(u2, "7", "GND")
    b.stub(u2, "8", "GND")
    b.stub(u2, "16", "+5V")
    b.stub(u2, "9", "GND")
    b.stub(u2, "10", "GND")
    b.stub(u2, "11", "GND")

    r9 = b.add("Device", "R", "R9", "1k", 295, 235,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r9, "1", "SW_X")
    b.stub(r9, "2", "T_P")
    r10 = b.add("Device", "R", "R10", "1k", 295, 285,
                value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r10, "1", "SW_Y")
    b.stub(r10, "2", "T_N")
    r5 = b.add("Device", "R", "R5", "100Ω", 270, 235,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r5, "1", "GATE")
    b.stub(r5, "2", "INH")
    r6 = b.add("Device", "R", "R6", "10k", 270, 285,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r6, "1", "INH")
    b.stub(r6, "2", "GND")
    c7 = b.add("Device", "C", "C7", "0.1µF", 380, 240,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(c7, "1", "+5V")
    b.stub(c7, "2", "GND")

    # ---------------- 6. 加热级 ----------------
    f2 = b.add("Switch", "SW_SPST_Temperature_NC", "F2",
               "KSD9700 400°C NC", 470, 55,
               value_dx=0, value_dy=-5, ref_dx=0, ref_dy=5)
    b.stub(f2, "1", "+5V")
    b.stub(f2, "2", "HEAT_F2")
    j4 = b.add("Connector", "Conn_01x02_Pin", "J4", "2-pin", 510, 55,
               value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(j4, "1", "HEAT_F2")
    b.stub(j4, "2", "HEAT_P")
    j2 = b.add("Connector", "Conn_01x02_Pin", "J2", "C210 JST", 550, 55,
               value_dx=0, value_dy=-6, ref_dx=0, ref_dy=6)
    b.stub(j2, "1", "HEAT_P")
    b.stub(j2, "2", "HEAT_N")

    q1 = b.add("Transistor_FET", "Q_NMOS_GDS", "Q1", "AOD4184",
               550, 130, value_dx=8, value_dy=0, ref_dx=-8, ref_dy=0)
    b.stub(q1, "1", "Q1_G")
    b.stub(q1, "2", "HEAT_N")
    b.stub(q1, "3", "GND")
    d2 = b.add("Device", "D_Schottky", "D2", "SS34", 505, 130,
               value_dx=0, value_dy=-7, ref_dx=0, ref_dy=7)
    b.stub(d2, "1", "HEAT_P")
    b.stub(d2, "2", "HEAT_N")
    r3 = b.add("Device", "R", "R3", "100Ω", 490, 155,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r3, "1", "GATE")
    b.stub(r3, "2", "Q1_G")
    r4 = b.add("Device", "R", "R4", "1k", 470, 155,
               value_dx=6, value_dy=0, ref_dx=-6, ref_dy=0)
    b.stub(r4, "1", "Q1_G")
    b.stub(r4, "2", "GND")

    # ---------------- 说明 ----------------
    b.text("C210 tip: heater + thermocouple in series; J2 pin1=HEAT+, pin2=HEAT-.",
           460, 185, 1.4)
    b.text("F2 KSD9700 400°C NC is in the heater harness, close to the handle.",
           460, 195, 1.4)

    b.text("5V/3A sink; CC1/CC2 5.1k; F1 3A PTC; D1 SMAJ5.0A TVS.",
           25, 40, 1.5)
    b.text("3.3V rail: U1/U4/UI; U2 74HCT4053 stays on +5V.", 25, 230, 1.5)
    b.text("T+/-: U2 X/Y -> R9/R10 1k -> MAX31855; BAT54S clamps to 3V3/GND; 1M bias.",
           25, 397, 1.4)
    b.text("U2: INH high = open = heater on / sensor isolated. X0=HEAT_P, Y0=HEAT_N.",
           240, 205, 1.4)
    b.text("U4 MCU: P3.0/P3.1 shared with MAX31855 and ISP; CS high in ISP.",
           240, 35, 1.4)

    notes = [
        "U4 STC8G1K08A SOP8: 1=P5.4 2=VCC 3=P5.5 4=GND",
        "  5=P3.0 6=P3.1 7=P3.2 8=P3.3",
        "U1 MAX31855 SOIC8: 1=GND 2=T- 3=T+ 4=VCC",
        "  5=SCK 6=CS 7=SO 8=NC",
        "U2 74HCT4053: X0=HEAT_P, Y0=HEAT_N, X/Y→R9/R10→T_P/T_N",
        "  INH=P5.4; X1=Y1=GND; VDD=+5V; VEE=VSS=GND",
        "LED: <300°C 2Hz; 300–400°C solid; >400°C 5Hz + heater off; FAULT 5Hz",
        "Safety: F1 3A PTC, F2 400°C NC, D2 SS34, R4 1k gate pulldown, watchdog",
        "Firmware: 1Hz; 120ms measure / 800ms max duty;",
        "  PID Kp=0.006 Ki=0.0015 Kd=0.030 FF=0.39",
        "ISP: P3.0/P3.1 shared; CS high; R17 SO pulldown; no jumper",
        "PCB renders / BOM / netlist: PCB_DESIGN.md",
    ]
    for i, line in enumerate(notes):
        b.text(line, 440, 240 + i * 10, 1.55)

    b.save()
    return b


# ---------------------------------------------------------------------------
# 导出 / 校验
# ---------------------------------------------------------------------------
def run(cmd):
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.stdout:
        print(p.stdout[-4000:])
    if p.stderr:
        print(p.stderr[-4000:])
    return p


def export():
    run([KICAD_CLI, "sch", "export", "pdf", "-o",
         str(HERE / "c210_schematic.pdf"), str(SCH_PATH)])
    run([KICAD_CLI, "sch", "export", "svg", "-o", str(HERE),
         str(SCH_PATH)])
    run([KICAD_CLI, "sch", "export", "netlist", "-o",
         str(HERE / "c210_schematic.net"), str(SCH_PATH)])
    run([KICAD_CLI, "sch", "erc", "-o", str(HERE / "c210_schematic.erc"),
         "--severity-all", "--format", "report", str(SCH_PATH)])


if __name__ == "__main__":
    build()
    export()
