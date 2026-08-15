---
name: pdf-extraction
description: "PDF文档内容提取技能：首选使用 tools/common/pdf_extract.py（基于 pdf-inspector 库）从PDF格式文档中提取文字和表格等数据和信息；仅当该工具返回失败时才回退使用 Poppler 工具集处理。适用于从下载的年报、财报等PDF文档中获取数据。"
disable-model-invocation: true
---
# PDF文档内容提取技能

**首选手段**：使用 `tools/common/pdf_extract.py`（基于 pdf-inspector 库，底层 Rust）从 PDF 格式文档中提取文字和表格等数据和信息，支持文本版和扫描版 PDF 检测。

**新增功能（v1.3.0）**：自动乱码检测 + OCR 回退。当检测到提取的文本为乱码（如 Adobe-CNS1 缺少 CMap 映射）且 tesseract OCR 可用时，自动触发 OCR 回退渲染提取。

**回退手段**：仅当 `tools/common/pdf_extract.py` 返回失败时，才使用 **Poppler 工具集**（pdftotext、pdfinfo、pdftoppm）从 PDF 格式文档中提取数据和信息。

**适用场景**：从下载的年报、季报、半年报等财务报告中提取财务数据和信息。

## 快速开始

> **统一入口**：经 `report_hub.py extract` 调用可自动缓存提取结果（`cninfo_reports/extracted/`）；
> 直接调用 `pdf_extract.py` 不走缓存，仅适用于临时性/一次性提取。
> 详见 [报告下载与提取统一入口](./report-hub.md)。

```
# 首选：使用 pdf_extract.py 提取（含表格，自动 OCR 回退）
python tools/common/pdf_extract.py markdown {PDF文件路径} --save-md

# 强制 OCR 模式（当自动检测未触发时使用）
python tools/common/pdf_extract.py text {PDF文件路径} --force-ocr

# 回退：pdf_extract.py 失败时使用 Poppler
pdftotext -layout {PDF文件路径} -
```

例如：

- `python tools/common/pdf_extract.py markdown 601899_2025年报.pdf --save-md`
- `python tools/common/pdf_extract.py all ./cninfo_reports/茅台_2024年报.pdf --save-md`
- `python tools/common/pdf_extract.py detect reports/腾讯_2025Q2财报.pdf`
- `python tools/common/pdf_extract.py text 688235_2025年报.pdf --force-ocr --ocr-langs chi_tra+eng`

## 设计理念

财务报告是投资研究的重要一手数据来源，但 PDF 格式文档存在以下挑战：

1. **格式多样**：文本版 PDF（可直接提取）vs 扫描版 PDF（图像格式）
2. **数据提取难度**：财务数据分布在表格、图表中，难以直接复制
3. **数据准确性要求高**：财务数字必须准确无误，不得有偏差
4. **文件体积大**：年报通常 100-300 页，需要高效处理

本技能提供**标准化的 PDF 提取流程**，确保数据提取的准确性和效率。

---

## 首选工具：tools/common/pdf_extract.py

`tools/common/pdf_extract.py` 是基于 **pdf-inspector** 库（Firecrawl 开源，底层 Rust，Python 绑定）开发的 PDF 文字与表格提取工具，**是 PDF 文档内容提取的首选手段**。它支持自动分类检测、文字提取、含财务附表的 Markdown 提取，能直接还原 PDF 中的表格结构。

### 依赖安装

```bash
# 核心依赖：pdf-inspector（基于 Firecrawl 开源 Rust 库）
pip install pdf-inspector

# OCR 回退依赖（处理乱码/扫描版 PDF 时需安装）
pip install pytesseract pymupdf pillow
# 并安装 tesseract OCR 引擎（详见下方"使用 Poppler 的注意事项 → 4. 工具可用性"）
```

> 当前工作环境已安装 pdf-inspector、pytesseract、pymupdf 等依赖。若在其他环境使用，请先执行上述安装命令后再调用。

### 支持的子命令

