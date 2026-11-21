/*
 * STC8G1K08A P5.5 blink using the FwLib_STC8 HAL (SDCC 4.6.0, mcs51)
 *
 * Requires: fw_gpio.h, fw_sys.h (they pull fw_conf.h/fw_types.h and the
 *           STC8G register headers) and src/fw_sys.c for SYS_Delay().
 *
 * Build defines (35 MHz IRC example):
 *   -D__CONF_FOSC=35000000UL
 *   -D__CONF_MCU_MODEL=MCU_MODEL_STC8G1K08
 *   -D__CONF_CLKDIV=0x00
 *   -D__CONF_IRCBAND=0x01
 *   -D__CONF_VRTRIM=0x1F
 *   -D__CONF_IRTRIM=0xB5
 *   -D__CONF_LIRTRIM=0x00
 *
 * SYS_Delay() is a busy-loop calibrated from __CONF_FOSC, not a hardware
 * timer. The MCU must actually run at the configured IRC frequency (set it
 * with STC-ISP), otherwise the delay scales accordingly. If you call
 * SYS_SetClock(), make sure the IRCBAND/VRTRIM/IRTRIM/LIRTRIM values match
 * your chip; values from STC-ISP or the clock_trim_scan demo are required.
 */

#include "fw_gpio.h"
#include "fw_sys.h"

void main(void)
{
    /* P5.5 push-pull output */
    GPIO_P5_SetMode(GPIO_Pin_5, GPIO_Mode_Output_PP);
    P55 = 1;

    while (1)
    {
        P55 = !P55;
        SYS_Delay(500);
    }
}
