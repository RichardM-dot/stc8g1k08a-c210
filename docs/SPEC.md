# STC8G1K08A-8PIN / JBC C210 焊笔控制器 — 执行规格（v1.0）

> 本文件是本次工作的唯一执行基准。所有子代理先读本文件，再读工程内已有代码。
> 原工程 `../stc8g1k08a-blink` **只读，不得修改**。

---

## 0. 目标与边界

| 项 | 值 |
|---|---|
| MCU | STC8G1K08A-8PIN，1T 8051，8KB Flash，256B idata + 1KB xdata |
| 供电 | USB-C 5V / 3A（5.1k CC1/CC2，5V sink） |
| 烙铁头 | JBC C210，2 线，加热丝与 K 型热电偶串联 |
| 测温 | MAX31855（SOIC-8，SPI，14 位，0.25°C/LSB，内置冷端补偿） |
| 加热隔离 | 74HCT4053 模拟开关：加热时 INH 高 → 断开热电偶；关断时闭合 |
| 加热开关 | AOD4184 N-MOSFET，P5.4 栅极，高 = 加热 |
| 显示 | 无屏幕 |
| 状态指示 | P5.5 LED，高电平点亮，串 330Ω |
| 按键 | P3.3，低有效，内部上拉 + 外部 10k 上拉，100nF 消抖 |
| 控制 | 裸机，Timer0 1ms tick，1Hz 控制周期，PID |
| 烧录 | `stcgal -p /dev/cu.usbmodemFX2348N1 -P stc8g -l 1200 -b 57600 -t 24000` |

**不做**：UART 遥测、屏幕、EEPROM 参数持久化、外壳建模、Gerber 投产文件。
PCB 渲染是“按网表绘制的详细布局/装配示意”，不是可直接投产的 Gerber；投板前必须用 KiCad/立创 EDA 复核封装与 DRC。

---

## 1. 路径与工具链

```text
原工程（只读）：/Users/theo-richard/workspace/projects/stc32/stc8g1k08a-blink
新工程：        /Users/theo-richard/workspace/projects/stc32/stc8g1k08a-c210
SDCC：          /Users/theo-richard/workspace/toolchains/sdcc-c251/bin/
stcgal：        /Users/theo-richard/workspace/toolchains/stcgal/bin/stcgal
串口：          /dev/cu.usbmodemFX2348N1
```

- `Makefile` 目标名 `stc8g1k08a-c210`。
- 保留 `Drivers/STC8G/FwLib_STC8`、`Drivers/STC8G/Inc/stc8g1k08a_regs.h`。
- 编译参数保持：
  `-mmcs51 --model-small --code-size 8192 --xram-size 1024 --iram-size 256`
- 删除 blink 的 `Core/Src/main.c`、`delay.c`、`diag.c`、`Core/Inc/delay.h`、`Config/stc8g1k08a_conf.h`（已删除）。
- 保留并扩展 `tools/verify.py` 框架；保留 `tools/dis8051.py`、`tools/flash_hotplug.py`、`tools/stcgal_retry.py`。

---

## 2. 硬件

### 2.1 系统框图

```text
USB-C 5V/3A
  VBUS ── F1 3A PTC ── SW1 5V 3A ── +5V ──┬── C1 100µF / C2 10µF / C3 0.1µF ── GND
                                           ├── U3 AMS1117-3.3 ── +3V3 ── MCU / MAX31855 / LED / 按键
                                           ├── U2 74HCT4053 VCC
                                           └── J4 温控开关 F2 ── J2 pin1 (HEAT+)
                                                                  │
                                                            C210 头（加热丝+热电偶）
                                                                  │
                                                            J2 pin2 (HEAT-) ── Q1 drain
                                                                                 │
                                                                               Q1 source ── GND
                                                                               Q1 gate ← R3 100Ω ← P5.4
```

测温路径：

```text
HEAT+ ── U2 X0 ── X ── R9 1kΩ ── T+ ── U1 MAX31855 T+
HEAT- ── U2 Y0 ── Y ── R10 1kΩ ── T- ── U1 MAX31855 T-
U2 INH ← R5 100Ω ← P5.4；R6 10k 下拉到 GND
U2 A/B/C = GND（选 X0/Y0/Z0）
```