| 子命令 | 功能 | 说明 |
|--------|------|------|
| `detect` | 分类检测 | 判断 PDF 类型（`text_based`/`scanned`/`mixed`），返回需 OCR 的页码 |
| `text` | 纯文本提取 | 提取扁平化纯文本（不含表格排版信息），不写文件 |
| `markdown` | 含表格的 Markdown 提取 | 自动完成类型检测 + 文字提取 + 表格识别 + 多栏重排 |
| `all` | 全流程 | 依次执行 分类 + 纯文本 + Markdown |

### 基本用法

```bash
# (1) 分类检测：判断文本版/扫描版
python tools/common/pdf_extract.py detect 601899_2025年报.pdf

# (2) 提取纯文本（不写文件，仅输出 JSON）
python tools/common/pdf_extract.py text 601899_2025年报.pdf

# (3) 提取含财务附表的 Markdown（推荐，能还原表格）
python tools/common/pdf_extract.py markdown 601899_2025年报.pdf --save-md --out-dir reports/pdf

# (4) 仅提取指定页（0 索引，支持逗号分隔或范围语法）
python tools/common/pdf_extract.py markdown 601899_2025年报.pdf --pages 0,1
python tools/common/pdf_extract.py markdown 688235_2025年报.pdf --pages 0-5,10,40-45

# (5) 全流程（分类 + 纯文本 + Markdown）
python tools/common/pdf_extract.py all 601899_2025年报.pdf --save-md

# (6) 强制 OCR（绕过 pdf-inspector，直接使用 tesseract OCR）
python tools/common/pdf_extract.py text 601899_2025年报.pdf --force-ocr

# (7) 指定 OCR 语言包（如繁体中文）
python tools/common/pdf_extract.py text 688235_2025年报.pdf --force-ocr --ocr-langs chi_tra+eng
```

### 输出与失败判定

所有子命令统一在 stdout 输出 JSON，结构为 `{"success": bool, "data": {...}, "meta": {...}}`。

**判定 `pdf_extract.py` 是否成功**（满足任一即视为失败，回退到 Poppler）：

1. **退出码非 0**：正常返回 0；文件不存在返回 2；处理异常返回 1
2. **`success` 字段为 `false`**：输出 JSON 中 `success` 为 false
3. **扫描格式**：`data.scanned.scanned` 为 `true`，或 `data.pdf_type` 为 `scanned`/`mixed`，说明无法直接提取文字/表格，需转交 Poppler（pdftoppm + OCR）流程

### 扫描格式处理

当 `detect` 判定 PDF 为扫描格式（`scanned`/`mixed`）或存在需 OCR 页面时，`pdf_extract.py` 会返回 `data.scanned.scanned = true` 且 `content` 为空。此时优先使用 `--force-ocr` 参数尝试 OCR 提取：

```bash
# 优先：强制 OCR 提取（需安装 tesseract + pytesseract + pymupdf）
python tools/common/pdf_extract.py text 报告.pdf --force-ocr

# 或：转交 Poppler 的 pdftoppm + OCR 流程（见下文"回退到 Poppler 工具集"）
```

### 自动乱码检测与 OCR 回退（v1.3.0）

当 `pdf_extract.py` 的非强制 OCR 模式（未加 `--force-ocr`）提取文本时，会自动检测以下情况并触发 OCR 回退：

1. **Adobe-CNS1 字体映射失败**：繁体中文 PDF 使用 Adobe-CNS1 CMap 编码，但 pdf-inspector 缺少 CMap 数据文件，导致输出为其他语系字形（藏文、埃塞俄比亚文等）
2. **其他字体编码不兼容**：PDF 内部字体编码无法被 pdf-inspector 正确解码

**检测机制**：计算文本中 CJK 字符（中文）占比，低于 30% 时判定为乱码，自动回退到 OCR 提取。

