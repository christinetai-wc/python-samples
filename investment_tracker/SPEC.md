# SPEC.md - 投資理財資金分配追蹤系統

## 資料模型

### DataFrame 結構

| 檔案名稱 | session_state key | 欄位 |
|---------|-------------------|------|
| investment_plan.csv | df_plan | 時間, 預計投入(USD), 匯率 |
| aggressive_allocation.csv | df_allocation | 股票代碼, 比重, 公允值(USD), 邊際1-5(%), 邊際1-5比重(%) |
| conservative_allocation.csv | df_conservative | 股票代碼, 比重, 說明 |
| lottery_allocation.csv | df_lottery | 股票代碼, 比重, 說明 |
| stock_transactions.csv | df_stock | 交易日期, 交易類型, 所屬分類, 股票代碼, 股數, 成交價格(USD), 手續費(USD), 交易稅(USD), 用途說明, 備註 |
| options_transactions.csv | df_option | 交易日期, 商品類型, 標的, 履約價, 到期日, 買賣權, 買賣方向, 口數, 權利金, 交易金額(USD), 手續費(USD), 保證金(USD), 總成本(USD), 資金來源, 策略說明 |

### 投資類型分類
- **保守型**: 低風險 ETF（如 VOO）
- **進攻型**: 個股投資，有安全邊際買入策略（如 TSLA, META, NVDA, GOOGL, MSFT）
- **樂透型**: 高風險標的（如 BTC）

### 向後相容
- 舊版 `investment_plan.csv` 有 `投資類型` 欄位，載入時自動 drop

---

## 架構設計

### 整體結構
```
Streamlit 單頁應用（investment_tracker.py）
├── 側邊欄
│   ├── 頁面選擇器（st.sidebar.radio，5 頁單選）
│   ├── 資料管理區（載入/儲存 CSV，僅此處有儲存按鈕）
│   └── 匯率資訊
│
├── 主內容區
│   ├── 📊 投資總覽（恐懼貪婪指數、水平/垂直配置圖、報酬率統計）
│   ├── 💵 投資計畫管理（水平比例設定、投入金額、配置表）
│   ├── 📈 股票交易記錄（表單 + 可點選表格）
│   ├── 🎯 選擇權交易記錄（表單 + 可點選表格）
│   └── 📉 數據分析（持倉明細、統計數據）
│
└── 共用函數層
    ├── 資料載入/儲存（load_from_folder, save_to_folder, export_all_to_zip）
    ├── 計算邏輯（actual_investment, sell_proceeds, option_margin, option_buy_cost, holdings, market_value）
    └── 外部 API（fear_greed_index, current_price, exchange_rate）
```

### 狀態管理
- `st.session_state` 管理所有 DataFrame 和 UI 狀態
- `FILE_MAPPING` 字典：檔案名稱 → session_state key
- `data_loaded`：資料載入標記
- `data_folder`：本地資料夾路徑（預設為程式所在目錄）
- `horizontal_ratio`：水平配置比例 dict
- `stock_edit_idx` / `option_edit_idx`：交易編輯索引
- 頁面編輯後自動存入 session_state，僅側邊欄提供 CSV 儲存

---

## 核心演算法

### 1. 總預算與資金分配
```
plan_total_raw = Σ 預計投入(USD)
realized_profit = 賣出收入 - 賣出股票的平均買入成本
total_budget = plan_total_raw + realized_profit

各類預算 = total_budget × horizontal_ratio[類型] / 100
各股預算 = 各類預算 × 該股比重 / 100
```

### 2. 已實現損益（平均成本法）
```
對每檔已賣出的股票：
  buy_cost = Σ (買進股數 × 成交價 + 手續費)
  buy_shares = Σ 買進股數
  avg_price = buy_cost / buy_shares
  sell_shares = Σ |賣出股數|
  sold_cost += avg_price × sell_shares

realized_profit = sell_proceeds - sold_cost
```

### 3. 實際投入金額
```
actual = Σ (買進股數 × 成交價格 + 手續費)
手續費預設 = 0（Firstrade 免手續費）
```

### 4. 選擇權保證金（賣方）
```
篩選：資金來源 = 指定股票 AND 到期日 >= 今天 AND 買賣方向 = 賣出
結果：Σ 保證金(USD)
歸屬到「資金來源」股票，非「標的」股票
```

### 5. 選擇權買方成本
```
篩選：資金來源 = 指定股票 AND 到期日 >= 今天 AND 買賣方向 = 買入
結果：Σ 交易金額(USD)
```

### 6. 無資金來源的選擇權自動分攤
```
1. 計算每檔股票的剩餘預算 = planned - actual - margin - buy_cost
2. 按剩餘預算比例分攤到多檔股票
3. 分攤後的金額加入對應股票的 margin 或 buy_cost
```

