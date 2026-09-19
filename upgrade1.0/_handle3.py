# -*- coding: utf-8 -*-
"""处理三项非阻塞披露事项：① tools-scripts 9 处指针就地订正；② CLAUDE.md 写入落盘纪律；③ 详细计划增量登记（十九）。"""

BASE = r"f:\Financial_Investment_Analysis"
CTG = BASE + r"\.trae\skills\tools-scripts\common-tools-guide.md"
GGP = BASE + r"\.trae\skills\tools-scripts\garp-geo-policy-tools.md"
CLAUDE = BASE + r"\CLAUDE.md"
PLAN = BASE + r"\upgrade1.0\GARP升级-软件与技能升级详细计划.md"


def patch(path, pairs):
    """逐对 (old, new) 确定性替换：断言 BOM / 新串不存在 / 锚点唯一，写入后回读。"""
    with open(path, "rb") as fh:
        raw = fh.read()
    assert raw[:3] != b"\xef\xbb\xbf", path + " 存在 BOM"
    text = raw.decode("utf-8")
    crlf = text.count("\r\n")
    nl = "\r\n" if crlf else "\n"  # 保持原行尾
    for old, new in pairs:
        assert new not in text, path + " 新串已存在：" + old[:36]
        assert text.count(old) == 1, path + " 锚点不唯一(" + str(text.count(old)) + "): " + old[:36]
        text = text.replace(old, new, 1)
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))
    with open(path, "rb") as fh:
        raw2 = fh.read()
    t2 = raw2.decode("utf-8")
    assert t2.count("\r\n") == crlf, path + " 回读行尾漂移"
    print("OK " + path.split("\\")[-1] + ": " + str(len(raw)) + "B -> " + str(len(raw2)) + "B / "
          + str(len(t2.splitlines())) + "L / CRLF=" + str(t2.count("\r\n")))
    return nl


# ===== ① common-tools-guide.md：7 行 8 处指针 + 版本行 =====
patch(CTG, [
    # L47 P23-D4：悬空指针 → 未修复
    ("工具缺口（修复评估转 P5-2）", "工具缺口（**未修复**：原指派 P5-2，该任务已收口且未承接）"),
    # L52 P23-D9
    ("工具局限（修复转 P5-2）", "工具局限（**未修复**：P5-2 转办不修）"),
    # L53 P23-D10 两处
    ("工具侧转 P5-2 |", "工具侧修复**未实施**（P5-2 转办不修） |"),
    ("工具缺口（修复转 P5-2）", "工具缺口（**未修复**：P5-2 转办不修）"),
    # L59 节标题
    ("### 工具缺陷登记指针（E 类 / A 类，**修复归 P5-2**）",
     "### 工具缺陷登记指针（E 类 / A 类，**收口状态已标注**）"),
    # L63 P23-E1：已修复 → 完成态常驻引用
    ("文档侧登记「已知限制 + 规避形态」；修复（`%` → `%%`）归 P5-2，修复后回改",
     "**已于 P5-2 §4.4 修复**（12 处 `%(` → `%%(`，四条 `--help` 退出码 0）；详见 "
     "[garp-governance-tools.md](./garp-governance-tools.md)"),
    # L64 P23-A4：已修复 → 完成态常驻引用
    ("示例修正为 `python -m` 模块形态；工具侧修复转 P5-2",
     "**已于 P5-2 §4.5 修复**（注入项目根到 `sys.path`，`python x.py` 与 `python -m x` 双形态均可调用）；详见 "
     "[garp-geo-policy-tools.md](./garp-geo-policy-tools.md)"),
    # L66 P23-B3
    ("工具侧补折算转 P5-2 |", "工具侧补折算**未实施**（P5-2 转办不修） |"),
    # 版本行 2.6.0 → 2.6.1
    ("- **版本**：2.6.0（补 `garp-valuation-tools.md` 索引行；新增「GARP 已知缺口与降级路径」节（P23-D1~D14 + E/A 类缺陷指针）；P4-23）",
     "- **版本**：2.6.1（2026-09-19 收口订正：E / A 类缺陷指针 8 处就地订正——P23-E1 / P23-A4 回改为**已修复**完成态，"
     "P23-D4 / D9 / D10 / B3 明确标注**未修复**（P5-2 转办不修）；2.6.0 为 P4-23 补 `garp-valuation-tools.md` 索引行与"
     "「GARP 已知缺口与降级路径」节）"),
])

