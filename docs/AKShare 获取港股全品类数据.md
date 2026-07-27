# AKShare 获取港股全品类数据

*———— 资料来源于豆包，未验证。*

# 结论：**AKShare 完全支持获取港股全品类数据**

内置新浪、东方财富、雪球多数据源，免费、无需密钥，覆盖实时行情、历史K线、复权、财报、指数、沪深港通、估值、个股基础信息等港股全场景数据。



## 一、常用港股核心接口分类

### 1\. 实时全市场行情（全部港股列表\+实时报价）

```Python
import akshare as ak

# 新浪数据源：全部港股实时行情，可获取全部港股代码
df_all_hk = ak.stock_hk_spot()
print(df_all_hk.head())

# 东方财富数据源：港股实时行情（推荐，数据更全）
df_all_hk_em = ak.stock_hk_spot_em()

# 仅港股主板实时行情
df_hk_main = ak.stock_hk_main_board_spot_em()
```



### 2\. 个股历史K线（支持复权、日线/分时）

#### 新浪接口（支持复权因子）

```Python
# 腾讯控股 00700，前复权日线
df_hk_hist = ak.stock_hk_daily(symbol="00700", adjust="qfq")
# adjust参数：""未复权 / qfq前复权 / hfq后复权 / qfq-factor复权因子
```



#### 东方财富接口（支持指定起止日期，更灵活）

```Python
df_hk_hist_em = ak.stock_hk_hist(
    symbol="00700",
    period="daily",  # daily日线 / min分时
    start_date="20250101",
    end_date="20260701",
    adjust="qfq"
)
```



### 3\. 港股指数（恒生指数HSI、恒生科技CES100等）

```Python
# 指数实时行情
df_hk_index_spot = ak.stock_hk_index_spot_sina()

# 指数历史日线
df_hsi = ak.stock_hk_index_daily_sina(symbol="HSI")  # 恒生指数
df_tech = ak.stock_hk_index_daily_sina(symbol="CES100") # 恒生科技
```



### 4\. 港股财务/基本面数据

```Python
# 三大财务报表（东方财富）
df_fin = ak.stock_financial_hk_report_em(symbol="00700", report_type="利润表")

# 财务分析指标（ROE、毛利率等）
df_fin_indicator = ak.stock_financial_hk_analysis_indicator_em(symbol="00700")

# 个股基础信息（雪球）
df_info = ak.stock_individual_basic_info_hk_xq(symbol="00700")

# 港股估值PE/PB
df_val = ak.stock_hk_valuation_baidu(symbol="00700")
```



### 5\. 资金与特色数据

```Python
# 沪深港通港股持股数据
df_hsgt = ak.stock_hsgt_individual_em(symbol="00700")

# 港股人气热度榜
df_hot = ak.stock_hk_hot_rank_em()

# A+H比价数据
df_ah = ak.stock_zh_ah_spot()
```



## 二、关键使用注意事项

1. **代码格式**

港股统一使用**5位数字字符串**，如腾讯 `00700`，不要加 `.HK` 前缀；部分接口兼容 `HK00700` 格式。

2. **版本要求**

建议升级到最新版保证接口可用：

```Bash
pip install akshare --upgrade
```

3. **数据源差异**

    - 新浪：支持复权因子，历史数据长；

    - 东方财富：字段更丰富、支持自定义起止日期、板块区分；

4. **限制**

免费公开爬虫接口，高频批量请求易触发风控，建议增加延时、分批请求；无分钟级实时高频tick，仅分时/日线。

## 三、完整最小示例

```Python
import akshare as ak

# 1. 获取全部港股代码与实时行情
all_hk = ak.stock_hk_spot_em()
print("港股总数量：", len(all_hk))

# 2. 获取腾讯控股前复权历史日线
tencent = ak.stock_hk_hist(symbol="00700", period="daily", adjust="qfq")
print(tencent.tail())

# 3. 获取恒生指数历史数据
hsi = ak.stock_hk_index_daily_sina(symbol="HSI")
print(hsi.head())
```



## 四、对比其他方案优势

- 无需注册、无token、免费使用；

- 统一返回 Pandas DataFrame，方便量化回测；

- 同时覆盖行情、财报、指数、互联互通资金，一站式港股数据。

---

# AkShare 获取港股财务指标完整教程（东方财富数据源，无需翻墙）

## 一、两个核心港股财务接口

### 1\. 综合财务比率指标（直接拿ROE、毛利率、负债率等，推荐）

