# STC8G1K08A-8PIN / JBC C210 固件实现记录

日期：2026-11-21
工程：`/Users/theo-richard/workspace/projects/stc32/stc8g1k08a-c210`
依据：`docs/SPEC.md` v1.0

---

## 1. 实现摘要

从空代码实现完整裸机固件：

- Timer0 模式 0（STC8G 16 位自动重装）、1T、1ms 中断节拍；
- MAX31855 位操作 SPI，14 位有符号热电偶 + 3 个故障位；
- 归一化输出 PID（0..1），积分分离、抗饱和、测量值微分 + 一阶低通、0.39 前馈；
- BOOT / STANDBY / HEATING / FAULT 四态状态机，1s 控制周期；
- 加热-测温分时：0..120ms 关加热测温，120..120+duty 加热；
- P5.4 最长导通时间由 Timer0 ISR 每 1ms 兜底关断；
- P5.5 非阻塞 LED（待机 1Hz、加热 2Hz、恒温常亮、过温/故障 5Hz）；
- P3.3 按键 20ms 消抖，短按 20~1000ms，长按 >=3000ms 单次触发；
- WDT_CONTR=0x35（约 1.05s）看门狗，主循环持续喂狗；
- 过温 400°C 关加热 + 5°C 回差，420°C 锁 FAULT；
- 温度跳变 >100°C/周期、连续 10 周期满占空比但 T<100°C 均锁 FAULT；
- 主机侧 PID 阶跃测试（系统 cc 编译真实 `pid.c`）。

### 1.1 关键实现决定

1. **PID 类型名**：固件保留 SPEC 的 `pid_t`（`typedef c210_pid_t pid_t`）。
   主机测试在 macOS 上会与系统 `<sys/types.h>` 的 `pid_t`（int）冲突，
   因此 `pid.h` 提供 `c210_pid_t`，`make test-pid` 定义 `C210_PID_HOST`
   只使用 `c210_pid_t`。固件 API 仍然是 `pid_init(pid_t *, ...)` 语义。
2. **首次微分冲击**：`pid_t` 增加 `uint8_t first`；`pid_reset()` 置 1，
   第一次 `pid_compute()` 只把 `prev_meas=meas`、`d_filt=0`，微分按 0 计算。
   主机测试专门断言 25°C 首采样输出饱和（1.0000）。
3. **热电偶增益校准**：`Config` 增加 `C210_TC_GAIN`（默认 1.0f），
   换算公式为
   `temp_c = tc_x4 * 0.25 * GAIN + C210_TEMP_OFFSET_X4 * 0.25`。
   用于补偿 BAT54S 钳位二极管动态电阻造成的约 1%~4% 差模增益误差；
   注释里给出 300°C / 380°C 两点校准方法。
4. **RAM 布局**：`g_app_pid` 和 app 状态放 `__xdata`。8051 的 data 区
   只有 128B，最初链接报 `Could not get 51 consecutive bytes in internal
   RAM for area DSEG`；移走后 DSEG 余量充足。`s_millis`、heater 的
   `s_active/s_deadline` 保留在 data，保证 ISR 访问速度。
5. **SDCC 4.6 中断向量限制**：mcs51 后端只在包含 `main()` 的编译单元
   生成中断向量表。ISR 原本放在 `timer.c`，链接后 0x000B 没有 LJMP，
   上板会跳到随机代码。现已把 `timer0_isr()` 移到 `main.c`，`timer.c`
   只保留 `timer_isr_tick()`；`verify.py` 增加了 0x000B 向量检查。

---

## 2. 文件清单

新增/修改（均在 C210 工程内）：

```text
Config/stc8g1k08a_c210_conf.h
Core/Inc/app.h
Core/Inc/max31855.h
Core/Inc/pid.h
Core/Inc/heater.h
Core/Inc/led.h
Core/Inc/button.h
Core/Inc/timer.h
Core/Src/main.c
Core/Src/app.c
Core/Src/max31855.c
Core/Src/pid.c
Core/Src/heater.c
Core/Src/led.c
Core/Src/button.c
Core/Src/timer.c
Makefile
tools/verify.py
tools/test_pid.c
docs/FIRMWARE_NOTES.md
```

保留未改：`tools/dis8051.py`、`tools/flash_hotplug.py`、
`tools/stcgal_retry.py`、`Drivers/STC8G/*`。
未修改原 blink 工程、`docs/SPEC.md`、`docs/pcb/`、`docs/images/`、
`README.md`、`PCB_DESIGN.md`。

