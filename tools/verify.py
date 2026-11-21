#!/usr/bin/env python3
"""
STC8G1K08A C210 固件静态自检。

检查项：
  1. IHX 可解析，地址全部落在 0x0000..0x1FFF（8KB Flash），ROM 1..8192B
  2. 0x0000 是 LJMP 复位向量，目标在 0x0000..0x1FFF
  3. map 中存在主流程符号：
       _main _app_task _max31855_read _pid_compute
       _heater_task _led_task _button_task
  4. Config 文本含 C210_SETPOINT_C 和 380/300/400/420
  5. main.lst 含 6 个 I/O 的初始化痕迹（位名或寄存器名）
  6. 机器码含 P5.5 / P5.4 的 SETB 和 CLR：
       SETB P5.5 = D2 CD, CLR P5.5 = C2 CD
       SETB P5.4 = D2 CC, CLR P5.4 = C2 CC
  7. .bin 大小 == 完整镜像（.mem ROM 大小）
  8. XRAM == 1024B，初始栈顶可解析
  9. build/*.lst 合计包含 WDT_CONTR / TMOD / AUXR / P3M0 / P3M1 / P5M0 / P5M1，
     且 main.lst 含 WDT_CONTR、timer.lst 含 TMOD/AUXR

用法：python3 -I tools/verify.py build/xxx.ihx build/xxx.map
"""
import re
import sys
from pathlib import Path