### 2.2 引脚分配（6 个 I/O 全部用满）

| 引脚 | 功能 | 配置 |
|---|---|---|
| P3.0 | MAX31855 SCK | 推挽输出；同时是 ISP RX（CS 高时 SO 高阻） |
| P3.1 | MAX31855 SO | 高阻输入；同时是 ISP TX |
| P3.2 | MAX31855 CS | 推挽输出，10k 上拉到 +3V3，复位/烧录时保持高 |
| P3.3 | 按键 | 高阻输入 + 内部上拉 + 外部 10k 上拉，按键到 GND，100nF 消抖 |
| P5.4 | Q1 栅极 / 74HCT4053 INH | 推挽；高=加热、隔离传感器；低=关断、接通传感器 |
| P5.5 | 状态 LED | 推挽输出，高电平点亮，330Ω 到 LED 正极，负极 GND |

### 2.3 网表（逐网络）

#### 电源

| 网络 | 连接 |
|---|---|
| VBUS | J1 VBUS → F1 pin1 |
| +5V_SW | F1 pin2 → SW1 pin1 |
| +5V | SW1 pin2 → D1 阴极、C1+、C2、C3、U3 IN、C4、U2 VCC、C7、J4 pin1、R4?（不，R4 到 GND）、U2 VEE?（VEE=GND） |
| +3V3 | U3 OUT、C5、C6、U1 VCC、C11、U4 VCC、C12、C13、R13、R15、R16、LED2 阳极（经 R16）、U2?（**U2 仍用 +5V**） |
| GND | J1 GND、F1?（不）、C1-、C2、C3、D1 阳极、U3 GND、C4、C5、C6、C7、U2 GND/VEE、Q1 source、R4、R6、C11、R7、R8、C9、C10、U1 GND、U4 GND、C12、C13、R14、LED1 阴极、SW2、R15、C14、J3 GND、LED2 阴极、TP3 |

> 星形地：功率地（J1 GND、C1/C2、Q1 source、U2 VEE、C7）与模拟地（U1、U4、R7/R8、C8/C9/C10、R9/R10 的滤波地）在 C1 负极单点汇合。加热电流不得流过 U1 地。

#### USB-C / 输入保护

| 网络 | 连接 |
|---|---|
| CC1 | J1 CC1 → R1 5.1k → GND |
| CC2 | J1 CC2 → R2 5.1k → GND |
| VBUS | J1 VBUS → F1 pin1；D1 SMAJ5.0A 阴极到 +5V，阳极到 GND（放在 F1 之后、SW1 之前或 +5V 节点，按布局定；推荐 +5V 节点） |
| +5V | F1 pin2 → SW1 pin1；SW1 pin2 → +5V 节点 |

#### 3.3V LDO

| 网络 | 连接 |
|---|---|
| +5V | U3 IN、C4+ |
| +3V3 | U3 OUT、C5+、C6 |
| GND | U3 GND、C4-、C5-、C6- |

#### 加热回路

| 网络 | 连接 |
|---|---|
| +5V | J4 pin1（F2 温控开关一端） |
| HEAT_P | J4 pin2 → J2 pin1 → U2 X0 → R9 pin1 → D2 阴极 |
| HEAT_N | J2 pin2 → Q1 drain → D2 阳极 → U2 Y0 → R10 pin1 |
| GATE | P5.4 → R3 100Ω → Q1 gate；R4 1kΩ gate→GND；R5 100Ω P5.4→U2 INH；R6 10kΩ INH→GND |
| GND | Q1 source |

- Q1 = AOD4184（TO-252，N-MOSFET）。
- D2 = SS34，阴极 HEAT_P、阳极 HEAT_N，续流。
- F2 = KSD9700 400°C NC，串在 +5V 与 J4 之间，靠近手柄。
- R4 改为 **1kΩ**（不是 10k）：STC8G 的 P5.4 作普通 I/O 时上电约 6.5ms 内部 4K 上拉，10k 下拉不足以在 6.5ms 内把栅极压到阈值以下；1k 下拉可把栅极拉到约 0.66V，确保复位期间加热关断。

#### 测温前端

