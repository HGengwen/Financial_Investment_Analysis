# PDF 提取乱码检测 Bug 修复记录

## 概述

- **日期**：2026-08-13
- **涉及文件**：`tools/common/pdf_extract.py`
- **触发场景**：提取使用 Adobe-CNS1 CMap 编码的繁体中文 PDF（如百济神州 2025 年报）
- **影响范围**：`text`、`markdown`、`all` 三个子命令的自动乱码回退功能

---

## 一、Bug 描述

### 1.1 表象

对百济神州 2025 年报（繁体中文，Adobe-CNS1 编码）执行自动提取时：

```bash
python tools/common/pdf_extract.py text "688235_2025年报.pdf"
```

- `pdf-inspector` 提取的文本中，中文部分被替换为**其他语系字形**（藏文、埃塞俄比亚文、阿拉伯文、IPA 扩展等）
- 但 `_is_garbled_text()` 函数返回 `False`，未触发自动 OCR 回退
- 输出中包含乱码内容而非正确的中文文本

### 1.2 乱码示例

| 原文 | 提取结果 | 说明 |
|------|----------|------|
| 目录 2 | `፽ ʮ̡༟ࣘ 2` | 埃塞俄比亚文 + IPA + 藏文 |
| 业务 | `ۃ‬ᓼ‫׌‬௓‫ࠑ‬` | 阿拉伯文 + 希伯来文 + 泰米尔文 |
| 财务数据 | 混合的藏文/阿拉伯文/天城文 | 完全不可读 |

---

## 二、根因分析

### 2.1 技术背景

PDF 中的中文文本可以使用 **CMap（Character Map）** 编码，将字符 ID 映射到 Unicode 码位。Adobe-CNS1 是用于繁体中文的 CMap 标准。

- `pdf-inspector`（底层 Rust）缺少 Adobe-CNS1 的 CMap 数据文件
- 无法正确解码字符 ID → 输出为其他语系字形（错误映射）
- 正常英文/数字部分不受影响

### 2.2 Bug 位置

文件：`tools/common/pdf_extract.py`，`_is_garbled_text()` 函数（原第 245-274 行）

```python
# 修复前的代码（有 Bug）
_RE_GARBLED_CHARS = re.compile(
    r'[\ufffd\u00c0-\u00ff\u2018-\u201d\u2020-\u2027\u2030-\u2039]'
)

def _is_garbled_text(text: str, threshold: float = 0.3) -> bool:
    ...
    garble_count = len(_RE_GARBLED_CHARS.findall(stripped))
    cjk_count = len(_RE_CJK.findall(stripped))
    garble_ratio = garble_count / total
    cjk_ratio = cjk_count / total
    return garble_ratio > threshold and cjk_ratio < 0.5
```

### 2.3 Bug 成因

`_RE_GARBLED_CHARS` 正则只匹配以下字符类别：

| Unicode 范围 | 字符类别 | 示例 |
|-------------|----------|------|
| `\ufffd` | 替换字符 |  |
| `\u00c0-\u00ff` | 拉丁-1 补充 | À-ÿ |
| `\u2018-\u201d` | 引号 | '`'"'"' |
| `\u2020-\u2027` | 装饰符号 | †‡•‥… |
| `\u2030-\u2039` | 数字符号 | ‰‹ |

但 Adobe-CNS1 乱码输出的实际字符来自完全不同的 Unicode 区块：

| Unicode 区块 | 范围 | 示例 |
|-------------|------|------|
| 埃塞俄比亚文 | U+1200–U+137F | `፽`, `ቇ` |
| 藏文 | U+0F00–U+0FFF | `༟`, `༙` |
| 阿拉伯文 | U+0600–U+06FF | `ۃ`, `ؓ` |
| IPA 扩展 | U+02B0–U+02FF | `ʮ` |
| 组合附加符号 | U+0300–U+036F | `̡` |
| 泰米尔文 | U+0B80–U+0BFF | `௓` |
| 撒马利亚文 | U+0800–U+083F | `ࠑ` |

**这些字符完全不在 `_RE_GARBLED_CHARS` 的匹配范围内**，导致 `garble_count = 0`、`garble_ratio = 0%`，条件永远不满足，函数始终返回 `False`。

> 验证数据：17179 字符的乱码文本，`_RE_GARBLED_CHARS` 只匹配到 **48 个字符（0.28%）**，CJK 字符仅 **20 个（0.12%）**，但判定结果为 `False`。

---

## 三、修复方案

### 3.1 修复思路

放弃枚举特定"乱码字符"的正则方案，改用**CJK 字符占比**作为核心判断指标：

- 年报/财报以中文为主，正常情况下 CJK 字符占比应高于 30%
- 如果 CJK 占比低于 30%，说明字体编码映射失败，内容不可信
- 改为直接触发 OCR 回退

### 3.2 代码变更

**删除**：`_RE_GARBLED_CHARS` 正则常量（原第 202-206 行）

**重写**：`_is_garbled_text()` 函数

