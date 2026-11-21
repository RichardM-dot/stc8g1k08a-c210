#!/usr/bin/env python3
"""
用 SDCC 自带的 s51 模拟器反汇编 8051 固件。

原理：s51 的 `dc start stop` 命令可以按 8051 指令集反汇编 ROM。
本脚本解析 Intel HEX 得到地址范围，调用 s51，再把常见 SFR / 位地址
（P5.5、P5M0、P5M1、P_SW2、Timer0 等）标注出来，输出到 .dis 文件。

用法：
  python3 -I tools/dis8051.py build/xxx.ihx [--s51 /path/to/s51] [--out build/xxx.dis]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_S51 = "/Users/theo-richard/workspace/toolchains/sdcc-c251/bin/s51"

# 直接地址（MOV/ORL/ANL 等）
SFR_NAMES = {
    0x80: "P0", 0x81: "SP", 0x82: "DPL", 0x83: "DPH", 0x87: "PCON",
    0x88: "TCON", 0x89: "TMOD", 0x8A: "TL0", 0x8B: "TL1",
    0x8C: "TH0", 0x8D: "TH1", 0x8E: "AUXR",
    0x90: "P1", 0x98: "SCON", 0x99: "SBUF", 0xA0: "P2", 0xA2: "P_SW1", 0xA8: "IE",
    0xB0: "P3", 0xB8: "IP", 0xBA: "P_SW2", 0xC0: "P4", 0xC8: "P5",
    0xC9: "P5M1", 0xCA: "P5M0", 0xD0: "PSW", 0xE0: "ACC", 0xF0: "B",
}

# 位地址（SETB/CLR/CPL/JB/JNB/JBC）
BIT_NAMES = {
    0x88: "IT0", 0x89: "IE0", 0x8A: "IT1", 0x8B: "IE1",
    0x8C: "TR0", 0x8D: "TF0", 0x8E: "TR1", 0x8F: "TF1",
    0xB0: "P3.0", 0xB1: "P3.1", 0xB2: "P3.2", 0xB3: "P3.3",
    0xB4: "P3.4", 0xB5: "P3.5", 0xB6: "P3.6", 0xB7: "P3.7",
    0xC8: "P5.0", 0xC9: "P5.1", 0xCA: "P5.2", 0xCB: "P5.3",
    0xCC: "P5.4", 0xCD: "P5.5", 0xCE: "P5.6", 0xCF: "P5.7",
    0xAF: "EA",
}

BIT_OPS = ("SETB", "CLR", "CPL", "JB", "JNB", "JBC")


def parse_ihx(path):
    mem = {}
    base = 0
    with open(path, "r", encoding="ascii", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line.startswith(":"):
                continue
            raw = bytes.fromhex(line[1:])
            count, addr, rectype = raw[0], (raw[1] << 8) | raw[2], raw[3]
            data = raw[4:4 + count]
            if rectype == 0x00:
                for i, b in enumerate(data):
                    mem[base + addr + i] = b
            elif rectype == 0x01:
                break
            elif rectype == 0x02:
                base = int.from_bytes(data, "big") << 4
            elif rectype == 0x04:
                base = int.from_bytes(data, "big") << 16
    return mem


def parse_map(path):
    syms = {}
    if not path or not Path(path).exists():
        return syms
    pat = re.compile(r"^C:\s+([0-9A-Fa-f]+)\s+(\S+)")
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = pat.match(line)
        if m:
            syms[int(m.group(1), 16)] = m.group(2)
    return syms


def annotate(line, syms):
    m = re.match(r"^(0x[0-9a-fA-F]{4})\s+((?:[0-9a-fA-F]{2}\s+)+)([A-Z][A-Z0-9]*)\s*(.*)$", line)
    if not m:
        return line
    addr, code, op, operand = m.groups()
    note = []
    opu = op.upper()
    if opu == "LCALL":
        t = re.search(r"0x([0-9a-fA-F]+)", operand)
        if t:
            ta = int(t.group(1), 16)
            if ta in syms:
                note.append(syms[ta])
    # 操作数里的直接地址/位地址
    if opu in BIT_OPS:
        # s51 对位操作会输出 "0x8d0x88 <TCON>.5"：前一个字节是位地址，
        # 后一个字节是所在 SFR 地址。优先取前一个。
        t = re.search(r"0x([0-9a-fA-F]{2})0x[0-9a-fA-F]{2}", operand)
        if not t:
            t = re.search(r"0x([0-9a-fA-F]{2})\b", operand)
        if t:
            ba = int(t.group(1), 16)
            if ba in BIT_NAMES:
                note.append(BIT_NAMES[ba])
    else:
        t = re.search(r"0x([0-9a-fA-F]{2})\b", operand)
        if t:
            da = int(t.group(1), 16)
            if da in SFR_NAMES:
                note.append(SFR_NAMES[da])
    if note:
        return f"{line.rstrip():<64} ; {' '.join(note)}"
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ihx")
    ap.add_argument("--s51", default=DEFAULT_S51)
    ap.add_argument("--map", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    mem = parse_ihx(args.ihx)
    if not mem:
        raise SystemExit("IHX 为空或无法解析")
    lo, hi = min(mem), max(mem)
    mapf = args.map or str(Path(args.ihx).with_suffix(".map"))
    syms = parse_map(mapf)

    script = f"dc 0x{lo:04X} 0x{hi:04X}\nquit\n"
    try:
        proc = subprocess.run(
            [args.s51, "-t", "C51", "-q", args.ihx],
            input=script, text=True, capture_output=True, timeout=30,
        )
    except FileNotFoundError:
        raise SystemExit(f"找不到 s51: {args.s51}")

    lines = []
    for line in proc.stdout.splitlines():
        if re.match(r"^0x[0-9a-fA-F]{4}\s+", line):
            lines.append(annotate(line, syms))
    if not lines:
        sys.stderr.write(proc.stdout + "\n" + proc.stderr + "\n")
        raise SystemExit("s51 没有输出反汇编（见上面的原始输出）")

    header = [
        f"; 反汇编：{Path(args.ihx).name}",
        f"; 地址范围：0x{lo:04X}..0x{hi:04X}，共 {hi - lo + 1} 字节",
        "; 由 tools/dis8051.py 调用 SDCC s51 `dc` 生成；; 后为 SFR/位/符号标注",
        "",
    ]
    out = "\n".join(header + lines) + "\n"
    outpath = Path(args.out) if args.out else Path(args.ihx).with_suffix(".dis")
    outpath.write_text(out, encoding="utf-8")
    print(out)
    print(f"\n已写入 {outpath}")


if __name__ == "__main__":
    main()