| 网络 | 连接 |
|---|---|
| HEAT_P | U2 X0（直连）；U2 X → R9 1kΩ → T_P |
| HEAT_N | U2 Y0（直连）；U2 Y → R10 1kΩ → T_N |
| T_P | U1 T+、R7 1M→GND、C8 100nF（T_P–T_N）、C9 10nF→GND、D3 BAT54S 钳位（pin3=T_P，pin1=GND，pin2=+3V3） |
| T_N | U1 T-、R8 1M→GND、C8 另一端、C10 10nF→GND、D4 BAT54S 钳位（pin3=T_N，pin1=GND，pin2=+3V3） |
| SCK | P3.0 → U1 SCK |
| SO | U1 SO → P3.1；**R17 10k 下拉到 GND**（芯片缺失时 SO 为确定低电平，裸板自检可预测） |
| CS | P3.2 → U1 CS；R13 10k 上拉到 +3V3 |
| +3V3 | U1 VCC、C11 0.1µF→GND |

**关键优化（相对原始规格）**：

1. R9/R10 从 100Ω 改为 **1kΩ**，并在 T+/T- 各加一个 **BAT54S** 双二极管钳位到 +3V3/GND。原因：加热关断时 74HCT4053 把 HEAT+/HEAT- 的约 5V 共模直接送到 MAX31855 输入，超过其 VCC+0.3V 绝对最大额定；100Ω 时钳位电流约 14mA，1kΩ 时约 1.4mA，BAT54S 把共模钳在约 3.6V，差模热电偶信号几乎不衰减。
2. 1M 偏置电阻保留，用于 4053 断开时把浮空输入拉到 GND。
3. 4053 仍用 +5V 供电（VCC=+5V，VEE=GND），保证 5V 共模在开关输入范围内；钳位放在开关之后、MAX31855 之前。
4. 新增 R17 10kΩ SO 下拉：没有 MAX31855 时 SO 为低，裸板自检可预测（上电读 0°C → STANDBY；按键后无升温 → 10 个周期后 FAULT）。

#### 74HCT4053

| 引脚 | 连接 |
|---|---|
| VCC (16) | +5V |
| GND (8) | GND |
| VEE (7) | GND |
| A/B/C (11/10/9) | GND |
| INH (6) | R5/R6 节点 |
| X0 (12) | HEAT_P（直连） |
| X (14) | R9 1kΩ → T_P |
| X1 (13) | GND |
| Y0 (1) | HEAT_N（直连） |
| Y (15) | R10 1kΩ → T_N |
| Y1 (2) | GND |
| Z0 (3) / Z1 (4) / Z (5) | GND（未用） |

> **最终网表（固件/PCB/文档统一）**：
> - HEAT_P → U2 X0；U2 X → R9 1k → T_P
> - HEAT_N → U2 Y0；U2 Y → R10 1k → T_N
> 这样 4053 输入看到 HEAT_P/HEAT_N 的 5V（在 5V 供电范围内）；R9/R10 与 BAT54S 在开关之后限制/钳位 MAX31855 输入。BAT54S 紧靠 U1 的 T+/T-。

#### MCU / 按键 / LED / ISP

| 网络 | 连接 |
|---|---|
| P3.0 | U1 SCK、J3 pin3（ISP RX） |
| P3.1 | U1 SO、J3 pin4（ISP TX） |
| P3.2 | U1 CS、R13 10k 到 +3V3 |
| P3.3 | SW2 到 GND、R15 10k 到 +3V3、C14 100nF 到 GND、J3?（不接） |
| P5.4 | R3 100Ω 到 Q1 gate、R5 100Ω 到 U2 INH |
| P5.5 | R14 330Ω 到 LED1 阳极，LED1 阴极 GND |
| +3V3 | U4 VCC、C12 0.1µF、C13 10µF、J3 pin1、R16 1k → LED2 绿 → GND |
| GND | U4 GND、J3 pin2、C12/C13/C14、LED1 阴极、LED2 阴极、SW2 另一端 |

**ISP 接线**：J3 = +3V3 / GND / P3.0 / P3.1。USB-TTL 只接 TX→P3.0、RX→P3.1、GND；**不要接 USB-TTL 的 VCC**（板子自己供电）。烧录时 P3.2 由 R13 上拉为高，MAX31855 CS 高 → SO 高阻，不冲突。

### 2.4 BOM（含新增保护件）

