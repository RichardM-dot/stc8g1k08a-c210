/**
 * @file    app.c
 * @brief   C210 焊笔状态机
 *
 * BOOT     : 等 150ms，读一次传感器；正常 -> STANDBY，故障 -> FAULT
 * STANDBY  : 关加热、LED 1Hz 慢闪、每秒测温；短按 -> HEATING
 * HEATING  : 1s 周期，前 120ms 关加热测温，随后按 PID duty 加热
 * FAULT    : 关加热、LED 5Hz、每秒测温；长按 3s 且 T<=350 才回 STANDBY
 *
 * 安全策略：
 *   - 传感器故障位/越界 -> FAULT
 *   - T>420°C -> FAULT
 *   - 单周期跳变 >100°C -> FAULT
 *   - 连续 10 个周期 duty>=790ms 且 T<100°C -> FAULT
 *   - T>400°C -> 立即关加热、LED 5Hz；降到 <=395°C 自动恢复（5°C 回差）
 */
#include "stc8g1k08a_c210_conf.h"
#include "app.h"
#include "max31855.h"
#include "heater.h"
#include "led.h"
#include "button.h"
#include "timer.h"

/* 应用层 PID 实例（main 在 app_init 前初始化）。
 * app 状态和 PID 都放 xdata：8051 的 data 区只有 128B，
 * 这些变量不在 ISR 热点里，放 xdata 不影响 1ms 节拍。 */
C210_APP_XDATA pid_t g_app_pid;

static __xdata app_state_t s_state;
static __xdata uint32_t    s_boot_ms;
static __xdata uint32_t    s_last_sample_ms;
static __xdata uint32_t    s_cycle_start_ms;

static __xdata int16_t  s_temp_x4;      /* 校准后的温度，0.25°C/LSB */
static __xdata float    s_temp_c;       /* 校准后的温度，°C */
static __xdata int16_t  s_prev_temp_x4;
static __xdata uint8_t  s_have_prev;

static __xdata uint16_t s_duty_ms;
static __xdata uint8_t  s_cycle_measured;
static __xdata uint8_t  s_overtemp;
static __xdata uint8_t  s_no_heat_cycles;
static __xdata uint8_t  s_fault_temp_valid;

/* ------------------------------------------------------------
 * 读传感器 + 校准
 * ------------------------------------------------------------ */
static uint8_t app_read_temp(void)
{
    int16_t raw_x4;

    if (max31855_read(&raw_x4) != 0)
    {
        return 1;
    }

    /* 校准公式（见 Config 注释）：
     *   temp_c = tc_x4 * 0.25 * GAIN + OFFSET_X4 * 0.25
     * 再换算回 0.25°C 单位，供 LED/保护阈值使用。 */
    s_temp_c = (float)raw_x4 * 0.25f * C210_TC_GAIN
             + (float)C210_TEMP_OFFSET_X4 * 0.25f;

    if (s_temp_c >= 0.0f)
    {
        s_temp_x4 = (int16_t)(s_temp_c * 4.0f + 0.5f);
    }
    else
    {
        s_temp_x4 = (int16_t)(s_temp_c * 4.0f - 0.5f);
    }

    return 0;
}

/* ------------------------------------------------------------
 * 状态入口
 * ------------------------------------------------------------ */
static void app_enter_standby(void)
{
    s_state = APP_STATE_STANDBY;
    heater_off();
    led_set_mode(LED_MODE_STANDBY);

    s_last_sample_ms = timer_millis();
    s_overtemp = 0;
    s_no_heat_cycles = 0;
    s_have_prev = 0;
    s_duty_ms = 0;
    pid_reset(&g_app_pid);
}

static void app_enter_heating(void)
{
    s_state = APP_STATE_HEATING;
    heater_off();
    led_set_mode(LED_MODE_HEATING);

    pid_reset(&g_app_pid);
    s_cycle_start_ms = timer_millis();
    s_cycle_measured = 0;
    s_duty_ms = 0;
    s_have_prev = 0;
    s_overtemp = 0;
    s_no_heat_cycles = 0;
}

