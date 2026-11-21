/**
 * @file    heater.h
 * @brief   P5.4 加热 MOSFET / 74HCT4053 INH 控制
 *
 * heater_task() 由 Timer0 中断每 1ms 调用一次，作为“最长导通时间”
 * 的硬件安全兜底：即使主循环卡死，也会在 deadline 到达时拉低 P5.4。
 */
#ifndef C210_HEATER_H
#define C210_HEATER_H

#include <stdint.h>

void heater_init(void);

/* 打开加热并设置最长导通时间（ms）；ms=0 等价于 heater_off() */
void heater_on_for(uint16_t ms);

/* 立即关闭加热并取消 deadline */
void heater_off(void);

/* 每 1ms 调用：到 deadline 强制拉低 P5.4 */
void heater_task(void);

/* 当前是否处于加热窗口（仅用于调试/自检） */
uint8_t heater_is_on(void);

#endif /* C210_HEATER_H */