| Ref | 值 | 封装 | 数量 | 备注 |
|---|---|---|---|---|
| J1 | USB-C 16P 母座 | SMD | 1 | 5V 3A sink，CC1/CC2 各 5.1k |
| F1 | PTC 3A hold / 6A trip | 1812 | 1 | 自恢复保险 |
| SW1 | 5V 3A 滑动开关 | THT | 1 | 总电源 |
| D1 | SMAJ5.0A | SMA | 1 | TVS |
| C1 | 100µF/10V | SMD 电解 6.3×6.3 | 1 | 5V 储能 |
| C2 | 10µF/10V | 0805 | 1 | |
| C3 | 0.1µF | 0603 | 1 | |
| U3 | AMS1117-3.3 | SOT-223 | 1 | 3.3V LDO |
| C4 | 10µF/10V | 0805 | 1 | LDO 输入 |
| C5 | 10µF/10V | 0805 | 1 | LDO 输出 |
| C6 | 0.1µF | 0603 | 1 | |
| U2 | 74HCT4053 | SOIC-16 | 1 | 模拟开关，+5V 供电 |
| C7 | 0.1µF | 0603 | 1 | U2 去耦 |
| R5 | 100Ω | 0603 | 1 | INH 串联 |
| R6 | 10kΩ | 0603 | 1 | INH 下拉 |
| J2 | 2-pin JST XH 2.5mm | THT | 1 | C210 头 |
| J4 | 2-pin 2.54 | THT | 1 | 温控开关 F2 |
| F2 | KSD9700 400°C NC | 线束 | 1 | 串在加热回路，靠近手柄 |
| Q1 | AOD4184 | TO-252 | 1 | N-MOSFET，2A |
| R3 | 100Ω | 0603 | 1 | 栅极串联 |
| R4 | **1kΩ** | 0603 | 1 | 栅极下拉（原 10k，改 1k 抗上电 4K 上拉） |
| D2 | SS34 | SMA | 1 | 续流 |
| U1 | MAX31855 | SOIC-8 | 1 | K 型热电偶 |
| C11 | 0.1µF | 0603 | 1 | U1 去耦 |
| R13 | 10kΩ | 0603 | 1 | CS 上拉 |
| R17 | **10kΩ** | 0603 | 1 | SO 下拉（新增，芯片缺失时读数确定） |
| R7/R8 | 1MΩ | 0603 | 2 | T+/T- 偏置 |
| R9/R10 | **1kΩ** | 0603 | 2 | T+/T- 串联限流（原 100Ω） |
| D3/D4 | **BAT54S** | SOT-23 | 2 | T+/T- 到 +3V3/GND 钳位（新增） |
| C8 | 100nF | 0603 | 1 | 差分滤波 |
| C9/C10 | 10nF | 0603 | 2 | 共模滤波 |
| U4 | STC8G1K08A-8PIN | SOP8 | 1 | MCU |
| C12 | 0.1µF | 0603 | 1 | MCU 去耦 |
| C13 | 10µF | 0805 | 1 | MCU 去耦 |
| LED1 | 红色 0805 | 0805 | 1 | 状态 |
| R14 | 330Ω | 0603 | 1 | LED 限流 |
| SW2 | 6×6 轻触开关 | THT | 1 | 可选 |
| R15 | 10kΩ | 0603 | 1 | 按键上拉 |
| C14 | 100nF | 0603 | 1 | 按键消抖 |
| J3 | 4-pin 2.54 | THT | 1 | ISP：+3V3/GND/P3.0/P3.1 |
| LED2 | 绿色 3mm | THT | 1 | 电源指示（可选） |
| R16 | 1kΩ | 0603 | 1 | 电源 LED |
| TP1–TP6 | 测试点 | 1.5mm pad | 6 | +5V/+3V3/GND/GATE/T+/T- |
| MH1–MH4 | M2 安装孔 | Ø2.2mm | 4 | 按外壳调整 |

### 2.5 PCB 布局 / 走线 / 安全

