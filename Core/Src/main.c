/* ==========================================================================
 * 文件：Core/Src/main.c
 * 芯片：STC8G1K08A-8PIN（1T 8051，8KB Flash / 256B idata / 1KB xdata）
 * 工具链：SDCC 4.6.0（-mmcs51）
 * 功能：JBC C210 焊笔控制器
 *
 * 引脚：
 *   P3.0  MAX31855 SCK   推挽输出
 *   P3.1  MAX31855 SO    高阻输入（同时是 ISP TX）
 *   P3.2  MAX31855 CS    推挽输出，初始高（同时是 ISP 下载模式脚，必须高）
 *   P3.3  按键           高阻输入 + 内部上拉，低有效
 *   P5.4  加热 / 4053 INH 推挽输出，初始低
 *   P5.5  状态 LED       推挽输出，初始低
 *
 * 主循环：app_task / heater_task / led_task / button_task + 喂狗。
 * heater_task 同时由 Timer0 中断每 1ms 调用，保证主循环卡死时也能关加热。
 * ========================================================================== */
#include "stc8g1k08a_regs.h"
#include "stc8g1k08a_c210_conf.h"
#include "timer.h"
#include "max31855.h"
#include "pid.h"
#include "led.h"
#include "button.h"
#include "heater.h"
#include "app.h"

/* ------------------------------------------------------------
 * 系统时钟 / 扩展 SFR / 复位脚
 * ------------------------------------------------------------ */
static void SystemClock_Config(void)
{
    /* 允许访问 0xFE00 起的扩展 SFR（CLKDIV、PxPU 等） */
    EAXFR_ENABLE();

    /* UART1 固定回 P3.0/P3.1，避免硬件选项把 P5.4/P5.5 占作串口 */
    P_SW1 = 0x00;

    /* HIRC 不分频；HIRC 频率由 ISP 下载时校准（本工程 -t 24000） */
    CLKDIV = 0x00;

    /* 清除 P54RST：保证 P5.4 是普通 I/O，而不是复位脚。
     * RSTCFG 是标准 SFR（0xFF），读-改-写保留其它复位选项。 */
    RSTCFG &= (unsigned char)~0x10;
}

/* ------------------------------------------------------------
 * 板级 IO 初始化：6 个 I/O 全部显式配置
 * ------------------------------------------------------------ */
static void Board_Init(void)
{
    /* 先写初始电平，再改端口模式，避免上电瞬间误加热/误点亮。
     * 默认准双向口锁存为 1，所以先把 P5.4 拉低。 */
    C210_HEATER_OFF();      /* P5.4 = 0：加热关断，4053 闭合 */
    C210_LED_OFF();         /* P5.5 = 0：LED 灭 */
    P30 = 0;                /* SCK 低 */
    P31 = 1;                /* SO 输入，释放 */
    P32 = 1;                /* CS 高，MAX31855 空闲 */
    P33 = 1;                /* 按键上拉，未按下为高 */

    /* P3.0 推挽输出（SCK） */
    GPIO_P3_SetMode(GPIO_Pin_0, GPIO_Mode_Output_PP);
    /* P3.1 高阻输入（SO；MAX31855 输出，R17 下拉） */
    GPIO_P3_SetMode(GPIO_Pin_1, GPIO_Mode_Input_HIP);
    /* P3.2 推挽输出（CS，外部 R13 10k 上拉） */
    GPIO_P3_SetMode(GPIO_Pin_2, GPIO_Mode_Output_PP);
    /* P3.3 高阻输入（按键，外部 10k + 内部上拉） */
    GPIO_P3_SetMode(GPIO_Pin_3, GPIO_Mode_Input_HIP);
    /* P5.4 推挽输出（Q1 栅极 / 4053 INH） */
    GPIO_P5_SetMode(GPIO_Pin_4, GPIO_Mode_Output_PP);
    /* P5.5 推挽输出（LED） */
    GPIO_P5_SetMode(GPIO_Pin_5, GPIO_Mode_Output_PP);

    /* P3.3 打开内部上拉（P3PU.3，XFR，需要 EAXFR=1） */
    GPIO_SetPullUp(GPIO_Port_3, GPIO_Pin_3, HAL_State_ON);

    /* 改完模式后再确认一次关键初始电平 */
    C210_HEATER_OFF();
    C210_LED_OFF();
    P30 = 0;
    P32 = 1;
}

/* ------------------------------------------------------------
 * Timer0 中断（向量 1）
 *
 * 重要：SDCC 4.6 的 mcs51 后端只在“包含 main() 的编译单元”生成
 * 中断向量表；如果 __interrupt 函数放在 timer.c，链接后 0x000B
 * 不会出现 LJMP，中断会跳到随机代码。所以 ISR 必须放在 main.c。
 * ------------------------------------------------------------ */
void timer0_isr(void) __interrupt(1)
{
    timer_isr_tick();       /* 1ms 毫秒计数 +1 */

    /* 加热最长导通时间的安全兜底：每 1ms 检查 deadline */
    heater_task();
}

/* ------------------------------------------------------------
 * 主函数
 * ------------------------------------------------------------ */
void main(void)
{
    SystemClock_Config();
    Board_Init();

    /* 初始化顺序：节拍 -> 传感器 -> PID -> LED -> 按键 -> 加热 -> 应用 */
    timer_init();
    max31855_init();
    pid_init(&g_app_pid, C210_PID_KP, C210_PID_KI, C210_PID_KD);
    led_init();
    button_init();
    heater_init();
    app_init();

    /* 看门狗：EN_WDT=1, CLR_WDT=1, PS=5 -> 24MHz 下约 1.05s
     * 注意：写 0x35 时 CLR_WDT 会立即清零计数并自动回 0。 */
    WDT_CONTR = 0x35;

    while (1)
    {
        app_task();
        heater_task();      /* 冗余调用：主循环也检查一次，ISR 仍是 1ms 兜底 */
        led_task();
        button_task();

        /* 喂狗：置 CLR_WDT 位 */
        WDT_CONTR |= 0x10;
    }
}