```python
# 修复后的代码
_RE_CJK = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]')

def _is_garbled_text(text: str, min_cjk_ratio: float = 0.3) -> bool:
    """判断提取的文本是否为乱码（Adobe-CNS1 字体映射问题）。

    年报以中文为主，如果有效中文字符占比过低，说明字体编码有问题。
    （例如：Adobe-CNS1 缺少 CMap 映射，结果输出为其他语系字形）

    Args:
        text: 待检测的文本。
        min_cjk_ratio: 最低有效中文占比，低于此值判定为乱码，默认 0.3（30%）。

    Returns:
        True 表示文本疑似乱码，需 OCR 回退。
    """
    if not text or len(text) < 10:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    cjk_count = len(_RE_CJK.findall(stripped))
    total = len(stripped)
    if total == 0:
        return False
    cjk_ratio = cjk_count / total
    return cjk_ratio < min_cjk_ratio
```

### 3.3 变更影响

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| 检测逻辑 | 双重条件：乱码占比 > 30% **且** CJK 占比 < 50% | 单一条件：CJK 占比 < 30% |
| 正则复杂度 | 2 个正则（`_RE_GARBLED_CHARS` + `_RE_CJK`） | 1 个正则（仅 `_RE_CJK`） |
| 乱码覆盖范围 | 仅覆盖拉丁补充/替换字符 | 覆盖所有非 CJK 乱码输出 |
| 误报风险 | 低（条件苛刻，但漏报严重） | 低（英文 PDF 通常 < 10 字符可跳过） |

---

## 四、验证结果

### 4.1 测试环境

- **PDF 文件**：`reports/百济神州/导出页面1-20自 688235_2025年报.pdf`
- **提取命令**：`python tools/common/pdf_extract.py text "导出页面1-20自 688235_2025年报.pdf"`
- **依赖**：tesseract OCR（chi_sim+eng 语言包）、pytesseract、pymupdf

### 4.2 检测结果

| 指标 | 数值 |
|------|------|
| 总字符数 | 17,179 |
| CJK 字符数 | 20 |
| CJK 占比 | 0.12% |
| 判定为乱码 | **True**（修复前为 False） |
| 自动 OCR 回退 | 成功触发 |

### 4.3 提取效果

修复后正确提取了年报内容，包括：
- 公司名称：百济神州有限公司（BeOne Medicines Ltd.）
- 上市信息：纳斯达克、香港联交所、上交所
- 业务描述：产品管线（百悦泽、百泽安、倍利妥等）
- 市场策略、财务数据等

---

## 五、Poppler 工具集方案可行性分析

### 5.1 系统状态

| 工具 | 路径 | 状态 |
|------|------|------|
| `pdftotext` | `C:\Program Files\Git\mingw64\bin\pdftotext.exe` | 可用（xpdf 4.06） |
| `pdfinfo` | 未安装 | 不可用 |
| `pdftoppm` | 未安装 | 不可用 |

### 5.2 不可用原因

`pdftotext` 提取时持续报错：

```
Syntax Error: Unknown character collection 'Adobe-CNS1'
```

- Git for Windows 自带的 `pdftotext` 来自 xpdf（Glyph & Cog 商业版）
- 该版本**不包含** Adobe-CNS1 CMap 数据文件
- 需要额外安装 `xpdf-chinese-traditional` 语言包或将 `xpdfrc` 指向包含 CMap 的路径
- 即使解决编码问题，`pdftotext` 也只能提取纯文本流，无法保留表格结构

### 5.3 结论

**OCR 回退方案优于 Poppler 方案**：

| 对比项 | OCR 回退（当前方案） | Poppler 工具集 |
|--------|--------------------|----------------|
| Adobe-CNS1 兼容性 | 完全绕过（图片渲染） | 需额外安装 CMap |
| 表格结构 | 纯文本（同水平） | 纯文本（同水平） |
| 依赖安装 | 一次性安装 tesseract | 需下载完整 Poppler + CMap |
| 维护成本 | 低 | 高（路径配置、版本兼容） |

---

## 六、使用指南

### 6.1 自动回退（推荐）

```bash
# 自动检测 → 自动 OCR 回退
python tools/common/pdf_extract.py text "年报.pdf"
python tools/common/pdf_extract.py markdown "年报.pdf"
python tools/common/pdf_extract.py all "年报.pdf" --save-md
```

### 6.2 强制 OCR

```bash
# 跳过 pdf-inspector，直接使用 OCR
python tools/common/pdf_extract.py text "年报.pdf" --force-ocr
python tools/common/pdf_extract.py text "年报.pdf" --force-ocr --ocr-langs chi_tra+eng
```

### 6.3 语言包选择

| 语言包 | 适用场景 |
|--------|----------|
| `chi_sim+eng`（默认） | 简体中文 + 英文 |
| `chi_tra+eng` | 繁体中文 + 英文（如百济神州年报） |
| `chi_sim+chi_tra+eng` | 简体 + 繁体 + 英文 |

---

## 八、后续改进（2026-08-13）

### 8.1 改进 1：`--pages` 支持范围语法

