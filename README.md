# STC8G1K08A-8PIN / JBC C210 焊笔控制器

> 5V/3A USB-C 供电 · JBC C210 烙铁头 · MAX31855 K 型热电偶 · 74HCT4053 加热/测温隔离 · 无屏 LED 状态 · STC8G1K08A-8PIN（1T 8051 / 8KB Flash / 1KB XRAM）

本工程从 `../stc8g1k08a-blink` 复制并完全重写为 C210 焊笔控制器。原 blink 工程未修改。
固件使用 SDCC 4.6.0 `-mmcs51`，KiCad 10 原理图，PCB 布局渲染为 42×24mm 2 层板（非 Gerber，投板前需复核）。

---

## 1. 当前状态（2026-11-21）

| 项目 | 结果 |
|---|---|
| `make` | ✅ 通过，无代码错误 |
| ROM | **6864 / 8192 B（83.8%，余量 1328 B）** |
| XRAM | **73 / 1024 B**（PID + app 状态放 xdata） |
| 栈 | **138 B 可用**（SP=0x75） |
| `make verify` | ✅ **55 项全过**（含 Timer0 0x000B 向量、P5.4/P5.5 SETB/CLR、WDT、P3/P5 模式） |
| `make test-pid` | ✅ 首采样无假微分；超调 **2.90%**；**46 s** 进入并保持 ±1°C；稳态误差 **0.000°C** |
| KiCad 原理图 | ✅ **0 ERC errors / 7 warnings**（5 条 4053 未用脚接 GND + 2 条生成符号名称比较；非电气错误） |
| 网表 | ✅ 已用 `kicad-cli` 导出并逐网络核对（`docs/pcb/kicad/c210_schematic.net`） |
| PCB 渲染 | ✅ 顶/底/装配/叠层/布局规则 PNG 已生成（`docs/images/`） |
| 烧录 | ✅ stcgal 成功：6864 B，24.011 MHz，UID `F794C4CA41F89F` |
| 裸板 LED 目视 | ⏳ 待你在板上确认：待机慢闪 / 按键后约 10 s 故障快闪 |

> 烧录日志：`Waiting for MCU → done`；目标 STC8G1K08A-8PIN，BSL 7.3.13U，写 flash 6864 B，设置选项完成，`Disconnected!`。
> 完整日志与测试数据见 [TEST_REPORT.md](TEST_REPORT.md)。

---

## 2. 硬件一览

| 项 | 值 |
|---|---|
| MCU | STC8G1K08A-8PIN，1T 8051，8KB Flash + 4KB EEPROM，256B idata + 1KB xdata，6 个 I/O |
| 供电 | USB-C 5V/3A sink，CC1/CC2 各 5.1k；F1 3A PTC；SW1 5V 3A；D1 SMAJ5.0A TVS |
| 3.3V | AMS1117-3.3，C4/C5 10µF + C6 0.1µF |
| 烙铁头 | JBC C210（加热丝 + K 型热电偶串联，2 线） |
| 测温 | MAX31855（SPI，14 位，0.25°C/LSB，内置冷端补偿） |
| 隔离 | 74HCT4053：P5.4 高 = 加热 + 传感器断开；P5.4 低 = 关断 + 传感器接通 |
| 加热开关 | AOD4184 N-MOSFET（TO-252），R3 100Ω 栅极串联，R4 **1k** 栅极下拉 |
| 保护 | F2 KSD9700 400°C NC 串在加热回路；D2 SS34 续流；D3/D4 BAT54S 把 T+/T- 钳位到 3V3/GND；R17 10k SO 下拉 |
| 状态 | P5.5 LED（高电平亮，330Ω 限流）；P3.3 按键（内部+外部 10k 上拉，100nF 消抖） |
| 烧录 | P3.0/P3.1 UART ISP；J3 4-pin：+3V3/GND/P3.0/P3.1 |

### 2.1 引脚分配（6 个 I/O 全部用满）

| 引脚 | 功能 | 配置 |
|---|---|---|
| P3.0 | MAX31855 SCK / ISP RX | 推挽输出 |
| P3.1 | MAX31855 SO / ISP TX | 高阻输入；R17 10k 下拉 |
| P3.2 | MAX31855 CS | 推挽输出，R13 10k 上拉，ISP 时保持高 |
| P3.3 | 按键 KEY | 高阻输入 + 内部上拉 + 外部 10k + 100nF |
| P5.4 | Q1 栅极 / 74HCT4053 INH | 推挽；高=加热/隔离，低=关断/测温 |
| P5.5 | 状态 LED | 推挽；高=亮 |