- 2 层板，建议 **1.0mm 厚**，1oz 铜；尺寸约 **38×22mm**（按外壳调整；渲染用 38×22mm）。
- 5V/2A 路径：USB-C VBUS→F1→SW1→J4/J2/Q1 走线 ≥2mm；Q1 drain/source 铺铜；TO-252 下方散热过孔。
- 星形地：功率地与模拟地在 C1 负极单点连接；加热电流不能流过 U1 地。
- MAX31855 远离 Q1、5V 大电流走线和加热连接器；T+/T- 走线短、成对、远离 GATE；BAT54S 紧靠 U1 输入；R9/R10 靠近 U1。
- C210 两根线用双绞线，尽量短。
- 74HCT4053 靠近 MAX31855 和 J2，缩短模拟路径。
- F1/D1 靠近 USB-C；CC 电阻靠近连接器；LDO 远离热源。
- 丝印：`+5V`、`+3V3`、`HEAT+`、`HEAT-`、`T+`、`T-`、`GATE`、`ISP`、`LED`、`KEY`。
- 安全：5V 低压，但烙铁头 380°C；F2 必须串在加热回路并靠近手柄；首次上电用限流电源，不要无人值守。
- 复位/上电期间：R4=1k 下拉 Q1 gate；R6=10k 下拉 INH；P5.4 内部 4K 上拉约 6.5ms，1k 下拉确保 Q1 关断。

---

## 3. 固件设计

### 3.1 文件结构

```text
Config/stc8g1k08a_c210_conf.h
Core/Inc/{app.h,max31855.h,pid.h,heater.h,led.h,button.h,timer.h}
Core/Src/{main.c,app.c,max31855.c,pid.c,heater.c,led.c,button.c,timer.c}
tools/{verify.py,dis8051.py,test_pid.c}
```

### 3.2 状态机

```text
BOOT
  ├─ 初始化 GPIO / Timer0 1ms / MAX31855 / PID / LED / 按键 / WDT
  ├─ 等 150ms，读一次 MAX31855
  │    ├─ 故障 → FAULT
  │    └─ 正常 → STANDBY
STANDBY
  ├─ 加热关断，LED 1Hz 慢闪（100ms 亮 / 900ms 灭）
  ├─ 按键短按 → HEATING
  └─ 传感器故障 → FAULT
HEATING
  ├─ 1s 控制周期：
  │   1) t=0：加热关断
  │   2) t=0..120ms：等 4053 闭合 + MAX31855 转换
  │   3) t=120ms：读温度、PID、得到 duty_ms
  │   4) t=120..120+duty_ms：加热
  │   5) 剩余时间 idle
  ├─ T<300 → LED 2Hz 闪（250ms 亮/250ms 灭）
  ├─ 300≤T≤400 → LED 常亮
  ├─ T>400 → 关加热，LED 5Hz 快闪（100ms 亮/100ms 灭）；降到 400 以下可恢复
  ├─ 按键短按 → STANDBY
  ├─ 传感器故障 / T>420 → FAULT
  ├─ |T - T_prev| > 100°C/周期 → FAULT
  └─ 连续 10 个周期 duty≈100% 且 T<100°C → FAULT
FAULT
  ├─ 加热关断，LED 5Hz 快闪
  ├─ 按键长按 3s 或重新上电清除；若温度仍 >350°C 则拒绝清除
  └─ 看门狗持续复位则重新进入 FAULT（传感器仍故障）
```

### 3.3 MAX31855 驱动

```c
void max31855_init(void);                 /* CS=1, SCK=0, SO 输入 */
uint8_t max31855_read(int16_t *tc_x4);    /* 0=成功, 1=故障 */
```

- 位操作 SPI：CS 低 → 32 个时钟（SCK 高、读 SO、SCK 低）→ CS 高。
- 解析：
  - `raw` 32 位；`tc_x4 = (int16_t)((int32_t)raw >> 18)`（14 位有符号，0.25°C/LSB）；
  - 故障位 `raw & 0x07`：bit0 开路、bit1 对 GND 短路、bit2 对 VCC 短路；
  - 内部冷端温度 `(raw >> 4) & 0x0FFF`（可选，仅调试）。
- 读数 < -50°C 或 >500°C 按故障处理。
- 加热关断后等 120ms 再读。MAX31855 自由运行，120ms 是“20ms 开关稳定 + 100ms 转换”的折中；实际读数最多比关断时刻晚 100ms，对慢热系统影响 <0.2°C。若实测发现混入加热期数据，可把 `C210_MEASURE_MS` 调到 150~200ms 并相应降低 `C210_MAX_DUTY_MS`。

