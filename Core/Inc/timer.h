/**
 * @file    timer.h
 * @brief   Timer0 1ms 系统节拍
 */
#ifndef C210_TIMER_H
#define C210_TIMER_H

#include <stdint.h>

/* 初始化 Timer0：模式 0（16 位自动重装）、1T、1ms 中断 */
void timer_init(void);

/* 原子读取 32 位毫秒计数（短暂关 EA）；只能在主循环/非中断上下文调用 */
uint32_t timer_millis(void);

/* 直接读取节拍计数，不做 EA 保护；只能在中断内或 EA=0 时调用 */
uint32_t timer_ticks(void);

/* 仅供 Timer0 ISR 调用：毫秒计数 +1。
 * SDCC 4.6 只在包含 main() 的模块生成中断向量表，因此 ISR 本体放在
 * main.c，这里只提供节拍累加。 */
void timer_isr_tick(void);

/* 阻塞延时（内部喂狗）；仅用于初始化阶段，避免长时间占用主循环 */
void timer_delay_ms(uint16_t ms);

#endif /* C210_TIMER_H */
