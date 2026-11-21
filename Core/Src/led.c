/**
 * @file    led.c
 * @brief   P5.5 状态 LED，非阻塞闪烁
 *
 * 所有模式都基于 timer_millis() 的绝对时间，不用 delay，
 * 因此不会阻塞 1s 控制周期。
 */
#include "stc8g1k08a_regs.h"
#include "stc8g1k08a_c210_conf.h"
#include "led.h"
#include "timer.h"

static led_mode_t s_mode = LED_MODE_OFF;
static uint32_t   s_phase_start_ms;

void led_init(void)
{
    s_mode = LED_MODE_OFF;
    s_phase_start_ms = timer_millis();
    C210_LED_OFF();
}

void led_set_mode(led_mode_t mode)
{
    /* 只在模式真正变化时重置相位，避免 app_task 反复调用导致闪烁停住 */
    if (mode == s_mode)
    {
        return;
    }

    s_mode = mode;
    s_phase_start_ms = timer_millis();
    C210_LED_OFF();
}

void led_task(void)
{
    uint32_t elapsed;
    uint16_t period_ms;
    uint16_t on_ms;

    switch (s_mode)
    {
    case LED_MODE_OFF:
        C210_LED_OFF();
        return;

    case LED_MODE_SOLID:
        C210_LED_ON();
        return;

    case LED_MODE_STANDBY:      /* 100ms 亮 / 900ms 灭 */
        period_ms = 1000;
        on_ms = 100;
        break;

    case LED_MODE_HEATING:      /* 250ms 亮 / 250ms 灭 */
        period_ms = 500;
        on_ms = 250;
        break;

    case LED_MODE_FAST:         /* 100ms 亮 / 100ms 灭 */
        period_ms = 200;
        on_ms = 100;
        break;

    default:
        C210_LED_OFF();
        return;
    }

    elapsed = timer_millis() - s_phase_start_ms;
    if (elapsed >= period_ms)
    {
        /* 主循环偶发卡顿后直接重新对齐，避免补闪一串 */
        s_phase_start_ms = timer_millis();
        elapsed = 0;
    }

    if (elapsed < on_ms)
    {
        C210_LED_ON();
    }
    else
    {
        C210_LED_OFF();
    }
}