### 3.4 PID

```c
typedef struct {
    float kp, ki, kd;
    float integral;
    float prev_meas;
    float d_filt;
    float out;
    float ff;
    float i_limit;
    float i_sep;
    float d_alpha;
} pid_t;

void pid_init(pid_t *p, float kp, float ki, float kd);
void pid_reset(pid_t *p);
float pid_compute(pid_t *p, float setpoint, float meas, float dt);
```

- 输出 `0.0..1.0`，映射到 `duty_ms = (uint16_t)(out * 800.0f + 0.5f)`。
- 误差 `e = setpoint - meas`。
- **前馈**：`out = kp*e + ki*integral + kd*d_filt + ff`，`ff = 0.39`（380°C、25°C 环境、10W 头的稳态占空比估计）。前馈让控制器一开始就接近稳态占空比，避免积分从 0 慢慢爬。
- **积分分离**：`|e| <= 50°C` 时才累加积分；`|e| > 50°C` 不累加。
- **抗饱和**：积分限幅 `±2000`；若输出已 ≥1 且 e>0，或输出已 ≤0 且 e<0，不再向同方向积分。
- **微分**：对测量值微分（`d_raw = -(meas - prev_meas)/dt`），一阶低通 `d_filt += alpha*(d_raw - d_filt)`，`alpha=0.2`。
- **整定参数（归一化输出）**：`Kp=0.006, Ki=0.0015, Kd=0.030, FF=0.39`。
  - 原始规格的 `Kp=4.0, Ki=0.02, Kd=20.0` 对应“输出毫秒”的量纲，直接用于 0..1 归一化输出会严重饱和/振荡；上述参数按 1s 周期、10W 头、25→380°C 阶跃整定，主机测试超调 ~3%、调节时间 ~45s、稳态误差 ~0°C。
- 故障时 `pid_reset()` 并输出 0。

### 3.5 加热 / 测量时序

- Timer0 模式 0（16 位自动重装），1ms tick；`AUXR |= 0x80`，`TMOD &= 0xF0`，reload = `65536 - 24000`。
- `P5.4` 高 = 加热，低 = 关断；74HCT4053 INH 跟随 P5.4。
- 控制周期 1000ms：
  - 0–120ms：P5.4 低，4053 闭合，等 MAX31855 新转换；
  - 120ms：读温度 + PID，得到 `duty_ms`；
  - 120–(120+duty_ms)：P5.4 高，加热；
  - 剩余时间：P5.4 低，等待下一周期。
- `duty_ms` 限制 0..800；如果 `duty_ms=800`，测量 120ms + 加热 800ms + 余量 80ms。
- 加热时 4053 断开，MAX31855 完全隔离 5V；关断后 20ms 等开关稳定，再等 100ms 转换。

### 3.6 LED / 按键

- P5.5 推挽输出，高电平点亮；R14 330Ω。
- `led_set_mode(LED_OFF/STANDBY/HEATING/SOLID/FAST)`；`led_task()` 每 1ms 调用，非阻塞。
- 模式：
  - STANDBY：100ms 亮 / 900ms 灭；
  - HEATING：250ms 亮 / 250ms 灭（<300°C）；
  - SOLID：常亮（300–400°C）；
  - FAST：100ms 亮 / 100ms 灭（>400°C 或 FAULT）。
- 按键 P3.3：内部上拉 `GPIO_SetPullUp(GPIO_Port_3, GPIO_Pin_3, HAL_State_ON)` + 外部 10k；20ms 消抖；短按切换 STANDBY/HEATING；长按 3s 清故障。
- 短按定义：按下 20ms~1000ms 后释放；长按：按住 ≥3000ms 触发一次，释放不再触发短按。

### 3.7 故障保护 / 看门狗

