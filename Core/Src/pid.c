/**
 * @file    pid.c
 * @brief   归一化输出 PID（0.0..1.0）
 *
 * 结构：
 *   e        = setpoint - meas
 *   积分分离：|e| <= i_sep 时才累加 e*dt
 *   抗饱和：  输出饱和且误差继续朝饱和方向时，撤销本次积分
 *   微分：    对测量值微分 d_raw = -(meas-prev)/dt，再做一阶低通
 *   前馈：    ff 直接叠加，380°C 稳态约 0.39
 *
 * 首次 compute 在 pid_reset() 之后调用时跳过微分冲击：
 * 只把 prev_meas 设为当前测量值，d_filt 保持 0。
 *
 * 本文件不包含 8051 头文件，可直接用系统 cc 做主机测试。
 */
#include "pid.h"
#include "stc8g1k08a_c210_conf.h"

/* 不使用 math.h，避免把浮点数学库整个链进来 */
static float pid_absf(float x)
{
    return (x < 0.0f) ? -x : x;
}

void pid_init(c210_pid_t *p, float kp, float ki, float kd)
{
    p->kp = kp;
    p->ki = ki;
    p->kd = kd;

    p->ff = C210_PID_FF;
    p->i_limit = C210_PID_I_LIMIT;
    p->i_sep = C210_PID_I_SEP;
    p->d_alpha = C210_PID_D_ALPHA;

    pid_reset(p);
}

void pid_reset(c210_pid_t *p)
{
    p->integral = 0.0f;
    p->prev_meas = 0.0f;
    p->d_filt = 0.0f;
    p->out = 0.0f;
    p->first = 1;
}

float pid_compute(c210_pid_t *p, float setpoint, float meas, float dt)
{
    float e;
    float d_raw;
    float integral;
    float out;

    e = setpoint - meas;

    integral = p->integral;

    /* 积分分离 + 积分限幅 */
    if (pid_absf(e) <= p->i_sep)
    {
        integral += e * dt;

        if (integral > p->i_limit)
        {
            integral = p->i_limit;
        }
        else if (integral < -p->i_limit)
        {
            integral = -p->i_limit;
        }
    }

    if (p->first)
    {
        /* pid_reset 后第一次调用：没有历史测量值，微分项按 0 计算。
         * 否则 25°C 首读会产生 -(25-0)/1 = -25 的假微分，
         * 把刚上电的输出压低。 */
        p->prev_meas = meas;
        p->d_filt = 0.0f;
        d_raw = 0.0f;
        p->first = 0;
    }
    else
    {
        /* 对测量值微分，避免设定值阶跃时的微分冲击 */
        d_raw = -(meas - p->prev_meas) / dt;
        p->d_filt += p->d_alpha * (d_raw - p->d_filt);
    }

    out = p->kp * e + p->ki * integral + p->kd * p->d_filt + p->ff;

    /* 抗饱和：输出已经饱和且误差继续推向饱和方向时，不接受本次积分 */
    if (out > 1.0f)
    {
        out = 1.0f;
        if (e > 0.0f)
        {
            integral = p->integral;
        }
    }
    else if (out < 0.0f)
    {
        out = 0.0f;
        if (e < 0.0f)
        {
            integral = p->integral;
        }
    }

    p->integral = integral;
    p->prev_meas = meas;
    p->out = out;

    return out;
}
