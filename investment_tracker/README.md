# 投資理財資金分配追蹤系統

個人投資組合追蹤工具，以視覺化方式管理美股、ETF、加密貨幣和選擇權的資金配置與執行進度。

## 功能概述

- **投資總覽** — CNN 恐懼貪婪指數、水平配置 Treemap、垂直配置堆疊長條圖、報酬率統計
- **投資計畫管理** — 設定預計投入金額、水平比例（保守/樂透/進攻）、進攻型安全邊際配置
- **股票交易記錄** — 買進/賣出紀錄、表單輸入 + 點選編輯
- **選擇權交易記錄** — 追蹤保證金、買方成本、資金來源歸屬
- **數據分析** — 持倉明細、平均成本、已實現/未實現損益

## 技術棧

| 技術 | 用途 |
|-----|------|
| Python + Streamlit | Web 應用框架 |
| Pandas | 資料處理 |
| Plotly | 互動式圖表 |
| yfinance | 即時股價與匯率 |
| CSV | 資料儲存 |

## 安裝與使用

```bash
# 安裝依賴
pip install streamlit pandas plotly yfinance fear_and_greed

# 啟動應用
streamlit run investment_tracker.py
```

## 資金配置邏輯

### 水平配置
總預算按比例分配到三種投資類型（預設 10% 保守型 / 10% 樂透型 / 80% 進攻型），比例可自訂。

### 垂直配置
每檔股票的預算以堆疊長條圖顯示四層進度：
1. 已買入金額（藍色）
2. 賣方選擇權保證金（橘色）
3. 買方選擇權成本（紫色）
4. 待部署資金（灰色）

進攻型股票另有五檔安全邊際買入價格標記。

## 資料檔案

| 檔案 | 內容 |
|-----|------|
| `investment_plan.csv` | 每月預計投入金額 |
| `aggressive_allocation.csv` | 進攻型股票配置與安全邊際 |
| `conservative_allocation.csv` | 保守型 ETF 配置 |
| `lottery_allocation.csv` | 樂透型標的配置 |
| `stock_transactions.csv` | 股票買賣紀錄 |
| `options_transactions.csv` | 選擇權交易紀錄 |
