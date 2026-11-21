/**
 * @file    timer.c
 * @brief   Timer0 1ms 节拍（STC8G 模式 0 = 16 位自动重装）
 *
 * 时钟：HIRC 24MHz，1T 模式（AUXR.T0x12=1）。
 * 1ms 需要 24000 个计数：
 *     reload = 65536 - 24000 = 41536 = 0xA240
 *     TL0 = 0x40，TH0 = 0xA2
 */
#include "stc8g1k08a_regs.h"
#include "stc8g1k08a_c210_conf.h"
#include "timer.h"

/* 中断与主循环共享：32 位毫秒计数 */
static volatile uint32_t s_millis;

/* 由 main.c 的 Timer0 ISR 调用，中断上下文，不要在这里做耗时操作 */
void timer_isr_tick(void)
{
    s_millis++;
}

void timer_init(void)
{
    /* T0x12=1：Timer0 工作在 1T 模式（每个时钟计数一次） */
    AUXR |= 0x80;

    /* 只改 Timer0 的模式位，保留 Timer1 配置；模式 0 = 16 位自动重装 */
    TMOD &= 0xF0;

    /* 先装初值，再启动，避免第一个周期变长 */
    TL0 = 0x40;
    TH0 = 0xA2;

    TR0 = 1;
    ET0 = 1;
    EA  = 1;
}

uint32_t timer_millis(void)
{
    uint32_t value;

    /* 32 位读取不是原子操作：短暂关中断，读完立刻恢复。
     * 本函数只允许在主循环调用，不能在 ISR 内调用（否则会把 EA 打开）。 */
    EA = 0;
    value = s_millis;
    EA = 1;

    return value;
}

uint32_t timer_ticks(void)
{
    /* 不加 EA 保护，供 ISR 或已经关中断的代码使用 */
    return s_millis;
}

void timer_delay_ms(uint16_t ms)
{
    uint32_t start = timer_millis();

    while ((uint32_t)(timer_millis() - start) < (uint32_t)ms)
    {
        /* 长延时期间持续喂狗，避免初始化阶段被看门狗复位 */
        WDT_CONTR |= 0x10;
    }
}