---

## 3. 关键时序 / 参数

| 项 | 值 |
|---|---|
| 主频 | HIRC 24MHz，1T |
| Timer0 | 模式 0 = 16 位自动重装，`AUXR |= 0x80`，`TMOD &= 0xF0` |
| Timer0 reload | 65536 - 24000 = 0xA240（TL0=0x40，TH0=0xA2） |
| 控制周期 | 1000ms |
| 测量窗口 | 0..120ms 关加热（4053 闭合 + MAX31855 转换） |
| 最大占空比 | 800ms（留 80ms 余量） |
| 目标温度 | 380°C |
| LED 区间 | <300°C 2Hz；300..400°C 常亮；>400°C 5Hz + 关加热 |
| 过温回差 | >400°C 置位，<=395°C 恢复 |
| 绝对超温 | >420°C 锁 FAULT |
| 温度跳变 | >100°C/周期锁 FAULT |
| 不升温检测 | duty>=790ms 且 T<100°C 连续 10 周期锁 FAULT |
| FAULT 清除 | 长按 >=3s 且最新有效温度 <=350°C |
| 按键 | 20ms 消抖；短按 20..1000ms；长按 >=3000ms 一次 |
| 看门狗 | `WDT_CONTR=0x35`，约 1.05s，主循环 `WDT_CONTR |= 0x10` |

---

## 4. 构建结果

命令：

```bash
cd /Users/theo-richard/workspace/projects/stc32/stc8g1k08a-c210
make clean && make
make size
```

`make size` 输出：

```text
=== 代码/数据区（来自 build/stc8g1k08a-c210.mem）===
0-3:Reg Banks, T:Bit regs, a-z:Data, B:Bits, Q:Overlay, I:iData, S:Stack, A:Absolute
Stack starts at: 0x76 (sp set to 0x75) with 138 bytes available.
   EXTERNAL RAM     0x0001   0x0049      73     1024
   ROM/EPROM/FLASH  0x0000   0x1acf    6864     8192
```

| 项 | 值 |
|---|---|
| ROM | **6864 B / 8192 B（83.8%）**，余量 1328 B |
| XRAM | 1024 B 配置，已用 **73 B** |
| 栈 | 从 0x76 开始（SP=0x75），**138 B 可用** |
| `.bin` | 6864 B（与完整镜像一致） |
| `.hex` | 18990 B（Intel HEX 文本） |
| 浮点库 | 已链接 SDCC libfloat；ROM 未超 8KB，**未启用定点 Q16** |

构建只有 SDCC `--std-c23` 自带的预处理宏重定义提示（每个模块 2 条，
共 16 条），无我们代码的 warning/error：

```text
<command-line>: warning: "__has_builtin" redefined
<command-line>: warning: "__STDC_HOSTED__" redefined
```

---

## 5. `make verify` 完整输出