**注意**：此检测仅针对**非强制 OCR 模式**。使用 `--force-ocr` 时直接跳过检测，直接使用 OCR。

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--force-ocr` | 强制使用 OCR 提取（绕过 pdf-inspector） | 不启用 |
| `--ocr-langs` | 指定 tesseract 语言包组合 | `chi_sim+eng` |

**语言包选择建议**：

| 语言包 | 适用场景 |
|--------|----------|
| `chi_sim+eng`（默认） | 简体中文 + 英文（如紫金矿业年报） |
| `chi_tra+eng` | 繁体中文 + 英文（如百济神州年报） |
| `chi_sim+chi_tra+eng` | 简体 + 繁体 + 英文（混合文档） |

---

## 回退手段：Poppler 工具集

**仅当 `tools/common/pdf_extract.py` 返回失败时**，才使用 Poppler 工具集从 PDF 中提取数据和信息。Poppler 是一个开源的 PDF 渲染库，提供以下命令行工具：

| 工具 | 功能 | 主要用途 |
|------|------|---------|
| `pdftotext` | 将PDF转换为纯文本 | 提取年报中的文字内容 |
| `pdfinfo` | 获取PDF文档信息 | 查看页数、标题、作者等元数据 |
| `pdftoppm` | 将PDF页面渲染为图像 | 处理扫描版PDF、提取图表 |

---

## 工具详细使用说明

### pdftotext：提取文本内容

```bash
# 基本用法：将PDF转换为文本文件
pdftotext 601899_2025年报.pdf 601899_2025年报.txt

# 保持原始布局（推荐）
pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt

# 指定页面范围（只提取第10-20页）
pdftotext -f 10 -l 20 -layout 601899_2025年报.pdf 601899_2025年报_部分.txt

# 输出到控制台（便于快速查看）
pdftotext -layout 601899_2025年报.pdf -
```

**应用场景**：
- **提取财务报表**：从年报中提取资产负债表、利润表、现金流量表
- **查找关键数据**：搜索"净利润"、"营业收入"、"毛利率"等关键词
- **验证数据来源**：与第三方数据源进行交叉验证

**示例：提取关键财务数据**

```bash
# 提取文本内容
pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt

# 搜索关键财务数据
grep -n "净利润\|营业收入\|毛利率\|ROE\|资产负债率" 601899_2025年报.txt

# 提取特定章节（如财务报表章节）
pdftotext -f 80 -l 100 -layout 601899_2025年报.pdf 601899_2025年报_财务报表.txt
```

---

### pdfinfo：获取文档信息

```bash
# 查看PDF基本信息
pdfinfo 601899_2025年报.pdf

# 输出示例：
# Title:          紫金矿业2025年年度报告
# Author:         紫金矿业集团股份有限公司
# Creator:        Microsoft Word
# Producer:       Acrobat Distiller
# CreationDate:   2026-03-15
# Pages:          256
# ...
```

**应用场景**：
- **确认报告年份**：通过创建日期判断报告是否为最新版
- **预估数据量**：根据页数规划提取工作量
- **验证报告完整性**：确认页数与官网公布是否一致

**示例：批量检查年报信息**

```bash
# 检查多个年报的基本信息
for file in *.pdf; do
    echo "=== $file ==="
    pdfinfo "$file" | grep -E "Title|Pages|CreationDate"
    echo ""
done
```

---

### pdftoppm：处理扫描版PDF

**重要**：A股年报常为扫描版PDF（图像格式），无法直接用 pdftotext 提取文本，需要使用 pdftoppm 渲染为图像。

```bash
# 将PDF页面渲染为高分辨率PNG图像
pdftoppm -png -r 300 601899_2025年报.pdf output/page

# 渲染指定页面（第50-60页）
pdftoppm -png -r 300 -f 50 -l 60 601899_2025年报.pdf output/page

# 超高分辨率（用于提取图表）
pdftoppm -png -r 600 601899_2025年报.pdf output/page

# JPEG格式（文件更小）
pdftoppm -jpeg -r 300 601899_2025年报.pdf output/page
```

**应用场景**：
- **处理扫描版年报**：将扫描版PDF转为图像，便于视觉检查
- **提取财务图表**：高分辨率渲染年报中的财务图表、数据表格
- **人工核对**：对关键数据进行人工验证

**示例：提取财务报表页面**

```bash
# 创建输出目录
mkdir -p financial_statements

# 假设财务报表在第100-120页
pdftoppm -png -r 300 -f 100 -l 120 601899_2025年报.pdf financial_statements/page

# 生成的文件：
# financial_statements/page-100.png
# financial_statements/page-101.png
# ...
```

---

## 完整的年报数据提取工作流

### 标准流程（首选 pdf_extract.py）

```bash
# 步骤1：下载年报PDF（使用A股工具）
python tools/common/report_hub.py ensure --code 601899 --report-type annual

