/**
 * @file    led.h
 * @brief   P5.5 状态 LED 非阻塞驱动
 */
#ifndef C210_LED_H
#define C210_LED_H

typedef enum
{
    LED_MODE_OFF = 0,      /* 常灭 */
    LED_MODE_STANDBY,      /* 100ms 亮 / 900ms 灭（1Hz 慢闪） */
    LED_MODE_HEATING,      /* 250ms 亮 / 250ms 灭（2Hz） */
    LED_MODE_SOLID,        /* 常亮 */
    LED_MODE_FAST          /* 100ms 亮 / 100ms 灭（5Hz） */
} led_mode_t;

void led_init(void);
void led_set_mode(led_mode_t mode);
void led_task(void);

#endif /* C210_LED_H */
