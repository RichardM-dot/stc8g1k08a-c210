# C210 A3 Drawing Sheet / Title Block

## 1. 文件用途

| 文件 | 说明 |
| --- | --- |
| `docs/pcb/kicad/c210.kicad_wks` | KiCad 图纸边框 + 标题栏定义，A3 横向（420 × 297 mm） |
| `docs/pcb/kicad/wks_test.kicad_sch` | 最小 A3 测试原理图（仅一个 10k 电阻），用于验证图框 |
| `docs/pcb/kicad/wks_test.pdf` | 用 `kicad-cli sch export pdf --drawing-sheet ...` 导出的验证 PDF |
| `docs/pcb/kicad/wks_test.pdf.png` | `qlmanage -t -s 3000` 渲染的预览图，检查边框/文字/重叠 |
| `docs/pcb/kicad/WKS_NOTES.md` | 本说明 |

图框风格参考 `docs/pcb/reference_lceda.png`：双线红/深色边框、上下 1–6 分区、左右 A–D 分区、右下角大标题栏。图框本身是单色的，PDF 中的红色来自 KiCad 默认 schematic worksheet 颜色主题。

## 2. 几何与字号

- 纸张：A3 横向，420 × 297 mm。
- 页边距：四周 10 mm；外框线宽 0.40 mm，内框在 15 mm 处、线宽 0.18 mm，形成 5 mm 宽分区带。
- 分区：上下各 6 格（1–6，每格 65 mm），左右各 4 格（A–D，每格 66.75 mm），分区字号 2.5 mm。
- 标题栏：180 × 55 mm，位于内框右下角；右侧/下侧与内框重合，外留 5 mm 分区带。
- 标题栏内部（自下而上）：9 mm 信息行、9 mm 信息行、10 mm 特性行、27 mm 标题区。
- 字体：KiCad 内置 stroke font。
  - 主标题：5.0 mm，bold；
  - 工艺/日期/版本/文件等字段：2.4 mm；
  - 特性行：2.2 mm；
  - 顶部 kicker：1.9 mm；
  - 全英文，无中文。

标题栏内容：

```
ZCODE ENGINEERING / SCHEMATIC
C210 SOLDERING PEN CONTROLLER
STC8G1K08A-8PIN + MAX31855 + 74HCT4053
USB-C 5V/3A  |  JBC C210  |  NO DISPLAY
DESIGNED BY ZCode        DATE 2026-11-21        REV 1.0
SIZE A3                  SHEET 1/1              FILE c210.kicad_sch
```

## 3. 如何给主原理图使用

### 3.1 kicad-cli（推荐，可重复构建）

在项目根目录执行：

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch export pdf \
  --drawing-sheet docs/pcb/kicad/c210.kicad_wks \
  -o docs/pcb/kicad/c210_schematic_v2.pdf \
  docs/pcb/kicad/c210_schematic_v2.kicad_sch
```

对 `c210.kicad_sch` 同理，只替换输入/输出文件名。`--drawing-sheet` 会覆盖工程里配置的图纸，不会写入 `.kicad_sch` 或 `.kicad_pro`。

如果需要纯黑白打印预览，加 `--black-and-white`；默认输出使用 schematic 主题的深红色图框。

### 3.2 KiCad GUI

1. 打开原理图，确认纸张为 **A3、横向**（File → Page Settings）。
2. 在 Page Settings → Drawing sheet 选择 `docs/pcb/kicad/c210.kicad_wks`。
3. 该图框不嵌入原理图文件，归档时需连同 `.kicad_wks` 一起复制。

### 3.3 注意事项

- 本图框按 A3 固定坐标绘制，**不随纸张自动缩放**。A4/A2 图纸不要直接套用；A2 会导致 6 列分区只覆盖左侧一部分。
- 当前 `c210.kicad_sch` 是 A3；直接使用本图框。导出时加 `--drawing-sheet c210.kicad_wks`。
- 标题栏文字是**静态字符串**（包括日期、版本、文件名、Sheet 1/1），发版前直接编辑 `c210.kicad_wks` 中的 `tb_*` 文本。
- 若希望标题栏动态取值，可把对应 `tbtext` 换成 KiCad 变量：`%T` 标题、`%D` 日期、`%R` 版本、`%S/%N` 图页、`%F` 文件名、`%Y` 公司；同时在 Page Settings 填好这些字段。当前版本为保证任意原理图导出都显示完整信息，使用静态文本。

## 4. 验证方法（可复现）

```bash
cd docs/pcb/kicad
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch export pdf \
  --drawing-sheet c210.kicad_wks \
  -o wks_test.pdf \
  wks_test.kicad_sch
qlmanage -t -s 3000 -o . wks_test.pdf
```

打开 `wks_test.pdf.png` 检查：

- A3 比例；外框距页边 10 mm；
- 上下 1–6、左右 A–D 完整且位于 5 mm 分区带内；
- 标题栏 180 × 55 mm，右下角，无文字重叠/出界；
- 标题、工艺行、字段在 100% A3 打印尺寸下可读。

## 5. 已知字体限制

- KiCad stroke font 对中文支持不稳定，本图框刻意只使用 ASCII 英文。若改成中文，可能显示为方框/问号或缺字。
- 避免使用 `·`、`µ`、`°`、弯引号等字符；本版本特性行用 `|` 分隔，避免中点符号缺字。
- stroke font 中 `-` 会画成较长的一笔，`STC8G1K08A-8PIN` 看起来像长破折号，这是正常渲染，不是字符错误。
- 修改文字后建议重新导出并渲染 PNG 检查，不要只依赖 PDF 文本抽取（KiCad 文字是描边路径，`pdftotext` 通常抽不到）。
- macOS 上 `kicad-cli` 可能打印 `Fontconfig error: Cannot load default config file`，这是系统字体配置警告；stroke font 由 KiCad 内置绘制，不影响图框/文字输出。

## 6. 不改动的文件

本任务只涉及 `docs/pcb/kicad/c210.kicad_wks`、`wks_test.*`、`WKS_NOTES.md`。未修改主原理图、`c210.kicad_sym`、`c210.kicad_pro`、代码或 README。
