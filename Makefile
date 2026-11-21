# Makefile — stc8g1k08a-c210（SDCC MCS-51，中文注释）
#
# 工具链固定指向工作区内的 sdcc-c251（该包同时含 mcs51 和 mcs251 后端），
# 不依赖 PATH。
#
# STC8G1K08A：8KB Flash + 256B idata + 1KB xdata（共 1.25KB SRAM），1T 8051。
# 代码从 0x0000 开始（传统 8051 复位向量），不要照抄 STC32G 的 0xFF0000。
TOOLCHAIN := /Users/theo-richard/workspace/toolchains/sdcc-c251/bin/
CC        := $(TOOLCHAIN)sdcc
PACKIHX   := $(TOOLCHAIN)packihx
OBJCOPY   := $(TOOLCHAIN)sdobjcopy
S51       := $(TOOLCHAIN)s51

TARGET    := stc8g1k08a-c210
BUILD     := build
HOSTCC    ?= cc

# -mmcs51：8051 内核（不是 STC32G 的 -mmcs251）
# --model-small：变量默认放 data/idata
# --code-size 8192：8KB Flash
# --xram-size 1024：片内扩展 RAM（datasheet：xdata 1KB，idata 256B）
# --iram-size 256：片内直接/间接寻址 RAM 256B
MCU       := -mmcs51 --model-small --code-size 8192 --xram-size 1024 --iram-size 256
INCLUDES  := -IConfig -ICore/Inc -IDrivers/STC8G/Inc \
             -IDrivers/STC8G/FwLib_STC8/include
DEFS      := -D__CONF_MCU_MODEL=MCU_MODEL_STC8G1K08 \
             -D__CONF_FOSC=24000000UL
CFLAGS    := $(MCU) $(INCLUDES) $(DEFS) --std-c23
LDFLAGS   := $(MCU)

C_SOURCES := Core/Src/main.c \
             Core/Src/app.c \
             Core/Src/max31855.c \
             Core/Src/pid.c \
             Core/Src/heater.c \
             Core/Src/led.c \
             Core/Src/button.c \
             Core/Src/timer.c
OBJECTS   := $(addprefix $(BUILD)/,$(notdir $(C_SOURCES:.c=.rel)))

# 烧录参数：USB-TTL 串口、stcgal 协议、波特率
PORT      ?= /dev/cu.usbmodemFX2348N1
PROTOCOL  ?= stc8g
# 实测：115200/2400 在这块 USB-TTL 上会 pulse timeout；
# 降到 57600/1200 + TRIM 24000 后稳定通过。
BAUD      ?= 57600
HANDSHAKE ?= 1200
TRIM      ?= 24000
STCGAL    ?= /Users/theo-richard/workspace/toolchains/stcgal/bin/stcgal

all: $(BUILD)/$(TARGET).ihx $(BUILD)/$(TARGET).hex $(BUILD)/$(TARGET).bin

$(BUILD):
	mkdir -p $@

$(BUILD)/%.rel: Core/Src/%.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/$(TARGET).ihx: $(OBJECTS)
	$(CC) $(LDFLAGS) $(OBJECTS) -o $@

$(BUILD)/$(TARGET).hex: $(BUILD)/$(TARGET).ihx
	$(PACKIHX) $< > $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).ihx
	$(OBJCOPY) -I ihex -O binary $< $@

# 从 .mem 打印 ROM 占用 / XRAM / 初始栈顶
size: $(BUILD)/$(TARGET).ihx
	@echo "=== 代码/数据区（来自 $(BUILD)/$(TARGET).mem）==="
	@grep -E "ROM/EPROM/FLASH|EXTERNAL RAM|Stack" $(BUILD)/$(TARGET).mem || true

# 反汇编（s51 dc + SFR/位/符号标注）
dis: $(BUILD)/$(TARGET).ihx
	/usr/bin/python3 -I tools/dis8051.py $(BUILD)/$(TARGET).ihx \
		--s51 $(S51) --map $(BUILD)/$(TARGET).map \
		--out $(BUILD)/$(TARGET).dis

symbols: $(BUILD)/$(TARGET).map
	@grep -E "^C:|^ +Value" $(BUILD)/$(TARGET).map | head -100

# 静态自检
verify: all
	/usr/bin/python3 -I tools/verify.py $(BUILD)/$(TARGET).ihx $(BUILD)/$(TARGET).map

# 主机侧 PID 阶跃测试：系统 cc 编译真实 pid.c，输出 build/pid_step.csv
test-pid: | $(BUILD)
	$(HOSTCC) -O2 -std=c11 -Wall -Wextra -ICore/Inc -IConfig \
		-DC210_PID_HOST tools/test_pid.c Core/Src/pid.c -lm -o $(BUILD)/test_pid
	./$(BUILD)/test_pid

# 烧录：先确认串口存在；看到 Waiting for MCU 后给目标板断电再上电
flash: $(BUILD)/$(TARGET).hex
	@test -e $(PORT) || { echo "找不到串口 $(PORT)（检查 USB-TTL）"; exit 1; }
	$(STCGAL) -p $(PORT) -P $(PROTOCOL) -l $(HANDSHAKE) -b $(BAUD) -t $(TRIM) $<

# 热插拔烧录：先运行本目标，然后按提示拔插 USB-TTL / 目标板 VCC
flash-hotplug: $(BUILD)/$(TARGET).hex
	/usr/bin/python3 -I tools/flash_hotplug.py \
		--port $(PORT) --hex $< --stcgal $(STCGAL) \
		--protocol $(PROTOCOL) --baud $(BAUD) --trim $(TRIM)

clean:
	rm -rf $(BUILD)

.PHONY: all size dis symbols verify test-pid flash flash-hotplug clean
