# 固件对抗审查

日期：2026-11-21
审查对象：`Config/stc8g1k08a_c210_conf.h`、`Core/Src/{main,app,pid,heater,led,button,timer,max31855}.c`、`tools/verify.py`、`tools/test_pid.c`、`docs/FIRMWARE_NOTES.md`、`build/stc8g1k08a-c210.mem`
结论：**未发现 BLOCKER**。构建/自检/主机 PID/烧录均通过；剩余风险主要是“未上板实测”和“栈余量未实测”。

> 说明：独立子代理初稿只落了占位；本报告由主代理按固件源码、反汇编、`make verify`、`make test-pid` 和 stcgal 日志逐项复核。每条给出证据与修法。

---

## BLOCKER

未发现。

关键项核对：

1. **Timer0 向量**：`0x000B` 是 `LJMP 0x015B`，`_timer0_isr @0x015B`；ISR 已从 `timer.c` 移到 `main.c`（SDCC 4.6 mcs51 只在含 `main()` 的编译单元生成 IVT）。`verify.py` 新增 0x000B 检查，`ok`。
2. **加热兜底**：`timer0_isr` 每 1ms 调 `heater_task()`；`heater_on_for()` 设 deadline 并置 P5.4，主循环/ISR 到点都强制拉低。机器码有 `SETB/CLR P5.4`。
3. **PID**：`pid_compute` 首次调用 `first` 标志跳过微分（25°C 首采样输出 1.0000，`d_filt=0`）；积分分离 50°C、限幅 2000、饱和时撤销本次积分；过温 400°C 首次进入 `pid_reset` 并本周期 return，395°C 恢复再 reset。
4. **故障/状态机**：传感器故障/越界、T>420°C、单周期跳变 >100°C、连续 10 周期 duty≥790ms 且 T<100°C 都进 FAULT；FAULT 长按 3s 且温度有效且 ≤350°C 才回 STANDBY；裸板 raw=0 有意不判故障（R17 拉低 SO，便于可预测自检）。
5. **看门狗**：`WDT_CONTR=0x35`（EN_WDT=1, CLR_WDT=1, PS=5），按 `T=12×32768×2^(PS+1)/24MHz ≈ 1.05s`；主循环每圈喂狗；`heater_task` 在 ISR 里也能关加热。
6. **资源**：ROM **6864/8192 B**，XRAM **73/1024 B**，栈 **138 B**；`g_app_pid` 和 app 状态在 xdata，避免 IRAM DSEG 溢出。
7. **烧录**：stcgal 成功写入 6864 B，目标 24.011MHz，UID `F794C4CA41F89F`，选项 `reset_pin_enabled=False`（P5.4 普通 GPIO）。

---

## MAJOR

### M1. 栈余量 138B 未实测

- 证据：`.mem` 显示 `Stack starts at: 0x76 ... 138 bytes available`。float PID + MAX31855 + 状态机的实测最坏嵌套没有做栈水位测试。
- 影响：如果后续增加 float 局部变量/递归/中断嵌套，可能栈溢出；当前代码路径应够，但未证明。
- 修法：在 `main` 初始化时把栈区填 `0x5A`，运行 10 分钟后读栈区找最后一个非 `0x5A` 字节，记录高水位；或临时把 SP 改到已知区域做压力测试。上板前建议做一次。

### M2. 热电偶精度/校准未完成

- 证据：`C210_TC_GAIN=1.0f`、`C210_TEMP_OFFSET_X4=0`；BAT54S 钳位动态电阻会带来约 1–4% 差模增益误差；MAX31855 冷端补偿和模块本身也有误差。
- 影响：未校准的 380°C 读数可能偏几度到十几度；验收要求 <5°C（未校准）/ <2°C（校准后）。
- 修法：接 MAX31855 + K 热电偶，用参考温度计在 300°C 和 380°C 两点测；先算 offset，再算 gain；写入 Config 后重新 `make flash`。测试记录填 `TEST_REPORT.md`。

### M3. 裸板 LED 行为未目视确认

- 证据：stcgal 烧录成功，但当前没有相机/人眼确认；`TEST_REPORT.md` 标为待确认。
- 影响：无法证明 P5.5 极性、P5.4 复位默认关断、按键消抖在真实板上符合预期。
- 修法：按 `TEST_REPORT.md §6` 观察：上电慢闪 → 短按 2Hz → 约 10s 5Hz FAULT → 长按回待机；记录视频/照片。

---

## MINOR

1. **`heater_on_for()` / `heater_off()` 无条件 `EA=1`**：当前只在主循环调用；如果以后从 ISR 调用会把中断提前打开。修法：保存 `EA` 原值再恢复，或加注释禁止 ISR 调用。
2. **`timer_delay_ms()` 用 `WDT_CONTR |= 0x10` 喂狗**：WDT 未使能时也会置 CLR_WDT；无害，但语义上应判断 EN_WDT。修法：初始化阶段不喂，或注释说明。
3. **`max31855_read()` 不把 raw==0 当故障**：这是为裸板自检故意保留的；真实传感器在 0°C 时 raw 不会全 0（内部冷端位非 0）。文档已说明，保留。
4. **`FAULT` 中继续喂狗**：如果主循环卡死，WDT 仍会复位；复位后若传感器仍故障会重新进 FAULT。符合“持续复位保持故障”的意图，但无法区分“偶发复位”和“持续故障”。可接受。
5. **主机 PID 测试模型理想化**：固定 K_heat/K_loss、无噪声、1s 采样；实测 C210 头的热时间常数/热损不同。当前增益是**起点**，上板必须按阶跃响应整定；若超调大，先降 Kp/增 Kd；若稳态误差大，增 Ki/检查前馈。
6. **`verify.py` 是静态检查**：机器码/字符串/符号检查不能证明运行时行为；PID 测试是主机侧；真实 MAX31855/加热回路/按键/LED 仍需上板测试。已明确写入 TEST_REPORT 的待办。
7. **`C210_MEASURE_MS=120` 的时序折中**：MAX31855 自由运行 100ms 转换，120ms 窗口可能包含最多 20ms 的加热期数据；对慢热系统影响小，但未实测。若发现读数抖动/偏高，把 `C210_MEASURE_MS` 加到 150–200ms，并相应降 `C210_MAX_DUTY_MS`。
8. **LED 300°C 常亮** 已按用户要求实现；`C210_LED_SOLID_HIGH=400`、`C210_OVERTEMP_C=420` 不变；如果希望 400°C 也常亮而不是快闪，需要改 `>` 为 `>=`，当前按规格 >400 快闪。

---

## 建议保留不动的部分

- PID 的 `first` 首采样保护、积分分离 50°C、积分限幅 2000、抗饱和、FF=0.39。
- 过温 400°C 关加热/395°C 恢复、420°C 锁 FAULT、长按 3s 且 ≤350°C 清除。
- Timer0 1ms + `heater_task` 双调用兜底；`WDT_CONTR=0x35`。
- `g_app_pid`/app 状态放 xdata 的 IRAM 布局。
- LED 300/400 阈值、按键 20ms 消抖/短按 20–1000ms/长按 3s。
- `make verify` 的 0x000B 向量、P5.4/P5.5 机器码、WDT/P3/P5 模式检查（不要为了“过”而削弱）。
