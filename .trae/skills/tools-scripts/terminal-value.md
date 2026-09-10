---
name: terminal-value
description: "长期折现估值工具（十年尺度）：使用 terminal_value.py 进行终值 PE、十年 IRR、r/ROIC/g 三输入与三条硬约束（C1 同币种/C2 r−g≥5pct/C3 离散风险不入 r/β）准出检查，禁止 LLM 心算与同业类比。"
disable-model-invocation: true
---

# 长期折现估值（十年尺度）

三年三情景回答"贵不贵"，本工具用永续增长模型回答"值不值得重仓"。凡是给出**十年期 IRR 或终值倍数**的研究，必须通过 `terminal_value.py` 走这套流程。

核心公式：`PE(终值) = (1 - g/ROIC) / (r - g)`

---

## 使用方法

```bash
# 单点退出 PE，打印完整算式
python tools/common/terminal_value.py pe --roic 0.20 --g 0.02 --r 0.06

# 单公司三档推演（内置 7 家预设）
python tools/common/terminal_value.py company --name 腾讯 --r 0.06 --g-shift -0.01

# 多公司横评 + 排序
python tools/common/terminal_value.py table --r 0.06 --g-shift -0.01 --rf 0.017

# 多档 r 敏感性 + 排序稳定性检验
python tools/common/terminal_value.py sweep --r 0.06,0.08,0.10,0.12 --g-shift -0.01 --rf 0.017

# 分母宽度体检
python tools/common/terminal_value.py check --r 0.06 --g-shift -0.01

# 三条硬约束准出检查（通过才可写进报告）
python tools/common/terminal_value.py audit \
  --currency {CNY|USD|HKD} --r {资本成本} --roic {稳态ROIC} \
  --g {悲观g},{基准g},{乐观g} --rf {无风险利率} --beta 1.0 \
  --discrete-risks "{风险名}:{情景|尾部档|概率|未建模},..."

# 从零算 IRR
python tools/common/terminal_value.py irr --profit 5390 --mcap 34420 --pe 22.5 --years 10 --payout 0.015
```

## 三条硬约束（audit 子命令）

| # | 检查 | 打回条件 |
|---|---|---|
| C1 | r 与 g 必须同币种（人民币 r 6%–9%、g≤2%；美元/港元 r 9%–11.5%、g≤4%） | r 落在别的币种区间，或基准档 g 超过本币上限 |
| C2 | 分母 r−g ≥ 5 个百分点 | 任一档不足 5pct（如需做情景加 `--upside-only`） |
| C3 | 离散风险不得进 r 或 β | 退市/VIE/地缘断供/监管重击写进 `折现率`/`r`/`beta` 一律打回；β≠1.0 必须给 `--beta-justification` |

## 报告里必须写出的四件事

1. r 取值、币种、配对的 g 上限
2. 至少两档 r 的敏感性及排序稳定性
3. 每一档 r−g 分母宽度（低于 5pct 标注"仅作情景参考"）
4. 未建模的离散风险清单（audit 标 `未建模` 的，写进"限制"章节）

## 注意事项

- 终值倍数唯一合法来源是永续增长模型，**禁止用同业类比**
- `g` 不随 `r` 变：g 是对终值年之后经济的判断，r 是你要求的回报
- 跨币种折算前先 `python tools/common/fx_rate.py --code USDCNY,HKDCNY` 获取实时汇率

