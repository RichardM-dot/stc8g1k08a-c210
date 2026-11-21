/**
 * @file    heater.c
 * @brief   P5.4 加热控制 + 最长导通时间兜底
 *
 * P5.4 高电平：
 *   - AOD4184 栅极导通，加热丝通电；
 *   - 74HCT4053 INH 为高，热电偶与 MAX31855 隔离。
 * P5.4 低电平：加热关断，4053 闭合，可以测温。
 */
#include "stc8g1k08a_regs.h"
#include "stc8g1k08a_c210_conf.h"
#include "heater.h"
#include "timer.h"

/* 中断和主循环共享的状态 */
static volatile uint8_t  s_active;
static volatile uint32_t s_deadline_ms;

void heater_init(void)
{
    s_active = 0;
    s_deadline_ms = 0;
    C210_HEATER_OFF();
}

void heater_on_for(uint16_t ms)
{
    if (ms == 0)
    {
        heater_off();
        return;
    }

    /* 关中断，保证 ISR 看到的 deadline/active 是一致的。
     * 这里只会在主循环上下文调用，EA 进入时为 1。 */
    EA = 0;
    s_deadline_ms = timer_ticks() + (uint32_t)ms;
    s_active = 1;
    C210_HEATER_ON();
    EA = 1;
}

void heater_off(void)
{
    EA = 0;
    s_active = 0;
    C210_HEATER_OFF();
    EA = 1;
}

void heater_task(void)
{
    /* 无局部变量、无参数，主循环与 Timer0 ISR 同时调用也是安全的：
     * 两边都只做“到点拉低”，重复执行不会改变结果。 */
    if (!s_active)
    {
        return;
    }

    /* 有符号差值比较，兼容 32 位毫秒计数回绕 */
    if ((int32_t)(timer_ticks() - s_deadline_ms) < 0)
    {
        return;
    }

    C210_HEATER_OFF();
    s_active = 0;
}

uint8_t heater_is_on(void)
{
    return s_active;
}