static void app_enter_fault(void)
{
    s_state = APP_STATE_FAULT;
    heater_off();
    led_set_mode(LED_MODE_FAST);

    s_last_sample_ms = timer_millis();
    s_fault_temp_valid = 0;
    s_duty_ms = 0;
    s_have_prev = 0;
    pid_reset(&g_app_pid);
}

/* ------------------------------------------------------------
 * HEATING：1s 控制周期
 * ------------------------------------------------------------ */
static void app_heating_task(uint32_t now)
{
    uint32_t elapsed = now - s_cycle_start_ms;

    /* 周期结束：先关加热，进入 0..120ms 测量窗口 */
    if (elapsed >= C210_PERIOD_MS)
    {
        s_cycle_start_ms += C210_PERIOD_MS;

        /* 主循环严重滞后时重新对齐，不追补多个周期 */
        if ((uint32_t)(now - s_cycle_start_ms) >= C210_PERIOD_MS)
        {
            s_cycle_start_ms = now;
        }

        s_cycle_measured = 0;
        s_duty_ms = 0;
        heater_off();
        elapsed = now - s_cycle_start_ms;
    }

    if (!s_cycle_measured)
    {
        int32_t diff;
        float out;
        int32_t duty;

        /* 0..120ms 保持关加热，等 4053 稳定 + MAX31855 完成转换 */
        if (elapsed < C210_MEASURE_MS)
        {
            return;
        }

        s_cycle_measured = 1;

        if (app_read_temp() != 0)
        {
            app_enter_fault();
            return;
        }

        /* 单周期温度跳变检查 */
        if (s_have_prev)
        {
            diff = (int32_t)s_temp_x4 - (int32_t)s_prev_temp_x4;
            if (diff < 0)
            {
                diff = -diff;
            }
            if (diff > (int32_t)(C210_TEMP_JUMP_C * 4))
            {
                app_enter_fault();
                return;
            }
        }
        s_prev_temp_x4 = s_temp_x4;
        s_have_prev = 1;

        /* 绝对超温锁存 FAULT */
        if (s_temp_x4 > (int16_t)(C210_OVERTEMP_C * 4))
        {
            app_enter_fault();
            return;
        }

        /* >400°C：首次进入时复位 PID；本周期直接关加热、快闪并返回。
         * 过温期间不跑 PID，避免积分朝负方向积累；也不累加 no-heat 计数。
         * 降到 <=395°C（5°C 回差）时再复位一次，让下一周期干净恢复。 */
        if (s_temp_x4 > (int16_t)(C210_LED_SOLID_HIGH * 4))
        {
            if (!s_overtemp)
            {
                s_overtemp = 1;
                pid_reset(&g_app_pid);
            }
            s_duty_ms = 0;
            heater_off();
            led_set_mode(LED_MODE_FAST);
            return;
        }

        if (s_overtemp &&
            s_temp_x4 <= (int16_t)((C210_LED_SOLID_HIGH - 5) * 4))
        {
            s_overtemp = 0;
            pid_reset(&g_app_pid);
        }

        /* PID：1s 周期，测量值已在 120ms 窗口读取 */
        out = pid_compute(&g_app_pid,
                          (float)C210_SETPOINT_C,
                          s_temp_c,
                          1.0f);
        duty = (int32_t)(out * (float)C210_MAX_DUTY_MS + 0.5f);
        if (duty < 0)
        {
            duty = 0;
        }
        if (duty > C210_MAX_DUTY_MS)
        {
            duty = C210_MAX_DUTY_MS;
        }
        s_duty_ms = (uint16_t)duty;

        /* 满占空比但温度仍很低：加热回路/传感器异常 */
        if (s_duty_ms >= (C210_MAX_DUTY_MS - 10) &&
            s_temp_x4 < (int16_t)(C210_NO_HEAT_TEMP_C * 4))
        {
            if (++s_no_heat_cycles >= C210_NO_HEAT_CYCLES)
            {
                app_enter_fault();
                return;
            }
        }
        else
        {
            s_no_heat_cycles = 0;
        }

        /* 加热窗口 120..120+duty；heater_task 会在 deadline 兜底拉低 */
        if (!s_overtemp && s_duty_ms > 0)
        {
            heater_on_for(s_duty_ms);
        }
        else
        {
            heater_off();
        }

        /* 温度区间 LED */
        if (s_temp_x4 < (int16_t)(C210_LED_SOLID_LOW * 4))
        {
            led_set_mode(LED_MODE_HEATING);
        }
        else if (s_temp_x4 <= (int16_t)(C210_LED_SOLID_HIGH * 4))
        {
            led_set_mode(LED_MODE_SOLID);
        }
        else
        {
            led_set_mode(LED_MODE_FAST);
        }
    }
    else
    {
        /* 本周期加热窗口已结束则提前拉低（正常由 heater_task 到点完成） */
        if (elapsed >= (uint32_t)(C210_MEASURE_MS + s_duty_ms))
        {
            heater_off();
        }
    }
}

