/**
 * @file    tools/test_pid.c
 * @brief   PID 主机侧阶跃测试（系统 cc 编译，不依赖 SDCC）
 *
 * 一阶热模型（dt=1s）：
 *   T[k+1] = T[k] + duty*78.7 - (T[k]-25)*0.086
 *
 * 场景：25°C 环境，200s 阶跃到 380°C。
 * 断言：
 *   1. pid_reset() 后首次 25°C 采样不产生假微分（输出直接饱和）
 *   2. 超调 < 10%（<38°C）
 *   3. 进入并保持 ±1°C 的时间 < 60s
 *   4. 200s 稳态误差 < 1°C
 *
 * 输出 build/pid_step.csv，供画图。
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "pid.h"
#include "stc8g1k08a_c210_conf.h"

#define SIM_SECONDS   200
#define SETPOINT      380.0
#define T_AMBIENT     25.0
#define K_HEAT        78.7
#define K_LOSS        0.086

static int failures = 0;

static void check(int cond, const char *name, double value, double limit)
{
    if (cond)
    {
        printf("  ok   %-36s %.3f (limit %.3f)\n", name, value, limit);
    }
    else
    {
        printf("  FAIL %-36s %.3f (limit %.3f)\n", name, value, limit);
        failures++;
    }
}

int main(void)
{
    c210_pid_t pid;
    double temperature = T_AMBIENT;
    double peak = T_AMBIENT;
    double steady;
    double overshoot;
    int settle_time = 0;
    int k;
    FILE *csv;

    /* ---- 1. 首采样 25°C：必须没有 -(25-0)/1 的假微分 ---- */
    pid_init(&pid, C210_PID_KP, C210_PID_KI, C210_PID_KD);
    pid_reset(&pid);
    {
        float first = pid_compute(&pid, (float)SETPOINT, (float)T_AMBIENT, 1.0f);
        printf("首采样 25°C 输出: %.4f\n", (double)first);
        check(first > 0.99f, "first sample output saturated", (double)first, 0.99);
        check(pid.d_filt == 0.0f, "first sample d_filt == 0", (double)pid.d_filt, 0.0);
    }

    /* ---- 2. 200s 阶跃仿真 ---- */
    pid_init(&pid, C210_PID_KP, C210_PID_KI, C210_PID_KD);
    pid_reset(&pid);

    csv = fopen("build/pid_step.csv", "w");
    if (!csv)
    {
        fprintf(stderr, "无法创建 build/pid_step.csv（请在工程根目录运行）\n");
        return 1;
    }
    fprintf(csv, "time_s,temperature_c,setpoint_c,duty\n");

    for (k = 1; k <= SIM_SECONDS; k++)
    {
        float duty = pid_compute(&pid, (float)SETPOINT, (float)temperature, 1.0f);
        double duty_d = (double)duty;

        if (duty_d < 0.0) duty_d = 0.0;
        if (duty_d > 1.0) duty_d = 1.0;

        temperature += duty_d * K_HEAT - (temperature - T_AMBIENT) * K_LOSS;

        if (temperature > peak)
        {
            peak = temperature;
        }
        if (fabs(temperature - SETPOINT) > 1.0)
        {
            /* 最后一次超出 ±1°C 的时刻；后面都必须在带内 */
            settle_time = k;
        }

        fprintf(csv, "%d,%.4f,%.1f,%.6f\n",
                k, temperature, SETPOINT, duty_d);
    }
    fclose(csv);

    steady = temperature;
    overshoot = peak - SETPOINT;

    printf("\n仿真结果（%ds，25 -> 380°C）：\n", SIM_SECONDS);
    printf("  峰值      : %.2f °C\n", peak);
    printf("  超调      : %.2f °C (%.2f%%)\n",
           overshoot, 100.0 * overshoot / SETPOINT);
    printf("  调节时间  : %d s（进入并保持 ±1°C）\n", settle_time);
    printf("  稳态值    : %.3f °C\n", steady);
    printf("  稳态误差  : %.3f °C\n", steady - SETPOINT);

    check(overshoot < 0.10 * SETPOINT,
          "overshoot < 10%", overshoot, 0.10 * SETPOINT);
    check(settle_time > 0 && settle_time < 60,
          "settling time < 60 s", (double)settle_time, 60.0);
    check(fabs(steady - SETPOINT) < 1.0,
          "steady-state error < 1 C", fabs(steady - SETPOINT), 1.0);

    if (failures)
    {
        printf("\nSOME PID CHECKS FAILED: %d\n", failures);
        return 1;
    }

    printf("\nALL PID CHECKS PASSED (CSV: build/pid_step.csv)\n");
    return 0;
}
