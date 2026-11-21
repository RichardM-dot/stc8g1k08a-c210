#!/usr/bin/env python3
"""
预加载 stcgal，并让串口打开操作重试等待。

用途：目标板由 USB-TTL 供电，冷启动只能拔插 USB-TTL。普通流程里
stcgal 启动/导入 Python 包要几百毫秒，等它打开串口时芯片的 ISP 握手
窗口可能已经过去。本脚本先启动（端口还不存在），把 stcgal 模块全部
导入好，然后调用 stcgal.cli()；此时 stcgal 会尝试打开串口，我们把
serial.Serial 换成“每 5ms 重试、最多 15 秒”的版本。用户插回 USB-TTL
的瞬间串口就绪，stcgal 立刻握手。

必须用 stcgal 的 venv Python 运行：
  /Users/theo-richard/workspace/toolchains/stcgal/venv/bin/python \
      -I tools/stcgal_retry.py -p /dev/cu.usbmodem... -P stc8g ... file.hex
"""
import sys
import time

import serial

_original_serial = serial.Serial


class RetrySerial(_original_serial):
    """保留 Serial 类的全部类属性（BAUDRATES 等），只重试 __init__ 打开串口。"""

    def __init__(self, *args, **kwargs):
        deadline = time.monotonic() + 15.0
        last_exc = None
        while time.monotonic() < deadline:
            try:
                super().__init__(*args, **kwargs)
                return
            except Exception as exc:  # SerialException / OSError / FileNotFoundError
                last_exc = exc
                try:
                    self.close()
                except Exception:
                    pass
                time.sleep(0.005)
        if last_exc is not None:
            raise last_exc
        raise serial.SerialException("retry_serial: timeout")


serial.Serial = RetrySerial

# 导入放在 patch 之后；stcgal.protocols 里调用的是 serial.Serial 模块属性，
# 所以 patch 对已经导入/之后导入的模块都生效。
from stcgal.frontend import cli  # noqa: E402

if __name__ == "__main__":
    print("stcgal_retry: 等待串口出现（端口一出现就打开）...", flush=True)
    sys.exit(cli())