/* ------------------------------------------------------------
 * 公共接口
 * ------------------------------------------------------------ */
void app_init(void)
{
    s_state = APP_STATE_BOOT;
    s_boot_ms = timer_millis();
    s_last_sample_ms = s_boot_ms;
    s_cycle_start_ms = s_boot_ms;

    s_temp_x4 = 0;
    s_temp_c = 0.0f;
    s_prev_temp_x4 = 0;
    s_have_prev = 0;
    s_duty_ms = 0;
    s_cycle_measured = 0;
    s_overtemp = 0;
    s_no_heat_cycles = 0;
    s_fault_temp_valid = 0;

    led_set_mode(LED_MODE_OFF);
}

void app_task(void)
{
    uint32_t now;
    uint8_t  short_press;
    uint8_t  long_press;

    now = timer_millis();
    short_press = button_take_short();
    long_press = button_take_long();

    switch (s_state)
    {
    case APP_STATE_BOOT:
        if ((uint32_t)(now - s_boot_ms) >= 150UL)
        {
            if (app_read_temp() != 0)
            {
                app_enter_fault();
            }
            else
            {
                s_prev_temp_x4 = s_temp_x4;
                s_have_prev = 1;

#if C210_AUTO_START
                app_enter_heating();
#else
                app_enter_standby();
#endif
            }
        }
        break;

    case APP_STATE_STANDBY:
        if ((uint32_t)(now - s_last_sample_ms) >= 1000UL)
        {
            s_last_sample_ms = now;
            if (app_read_temp() != 0)
            {
                app_enter_fault();
                break;
            }
        }

        if (short_press)
        {
            app_enter_heating();
        }
        break;

    case APP_STATE_HEATING:
        /* 短按退出加热；短按在 FAULT 中无效 */
        if (short_press)
        {
            app_enter_standby();
            break;
        }
        app_heating_task(now);
        break;

    case APP_STATE_FAULT:
        /* 每秒测温，供长按清除时判断温度 */
        if ((uint32_t)(now - s_last_sample_ms) >= 1000UL)
        {
            s_last_sample_ms = now;
            if (app_read_temp() == 0)
            {
                s_fault_temp_valid = 1;
            }
            else
            {
                s_fault_temp_valid = 0;
            }
        }

        /* 长按 3s 且温度 <=350°C 才允许清除；否则保持 FAULT */
        if (long_press && s_fault_temp_valid &&
            s_temp_x4 <= (int16_t)(C210_FAULT_CLEAR_MAX_C * 4))
        {
            app_enter_standby();
        }
        break;

    default:
        app_enter_fault();
        break;
    }
}

app_state_t app_get_state(void)
{
    return s_state;
}

int16_t app_get_temp_x4(void)
{
    return s_temp_x4;
}
