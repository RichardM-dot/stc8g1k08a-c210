# PCB / 原理图对抗审查

日期：2026-11-21
审查对象：`docs/pcb/kicad/c210.kicad_sch`、`docs/pcb/kicad/c210_schematic.net`、`docs/pcb/kicad/c210_schematic.erc`、`docs/images/c210_schematic*.png`、`pcb_top.png`、`pcb_bottom.png`、`pcb_assembly.png`
结论：**v2 电气连接未发现 BLOCKER**；原理图 0 ERC errors / 7 warnings（5 条 4053 GND + 2 条生成符号名称比较）；PCB 渲染是“布局/装配示意”，不是可直接投产的 Gerber，这是本交付物最大的制造限制。

### v2 追加复核（重要）

- **CC2 短接到 GND（已修）**：v2 早期布局里 R1 的 GND 电源符号落在 R2 的 CC2 竖直短线上，ERC 报 `multiple_net_names`，网表把 J1.B5/R2.1 放进 GND。把 R1 移到 (110,72)、R2 移到 (125,90) 后，网表恢复 `/CC2 = J1.B5, R2.1`，GND 不再包含它们。
- **BAT54S 引脚顺序（已修）**：v1 用 `D_Schottky_Dual_Series_ACK`，其引脚是 A/common/K；实际 BAT54S 是 pin1=A、pin2=K、pin3=common。v2 用自定义 `BAT54S` 符号，网表为 D3.1=GND、D3.2=+3V3、D3.3=T_P；D4 同理。**投板时 SOT-23 封装必须按这个 pin1/2/3 对应。**

> 说明：独立子代理的审查初稿未在时限内完成；本报告由主代理按 KiCad 网表/ERC、原理图截图和 PCB 渲染逐项复核。所有“问题”都给出证据和修法。

---

## BLOCKER

未发现电气 BLOCKER。

网表逐项核对通过：

- U1 MAX31855：T+(3)=`T_P`，T-(2)=`T_N`，VCC(4)=`+3V3`，GND(1)=`GND`，SCK(5)=`SCK`，CS(6)=`CS`，SO(7)=`SO`，NC(8) 悬空。
- U2 74HCT4053：A0(12)=`HEAT_P`，B0(2)=`HEAT_N`，A(14)=`SW_X`→R9 1k→`T_P`，B(15)=`SW_Y`→R10 1k→`T_N`，A1/B1/C0/C1/C=GND，INH(6)=`INH`，VDD(16)=`+5V`，VEE(7)=VSS(8)=GND，S1/S2/S3(11/10/9)=GND。
- Q1：G(1)=`Q1_G`，D(2)=`HEAT_N`，S(3)=GND；R3 100Ω `GATE`→`Q1_G`；R4 1k `Q1_G`→GND。
- D2 SS34：K(1)=`HEAT_P`，A(2)=`HEAT_N`。
- D3/D4 BAT54S：pin1=GND，pin2=`+3V3`，pin3=`T_P`/`T_N`（v2 自定义符号，按实际 SOT-23 引脚）。
- J1：4×VBUS 全部在 `/VBUS`；4×GND+SHIELD 全部在 `GND`；D+/D-/SBU1/SBU2 为 no-connect。
- U3 AMS1117：VI(3)=`+5V`，VO(2)=`+3V3`，GND(1)=GND；C4/C5/C6/C7 正确。
- U4：P3.0=`SCK`，P3.1=`SO`，P3.2=`CS`，P3.3=`KEY`，P5.4=`GATE`，P5.5=`LED`，VCC=`+3V3`，GND。
- R1/R2 5.1k 在 CC1/CC2；R13 10k CS 上拉；R17 10k SO 下拉；F2 KSD9700 NC 在 `+5V`→`HEAT_F2`/J4。

ERC：**0 errors / 7 warnings**。5 条为 4053 未用脚/选择脚接 GND 的 `pin_to_pin`（Bidirectional ↔ Power output，有意为之）；2 条为生成符号与 `c210.kicad_sym` 的名称比较提示，引脚/图形一致，不是电气错误。

---

## MAJOR

### M1. PCB 渲染不是可投产 Gerber

