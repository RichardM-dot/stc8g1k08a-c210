/**
 * @file    stc8g1k08a_regs.h
 * @brief   STC8G1K08A 的 SDCC 寄存器适配层
 *
 * 本文件不再手写 SFR，而是包含从 GitHub 拉取并适配的 FwLib_STC8：
 *   https://github.com/IOsetting/FwLib_STC8  (Apache-2.0)
 *
 * 工程使用其中 3 个头文件：
 *   - fw_conf.h        MCU 型号 / 主频 / IRC 修调参数
 *   - fw_reg_stc8g.h   STC8G 全量 SFR + 位定义（SDCC __sfr/__sbit 语法）
 *   - fw_gpio.h        GPIO 模式宏（GPIO_P5_SetMode 等）
 *
 * 编译时必须定义（见 Makefile）：
 *   -D__CONF_MCU_MODEL=MCU_MODEL_STC8G1K08
 *   -D__CONF_FOSC=24000000UL
 *
 * 说明：
 *  1. FwLib_STC8 的 P5/P5M0/P5M1/P55 等定义已经包含在 fw_reg_base.h /
 *     fw_reg_stc8g.h 中，工程不要再重复定义。
 *  2. P5M0/P5M1 是标准 SFR（0xC9/0xCA），不需要 EAXFR；
 *     CLKDIV、PxPU/PxPD 等 XFR 在 0xFE00 起的 xdata 区，访问前需 EAXFR。
 *  3. 官方 Keil 原版头文件 STC8G.H 仅作地址/位定义对照，不参与编译。
 */
#ifndef STC8G1K08A_REGS_H
#define STC8G1K08A_REGS_H

#include "fw_conf.h"
#include "fw_reg_stc8g.h"
#include "fw_gpio.h"

/* ---- 扩展 SFR 访问开关（P_SW2.7，非位寻址，必须整字节操作）---- */
#define EAXFR_ENABLE()   do { P_SW2 |= 0x80; } while (0)
#define EAXFR_DISABLE()  do { P_SW2 &= (unsigned char)~0x80; } while (0)

#endif /* STC8G1K08A_REGS_H */