### 2.2 LED 行为（按你的要求：300°C 起常亮）

| 状态 / 温度 | LED |
|---|---|
| STANDBY | 1Hz 慢闪（100ms 亮 / 900ms 灭） |
| HEATING，T < 300°C | 2Hz 闪（250ms 亮 / 250ms 灭） |
| HEATING，300°C ≤ T ≤ 400°C | **常亮** |
| HEATING，T > 400°C | 5Hz 快闪 + 立即关加热；降到 ≤395°C 自动恢复 |
| FAULT（传感器/超温锁存/跳变/不升温） | 5Hz 快闪 |
| BOOT | 灭（约 150ms） |

---

## 3. 固件

### 3.1 状态机

```text
BOOT ──150ms 读一次──> STANDBY ──短按──> HEATING
  │                       │                 │
  └─传感器故障────────────┴────────────────> FAULT
                                               │
                         长按 3s 且 T≤350°C ──┘
```

- **HEATING 1s 周期**：0–120ms 关加热（4053 闭合 + MAX31855 转换）；120ms 读温度 + PID；120–(120+duty) 加热（duty 0–800ms）；余下 idle。
- **PID**：归一化输出 0..1；`Kp=0.006, Ki=0.0015, Kd=0.030, FF=0.39`；积分分离 50°C、积分限幅 2000、抗饱和、测量值微分一阶低通 α=0.2；首次采样跳过微分冲击。
- **故障保护**：MAX31855 故障位/越界；T>420°C 锁 FAULT；T>400°C 关加热+快闪（395°C 回差恢复）；单周期跳变 >100°C；连续 10 周期 duty≥790ms 且 T<100°C；WDT `WDT_CONTR=0x35` 约 1.05s。
- **加热兜底**：`heater_task()` 在 Timer0 1ms ISR 和主循环都调用，deadline 到点强制拉低 P5.4。
- **裸板无 MAX31855**：R17 把 SO 拉低，上电读 0°C → STANDBY（慢闪）；按键后 10 个周期无升温 → FAULT（快闪）。

### 3.2 关键配置 `Config/stc8g1k08a_c210_conf.h`

```c
#define C210_SETPOINT_C        380
#define C210_LED_SOLID_LOW     300
#define C210_LED_SOLID_HIGH    400
#define C210_OVERTEMP_C        420
#define C210_PERIOD_MS         1000
#define C210_MEASURE_MS        120
#define C210_MAX_DUTY_MS       800
#define C210_TC_GAIN           1.0f   /* BAT54S 前端增益校准 */
#define C210_TEMP_OFFSET_X4    0
#define C210_PID_KP            0.006f
#define C210_PID_KI            0.0015f
#define C210_PID_KD            0.030f
#define C210_PID_FF            0.39f
#define C210_PID_I_LIMIT       2000.0f
#define C210_PID_I_SEP         50.0f
#define C210_PID_D_ALPHA       0.2f
```

---

## 4. 构建 / 烧录

```bash
cd /Users/theo-richard/workspace/projects/stc32/stc8g1k08a-c210

make            # 产出 build/stc8g1k08a-c210.{ihx,hex,bin}
make size       # ROM / XRAM / 栈
make verify     # 55 项静态自检
make test-pid   # 主机 PID 阶跃测试 + build/pid_step.csv
make dis        # 反汇编 build/stc8g1k08a-c210.dis

make flash      # stcgal -p /dev/cu.usbmodemFX2348N1 -P stc8g -l 1200 -b 57600 -t 24000
```

- 冷启动：**只断目标板 VCC 约 1 秒再上电，USB-TTL 保持插在 Mac 上**；看到 `Waiting for MCU` 后上电。
- USB-TTL 只接 **TX→P3.0、RX→P3.1、GND**；**不要接 USB-TTL 的 VCC**。
- 若只能拔插 USB-TTL，用 `make flash-hotplug`。

### 4.1 已验证的烧录日志