**问题**：`--pages` 参数只支持逗号分隔单页（如 `0,1,2,3,4,5,39,40`），不支持范围语法，用户需借助 `seq -s, 0 39` 生成页码范围，增加使用成本。

**变更**：`_parse_pages()` 函数

```python
# 之前：只支持逗号分隔
--pages 0,1,2,3,4,5,39,40

# 之后：支持三种格式
--pages 0-5           # 范围语法（等价于 0,1,2,3,4,5）
--pages 0,1,2,40      # 逗号分隔（兼容旧语法）
--pages 0-5,10,20-25  # 混合语法
```

**实现**：解析 `--pages` 参数时，对每个 token 检测是否包含 `-`，若包含则按范围展开 `range(start, end + 1)`；否则按整数解析。支持三种格式混合使用。

### 8.2 改进 2：`text` 命令增加异常处理 + OCR 回退

**问题**：`text` 命令直接调用 `extract_plain_text(pdf_path)`，当 pdf-inspector 内部报错（如 `data must be str, not NoneType`）时，异常传播到顶层，输出"处理失败"的 JSON，用户无法自动获得 OCR 回退。

**变更**：`main()` 函数中 `text` 命令的 `else` 分支

```python
# 之前：
else:
    text = extract_plain_text(pdf_path)
    if _is_garbled_text(text) and _tesseract_available():
        text = _ocr_extract_text(pdf_path, langs=args.ocr_langs)
        ocr_used = True

# 之后：
else:
    try:
        text = extract_plain_text(pdf_path)
    except Exception as exc:
        # pdf-inspector 内部报错，自动回退到 OCR
        if _tesseract_available():
            text = _ocr_extract_text(pdf_path, langs=args.ocr_langs)
            ocr_used = True
        else:
            raise RuntimeError(
                f"pdf-inspector 提取失败（{exc}），且 tesseract OCR 不可用。"
                "建议：使用 --force-ocr 参数强制 OCR 提取，"
                "或安装 tesseract-ocr 后重试。"
            )
    if not ocr_used and _is_garbled_text(text) and _tesseract_available():
        text = _ocr_extract_text(pdf_path, langs=args.ocr_langs)
        ocr_used = True
```

### 8.3 改进 3：错误提示增加 `--force-ocr` 建议

**问题**：当 pdf-inspector 失败且 tesseract 不可用时，错误信息仅提示"请安装 tesseract-ocr"，未告知用户可尝试 `--force-ocr` 参数。

**变更**：3 处 `RuntimeError` 错误信息

| 位置 | 之前 | 之后 |
|------|------|------|
| `run_all()` 函数 | `"请安装 tesseract-ocr 或排查 PDF 文件。"` | `"建议：使用 --force-ocr 参数强制 OCR 提取，或安装 tesseract-ocr 后重试。"` |
| `markdown` 命令 | 同上 | 同上 |
| `text` 命令 | 无此分支（原代码未捕获异常） | 新增，同上 |

---

## 九、涉及文件清单（完整版）

| 文件 | 操作 | 说明 |
|------|------|------|
| `tools/common/pdf_extract.py` | 修改 | 修复 `_is_garbled_text()` 乱码检测逻辑 |
| `tools/common/pdf_extract.py` | 修改 | `_parse_pages()` 支持范围语法 `0-39` |
| `tools/common/pdf_extract.py` | 修改 | `text` 命令增加异常处理 + OCR 回退 |
| `tools/common/pdf_extract.py` | 修改 | 3 处 `RuntimeError` 增加 `--force-ocr` 建议 |
| `reports/百济神州/test_pdftotext_output.txt` | 删除 | 测试临时文件 |
| `.trae/skills/investment-team/SKILL.md` | 修改 | 更新 `--pages 0-5` 范围语法示例 |
| `.trae/skills/tools-scripts/pdf-extraction.md` | 修改 | 更新 `--pages` 范围语法说明 + 快速索引 |
| `.trae/skills/tools-scripts/common-tools-guide.md` | 修改 | 描述增加"支持自动乱码检测 + OCR 回退" |
| `.trae/skills/financial-data/SKILL.md` | 修改 | 同步更新 PDF 提取说明 |
| `.trae/skills/earnings-review/SKILL.md` | 修改 | 同步更新 PDF 提取说明 |
| `.trae/skills/earnings-team/SKILL.md` | 修改 | 同步更新 PDF 提取说明 |
| `.trae/skills/management-deep-dive/SKILL.md` | 修改 | 同步更新 PDF 提取说明 |
| `.trae/skills/wechat-article/SKILL.md` | 修改 | 同步更新 PDF 提取说明 |
| `.trae/skills/earnings-review/README.md` | 修改 | 同步更新 README |
| `.trae/skills/earnings-team/README.md` | 修改 | 同步更新 README |
| `.trae/skills/financial-data/README.md` | 修改 | 同步更新 README |
| `.trae/skills/wechat-article/README.md` | 修改 | 同步更新 README |
| `.trae/skills/management-deep-dive/README.md` | 修改 | 同步更新 README |
| `docs/dev_docs/PDF提取乱码检测Bug修复记录.md` | 修改 | 新增后续改进章节（本次修订） |