- MAX31855 故障位 → 立即关加热、FAULT。
- T > 400°C：关加热、快闪；降到 400°C 以下自动恢复（回差 5°C，即 ≤395°C 恢复）。
- T > 420°C：锁存 FAULT，必须冷却 + 长按/重新上电清除。
- 温度突变 > 100°C/周期 → FAULT（传感器/干扰）。
- 连续 10 个周期 `duty>=790ms` 且 T < 100°C → FAULT（加热回路/传感器异常）。
- 看门狗：`WDT_CONTR = 0x35`（EN_WDT=1, CLR_WDT=1, PS=5；24MHz 约 1.05s），主循环定期喂狗；复位时 P5.4 高阻、R4 1k 下拉，加热关断。
- 硬件兜底：F1 3A PTC、F2 400°C KSD、Q1 栅极 1k 下拉、D2 续流、BAT54S 输入钳位。

### 3.8 配置参数（`Config/stc8g1k08a_c210_conf.h`）

```c
#define MAIN_Fosc              24000000UL
#define C210_SETPOINT_C        380
#define C210_LED_SOLID_LOW     300
#define C210_LED_SOLID_HIGH    400
#define C210_OVERTEMP_C        420
#define C210_PERIOD_MS         1000
#define C210_MEASURE_MS        120
#define C210_MAX_DUTY_MS       800
#define C210_AUTO_START        0     /* 1=上电自动加热；0=按键启动 */
#define C210_TEMP_OFFSET_X4    0     /* 校准偏移，0.25°C 单位 */
#define C210_TC_GAIN           1.0f  /* 热电偶增益校准；BAT54S 钳位动态电阻会带来约 1–4% 误差 */
#define C210_PID_KP            0.006f
#define C210_PID_KI            0.0015f
#define C210_PID_KD            0.030f
#define C210_PID_FF            0.39f
#define C210_PID_I_LIMIT       2000.0f
#define C210_PID_I_SEP         50.0f
#define C210_PID_D_ALPHA       0.2f
#define C210_FAULT_CLEAR_MAX_C 350
#define C210_TEMP_JUMP_C       100
#define C210_NO_HEAT_CYCLES    10
#define C210_NO_HEAT_TEMP_C    100
```

> `verify.py` 的 Config 文本检查用 380 / 300 / 400 / 420（不是 350）。

---

## 4. 构建 / 自检 / 烧录

### 4.1 构建

```bash
cd /Users/theo-richard/workspace/projects/stc32/stc8g1k08a-c210
make
make size
make dis
make verify
make test-pid
```

### 4.2 `verify.py` 检查项

- IHX 最低地址 0x0000，最高 ≤0x1FFF；ROM ≤8192B。
- 0x0000 是 LJMP，目标在 8KB 内。
- map 中存在 `_main`、`_app_task`、`_max31855_read`、`_pid_compute`、`_heater_task`、`_led_task`、`_button_task`。
- Config 文本包含 380/300/400/420（以及 `C210_SETPOINT_C`）。
- `main.lst` 包含 P5.4/P5.5/P3.0/P3.1/P3.2/P3.3 的初始化（寄存器名或位名均可）。
- 机器码包含 P5.5 的 SETB/CLR（LED）和 P5.4 的 SETB/CLR（加热）。
- `.bin` 大小 == 完整镜像大小；XRAM 1024B。
- 建议额外检查：`WDT_CONTR`、`TMOD`、`AUXR`、`P3M0/P3M1`、`P5M0/P5M1` 出现在 `.lst`。

### 4.3 主机侧 PID 测试

`tools/test_pid.c`（系统 `cc` 编译，不依赖 SDCC）：

- 一阶热模型：`T[k+1] = T[k] + duty*K_heat - (T[k]-Tamb)*K_loss`；
- `Tamb=25`, `K_heat=78.7`, `K_loss=0.086`, `dt=1.0s`；
- 跑 200s 阶跃 25→380°C；
- 断言：超调 <10%，调节到 ±1°C 的时间 <60s，稳态误差 <1°C；
- 输出 CSV 到 `build/pid_step.csv` 供画图；控制台打印峰值/超调/调节时间/稳态值。

### 4.4 烧录

```bash
cd /Users/theo-richard/workspace/projects/stc32/stc8g1k08a-c210
make flash
# 等价于：
# /Users/theo-richard/workspace/toolchains/stcgal/bin/stcgal \
#   -p /dev/cu.usbmodemFX2348N1 -P stc8g -l 1200 -b 57600 -t 24000 \
#   build/stc8g1k08a-c210.hex
```

