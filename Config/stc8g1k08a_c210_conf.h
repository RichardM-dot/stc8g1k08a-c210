/**
 * @file    stc8g1k08a_c210_conf.h
 * @brief   JBC C210 焊笔控制器板级配置（STC8G1K08A-8PIN）
 *
 * 硬件（全部 6 个 I/O 都用满）：
 *   P3.0  MAX31855 SCK   推挽输出
 *   P3.1  MAX31855 SO    高阻输入
 *   P3.2  MAX31855 CS    推挽输出，默认高
 *   P3.3  按键           高阻输入 + 内部上拉，低有效
 *   P5.4  加热 / 4053 INH 推挽输出，高 = 加热（同时断开热电偶）
 *   P5.5  状态 LED       推挽输出，高 = 点亮
 *
 * 本文件只放“可配置常量”，不放函数和 SFR 操作。pid.c 也会包含它，
 * 因此这里不能依赖任何 8051 头文件。
 */
#ifndef STC8G1K08A_C210_CONF_H
#define STC8G1K08A_C210_CONF_H

/* ============================================================
 * 1. 时钟 / 控制周期
 * ============================================================ */
#define MAIN_Fosc               24000000UL  /* HIRC 24MHz，下载时由 -t 24000 校准 */

#define C210_SETPOINT_C         380         /* 目标温度（°C） */
#define C210_LED_SOLID_LOW     300         /* 低于此温度 LED 2Hz 闪 */
#define C210_LED_SOLID_HIGH    400         /* 300..400°C LED 常亮；>400°C 5Hz 闪并关加热 */
#define C210_OVERTEMP_C        420         /* 超过此温度锁存 FAULT */

#define C210_PERIOD_MS         1000        /* 控制周期 1s */
#define C210_MEASURE_MS        120         /* 每个周期前 120ms 关加热等 4053/MAX31855 */
#define C210_MAX_DUTY_MS       800         /* 单周期最大加热时间，留 80ms 余量 */

#define C210_AUTO_START        0           /* 1=上电自动加热；0=按键启动 */
#define C210_TEMP_OFFSET_X4    0           /* 校准偏移，0.25°C 单位 */
/*
 * 热电偶增益校准：
 *   T+/T- 前的 BAT54S 钳位二极管存在动态电阻，会带来约 1%~4% 的
 *   差模增益误差（380°C 时可能偏差几度到十几度）。
 *   temp_c = tc_x4 * 0.25 * C210_TC_GAIN + C210_TEMP_OFFSET_X4 * 0.25
 *   现场校准时用参考温度计在 300°C 与 380°C 两点测量，先算偏移
 *   （C210_TEMP_OFFSET_X4），再按下式修正增益：
 *       C210_TC_GAIN = (T_ref2 - T_ref1) / (T_meas2 - T_meas1)
 *   默认 1.0f 表示不修正。
 */
#define C210_TC_GAIN           1.0f

/* ============================================================
 * 2. PID 参数（归一化输出 0.0..1.0）
 * ============================================================ */
#define C210_PID_KP            0.006f
#define C210_PID_KI            0.0015f
#define C210_PID_KD            0.030f
#define C210_PID_FF            0.39f       /* 380°C 稳态占空比前馈 */
#define C210_PID_I_LIMIT       2000.0f     /* 积分限幅 */
#define C210_PID_I_SEP         50.0f       /* |e|<=50°C 才积分（积分分离） */
#define C210_PID_D_ALPHA       0.2f        /* 微分一阶低通系数 */

/* ============================================================
 * 3. 故障保护阈值
 * ============================================================ */
#define C210_FAULT_CLEAR_MAX_C 350         /* FAULT 长按清除的最高允许温度 */
#define C210_TEMP_JUMP_C       100         /* 单周期温度跳变上限，超过判传感器故障 */
#define C210_NO_HEAT_CYCLES    10          /* 连续满占空比周期数 */
#define C210_NO_HEAT_TEMP_C    100         /* 满占空比但低于此温度 -> 加热回路故障 */

/* ============================================================
 * 4. 引脚宏（只在硬件相关 .c 中使用）
 * ============================================================ */
#define C210_MAX_SCK_PIN       P30
#define C210_MAX_SO_PIN        P31
#define C210_MAX_CS_PIN        P32
#define C210_KEY_PIN           P33
#define C210_HEAT_PIN          P54
#define C210_LED_PIN           P55

#define C210_MAX_SCK_HIGH()    do { C210_MAX_SCK_PIN = 1; } while (0)
#define C210_MAX_SCK_LOW()     do { C210_MAX_SCK_PIN = 0; } while (0)
#define C210_MAX_CS_HIGH()     do { C210_MAX_CS_PIN  = 1; } while (0)
#define C210_MAX_CS_LOW()      do { C210_MAX_CS_PIN  = 0; } while (0)

#define C210_HEATER_ON()       do { C210_HEAT_PIN = 1; } while (0)
#define C210_HEATER_OFF()      do { C210_HEAT_PIN = 0; } while (0)
#define C210_LED_ON()          do { C210_LED_PIN  = 1; } while (0)
#define C210_LED_OFF()         do { C210_LED_PIN  = 0; } while (0)

#endif /* STC8G1K08A_C210_CONF_H */