### 7. 持股數量
```
holdings[股票] = Σ 買進股數 - Σ |賣出股數|
全部賣出的股票不顯示在圖表，但已實現損益納入總計
```

### 8. 目前市值
```
市值 = Σ (持股數 × 現價)
現價來源：yfinance API（5 分鐘快取）
三層 fallback：fast_info → history → info
```

### 9. 報酬率
```
總成本 = 持有中股票的買入成本（不含已賣出）
未實現損益 = 目前市值 - 總成本
股票損益 = 未實現損益 + 已實現損益
股票報酬率 = 股票損益 / 總成本 × 100%
選擇權報酬率 = 選擇權收支 / 被壓住保證金 × 100%
總報酬率 = (股票損益 + 選擇權收支) / 總成本 × 100%
```

### 10. 執行率
```
執行率 = (持有成本 + 被壓住保證金) / 總預算 × 100%
```

### 11. 安全邊際價格（進攻型專用）
```
邊際買入價 = 公允值 × 邊際百分比
邊際1-5比重：各邊際價對應的資金買入比重（預設 30/30/10/10/20）
```

---

## 圖表設計

### 水平配置 Treemap
- 使用 `plotly.graph_objects.Treemap`
- `tiling=dict(packing='dice')`：水平排列
- `branchvalues='remainder'`
- `sort=False`：保持資料順序（保守→樂透→進攻）
- 兩層：類型 → 個股
- Hover 顯示：預計投入、已買入、保證金、買方成本、待部署、市值

### 垂直配置堆疊長條圖
- `barmode='stack'`，4 層：
  - 已買入（藍 `#3498db`）
  - 賣方保證金（橘 `#e67e22`）
  - 買方成本（紫 `#9b59b6`）
  - 待部署（灰 `#bdc3c7`）
- 所有類型的股票都顯示（不只進攻型）
- 進攻型額外標記紅框邊際買入價

### 排序
- 兩張圖表共用 `sorted_chart`
- 排序規則：`type_order`（保守=0, 樂透=1, 進攻=2）→ 原始索引

---

## 邊界情況處理

| 情況 | 處理方式 |
|-----|---------|
| DataFrame 為空 | 顯示預設範例資料，計算函數返回 0 或空 dict |
| 欄位不存在 | `if 'col' not in df.columns` 檢查後補預設值 |
| yfinance 失敗 | 三層 fallback，失敗返回 None，市值顯示 0 |
| fear_and_greed 失敗 | try-except，失敗返回 None，不顯示儀表板 |
| 匯率查詢失敗 | fallback 到 `USD_RATE = 31.5` |
| 數值空值 | `pd.notna()` 檢查，`fillna()` 填充 |
| 比重加總 ≠ 100% | 顯示警告訊息 |
| 全部賣出的股票 | 不顯示在圖表，已實現損益納入總計 |
| 選擇權無資金來源 | 按剩餘預算比例分攤到多檔股票 |

---

## 外部依賴與 API

### 核心依賴
| 套件 | 版本需求 | 用途 |
|-----|---------|------|
| streamlit | - | Web 框架 |
| pandas | - | 資料處理 |
| plotly | - | 互動式圖表 |

### 可選依賴
| 套件 | 用途 | 缺少時行為 |
|-----|------|-----------|
| yfinance | 股價查詢、即時匯率 (`USDTWD=X`) | 市值顯示 0，匯率用預設值 |
| fear_and_greed | CNN 恐懼貪婪指數 | 不顯示儀表板 |

### 加密貨幣代碼映射
```python
crypto_map = {'BTC': 'BTC-USD', 'ETH': 'ETH-USD', 'SOL': 'SOL-USD',
              'XRP': 'XRP-USD', 'ADA': 'ADA-USD', 'DOGE': 'DOGE-USD'}
```

---

## 設計決策

| 決策 | 理由 | 替代方案 |
|-----|------|---------|
| Streamlit | 快速開發、內建 data_editor、部署簡單 | Flask+React, Dash |
| CSV 儲存 | 簡單、可攜、可用 Excel 編輯 | SQLite, JSON |
| session_state | Streamlit 原生、刷新保持狀態 | 外部資料庫 |
| yfinance | 免費、支援美股和加密貨幣 | Alpha Vantage, IEX Cloud |
| 水平比例分配 | 不需每筆投入指定類型，簡化操作 | 每筆交易指定投資類型 |
| 保證金歸屬資金來源 | 反映資金實際被佔用的部位 | 歸屬到標的 |
| 表單+可點選表格 | 比 data_editor 更直覺的編輯體驗 | st.data_editor |

---

## 已知限制

1. 僅支援 USD 單一幣別
2. 無歷史績效追蹤（只有當前快照）
3. 無自動同步，需手動載入/儲存
4. 無使用者認證（單機使用）
5. Yahoo Finance 可能被限速
6. 無單元測試覆蓋