# 下载的文件默认保存在 ./cninfo_reports/ 目录
# 文件命名：{股票代码}_{年份}年报.pdf，如 601899_2025年报.pdf

# 步骤2（首选）：用 pdf_extract.py 分类检测 PDF 类型
python tools/common/pdf_extract.py detect 601899_2025年报.pdf

# 步骤3（首选）：提取含财务附表的 Markdown 并写盘
python tools/common/pdf_extract.py markdown 601899_2025年报.pdf --save-md --out-dir reports/pdf

# 若需纯文本，使用 text 子命令
python tools/common/pdf_extract.py text 601899_2025年报.pdf

# 步骤4：若 pdf_extract.py 返回失败（退出码非0 / success=false / 扫描件），回退到 Poppler
pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt   # 文本版
pdftoppm -png -r 300 601899_2025年报.pdf output/page         # 扫描版

# 步骤5：搜索关键财务数据（文本版）
grep -n "净利润\|营业收入\|毛利率\|ROE" 601899_2025年报.txt

# 步骤6：数据交叉验证
# 将提取的数据与其他来源（东方财富、巨潮资讯）进行对比
python tools/a_share/stock_financial.py --code 601899
```

### 针对不同类型PDF的处理策略

| PDF类型 | 识别方法 | 首选处理工具 | 回退处理工具 | 数据提取方式 |
|---------|---------|-------------|-------------|-------------|
| **文本版PDF** | pdf_extract.py detect 返回 `text_based` | `pdf_extract.py markdown` | `pdftotext` | 直接提取文字/表格，用 grep 搜索关键词 |
| **扫描版PDF** | pdf_extract.py detect 返回 `scanned`/`mixed` 或 `scanned=true` | `pdf_extract.py` 返回标志，转 Poppler | `pdftoppm + OCR` | 渲染为图像，用 OCR 工具识别或人工核对 |
| **混合版PDF** | 部分页面可提取，部分需 OCR | `pdf_extract.py`（自动识别表格页） | `pdftotext + pdftoppm` | 区分处理，文本部分直接提取，扫描部分渲染 |
| **OCR 大文档（300+页）** | 需强制 OCR 提取 | 先提取目录页（0-10页） | 按需提取关键章节 | 避免全量 OCR，节省时间；找到目录后再提取财务章节 |

---

### 性能优化建议：OCR 提取大文档分步处理

OCR 渲染每页耗时约 1-2 秒，300+ 页年报全量 OCR 需 5-10 分钟。建议**分步提取**：

```bash
# 第一步：仅提取前 10 页（目录 + 财务摘要），定位章节位置
python tools/common/pdf_extract.py text 年报.pdf --force-ocr --ocr-langs chi_tra+eng --pages 0-10

# 第二步：根据目录确定财务报表章节页码，仅提取关键页
python tools/common/pdf_extract.py markdown 年报.pdf --force-ocr --ocr-langs chi_tra+eng --pages 40-60,80-120 --save-md
```

**优势**：
- 避免对整个大 PDF 全量 OCR，节省大量时间
- 目录帮助定位关键章节，只提取需要的内容
- 对于 300+ 页年报，通常只需要提取财务报表（50-80 页），可节省 70% 时间

---

## 使用 Poppler 的注意事项

### 1. 扫描版PDF限制

- 扫描版PDF无法直接提取文本，必须使用 pdftoppm 转为图像
- 转换后的图像可以用 OCR 工具进一步处理（如 tesseract）
- **A股年报常见扫描版**，务必先检查PDF类型

### 2. 文件大小管理

- 高分辨率渲染会生成大量图像文件（每页1-5MB）
- 300页年报渲染为300dpi PNG，总计约1-1.5GB
- **建议**：先用低分辨率预览，确定需要的页面后再高分辨率渲染

```bash
# 低分辨率预览（快速查看）
pdftoppm -png -r 100 601899_2025年报.pdf preview/page