接口：`stock_financial_hk_analysis_indicator_em`

作用：一次性返回**预计算好的财务比率**，覆盖盈利能力、偿债、营运、成长、估值指标，带同比、行业均值、行业排名

### 2\. 三大原始财务报表（利润表/资产负债表/现金流量表）

接口：`stock_financial_hk_report_em`

作用：原始财报科目，可自行计算自定义指标，支持**年度/单季度报告期**切换



## 二、前置环境

```Bash
# 升级最新版akshare，旧版本港股财务接口会缺失
pip install akshare --upgrade
```

```Python
import akshare as ak
import pandas as pd
import time
```



## 三、示例1：直接获取成品财务指标（最常用）

以腾讯控股 `00700` 演示

```Python
# 港股代码：5位数字字符串，不带.HK
symbol = "00700"

# 获取全部财务分析指标
df_indicator = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol)

# 查看全部指标类型
print(df_indicator["指标名称"].unique())
# 打印前20行
print(df_indicator.head(20))
```

### 返回字段说明

- 指标名称：ROE、销售净利率、毛利率、资产负债率、每股收益、营收同比、PE、PB等

- 报告期：2024年报、2025中报、2025三季报等

- 指标值、同比增长率、行业平均、行业排名

### 筛选指定指标（只看ROE、毛利率）

```Python
target = ["净资产收益率(ROE)(%)", "销售毛利率(%)"]
df_filter = df_indicator[df_indicator["指标名称"].isin(target)]
print(df_filter)
```



## 四、示例2：获取三大原始财务报表

接口参数：

- stock：港股代码 `00700`

- symbol：报表类型 `利润表` / `资产负债表` / `现金流量表`

- indicator：`年度` / `报告期`（年度=年报；报告期=年报\+中报\+季报）

```Python
# 1. 年度利润表
df_profit = ak.stock_financial_hk_report_em(
    stock="00700",
    symbol="利润表",
    indicator="年度"
)
print("年度利润表：")
print(df_profit)

# 2. 全部报告期资产负债表（含季报、中报）
df_balance = ak.stock_financial_hk_report_em(
    stock="00700",
    symbol="资产负债表",
    indicator="报告期"
)

# 3. 现金流量表
df_cash = ak.stock_financial_hk_report_em(
    stock="00700",
    symbol="现金流量表",
    indicator="年度"
)
```

原始报表包含：营业收入、净利润、总资产、总负债、经营现金流等原始科目，适合自己计算自定义财务比率。



## 五、示例3：批量多只港股财务指标采集

批量请求加延时防东财反爬

```Python
hk_list = ["00700", "9988", "03690"]
all_fin = []

for code in hk_list:
    try:
        df = ak.stock_financial_hk_analysis_indicator_em(symbol=code)
        df["股票代码"] = code
        all_fin.append(df)
        time.sleep(1.5)  # 间隔1.5秒
    except Exception as e:
        print(f"{code} 获取失败：{e}")

# 合并全部数据
df_all = pd.concat(all_fin, ignore_index=True)
# 导出Excel
df_all.to_excel("港股财务指标汇总.xlsx", index=False)
```



## 六、补充配套港股基本面接口

### 1\. 港股估值PE/PB（百度数据源）

```Python
df_val = ak.stock_hk_valuation_baidu(symbol="00700")
print(df_val)
```

### 2\. 个股基础简介（雪球）

```Python
df_info = ak.stock_individual_basic_info_hk_xq(symbol="00700")
```

### 3\. 沪深港通持仓资金数据

```Python
df_hsgt = ak.stock_hsgt_individual_em(symbol="00700")
```



## 七、关键注意事项

1. **网络**：全部`_em`东方财富港股接口内地直连，**不需要科学上网**；全局VPN反而会403/空数据，建议关闭代理

2. **代码格式**：必须5位字符串，如`00700`，不能写`700`、`0700.HK`

3. **反爬限制**：批量循环务必加`time.sleep(1~2)`，短时间高频请求会被限流返回空表

4. **币种**：财报数据单位统一为**港币**，注意和A股区分

5. **版本**：低版本AKShare无港股财务接口，必须执行`pip install akshare --upgrade`升级

## 八、常见报错解决

1. 返回空DataFrame

    - 升级akshare；关闭全局代理；延长请求延时；确认代码为5位字符串

2. 403访问拒绝

    - 请求过快，增加sleep；切换手机热点重试

3. 字段缺失

    - 部分港股新股/仙股披露财报不全，属于原始网站数据缺失，非接口问题

