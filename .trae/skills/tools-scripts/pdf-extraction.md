---
name: pdf-extraction
description: "PDF文档内容提取技能：使用Poppler工具集从PDF格式文档中提取数据和信息，支持文本版和扫描版PDF处理。适用于从下载的年报、财报等PDF文档中获取数据。"
disable-model-invocation: true
---

# PDF文档内容提取技能

使用 **Poppler 工具集** 从 PDF 格式文档中提取数据和信息，支持文本版和扫描版 PDF 处理。

**适用场景**：从下载的年报、季报、半年报等财务报告中提取财务数据和信息。

## 快速开始

```
/pdf-extraction {PDF文件路径}
```

例如：
- `/pdf-extraction 601899_2025年报.pdf`
- `/pdf-extraction ./cninfo_reports/茅台_2024年报.pdf`
- `/pdf-extraction reports/腾讯_2025Q2财报.pdf`

## 设计理念

财务报告是投资研究的重要一手数据来源，但 PDF 格式文档存在以下挑战：

1. **格式多样**：文本版 PDF（可直接提取）vs 扫描版 PDF（图像格式）
2. **数据提取难度**：财务数据分布在表格、图表中，难以直接复制
3. **数据准确性要求高**：财务数字必须准确无误，不得有偏差
4. **文件体积大**：年报通常 100-300 页，需要高效处理

本技能提供**标准化的 PDF 提取流程**，确保数据提取的准确性和效率。

---

## Poppler 工具集介绍

Poppler 是一个开源的 PDF 渲染库，提供以下命令行工具：

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

### 标准流程

```bash
# 步骤1：下载年报PDF（使用A股工具）
python tools/a_share/stock_equity.py --code 601899 --download-report

# 下载的文件默认保存在 ./cninfo_reports/ 目录
# 文件命名：{股票代码}_{年份}年报.pdf，如 601899_2025年报.pdf

# 步骤2：检查PDF类型（文本版 vs 扫描版）
pdftotext -layout 601899_2025年报.pdf - | head -100

# 如果能正常输出文本 -> 文本版PDF
# 如果输出乱码或空白 -> 扫描版PDF，需要使用 pdftoppm

# 步骤3A（文本版PDF）：提取文本内容
pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt

# 步骤3B（扫描版PDF）：渲染为图像
mkdir output
pdftoppm -png -r 300 601899_2025年报.pdf output/page

# 步骤4：搜索关键财务数据（文本版）
grep -n "净利润\|营业收入\|毛利率\|ROE" 601899_2025年报.txt

# 步骤5：数据交叉验证
# 将提取的数据与其他来源（东方财富、巨潮资讯）进行对比
python tools/a_share/stock_financial.py --code 601899
```

### 针对不同类型PDF的处理策略

| PDF类型 | 识别方法 | 处理工具 | 数据提取方式 |
|---------|---------|---------|-------------|
| **文本版PDF** | pdftotext 能正常输出文本 | pdftotext | 直接提取文本，用 grep 搜索关键词 |
| **扫描版PDF** | pdftotext 输出乱码或空白 | pdftoppm + OCR | 渲染为图像，用 OCR 工具识别或人工核对 |
| **混合版PDF** | 部分页面可提取，部分不能 | pdftotext + pdftoppm | 区分处理，文本部分直接提取，扫描部分渲染 |

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

- **Windows 用户**：需要安装 [Poppler for Windows](http://blog.alivate.com.au/poppler-windows/)
- **Linux/macOS 用户**：系统通常已预装 Poppler 工具
- **验证安装**：运行 `pdftotext -v` 检查是否可用

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
python tools/a_share/stock_equity.py --code 601899 --download-report

# 步骤2：提取PDF中的关键财务数据
pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt
grep -n "净利润\|营业收入" 601899_2025年报.txt

# 步骤3：与其他数据源进行交叉验证
python tools/a_share/stock_financial.py --code 601899

# 步骤4：对比两个来源的数据，计算误差率
# 如果误差>1%，按照全局约束规范进行标记
```

---

## 常见问题与解决方案

### Q1: 如何判断PDF是文本版还是扫描版？

**方法**：使用 pdftotext 快速测试

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

- **Windows**: [Poppler for Windows](http://blog.alivate.com.au/poppler-windows/)
- **Linux**: `sudo apt-get install poppler-utils`
- **macOS**: `brew install poppler`

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

1. **扫描版PDF处理限制**：扫描版PDF需要额外使用OCR工具，准确度依赖图像质量
2. **表格数据提取困难**：PDF中的复杂表格难以完美还原，建议手动核对
3. **数据验证要求**：提取的数据必须与其他来源交叉验证，不能单独使用
4. **工具依赖性**：需要安装 Poppler 工具集，Windows 用户需要额外配置

---

## 快速索引

| 场景 | 推荐工具 | 命令示例 |
|------|---------|---------|
| **提取年报全文** | pdftotext | `pdftotext -layout 年报.pdf 年报.txt` |
| **查看PDF信息** | pdfinfo | `pdfinfo 年报.pdf` |
| **处理扫描版PDF** | pdftoppm | `pdftoppm -png -r 300 年报.pdf output/page` |
| **搜索关键数据** | pdftotext + grep | `grep -n "净利润" 年报.txt` |
| **提取特定页面** | pdftotext -f -l | `pdftotext -f 80 -l 100 -layout 年报.pdf 部分.txt` |
| **批量OCR处理** | tesseract | `tesseract page.png output -l chi_sim` |

---

## 版本信息

- **版本**：1.1.0
- **创建日期**：2026-07-22
- **最后更新**：2026-07-31（更新相关技能引用）
- **维护状态**：活跃维护
- **依赖工具**：Poppler 工具集（pdftotext、pdfinfo、pdftoppm）
- **相关技能**：[A股数据获取](./a-share-data.md)、[财务计算与验证](./financial-calc.md)、[全局约束规范](./global-constraints.md)、[公共工具索引](./common-tools-guide.md)

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。提取的财务数据必须与其他来源进行交叉验证，数据准确性由使用者自行负责。