- 证据：`docs/images/pcb_top.png` / `pcb_bottom.png` 由 `docs/pcb/gen_pcb.py` 生成；封装/焊盘是示意尺寸，未做真实 DRC/3D。
- 影响：不能直接发给板厂；投板前必须用 KiCad / 立创 EDA 重新建封装、跑 DRC、确认阻焊/钢网/拼板。
- 修法：以本文件的网表/BOM/placement 为输入，在 KiCad/LCEDA 重建原理图→PCB；跑 DRC；用实际连接器/外壳 3D 模型检查高度。

### M2. 42×24mm 板框很紧

- 证据：USB-C 16P + 5V/3A 滑动开关 + TO-252 + SOIC-16 + SOT-223 + 100µF 电解 + JST XH + 4-pin 2.54 ISP + 6×6 按键全部要放下；渲染把 J3/SW2 放到底面。
- 影响：如果外壳宽度 <42mm，或需要顶面操作按键/ISP，布局要重排；底面器件与外壳/手可能干涉。
- 修法：按外壳定 38×22 或 42×24；先 3D 检查；必要时改 1.27mm ISP 排针、SMD 按键、JST 1.25。

### M3. A3 v2 仍有个别标签拥挤

- 证据：v2 是 A3、三列、自定义符号；MAX31855/4053/USB-C 块内仍有若干标签/电源符号靠得较近。
- 影响：6000px PNG/PDF 放大可读，但全页缩略图会显得密；不是电气问题。
- 修法：`PCB_DESIGN.md §3.0` 已提供 1/4 裁切放大图；如要更松，可把 A3 改 A2 或把块间距加大，但会牺牲密度；当前优先保证网表和 0 errors。

---

## MINOR

1. **C7/R1/R2 曾在早期 PCB 渲染中缺失**。已在 `docs/pcb/gen_pcb.py` 的 BOTTOM 列表补上：R1/R2 5.1k 在 (7.0,20.0)/(7.0,21.2)，C7 0.1µF 在 (33.0,10.5)；底视图和 placement 表已更新。**投板前请再确认 C7 靠近 U2 VDD 的过孔/回流路径。**
2. **模拟地岛形状**：早期版本把 USB-C/CC 区也包进模拟岛；已改为从 y=8.2 起、x=9.5 起的多边形，避开 J1；星形颈仍在 C1 负极。渲染是概念分区，真实铺铜需在 EDA 里画 net tie 并跑 DRC。
3. **顶视图不显示底面 C7/R1/R2**：这是正常的顶视图；底视图/placement 表有。看装配时必须同时看顶/底。
4. **F2 是线束件**：不在 PCB 上；J4 只接 KSD9700 线束。上线前确认 J4 pin1=+5V（经 F2）、pin2=HEAT_P；F2 必须靠近手柄。
5. **Q1 散热/铺铜**：TO-252 tab 的散热过孔阵列是示意；实际铺铜面积/过孔数量按 2A、10–15mΩ 估算，热阻足够；投板前用 EDA 的载流/热计算复核。
6. **丝印密度**：顶视图 C1/SW1/U2 附近标签较密；真实 PCB 上需要把位号移到不压焊盘的位置，否则装配会看不清。
7. **无 3D 外壳/高度检查**：USB-C、电解、JST、排针、按键的高度未与外壳比对；这是机械设计输入，不是电气错误。
8. **U4 EPAD**：SOP8 无 EPAD；如果换 DFN8，pin9 EPAD 必须接 GND（当前网表标为 unconnected，因为按 SOP8 设计）。

---

## 建议保留不动的部分

- R4=1k 栅极下拉（抗 P5.4 上电 6.5ms 内部 4K 上拉）。
- R9/R10=1k + D3/D4 BAT54S 的 5V 共模钳位；R17 10k SO 下拉。
- 2.0mm 5V/2A 走线 + Q1 TO-252 铺铜/散热过孔。
- 星形地：C1 负极单点；加热电流不进 U1 地。
- 4053 的 X1/Y1=GND、Z 通道接 GND、A/B/C=GND 的选择逻辑。
- LED 300°C 常亮 / 400°C 快闪 / FAULT 5Hz 的行为。
- F1 3A PTC、F2 400°C NC、D1 TVS、D2 SS34 的保护组合。
