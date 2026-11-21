/**
 * @file    button.h
 * @brief   P3.3 按键：20ms 消抖、短按/长按事件
 */
#ifndef C210_BUTTON_H
#define C210_BUTTON_H

#include <stdint.h>

void button_init(void);
void button_task(void);

/* 取一次短按事件（按下 20~1000ms 后释放），读取后自动清除 */
uint8_t button_take_short(void);

/* 取一次长按事件（按住 >=3000ms 触发一次），读取后自动清除 */
uint8_t button_take_long(void);

#endif /* C210_BUTTON_H */