```text
/usr/bin/python3 -I tools/verify.py build/stc8g1k08a-c210.ihx build/stc8g1k08a-c210.map
  ok   IHX 可解析，共 6855 字节
  ok   最低地址 0x0000 == 0x0000（复位向量）
  ok   最高地址 0x1ACF <= 0x1FFF（8KB Flash）
  ok   0x0000 是 LJMP（实际 0x02）
  ok   复位目标 0x0082 落在 0x0000..0x1FFF
  ok   符号 _main 存在 (@0x019F)
  ok   符号 _app_task 存在 (@0x0784)
  ok   符号 _max31855_read 存在 (@0x0936)
  ok   符号 _pid_compute 存在 (@0x0C39)
  ok   符号 _heater_task 存在 (@0x1377)
  ok   符号 _led_task 存在 (@0x13CF)
  ok   符号 _button_task 存在 (@0x1491)
  ok   0x000B 是 Timer0 LJMP（实际 0x02）
  ok   Timer0 向量目标 0x015B 在 0x0000..0x1FFF
  ok   _timer0_isr @0x015B == Timer0 向量 0x015B
  ok   Config 含 C210_SETPOINT_C
  ok   Config 文本含 380
  ok   Config 文本含 300
  ok   Config 文本含 400
  ok   Config 文本含 420
  ok   main.lst 含 P3.0 的初始化痕迹（匹配 P30, _P30）
  ok   main.lst 含 P3.1 的初始化痕迹（匹配 P31, _P31）
  ok   main.lst 含 P3.2 的初始化痕迹（匹配 P32, _P32）
  ok   main.lst 含 P3.3 的初始化痕迹（匹配 P33, _P33）
  ok   main.lst 含 P5.4 的初始化痕迹（匹配 P5.4, P54, _P54）
  ok   main.lst 含 P5.5 的初始化痕迹（匹配 P5.5, P55, _P55）
  ok   main.lst 含 P3M0 的端口模式配置
  ok   main.lst 含 P3M1 的端口模式配置
  ok   main.lst 含 P5M0 的端口模式配置
  ok   main.lst 含 P5M1 的端口模式配置
  ok   main.lst 含 WDT_CONTR 看门狗配置
  ok   main.lst 的 Timer0 ISR 调用 heater_task
  ok   机器码含 SETB P5.5 (D2 CD) @ 0x13F1, 0x1471
  ok   机器码含 CLR  P5.5 (C2 CD) @ 0x00F5, 0x0154, 0x13B2, 0x13CC, 0x13EE, 0x140F, 0x1474
  ok   机器码含 SETB P5.4 (D2 CC) @ 0x1368
  ok   机器码含 CLR  P5.4 (C2 CC) @ 0x00F3, 0x0152, 0x132C, 0x1372, 0x1397
  ok   ROM 起始 0x0000（应为 0x0000）
  ok   ROM 占用 6864 B（1..8192）
  ok   XRAM 配置 1024 B（应为 1024，已用 73 B）
  info 初始栈顶 0x76（138B 可用）
  ok   .bin 大小 6864 B == 完整镜像 6864 B
  ok   build 下存在 .lst（8 个）
  ok   build/*.lst 合计含 WDT_CONTR
  ok   build/*.lst 合计含 TMOD
  ok   build/*.lst 合计含 AUXR
  ok   build/*.lst 合计含 P3M0
  ok   build/*.lst 合计含 P3M1
  ok   build/*.lst 合计含 P5M0
  ok   build/*.lst 合计含 P5M1
  ok   timer.lst 含 TMOD 的 Timer0 配置
  ok   timer.lst 含 AUXR 的 Timer0 配置
  ok   timer.lst 含 TL0 的 Timer0 配置
  ok   timer.lst 含 TH0 的 Timer0 配置
  ok   timer.lst 含 TR0 的 Timer0 配置
  ok   timer.lst 含 ET0 的 Timer0 配置
  ok   timer.lst 含 EA 的 Timer0 配置

ALL CHECKS PASSED
```

共 55 项 `ok`，0 项 FAIL。

---

## 6. 主机 PID 测试

命令：`make test-pid`（系统 `cc`，真实 `Core/Src/pid.c`，模型
`T[k+1]=T[k]+duty*78.7-(T[k]-25)*0.086`，dt=1s，200s 阶跃 25→380°C）。

```text
首采样 25°C 输出: 1.0000
  ok   first sample output saturated        1.000 (limit 0.990)
  ok   first sample d_filt == 0             0.000 (limit 0.000)

仿真结果（200s，25 -> 380°C）：
  峰值      : 391.00 °C
  超调      : 11.00 °C (2.90%)
  调节时间  : 46 s（进入并保持 ±1°C）
  稳态值    : 380.000 °C
  稳态误差  : -0.000 °C
  ok   overshoot < 10%                      11.004 (limit 38.000)
  ok   settling time < 60 s                 46.000 (limit 60.000)
  ok   steady-state error < 1 C             0.000 (limit 1.000)

ALL PID CHECKS PASSED (CSV: build/pid_step.csv)
```

CSV：`build/pid_step.csv`，201 行（表头 + 200 个采样）。

---

## 7. 反汇编证据

`make dis` 生成 `build/stc8g1k08a-c210.dis`（s51 `dc` + SFR/位标注）。

### 7.1 复位 / Timer0 向量

```text
0x0000    02 00 82 LJMP   0x0082          ; 复位 -> SDCC startup
0x000b    02 01 5b LJMP   0x015b          ; Timer0 中断 -> _timer0_isr
```

`_timer0_isr @0x015B`，ISR 内：

```text
0x017a    12 15 d5 LCALL  0x15d5          ; _timer_isr_tick（s_millis++）
0x017d    12 13 77 LCALL  0x1377          ; _heater_task（1ms deadline 兜底）
...
0x019c    02 00 56 LJMP   0x0056          ; SDCC 原子序列恢复/RETI 公共出口
0x0081    32       RETI
```