def parse_ihx(path):
    mem = {}
    base = 0
    with open(path, "r", encoding="ascii", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if not line.startswith(":"):
                raise SystemExit(f"IHX 第 {lineno} 行不是 Intel HEX 记录: {line!r}")
            raw = bytes.fromhex(line[1:])
            count = raw[0]
            addr = (raw[1] << 8) | raw[2]
            rectype = raw[3]
            data = raw[4:4 + count]
            if len(data) != count:
                raise SystemExit(f"IHX 第 {lineno} 行长度不符")
            if rectype == 0x00:
                for i, b in enumerate(data):
                    mem[base + addr + i] = b
            elif rectype == 0x01:
                break
            elif rectype == 0x02:
                base = int.from_bytes(data, "big") << 4
            elif rectype == 0x04:
                base = int.from_bytes(data, "big") << 16
            # 03/05 是入口地址记录，忽略
    return mem


def parse_map_symbols(path):
    syms = {}
    pat = re.compile(r"^C:\s+([0-9A-Fa-f]+)\s+(\S+)")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = pat.match(line.rstrip())
            if m:
                syms[m.group(2)] = int(m.group(1), 16)
    return syms


def parse_mem(path):
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    m = re.search(r"ROM/EPROM/FLASH\s+([0-9a-fA-Fx]+)\s+([0-9a-fA-Fx]+)\s+(\d+)", text)
    if not m:
        return None

    # SDCC 4.6 的 .mem 是四列：
    #   EXTERNAL RAM  0x0001  0x0049  73  1024   (start/end/used/max)
    # 旧版是两列：EXTERNAL RAM 0 1024
    xram = None
    xram_used = None
    for line in text.splitlines():
        if "EXTERNAL RAM" not in line:
            continue
        nums = re.findall(r"0x[0-9a-fA-F]+|\d+", line)
        if len(nums) >= 4:
            xram_used = int(nums[2], 0)
            xram = int(nums[3], 0)
        elif len(nums) >= 2:
            xram = int(nums[-1], 0)
        break

    sm = re.search(r"(?:initial )?stack starts at: 0x([0-9a-fA-F]+)", text, re.I)
    sf = re.search(r"with\s+(\d+)\s+bytes available", text, re.I)
    return {
        "start": int(m.group(1), 16),
        "end": int(m.group(2), 16),
        "size": int(m.group(3)),
        "xram": xram,
        "xram_used": xram_used,
        "stack": sm.group(1) if sm else "?",
        "stack_free": sf.group(1) if sf else "?",
    }


def find_bytes(mem, pattern):
    pat = bytes(pattern)
    hits = []
    for addr in range(0, 0x2000 - len(pat) + 1):
        if all(mem.get(addr + i) == pat[i] for i in range(len(pat))):
            hits.append(addr)
    return hits


def main():
    if len(sys.argv) < 3:
        raise SystemExit("用法: verify.py <ihx> <map>")
    ihx, mapf = sys.argv[1], sys.argv[2]
    build = Path(ihx).parent
    root = build.parent
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + msg)
        ok = ok and bool(cond)

    # ---------- 1. IHX / 复位向量 ----------
    mem = parse_ihx(ihx)
    check(bool(mem), f"IHX 可解析，共 {len(mem)} 字节")
    check(min(mem) == 0x0000, f"最低地址 0x{min(mem):04X} == 0x0000（复位向量）")
    check(max(mem) <= 0x1FFF, f"最高地址 0x{max(mem):04X} <= 0x1FFF（8KB Flash）")

    lo = min(mem)
    vec = [mem.get(lo + i, 0) for i in range(3)]
    check(vec[0] == 0x02, f"0x0000 是 LJMP（实际 {vec[0]:#04x}）")
    target = (vec[1] << 8) | vec[2]
    check(0x0000 <= target <= 0x1FFF,
          f"复位目标 0x{target:04X} 落在 0x0000..0x1FFF")

    # ---------- 2. map 符号 ----------
    syms = parse_map_symbols(mapf)
    for name in ("_main", "_app_task", "_max31855_read", "_pid_compute",
                 "_heater_task", "_led_task", "_button_task"):
        check(name in syms, f"符号 {name} 存在 (@0x{syms.get(name, 0):04X})")

    # Timer0 中断向量在 0x000B，必须是 LJMP 到 _timer0_isr。
    # SDCC 4.6 只在含 main() 的模块生成 IVT，这一项能防止 ISR 放错文件。
    tv = [mem.get(0x000B + i, 0) for i in range(3)]
    check(tv[0] == 0x02, f"0x000B 是 Timer0 LJMP（实际 {tv[0]:#04x}）")
    tvec = (tv[1] << 8) | tv[2]
    check(0x0000 <= tvec <= 0x1FFF,
          f"Timer0 向量目标 0x{tvec:04X} 在 0x0000..0x1FFF")
    check(syms.get("_timer0_isr") == tvec,
          f"_timer0_isr @0x{syms.get('_timer0_isr', 0):04X} "
          f"== Timer0 向量 0x{tvec:04X}")

    # ---------- 3. Config 参数 ----------
    conf = root / "Config" / "stc8g1k08a_c210_conf.h"
    if conf.exists():
        text = conf.read_text(encoding="utf-8", errors="replace")
        check("C210_SETPOINT_C" in text, "Config 含 C210_SETPOINT_C")
        for token in ("380", "300", "400", "420"):
            check(token in text, f"Config 文本含 {token}")
    else:
        check(False, f"Config 文件存在: {conf}")

    # ---------- 4. main.lst 的 6 个 IO 初始化 ----------
    main_lst = build / "main.lst"
    if main_lst.exists():
        text = main_lst.read_text(encoding="utf-8", errors="replace")
        # SDCC 的汇编列表把位变量写成 _P30.._P55；也接受源码注释里的 P3.0 形式
        pin_forms = {
            "P3.0": ("P3.0", "P30", "_P30"),
            "P3.1": ("P3.1", "P31", "_P31"),
            "P3.2": ("P3.2", "P32", "_P32"),
            "P3.3": ("P3.3", "P33", "_P33"),
            "P5.4": ("P5.4", "P54", "_P54"),
            "P5.5": ("P5.5", "P55", "_P55"),
        }
        for pin, forms in pin_forms.items():
            matched = [f for f in forms if f in text]
            check(bool(matched),
                  f"main.lst 含 {pin} 的初始化痕迹"
                  f"（匹配 {', '.join(matched) if matched else '无'}）")
        for reg in ("P3M0", "P3M1", "P5M0", "P5M1"):
            check(reg in text, f"main.lst 含 {reg} 的端口模式配置")
        check("WDT_CONTR" in text, "main.lst 含 WDT_CONTR 看门狗配置")
        check("_timer0_isr" in text and "heater_task" in text,
              "main.lst 的 Timer0 ISR 调用 heater_task")
    else:
        check(False, "main.lst 存在")

    # ---------- 5. 机器码：P5.5 / P5.4 SETB/CLR ----------
    patterns = {
        "SETB P5.5 (D2 CD)": [0xD2, 0xCD],
        "CLR  P5.5 (C2 CD)": [0xC2, 0xCD],
        "SETB P5.4 (D2 CC)": [0xD2, 0xCC],
        "CLR  P5.4 (C2 CC)": [0xC2, 0xCC],
    }
    for name, pat in patterns.items():
        hits = find_bytes(mem, pat)
        check(bool(hits),
              f"机器码含 {name} @ "
              f"{', '.join(f'0x{a:04X}' for a in hits) or '未找到'}")

    # ---------- 6. .mem / .bin ----------
    info = parse_mem(str(build / (Path(ihx).stem + ".mem")))
    if info:
        check(info["start"] == 0x0000,
              f"ROM 起始 0x{info['start']:04X}（应为 0x0000）")
        check(1 <= info["size"] <= 8192,
              f"ROM 占用 {info['size']} B（1..8192）")
        used = info.get("xram_used")
        check(info["xram"] == 1024,
              f"XRAM 配置 {info['xram']} B（应为 1024，已用 "
              f"{used if used is not None else '?'} B）")
        print(f"  info 初始栈顶 0x{info['stack']}"
              f"（{info.get('stack_free', '?')}B 可用）")
    else:
        check(False, "能解析 .mem")
        info = {"size": max(mem) + 1}

    binf = build / (Path(ihx).stem + ".bin")
    if binf.exists():
        expect = info["size"]
        check(binf.stat().st_size == expect,
              f".bin 大小 {binf.stat().st_size} B == 完整镜像 {expect} B")
    else:
        check(False, ".bin 存在")

    # ---------- 7. 所有 .lst 的寄存器配置 ----------
    lst_files = sorted(build.glob("*.lst"))
    check(bool(lst_files), f"build 下存在 .lst（{len(lst_files)} 个）")
    union = "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in lst_files
    )
    for reg in ("WDT_CONTR", "TMOD", "AUXR", "P3M0", "P3M1", "P5M0", "P5M1"):
        check(reg in union, f"build/*.lst 合计含 {reg}")

    timer_lst = build / "timer.lst"
    if timer_lst.exists():
        text = timer_lst.read_text(encoding="utf-8", errors="replace")
        for reg in ("TMOD", "AUXR", "TL0", "TH0", "TR0", "ET0", "EA"):
            check(reg in text, f"timer.lst 含 {reg} 的 Timer0 配置")
    else:
        check(False, "timer.lst 存在")

    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
