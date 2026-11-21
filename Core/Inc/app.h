/**
 * @file    app.h
 * @brief   焊笔状态机（BOOT/STANDBY/HEATING/FAULT）
 */
#ifndef C210_APP_H
#define C210_APP_H

#include <stdint.h>
#include "pid.h"

typedef enum
{
    APP_STATE_BOOT = 0,
    APP_STATE_STANDBY,
    APP_STATE_HEATING,
    APP_STATE_FAULT
} app_state_t;

/* 应用层 PID 实例；由 main 在 app_init 前调用 pid_init()。
 * 8051 的 data 区只有 128B，PID 结构放到 xdata（1KB），避免 DSEG 溢出。 */
#if defined(__SDCC)
#define C210_APP_XDATA __xdata
#else
#define C210_APP_XDATA
#endif
extern C210_APP_XDATA pid_t g_app_pid;

void app_init(void);
void app_task(void);

app_state_t app_get_state(void);
int16_t app_get_temp_x4(void);

#endif /* C210_APP_H */
