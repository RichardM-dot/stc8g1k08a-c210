/**
 * @file    max31855.c
 * @brief   MAX31855 位操作 SPI 读取
 *
 * 时序：CS 低 -> 32 个时钟（SCK 高时读 SO，再拉低）-> CS 高。
 * 每个半周期插入少量 NOP，保证 24MHz 1T 下 SCK 不会被拉得过高。
 *
 * 数据格式（32 位）：
 *   bit31..18  14 位有符号热电偶温度，0.25°C/LSB
 *   bit17..4   12 位内部冷端温度
 *   bit3       保留
 *   bit2       对 VCC 短路
 *   bit1       对 GND 短路
 *   bit0       热电偶开路
 */
#include "stc8g1k08a_regs.h"
#include "stc8g1k08a_c210_conf.h"
#include "max31855.h"

/* 约 4 个 NOP 的半周期延时，SCK 频率远低于 MAX31855 的 5MHz 上限 */
static void spi_halfbit_delay(void)
{
    NOP();
    NOP();
    NOP();
    NOP();
}

void max31855_init(void)
{
    /* 模式由 Board_Init 统一配置，这里再保证一次方向和空闲电平 */
    GPIO_P3_SetMode(GPIO_Pin_0, GPIO_Mode_Output_PP);   /* SCK */
    GPIO_P3_SetMode(GPIO_Pin_1, GPIO_Mode_Input_HIP);   /* SO  */
    GPIO_P3_SetMode(GPIO_Pin_2, GPIO_Mode_Output_PP);   /* CS  */

    C210_MAX_CS_HIGH();
    C210_MAX_SCK_LOW();

    /* 给 MAX31855 一点上电稳定时间（首次转换需要约 100ms，
     * BOOT 状态还会再等 150ms，这里只做短延时） */
    spi_halfbit_delay();
}

uint8_t max31855_read(int16_t *tc_x4)
{
    uint32_t raw = 0;
    uint8_t  i;
    uint8_t  fault;
    int32_t  value;

    C210_MAX_CS_LOW();
    spi_halfbit_delay();

    for (i = 0; i < 32; i++)
    {
        /* SCK 高时 SO 有效 */
        C210_MAX_SCK_HIGH();
        spi_halfbit_delay();

        raw <<= 1;
        if (C210_MAX_SO_PIN)
        {
            raw |= 1UL;
        }

        C210_MAX_SCK_LOW();
        spi_halfbit_delay();
    }

    C210_MAX_CS_HIGH();
    spi_halfbit_delay();

    /* 故障位：bit0 开路、bit1 对 GND 短路、bit2 对 VCC 短路 */
    fault = (uint8_t)(raw & 0x07UL);
    if (fault != 0)
    {
        return 1;
    }

    /* 14 位有符号数，bit31 是符号位；先转 int32_t 再算术右移 18 位。
     * 不要写成 raw >> 18（无符号右移会丢掉符号扩展）。 */
    value = (int32_t)raw >> 18;

    /* 允许范围 -50°C..500°C，0.25°C/LSB */
    if (value < -200 || value > 2000)
    {
        return 1;
    }

    *tc_x4 = (int16_t)value;

    /* 故意不判断 raw==0：裸板 R17 把 SO 拉低，上电读 0°C 进入 STANDBY，
     * 按键启动后由“连续 10 周期满占空比不升温”判加热回路故障。 */
    return 0;
}