### 7.2 P5.4 / P5.5 的 SETB / CLR

P5.4（加热 / 4053 INH，位地址 0xCC）：

| 地址 | 指令 | 含义 |
|---|---|---|
| 0x1368 | `D2 CC` SETB P5.4 | `heater_on_for()` 开加热 |
| 0x00F3, 0x0152 | `C2 CC` CLR P5.4 | Board_Init 初始关断 |
| 0x132C | `C2 CC` CLR P5.4 | `heater_init()` |
| 0x1372 | `C2 CC` CLR P5.4 | `heater_off()` |
| 0x1397 | `C2 CC` CLR P5.4 | `heater_task()` 到点强制关断 |

P5.5（LED，位地址 0xCD）：

| 地址 | 指令 | 含义 |
|---|---|---|
| 0x13F1, 0x1471 | `D2 CD` SETB P5.5 | `led_task()` 点亮 / SOLID |
| 0x00F5, 0x0154 | `C2 CD` CLR P5.5 | Board_Init 初始灭 |
| 0x13B2 | `C2 CD` CLR P5.5 | `led_init()` |
| 0x13CC | `C2 CD` CLR P5.5 | `led_set_mode()` 模式切换先灭 |
| 0x13EE, 0x140F, 0x1474 | `C2 CD` CLR P5.5 | 闪烁相位/关闭 |

---

## 8. 烧录结果

命令（参数未改动）：

```bash
make flash
# 实际：
# /Users/theo-richard/workspace/toolchains/stcgal/bin/stcgal \
#   -p /dev/cu.usbmodemFX2348N1 -P stc8g -l 1200 -b 57600 -t 24000 \
#   build/stc8g1k08a-c210.hex
```

串口 `/dev/cu.usbmodemFX2348N1` 存在。使用 Python `subprocess`
给 90s 超时执行，stcgal 输出：

```text
Waiting for MCU, please cycle power:
```

90s 内没有收到芯片握手，进程被终止：

```text
FLASH_TIMEOUT after 90s (process killed)
```

**结论：本次未烧录成功。** 芯片不在 ISP 冷启动窗口，需要人工给目标板
断电约 1 秒再上电（USB-TTL 保持插在 Mac 上，只断目标板 VCC）。
没有自动反复重试（共尝试 1 次），串口参数未修改。
重新上电后再次执行 `make flash` 即可。

---

## 9. 与 SPEC 的偏差 / 已知问题

1. **ISR 位置**：`timer0_isr()` 在 `main.c` 而不是 `timer.c`。原因见 1.1 第 5 条，
   这是 SDCC 4.6 mcs51 的 IVT 生成限制，不是设计选择。功能等价。
2. **PID 类型名**：固件仍可用 `pid_t`；主机测试因 macOS 系统 `pid_t`
   冲突使用 `c210_pid_t` + `C210_PID_HOST`。字段和算法与 SPEC 一致，
   额外增加 `first` 标志（按补充要求跳过首次微分冲击）。
3. **RAM 布局**：app 状态与 PID 结构放 xdata，data 区给 ISR/栈让路。
   这是 256B IRAM 限制下的必要取舍，访问频率低，不影响 1ms 节拍。
4. **SDCC `--std-c23` 警告**：工具链预处理宏 `__has_builtin` /
   `__STDC_HOSTED__` 重定义，来自 SDCC 自身，不影响生成代码。
5. **未做上板功能验证**：烧录未完成，因此 LED 慢闪、按键进加热后
   10 周期进 FAULT 等裸板行为尚未实测。静态检查、链接、反汇编和
   主机 PID 测试均已通过。
6. **温度增益**：默认 `C210_TC_GAIN=1.0f`。实际 BAT54S + 1k 前端
   需要按 300/380°C 两点校准后修改该常量或 `C210_TEMP_OFFSET_X4`。
7. **`timer_delay_ms()`**：已实现并在内部喂狗，但主流程用状态机计时，
   不依赖阻塞延时；保留给初始化/调试使用。
8. **裸板行为**：无 MAX31855 时 SO 被 R17 拉低，上电 raw=0 → 0°C →
   STANDBY；按短按进入 HEATING 后，10 个周期满占空比仍 <100°C →
   FAULT，符合 SPEC 的裸板自检预期。