```text
Waiting for MCU, please cycle power: done
Target model: STC8G1K08A-8PIN
Target frequency: 23.989 MHz
Target BSL version: 7.3.13U
Loading flash: 6864 bytes (Intel HEX)
Target frequency: Target 24.000 MHz
Adjusted frequency: 24.011 MHz(0.045%)
Erasing flash: done
Writing flash: 100%
Finishing write: done
Setting options: done
Target UID: F794C4CA41F89F
Disconnected!
```

---

## 5. 工程结构

```text
stc8g1k08a-c210/
├── Makefile
├── README.md                     # 本文
├── PCB_DESIGN.md                 # 原理图 + 网表 + BOM + PCB 渲染 + 布局/安全
├── TEST_REPORT.md                # 构建/自检/PID/ERC/烧录记录
├── PIN_GUIDE.md                  # STC8G 芯片参考（保留）
├── Config/
│   └── stc8g1k08a_c210_conf.h
├── Core/
│   ├── Inc/{app,max31855,pid,heater,led,button,timer}.h
│   └── Src/{main,app,max31855,pid,heater,led,button,timer}.c
├── Drivers/STC8G/                # FwLib_STC8 子集 + SDCC 适配层
├── docs/
│   ├── SPEC.md                   # 执行规格
│   ├── FIRMWARE_NOTES.md         # 固件实现记录
│   ├── images/                   # 原理图/PCB/PID 曲线 PNG
│   ├── pcb/                      # PCB 生成器/渲染
│   │   └── kicad/                # KiCad 10 工程 + 自定义符号 + A3 图框 + 网表/ERC
│   ├── reviews/                  # 对抗审查报告
│   └── ...
├── tools/
│   ├── verify.py
│   ├── dis8051.py
│   ├── test_pid.c
│   └── flash_hotplug.py / stcgal_retry.py
└── build/                        # .rel/.ihx/.hex/.bin/.map/.mem/.lst/.dis
```

---

## 6. 文档索引

- [PCB_DESIGN.md](PCB_DESIGN.md) — **KiCad 原理图（图片直接嵌在 MD 中）**、完整网表、BOM、引脚表、42×24mm 顶/底/装配/叠层/布局规则渲染、placement/trace/via 表、星形地/安全/制造/上电调试。
- [TEST_REPORT.md](TEST_REPORT.md) — 构建、55 项自检、PID 阶跃曲线、KiCad 网表/ERC、stcgal 烧录日志、裸板自检步骤。
- [docs/SPEC.md](docs/SPEC.md) — 原始执行规格与所有关键决策。
- [docs/FIRMWARE_NOTES.md](docs/FIRMWARE_NOTES.md) — 固件实现细节、SDCC 中断向量坑、IRAM 布局、烧录记录。
- [docs/pcb/kicad/](docs/pcb/kicad/) — **完整 KiCad 10 工程**：`c210.kicad_pro`、`c210.kicad_sch`、自定义 `c210.kicad_sym`、A3 图框 `c210.kicad_wks`、`sym-lib-table`/`fp-lib-table`。
- [docs/pcb/kicad/c210_schematic.pdf](docs/pcb/kicad/c210_schematic.pdf) — 可缩放的 A3 原理图 PDF。
- [docs/pcb/kicad/c210_schematic.net](docs/pcb/kicad/c210_schematic.net) — KiCad 导出的真实网表。
- [docs/pcb/kicad/c210_schematic.erc](docs/pcb/kicad/c210_schematic.erc) — ERC 报告（0 errors / 7 warnings）。

---

## 7. 安全

- 烙铁头可达 380°C；F2 KSD9700 400°C NC 必须串在加热回路并靠近手柄。
- 首次上电用**限流电源**，不要无人值守；先确认 3.3V/5V、无短路，再按键加热。
- R4=1k 栅极下拉用于抵消 P5.4 上电约 6.5ms 的内部 4K 上拉；不要改回 10k。
- 5V 低压但 2A 电流；USB-C、F1、SW1、J4/J2、Q1 走线 ≥2mm，Q1 铺铜 + 散热过孔。
- 传感器前端：加热关断时 4053 把约 5V 共模送到 T+/T-；R9/R10=1k + BAT54S 钳位到 3V3/GND，不能省。
- 本工程 PCB 渲染是**布局/装配示意**，不是可直接投产的 Gerber；投板前必须用 KiCad/立创 EDA 复核封装与 DRC。