- 目标板独立 3.3V 供电；USB-TTL 只接 TX→P3.0、RX→P3.1、GND。
- 冷启动只断目标板 VCC，USB-TTL 保持插在 Mac。
- 当前裸板没有 MAX31855：烧录后 P5.5 应 **待机慢闪**；短接 P3.3 到 GND（模拟按键）→ 进入 HEATING，因无传感器 → **5Hz 快闪故障**。这证明固件在跑。
- 如果 `make flash` 因冷启动窗口失败，使用 `make flash-hotplug` 或手动断电重试；记录 stcgal 输出。
- **烧录前先确认端口存在**；烧录是用户明确授权的硬件动作。

---

## 5. 验收标准

- 编译：`make` 无错误，ROM ≤8192B，`make verify` 全过，`make test-pid` 全过。
- 裸板：P5.5 待机慢闪；按键→故障快闪；复位后重复。
- 测温：MAX31855 读数与参考温度计误差 <5°C（未校准）/ <2°C（校准后）。
- 控温：380°C 稳态波动 <±5°C；阶跃 25→380°C 超调 <10%，调节时间 <60s（按实际热头调整）。
- LED：<300°C 2Hz 闪；300–400°C 常亮；>400°C 快闪并关加热。
- 安全：传感器开路/短路、超温、看门狗复位都能关断加热；F2 温控开关串联在加热回路。
- 文档：`README.md` + `PCB_DESIGN.md` + `TEST_REPORT.md`，含完整原理图/网表/BOM/引脚表/PCB 顶底渲染/走线规则/安全说明/实测记录。

---

## 6. 主要风险

1. **5V/10W 到 380°C 可能偏慢/到不了**：参考工程 300°C 3–4s；380°C 热损更大。先实测最大可达温度；不够就换低阻头或 5V 3A 电源。
2. **MAX31855 前端**：4053 + 1k + BAT54S 方案需实测开关漏电/电荷注入；MAX31855 远离热源做冷端补偿。
3. **无 UART 遥测**：P3.0/P3.1 与 MAX31855 共用，烧录没问题但正常运行时没有串口；需要曲线就用 MAX31855 模块 + 临时飞线，或改 MCP9600 方案。
4. **安全**：烙铁头 380°C；F1/F2、栅极 1k 下拉、看门狗、限流上电、有人值守，缺一不可。
5. **8KB Flash**：PID 用 float 若超 8KB，改定点 Q16；先编译看 `.mem`。
6. **P5.4 上电 4K 上拉**：R4 必须 1k；如果实测仍有加热毛刺，改用 P5.4 以外的引脚或加硬件使能门。

---

## 7. 子代理分工与文件所有权

| 角色 | 负责 | 不得修改 |
|---|---|---|
| 固件构建代理 | `Config/`、`Core/`、`Makefile`、`tools/verify.py`、`tools/test_pid.c`、`build/` | 原 blink 工程、`docs/pcb/`、`docs/images/`、`README.md`、`PCB_DESIGN.md` |
| PCB 设计代理 | `docs/pcb/`、`docs/images/` | `Config/`、`Core/`、`Makefile`、`tools/`、原 blink 工程 |
| 对抗审查代理 | 只读；报告写到 `docs/reviews/` | 所有源码/渲染文件 |
| 文档汇总（主代理） | `README.md`、`PCB_DESIGN.md`、`TEST_REPORT.md` | 不覆盖子代理产物，只引用 |

---

## 8. 关键“不要做”

- 不要修改 `/Users/theo-richard/workspace/projects/stc32/stc8g1k08a-blink` 的任何文件。
- 不要用 `-mmcs251` 或 `--code-loc 0xFF0000`；这是 8051，代码从 0x0000 起。
- 不要把 P5.4 配成复位脚；它必须是普通 GPIO。
- 不要在 P3.0/P3.1/P3.2 同时为低时上电（会进 USB 下载模式）；R13 上拉 CS，按键只在 P3.3。
- 不要把 74HCT4053 的 INH 逻辑接反：P5.4 高 = INH 高 = 开关断开 = 加热。
- 不要把 MAX31855 的 T+/T- 直接接到 5V 共模而不加 1k + BAT54S。
- 不要在没有 F2 温控开关的情况下长时间加热。
