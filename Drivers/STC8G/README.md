# Drivers/STC8G — STC8G1K08A 寄存器头文件与 FwLib_STC8

本目录放两类东西：

1. **工程实际编译的 SDCC 寄存器层**：`stc8g1k08a_regs.h` + `FwLib_STC8/include/`；
2. **只读参考的官方 Keil 头文件**：`STC8G.H`（不参与编译）。

---

## 1. 文件表

| 文件 | 来源 | 用途 |
| --- | --- | --- |
| `Inc/stc8g1k08a_regs.h` | 本工程编写 | SDCC 适配层：包含 FwLib 头 + `EAXFR_ENABLE/DISABLE` |
| `FwLib_STC8/include/fw_conf.h` | [IOsetting/FwLib_STC8](https://github.com/IOsetting/FwLib_STC8) | MCU 型号、主频、IRC 修调参数 |
| `FwLib_STC8/include/fw_reg_base.h` | 同上 | 基础 SFR/位：P5、P5M0/P5M1、P55、TCON、TMOD、AUXR… |
| `FwLib_STC8/include/fw_reg_stc8g.h` | 同上 | STC8G 扩展 SFR：CLKDIV、VRTRIM、PxPU… |
| `FwLib_STC8/include/fw_gpio.h` | 同上 | `GPIO_P5_SetMode()` 等 GPIO 模式宏 |
| `FwLib_STC8/include/fw_types.h` | 同上 | `uint8_t` / `B00000001` 等基础定义 |
| `FwLib_STC8/include/fw_sys.h` | 同上 | `SYS_SetClock()` / `SYS_Delay()` 声明（本工程未用） |
| `FwLib_STC8/include/fw_rcc.h` | 同上 | 时钟相关声明（本工程未用） |
| `FwLib_STC8/include/fw_cid_stc8g.h` | 同上 | CHIPID 相关定义（本工程未用） |
| `FwLib_STC8/src/fw_sys.c` | 同上 | `SYS_Delay()` 参考实现（**未加入编译**） |
| `FwLib_STC8/examples/blink_p55_hal.c` | 同上 | 原库 P5.5 闪灯示例（参考） |
| `FwLib_STC8/LICENSE` | 同上 | Apache-2.0 许可证 |
| `Inc/STC8G.H` | [LongXL6/LongXL-LED-Open-Source-Version](https://github.com/LongXL6/LongXL-LED-Open-Source-Version)（MIT）中的 STC 官方头文件 | 查寄存器地址/位定义（**Keil 语法，不能直接 include**） |

## 2. 版本与许可证

| 项 | 值 |
| --- | --- |
| FwLib_STC8 仓库 | <https://github.com/IOsetting/FwLib_STC8> |
| FwLib_STC8 commit | `992a4e060a48d860c203ce4ce61dfe90b51acbd6`（master） |
| FwLib_STC8 许可证 | **Apache-2.0**（保留 `LICENSE` 与各文件版权头） |
| STC8G.H 来源 | <https://github.com/LongXL6/LongXL-LED-Open-Source-Version> |
| STC8G.H 许可证 | 仓库为 MIT；文件本身是 STC 官方发布的寄存器头 |
| STC8G.H 编码 | 原文件为 **GBK + CRLF**，中文注释在 UTF-8 编辑器里可能显示为乱码 |

> `IOsetting/stc8xx-library` 在 GitHub 上是 404；实际可用的仓库名是
> **FwLib_STC8**。

## 3. 本工程对库做了什么修改

1. **只取子集**：没有复制整个 FwLib_STC8，只取 `fw_conf.h`、`fw_reg_base.h`、
   `fw_reg_stc8g.h`、`fw_gpio.h`、`fw_types.h`、`fw_sys.h`、`fw_rcc.h`、
   `fw_cid_stc8g.h` 共 8 个头文件；`fw_sys.c` 仅作参考，不参与编译。
2. **型号适配**：FwLib 没有 `MCU_MODEL_STC8G1K08A`，使用
   `MCU_MODEL_STC8G1K08`（同系列 8KB Flash 型号，SFR 一致）。
   Makefile 中显式定义：
   ```make
   -D__CONF_MCU_MODEL=MCU_MODEL_STC8G1K08
   -D__CONF_FOSC=24000000UL
   ```
3. **SDCC 适配层**：`Inc/stc8g1k08a_regs.h` 只做三件事：
   - `#include "fw_conf.h"` / `"fw_reg_stc8g.h"` / `"fw_gpio.h"`；
   - 增加 `EAXFR_ENABLE()` / `EAXFR_DISABLE()`（P_SW2.7，非位寻址）；
   - 不再重复定义 P5/P5M0/P5M1/P55，避免和 FwLib 冲突。
4. **启动/链接**：使用 SDCC 默认启动代码，不需要 `STARTUP.A51`；
   编译参数统一为 `-mmcs51 --model-small --code-size 8192
   --xram-size 1024 --iram-size 256`。**不要**把 FwLib 默认的
   `--model-large` 和本工程的 `--model-small` 混用（所有 `.rel` 必须一致）。
5. **延时**：FwLib 的 `SYS_Delay()` 是忙循环，不是硬件定时器；本工程改用
   Timer0 模式 0（16 位自动重装）做 1ms 节拍，见 `Core/Src/delay.c`。

## 4. 关键寄存器核对（已实测编译）

| 名称 | 地址 | 说明 |
| --- | --- | --- |
| `P5` | `0xC8` | P5 数据口（位寻址） |
| `P5M1` | `0xC9` | P5 模式寄存器 1 |
| `P5M0` | `0xCA` | P5 模式寄存器 0 |
| `P55` | 位 `0xCD` | P5.5，本工程 LED |
| `P_SW2` | `0xBA` | bit7 = EAXFR |
| `CLKDIV` | xdata `0xFE01` | 系统时钟分频，需 EAXFR |
| `AUXR` | `0x8E` | T0x12 等 |
| `TMOD` | `0x89` | Timer0/1 模式 |
| `TL0` / `TH0` | `0x8A` / `0x8C` | Timer0 计数/重装 |
| `TR0` / `TF0` | 位 `0x8C` / `0x8D` | TCON.4 / TCON.5 |

SDCC 生成的 P5.5 推挽代码（`GPIO_P5_SetMode` 宏展开）：

```text
0x00c6    74 df    MOV    A,#0xdf
0x00c8    55 ca    ANL    A,0xca       ; P5M0
0x00ca    44 20    ORL    A,#0x20
0x00cc    f5 ca    MOV    0xca,A
0x00ce    53 c9 df ANL    0xc9,#0xdf   ; P5M1
```

如果编译器把宏优化成直接 `ORL P5M0,#0x20`，也等价。

另外，工程在 `SystemClock_Config()` 里写 `P_SW1 = 0x00`，把 UART1 固定在
P3.0/P3.1。原因是 STC8G1K08A 的 `P_SW1.S1_S[1:0]` 可以把 UART1 切到
P3.2/P3.3 或 **P5.4/P5.5**；如果芯片硬件选项 `uart1_remap=True`，P5.5
可能被 UART1 占用，导致 GPIO 翻转无效。

## 5. 为什么不用官方 STC8G.H 直接编译

1. `sfr P0 = 0x80;` / `sbit P00 = P0^0;` 是 Keil C51 语法，SDCC 报
   `Syntax error at 'sfr'`；
2. `interrupt N`、`_nop_()`、`#pragma` 等也不兼容；
3. 官方头文件用 `(*(unsigned char volatile xdata *)0xFE01)` 定义 XFR，
   SDCC 需要 `__xdata` 关键字（部分社区头文件直接用裸 `xdata` 会报错）。

FwLib_STC8 已经用 `SFR()/SBIT()/SFRX()` 宏同时兼容 SDCC 与 Keil，
所以本工程直接采用它，而不是自己逐行改写 814 行的官方头文件。
