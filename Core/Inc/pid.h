/**
 * @file    pid.h
 * @brief   归一化输出 PID（0.0..1.0）
 */
#ifndef C210_PID_H
#define C210_PID_H

#include <stdint.h>

typedef struct
{
    float kp, ki, kd;
    float integral;
    float prev_meas;
    float d_filt;
    float out;
    float ff;
    float i_limit;
    float i_sep;
    float d_alpha;
    uint8_t first;          /* 1 = 下一次 compute 跳过微分冲击（pid_reset 后置位） */
} c210_pid_t;

/* 固件沿用 SPEC 的 pid_t 名称。
 * 主机测试（macOS/glibc）的 <sys/types.h> 已经把 pid_t 定义为 int，
 * 因此 test-pid 编译时定义 C210_PID_HOST，只使用 c210_pid_t。 */
#if !defined(C210_PID_HOST)
typedef c210_pid_t pid_t;
#endif

void pid_init(c210_pid_t *p, float kp, float ki, float kd);
void pid_reset(c210_pid_t *p);
float pid_compute(c210_pid_t *p, float setpoint, float meas, float dt);

#endif /* C210_PID_H */
