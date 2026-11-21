#!/usr/bin/env python3
"""
热插拔烧录：等待 USB-TTL 重新枚举后立刻启动 stcgal。

适用场景：目标板由 USB-TTL 供电，冷启动只能靠拔插 USB-TTL。
如果先启动 stcgal 再拔 USB，stcgal 打开的串口会消失并报
`[Errno 6] Device not configured`。本脚本先等端口消失，再等它出现，
出现后立刻启动 stcgal，尽量赶上芯片 ISP 的握手窗口。

用法：
  python3 -I tools/flash_hotplug.py \
      --port /dev/cu.usbmodemFX2348N1 \
      --hex build/stc8g1k08a-blink-diag.hex
"""
import argparse
import os
import subprocess
import sys
import time

DEFAULT_STCGAL = "/Users/theo-richard/workspace/toolchains/stcgal/bin/stcgal"
STCGAL_PYTHON = "/Users/theo-richard/workspace/toolchains/stcgal/venv/bin/python"
RETRY_WRAPPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stcgal_retry.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--hex", required=True)
    ap.add_argument("--stcgal", default=DEFAULT_STCGAL)
    ap.add_argument("--protocol", default="stc8g")
    ap.add_argument("--baud", default="115200")
    ap.add_argument("--trim", default="24000")
    ap.add_argument("--disappear-timeout", type=float, default=8.0,
                    help="端口一直不消失时，等这么多秒后直接启动 stcgal；<=0 表示一直等")
    args = ap.parse_args()

    if not os.path.exists(args.hex):
        raise SystemExit(f"找不到 hex: {args.hex}")

    print(f"端口: {args.port}")
    print("请现在拔掉 USB-TTL（或目标板 VCC），等 1 秒再插回……")
    print("脚本会等端口消失后重新出现，再立刻启动 stcgal。")

    start = time.time()
    while os.path.exists(args.port):
        if args.disappear_timeout > 0 and (time.time() - start) >= args.disappear_timeout:
            break
        time.sleep(0.05)

    if os.path.exists(args.port):
        print("端口没有消失：按“只给目标板断电”处理，直接启动 stcgal。")
        cmd = [
            args.stcgal,
            "-p", args.port,
            "-P", args.protocol,
            "-b", str(args.baud),
            "-t", str(args.trim),
            args.hex,
        ]
    else:
        # 端口已经消失：立刻启动“预加载 + 串口重试”的 stcgal。
        # 它在端口还不存在时就开始重试打开；用户插回 USB-TTL 的瞬间
        # 就能打开串口并发握手，避免冷启动窗口错过。
        print("端口已消失：启动预加载 stcgal，端口一出现就握手……")
        cmd = [
            STCGAL_PYTHON,
            "-I",
            RETRY_WRAPPER,
            "-p", args.port,
            "-P", args.protocol,
            "-b", str(args.baud),
            "-t", str(args.trim),
            args.hex,
        ]

    print("+ " + " ".join(cmd))
    sys.stdout.flush()
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
