/**
 * @file    max31855.h
 * @brief   MAX31855 K 型热电偶放大器位操作 SPI 驱动
 */
#ifndef C210_MAX31855_H
#define C210_MAX31855_H

#include <stdint.h>

void max31855_init(void);

/**
 * 读取一次热电偶温度。
 * @param tc_x4 输出，0.25°C 为单位；成功时有效
 * @return 0 = 成功；1 = 故障（SPI 故障位 / 读数越界）
 *
 * 注意：裸板没有 MAX31855 时，R17 把 SO 拉低，raw 全 0，返回 0°C。
 * 这是有意保留的“可预测上电”行为，不在驱动层把 raw==0 当故障。
 */
uint8_t max31855_read(int16_t *tc_x4);

#endif /* C210_MAX31855_H */