# 确定需要的页面后，高分辨率渲染
pdftoppm -png -r 300 -f 100 -l 120 601899_2025年报.pdf output/page
```

### 3. 内容完整性验证

- 扫描版PDF可能存在字迹模糊、页面倾斜等问题
- 重要数据建议人工复核，不要完全依赖工具提取
- **关键数字必须人工验证**：净利润、营业收入、ROE等核心指标

### 4. 工具可用性

Poppler 工具集是第三方命令行工具，需要单独安装。各平台安装方法如下：

**Windows**：

```bash
# 方式A：choco 安装（推荐，需先安装 Chocolatey）
choco install poppler

# 方式B：conda 安装（适用于 Anaconda 环境）
conda install -c conda-forge poppler

# 方式C：下载预编译二进制包
# 1. 访问 https://github.com/oschwartz10612/poppler-windows 下载最新 Release
# 2. 解压到本地目录（如 C:\Program Files\poppler）
# 3. 将 {解压目录}\Library\bin 添加到系统 PATH 环境变量
```

**Linux**：

```bash
# Ubuntu / Debian
sudo apt-get install poppler-utils

# CentOS / RHEL
sudo yum install poppler-utils
# 或 dnf 系（Fedora 等）
sudo dnf install poppler-utils

# Alpine
apk add poppler-utils
```

**macOS**：

```bash
brew install poppler
```

**验证安装**：运行 `pdftotext -v` 检查是否可用；若显示版本信息则安装成功，若提示"命令未找到"则需将安装目录加入 PATH。

```bash
# 验证命令
pdftotext -v

# Windows 下若提示找不到命令，检查 PATH 是否已包含 Poppler 安装目录
where pdftotext
```

### tesseract OCR 引擎安装

**OCR 回退功能需要安装 tesseract OCR 引擎，Python 包已提前安装**（`pytesseract`, `pymupdf`, `pillow`），但需要单独安装引擎二进制文件：

**Windows**：

```bash
# 方式A：从 GitHub 下载安装包
# 1. 访问 https://github.com/tesseract-ocr/tesseract 下载 UB-Mannheim 编译的安装包
# 2. 运行安装程序，默认安装路径：C:\Program Files\Tesseract-OCR\tesseract.exe
# 3. 安装时勾选简体中文 (chi_sim) 和繁体中文 (chi_tra) 语言包

# 方式B：choco 安装（推荐，需先安装 Chocolatey）
choco install tesseract
choco install tesseract-chi-sim  # 简体中文语言包
choco install tesseract-chi-tra  # 繁体中文语言包

# 方式C：winget 安装
winget install UB-Mannheim.TesseractOCR
```

**Linux**：

```bash
# Ubuntu / Debian
sudo apt-get install tesseract-ocr
sudo apt-get install tesseract-ocr-chi-sim  # 简体中文
sudo apt-get install tesseract-ocr-chi-tra  # 繁体中文

# CentOS / RHEL
sudo yum install tesseract tesseract-devel
sudo yum install tesseract-langpack-chi-sim
```

**macOS**：

```bash
brew install tesseract
brew install tesseract-lang  # 包含所有语言包
```

**验证安装**：

```bash
# 验证命令
tesseract --version

# 列出可用语言包
tesseract --list-langs
```

**当前环境**：tesseract 已安装在 `C:\Program Files\Tesseract-OCR\tesseract.exe`，且已安装 `chi_sim` 和 `chi_tra` 语言包。

### 5. 数据验证原则

- 从PDF提取的数据必须与其他来源进行交叉验证
- 特别关注数字、单位、小数点位置的准确性
- **误差>1%必须标记**，参见 [全局约束规范](./global-constraints.md)

---

## 扫描版PDF的替代方案

如果 Poppler 无法满足需求，可以考虑以下替代方案：

### 1. OCR工具

| 工具 | 类型 | 特点 | 适用场景 |
|------|------|------|---------|
| **tesseract** | 开源 | 免费、支持中文、准确度中等 | 批量处理、预算有限 |
| **ABBYY FineReader** | 商业 | 准确度高、支持表格识别、价格高 | 专业文档处理、预算充足 |
| **Adobe Acrobat Pro** | 商业 | 功能全面、PDF原生支持 | 综合PDF处理 |

**tesseract 使用示例**：

```bash
# 安装tesseract（Windows需要下载安装包）
# Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim

