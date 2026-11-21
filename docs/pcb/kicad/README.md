# C210 KiCad 10 工程

本目录是 C210 焊笔控制器的 **KiCad 10 原理图工程**，包含自定义符号库、A3 图框、网表和 ERC 报告。

## 文件

| 文件 | 用途 |
|---|---|
| `c210.kicad_pro` | KiCad 工程文件（打开这个） |
| `c210.kicad_sch` | A3 原理图（自定义符号 + 标准符号） |
| `c210.kicad_sym` | 自定义符号库：STC8G1K08A-8PIN SOP8、MAX31855、74HCT4053、AMS1117-3.3、BAT54S、AOD4184、KSD9700 |
| `c210.kicad_wks` | A3 图框/标题栏（`C210 SOLDERING PEN CONTROLLER`、SHEET/DATE/REV/SIZE/FILE） |
| `sym-lib-table` | 指向 `c210.kicad_sym`（`${KIPRJMOD}`） |
| `fp-lib-table` | 空表；封装在 KiCad 里按 BOM/PCB_DESIGN 分配 |
| `c210_schematic.pdf` | 带 A3 图框的矢量原理图 |
| `c210_schematic.svg` | 带 A3 图框的 SVG |
| `c210_schematic.net` | KiCad 导出网表 |
| `c210_schematic.erc` | ERC 报告 |

## 打开

```bash
open -a "KiCad" docs/pcb/kicad/c210.kicad_pro
```

或在 KiCad 10 → File → Open → 选择 `c210.kicad_pro`。符号库通过同目录 `sym-lib-table` 自动加载；不要删除 `c210.kicad_sym`。

导出：

```bash
kicad-cli sch export pdf --drawing-sheet c210.kicad_wks -o c210_schematic.pdf c210.kicad_sch
kicad-cli sch export svg --drawing-sheet c210.kicad_wks -o . c210.kicad_sch
kicad-cli sch export netlist -o c210_schematic.net c210.kicad_sch
kicad-cli sch erc -o c210_schematic.erc --severity-all --format report c210.kicad_sch
```

## 网表/ERC 结果

- **0 ERC errors / 7 warnings**：
  - 5 条 `pin_to_pin`：4053 未用脚/选择脚接 GND，有意为之；
  - 2 条 `lib_symbol_mismatch`：`MAX31855` / `STC8G1K08A-8PIN` 嵌入符号与 `c210.kicad_sym` 的名称比较提示；引脚/图形一致，不是电气错误。
- 关键网表（真实导出，见 `c210_schematic.net`）：
  - `U1` MAX31855：T+3=`T_P`、T-2=`T_N`、SCK5、CS6、SO7、VCC4=`+3V3`、GND1。
  - `U2` 74HCT4053：`A0(12)=HEAT_P`、`B0(2)=HEAT_N`、`A(14)=SW_X→R9→T_P`、`B(15)=SW_Y→R10→T_N`、`INH(6)`、`VDD(16)=+5V`、`VEE/VSS=GND`。
  - `Q1` AOD4184：G1=`Q1_G`、D2=`HEAT_N`、S3=GND。
  - `D3/D4` BAT54S：**pin1=GND、pin2=+3V3、pin3=T_P/T_N**（实际 SOT-23 引脚）。
  - `J1` USB-C：4×VBUS、4×GND+SHIELD；D+/D-/SBU1/SBU2 NC。
  - `C7/R1/R2` 已包含：C7 `+5V/GND`，R1/R2 `CC1/CC2→GND`。
- **v2 修正记录**：
  - 早期 v2 布局 R1 的 GND 符号落在 R2 的 CC2 短线上，导致 CC2 短接 GND；已移动 R1/R2，网表恢复 `/CC2 = J1.B5, R2.1`。
  - v1 用 ACK 双二极管符号（pin2=common、pin3=K），与实际 BAT54S 不符；v2 用自定义 `BAT54S`，pin1=GND、pin2=+3V3、pin3=信号。投板 SOT-23 封装必须按此对应。

## 自定义符号引脚

| 符号 | 引脚 |
|---|---|
| `STC8G1K08A-8PIN` SOP8 | 1=P5.4, 2=VCC, 3=P5.5, 4=GND, 5=P3.0, 6=P3.1, 7=P3.2, 8=P3.3 |
| `MAX31855` SOIC8 | 1=GND, 2=T-, 3=T+, 4=VCC, 5=SCK, 6=CS, 7=SO, 8=NC |
| `74HCT4053` SOIC16 | 1=Y1, 2=Y0, 3=Z1, 4=Z, 5=Z0, 6=INH, 7=VEE, 8=GND/VSS, 9=C(S3), 10=B(S2), 11=A(S1), 12=X0, 13=X1, 14=X, 15=Y, 16=VDD |
| `AMS1117-3.3` SOT-223 | 1=GND, 2=VO, 3=VI；tab=VO |
| `BAT54S` SOT-23 | 1=A1, 2=K2, 3=common；钳位：1=GND, 2=+3V3, 3=信号 |
| `AOD4184` TO-252 | 1=G, 2=D, 3=S |
| `KSD9700` | 1/2，NC 温控开关 |

## 注意

- 图框是 A3 固定坐标；如果改 A2/A4，需要改 `c210.kicad_wks` 的坐标。
- `c210.kicad_pro` 是最小工程文件；封装分配/DRC 请在 KiCad 里完成。
- 原理图里的 `power` 符号来自 KiCad 标准库；`c210` 自定义符号已嵌入 `lib_symbols`，但工程仍依赖同目录 `c210.kicad_sym` 做 ERC 对比。
- 本工程不是 Gerber；PCB 渲染/placement 见 `../../PCB_DESIGN.md`。