# ===== ① garp-geo-policy-tools.md：1 处指针 + 版本行 =====
patch(GGP, [
    ("**转 P5-2 / P5-3**；本任务**不改签名、只标注差异**",
     "**未实施**（原指 P5-2 / P5-3，两任务均已收口且未承接）；本文件**不改签名、只标注差异**"),
    ("- **版本**：1.2.0（P5-2 §4.5 修复 A4：`scan` 支持脚本直连与模块两种调用形态，撤销 1.1.0 的「仅 `python -m`」限制；补渗透率取数来源与口径基准（P23-A1）、补 `trend_tech_screen.py` 二维差异标注（P23-A2）、补 `screen`/`localize` 输出字段；P5-2）",
     "- **版本**：1.2.1（2026-09-19 收口订正：L138「三维扩展转 P5-2 / P5-3」订正为**未实施**；1.2.0 为 P5-2 §4.5 修复 A4、"
     "补 P23-A1 / A2 与 `screen`/`localize` 输出字段）"),
])

# ===== ② CLAUDE.md：新增「文件落盘纪律」 =====
nl = patch(CLAUDE, [
    ("- **推送前**：询问用户是否需要推送到 GitHub；推送前务必 `git pull --rebase`\n",
     "- **推送前**：询问用户是否需要推送到 GitHub；推送前务必 `git pull --rebase`\n"
     "- **文件落盘纪律**：修改既有文件一律走**确定性写入范式**，不依赖 `Edit` 工具单次调用——本项目多次出现"
     "「`Edit` 返回成功但**未落盘**」的静默失败。范式四步：① `read_bytes()` 读入并解码；② 断言**无 BOM**、"
     "行尾与目标一致；③ 断言**新串不存在**（防重复写入）、**锚点计数 = 1**（防误替换）；④ 写入后**立即回读断言**"
     "（字节数 / 行数 / 关键锚点）。整文件重写（`Write`）可能引入 **CRLF** 与**超长截断**（约 850~900 行以上易不落盘），"
     "须事后归一与校验；临时脚本一律用后即删。\n"),
])

# ===== ③ 详细计划：增量登记（十九） =====
g18_tail = "四件行尾 / 编码（UTF-8 无 BOM）现**统一**。\n"
g19 = (
    "> **2026-09-19 增量登记（十九）**：**用户就三项非阻塞披露事项作出裁定并已执行**——"
    "① **`tools-scripts/` 3 文件 / 9 处历史指针**：裁定「**全部 9 处仅就地订正文本，不新增子任务、不改代码**」。"
    "据此完成订正：**甲组 2 处**（`common-tools-guide.md` L63 P23-E1 / L64 P23-A4）回改为**已修复完成态常驻引用**"
    "（指向 P5-2 §4.4 / §4.5 及对应 `garp-*-tools.md`）；**乙组 6 处**（L47 P23-D4 / L52 P23-D9 / L53 P23-D10 两处 / "
    "L59 节标题 / L66 P23-B3 / `garp-geo-policy-tools.md` L138 三维扩展）就地订正为「**未修复**"
    "（P5-2 转办不修 / 已收口未承接）」。**如实披露（交接链断裂）**：P5-2《集成验收记录》§9.5 载 4 项"
    "「转办不修……**转 P5-3**」，但 P5-3 三份文书对该 4 项**零命中**，**P5-3 收口时未承接**；"
    "P5-5《开发方案与计划》§3.4「其语义已随 P5-2 / P5-3 交付兑现」之判断**仅对甲组 2 处成立**，本登记予以**订正**。"
    "**范围声明**：本次仅**文本订正**，**零工具代码改动**——乙组所指工具缺陷（D4 能力缺口 / D9 权重归一 / "
    "D10 `--markdown-only` / B3 跨币种折算 / 三维扩展）**依旧未修复**，按各自左列既定规避路径使用，"
    "**不新增子任务承接**（据本次用户裁定）。版本影响：`common-tools-guide.md` 2.6.0 → **2.6.1**、"
    "`garp-geo-policy-tools.md` 1.2.0 → **1.2.1**（仅版本行与指针文本）。"
    "② **`Edit` 工具静默失败纪律**：裁定「**固化至 `CLAUDE.md`『工作规范』**（工作区级，全局生效）」，"
    "已在该节新增「**文件落盘纪律**」条（确定性写入范式四步：读入 → 断言无 BOM 与行尾 → 断言新串不存在且锚点唯一 → "
    "写入后立即回读；并载明 `Write` 的 CRLF / 超长截断风险与临时脚本用后即删）。"
    "③ **git 未提交变更（84 项，含整个 `upgrade1.0/` 未跟踪）**：裁定「**分主题多次提交，暂不推送**」，"
    "提交粒度与时机见提交记录。**本登记为编排层流程留痕**。\n"
)
patch(PLAN, [(g18_tail, g18_tail + g19)])
print("DONE")