# 对渲染的图像进行OCR识别
tesseract output/page-100.png output/page-100 -l chi_sim

# 批量处理
for file in output/*.png; do
    tesseract "$file" "${file%.png}" -l chi_sim
done
```

### 2. 在线工具

| 工具 | 网址 | 特点 | 适用场景 |
|------|------|------|---------|
| **Adobe Acrobat Online** | adobe.com/acrobat/online | 免费额度、功能全面 | 单个文档处理 |
| **Smallpdf** | smallpdf.com | 免费额度、界面友好 | 快速转换 |
| **iLovePDF** | ilovepdf.com | 免费额度、批量处理 | 批量PDF处理 |

**注意**：在线工具可能存在数据隐私风险，敏感财务数据建议使用本地工具。

### 3. 手动处理

对于关键页面和核心数据，建议手动输入：

- **优点**：确保数据准确性，避免工具识别错误
- **缺点**：效率低，适合少量关键数据
- **适用场景**：净利润、ROE、毛利率等核心指标的验证

**推荐流程**：
1. 使用 pdftoppm 渲染关键页面为图像
2. 在图像上标注关键数据
3. 手动输入到Excel或研究笔记中
4. 与其他数据源进行交叉验证

---

## 与其他技能的集成使用

本技能为以下投研技能提供 PDF 数据提取支持：

| 技能 | PDF提取应用场景 | 集成方式 |
|------|----------------|---------|
| **financial-data** | 从年报PDF提取财务数据进行交叉验证 | 作为数据源之一，与东方财富等数据源对比 |
| **management-deep-dive** | 从年报PDF提取管理层承诺和发言 | 提取"管理层讨论与分析"章节 |
| **investment-research** | 从年报PDF提取业务数据、行业分析 | 提取关键章节内容 |
| **earnings-review** | 从季报PDF提取最新财务数据 | 提取财务报表页面 |

**集成示例**（以 financial-data 为例）：

```bash
# 步骤1：下载年报PDF
python tools/common/report_hub.py ensure --code 601899 --report-type annual

# 步骤2（首选）：用 pdf_extract.py 提取含财务附表的 Markdown
python tools/common/pdf_extract.py markdown 601899_2025年报.pdf --save-md --out-dir reports/pdf

# 步骤2回退：若 pdf_extract.py 失败，使用 Poppler 提取
# pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt
# grep -n "净利润\|营业收入" 601899_2025年报.txt

# 步骤3：与其他数据源进行交叉验证
python tools/a_share/stock_financial.py --code 601899

# 步骤4：对比两个来源的数据，计算误差率
# 如果误差>1%，按照全局约束规范进行标记
```

---

## 常见问题与解决方案

### Q1: 如何判断PDF是文本版还是扫描版？

**首选方法**：使用 `pdf_extract.py detect` 分类检测

```bash
python tools/common/pdf_extract.py detect 报告.pdf
```

- 返回 `pdf_type: "text_based"` -> 文本版PDF，可直接用 `pdf_extract.py markdown` 提取
- 返回 `pdf_type: "scanned"`/`"mixed"` 或 `scanned.scanned: true` -> 扫描版PDF，转交 Poppler（pdftoppm + OCR）

**回退方法**：使用 pdftotext 快速测试

```bash
pdftotext -layout 报告.pdf - | head -50
```

- 如果能正常输出文本 -> 文本版PDF
- 如果输出乱码或空白 -> 扫描版PDF

### Q2: 扫描版PDF如何提取数据？

**方案**：
1. 使用 pdftoppm 渲染为高分辨率图像
2. 使用 OCR 工具（如 tesseract）识别文字
3. 重要数据手动输入验证

### Q3: 提取的财务数据如何验证准确性？

**验证流程**：
1. 与第三方数据源（东方财富、巨潮资讯）对比
2. 计算误差率，误差>1%必须标记
3. 核心指标（净利润、ROE）建议人工复核

### Q4: Poppler 工具在哪里下载？

各平台安装方法详见上文"使用 Poppler 的注意事项 → 4. 工具可用性"，快速指引：

- **Windows**: 推荐 `choco install poppler` 或 `conda install -c conda-forge poppler`；亦可在 [oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows) 下载预编译包并配置 PATH
- **Linux**: `sudo apt-get install poppler-utils`（Debian/Ubuntu）
- **macOS**: `brew install poppler`
- **验证安装**: 运行 `pdftotext -v`

### Q5: 如何处理超大PDF文件（如200页年报）？

**建议**：
1. 先用 pdfinfo 查看总页数
2. 用 pdftotext 指定页面范围，分批提取
3. 重点页面（如财务报表）单独处理

```bash
# 分批提取
pdftotext -f 1 -l 50 -layout 报告.pdf 报告_第1-50页.txt
pdftotext -f 51 -l 100 -layout 报告.pdf 报告_第51-100页.txt
```

---

## 局限性说明

1. **扫描版PDF处理限制**：扫描版PDF需要额外使用OCR工具，准确度依赖图像质量；`pdf_extract.py` 检测到扫描格式会返回标志，优先使用 `--force-ocr` 参数尝试 OCR 提取，失败后再转交 Poppler
2. **表格数据提取困难**：`pdf_extract.py` 能自动还原多数财务附表，但极复杂表格仍可能需手动核对
3. **数据验证要求**：提取的数据必须与其他来源交叉验证，不能单独使用
4. **工具依赖性**：首选方式依赖 `pdf-inspector` 库（需 `pip install pdf-inspector`）；OCR 回退需安装 tesseract + pytesseract + pymupdf；回退方式需安装 Poppler 工具集，Windows 用户需要额外配置

---

## 快速索引

| 场景 | 首选工具 | 回退工具 | 命令示例 |
|------|---------|---------|---------|
| **分类检测** | `pdf_extract.py detect` | `pdftotext - \| head` | `python tools/common/pdf_extract.py detect 年报.pdf` |
| **提取含表格内容** | `pdf_extract.py markdown` | `pdftotext` | `python tools/common/pdf_extract.py markdown 年报.pdf --save-md` |
| **提取纯文本** | `pdf_extract.py text` | `pdftotext` | `python tools/common/pdf_extract.py text 年报.pdf` |
| **全流程提取** | `pdf_extract.py all` | `pdftotext + pdftoppm` | `python tools/common/pdf_extract.py all 年报.pdf --save-md` |
| **查看PDF信息** | `pdf_extract.py detect` | `pdfinfo` | `python tools/common/pdf_extract.py detect 年报.pdf` |
| **处理扫描版PDF** | `pdf_extract.py --force-ocr` | `pdftoppm` | `python tools/common/pdf_extract.py text 年报.pdf --force-ocr` |
| **处理繁体中文PDF** | `pdf_extract.py --ocr-langs chi_tra+eng` | `pdftotext` | `python tools/common/pdf_extract.py text 年报.pdf --force-ocr --ocr-langs chi_tra+eng` |
| **自动乱码回退** | `pdf_extract.py text`（自动） | `--force-ocr` | `python tools/common/pdf_extract.py text 年报.pdf` |
| **搜索关键数据** | `pdf_extract.py markdown` | `pdftotext + grep` | `python tools/common/pdf_extract.py markdown 年报.pdf` |
| **提取特定页面** | `pdf_extract.py markdown --pages`（支持 `0-5,10,20-25` 范围语法） | `pdftotext -f -l` | `python tools/common/pdf_extract.py markdown 年报.pdf --pages 0-5,10,20-25` |
| **批量OCR处理** | - | `tesseract` | `tesseract page.png output -l chi_sim` |

---

## 版本信息

- **版本**：1.3.0
- **创建日期**：2026-07-22
- **最后更新**：2026-08-13（新增自动乱码检测 + OCR 回退功能）
- **维护状态**：活跃维护
- **依赖工具**：首选 `pdf-inspector` 库（`tools/common/pdf_extract.py`）；OCR 回退 tesseract + pytesseract + pymupdf；回退 Poppler 工具集（pdftotext、pdfinfo、pdftoppm）
- **相关技能**：[A股数据获取](./a-share-data.md)、[财务计算与验证](./financial-calc.md)、[全局约束规范](./global-constraints.md)、[公共工具索引](./common-tools-guide.md)

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。提取的财务数据必须与其他来源进行交叉验证，数据准确性由使用者自行负责。
