/**
 * @file    button.c
 * @brief   P3.3 按键驱动
 *
 * 电气：内部上拉 + 外部 10k 上拉到 +3V3，按键另一端到 GND，100nF 消抖。
 * 逻辑：
 *   - 20ms 消抖；
 *   - 短按：按下 20ms~1000ms 后释放，产生一次短按事件；
 *   - 长按：按住 >=3000ms 立即产生一次长按事件，释放后不再产生短按。
 */
#include "stc8g1k08a_regs.h"
#include "stc8g1k08a_c210_conf.h"
#include "button.h"
#include "timer.h"

#define BTN_DEBOUNCE_MS   20U
#define BTN_LONG_MS       3000U
#define BTN_SHORT_MAX_MS  1000U

/* 状态机 */
#define BTN_ST_RELEASED   0U
#define BTN_ST_DEBOUNCE_D 1U
#define BTN_ST_PRESSED    2U
#define BTN_ST_DEBOUNCE_U 3U

static uint8_t  s_state = BTN_ST_RELEASED;
static uint32_t s_edge_ms;       /* 本次边沿（按下或释放）的时间戳 */
static uint32_t s_press_ms;      /* 确认按下时的“首次低电平”时间戳 */
static uint8_t  s_long_fired;
static uint8_t  s_short_event;
static uint8_t  s_long_event;

void button_init(void)
{
    s_state = BTN_ST_RELEASED;
    s_edge_ms = 0;
    s_press_ms = 0;
    s_long_fired = 0;
    s_short_event = 0;
    s_long_event = 0;
}

void button_task(void)
{
    uint32_t now = timer_millis();
    uint8_t  is_low = (C210_KEY_PIN == 0) ? 1U : 0U;

    switch (s_state)
    {
    case BTN_ST_RELEASED:
        if (is_low)
        {
            s_state = BTN_ST_DEBOUNCE_D;
            s_edge_ms = now;
        }
        break;

    case BTN_ST_DEBOUNCE_D:
        if (!is_low)
        {
            /* 抖动，回到释放态 */
            s_state = BTN_ST_RELEASED;
        }
        else if ((uint32_t)(now - s_edge_ms) >= BTN_DEBOUNCE_MS)
        {
            s_state = BTN_ST_PRESSED;
            s_press_ms = s_edge_ms;   /* 从首次低电平算按下时间 */
            s_long_fired = 0;
        }
        break;

    case BTN_ST_PRESSED:
        if (!is_low)
        {
            s_state = BTN_ST_DEBOUNCE_U;
            s_edge_ms = now;
        }
        else if (!s_long_fired &&
                 (uint32_t)(now - s_press_ms) >= BTN_LONG_MS)
        {
            /* 长按只触发一次 */
            s_long_fired = 1;
            s_long_event = 1;
        }
        break;

    case BTN_ST_DEBOUNCE_U:
        if (is_low)
        {
            /* 释放抖动，回到按下态 */
            s_state = BTN_ST_PRESSED;
        }
        else if ((uint32_t)(now - s_edge_ms) >= BTN_DEBOUNCE_MS)
        {
            uint32_t duration = s_edge_ms - s_press_ms;

            if (!s_long_fired &&
                duration >= BTN_DEBOUNCE_MS &&
                duration <= BTN_SHORT_MAX_MS)
            {
                s_short_event = 1;
            }
            s_state = BTN_ST_RELEASED;
        }
        break;

    default:
        s_state = BTN_ST_RELEASED;
        break;
    }
}

uint8_t button_take_short(void)
{
    uint8_t value = s_short_event;
    s_short_event = 0;
    return value;
}

uint8_t button_take_long(void)
{
    uint8_t value = s_long_event;
    s_long_event = 0;
    return value;
}
