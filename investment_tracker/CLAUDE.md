# CLAUDE.md - 投資理財資金分配追蹤系統

## 開發指令
```bash
streamlit run investment_tracker.py        # 啟動應用
python -c "import ast; ast.parse(open('investment_tracker.py').read()); print('OK')"  # 語法檢查
```

## 關鍵路徑與常數
- `investment_tracker.py` — 唯一程式檔，所有邏輯都在這裡
- `USD_RATE = 31.5` — 預設匯率 fallback
- `.streamlit/secrets.toml` — Streamlit 設定
- CSV 檔案：`investment_plan.csv`, `aggressive_allocation.csv`, `conservative_allocation.csv`, `lottery_allocation.csv`, `stock_transactions.csv`, `options_transactions.csv`

## 模組結構（單檔，依區塊分）
| 區塊 | 職責 |
|-----|------|
| 初始化區 | 導入套件、常數、`init_session_state()` |
| 計算函數 | `calculate_actual_investment`, `calculate_sell_proceeds`, `calculate_option_margin`, `calculate_option_buy_cost`, `calculate_holdings`, `calculate_market_value` |
| 外部 API | `get_fear_greed_index`, `get_current_price`, `get_exchange_rate` |
| 資料載入/儲存 | `load_from_folder`, `load_from_uploaded_files`, `save_to_folder`, `export_all_to_zip` |
| 頁面渲染 | 5 個功能頁的 UI 邏輯 |

## 數據模型

### session_state 對應
| 檔案 | key | 重要欄位 |
|-----|-----|---------|
| investment_plan.csv | df_plan | 時間, 預計投入(USD), 匯率 |
| aggressive_allocation.csv | df_allocation | 股票代碼, 比重, 公允值(USD), 邊際1-5(%), 邊際1-5比重(%) |
| conservative_allocation.csv | df_conservative | 股票代碼, 比重, 說明 |
| lottery_allocation.csv | df_lottery | 股票代碼, 比重, 說明 |
| stock_transactions.csv | df_stock | 交易日期, 交易類型, 所屬分類, 股票代碼, 股數, 成交價格(USD), 手續費(USD), 交易稅(USD) |
| options_transactions.csv | df_option | 交易日期, 商品類型, 標的, 履約價, 到期日, 買賣權, 買賣方向, 口數, 權利金, 交易金額(USD), 手續費(USD), 保證金(USD), 資金來源, 策略說明 |

### 水平配置（horizontal_ratio）
- `st.session_state.horizontal_ratio` = `{'保守型': 10.0, '樂透型': 10.0, '進攻型': 80.0}`
- 總預算按此比例分配到三種類型，不需每筆投入指定類型
- 已實現損益（賣股獲利）加回總預算池：`total_budget = plan_total_raw + realized_profit`

## 核心演算法

### 總預算與資金分配
```
總預算 = Σ 預計投入 + 已實現損益
各類預算 = 總預算 × 水平比例
各股預算 = 各類預算 × 股票比重
```

### 已實現損益（平均成本法）
```
已實現損益 = Σ (賣出股數 × 成交價) - Σ (賣出股數 × 平均買入價)
平均買入價 = 該股總買入成本 / 該股總買入股數
```

### 選擇權歸屬
- 保證金（賣方）和買方成本都歸屬到「資金來源」欄位指定的股票
- **資金來源為空時**：按各股票剩餘預算比例自動分攤，可拆分到多檔股票

### 垂直配置堆疊長條圖（4 層）
```
已買入（藍）+ 賣方保證金（橘）+ 買方成本（紫）+ 待部署（灰）= 該股預算
```

### 執行率
```
執行率 = (持有成本 + 被壓住保證金) / 總預算 × 100%
```

## 慣例
- 所有有時間欄位的表格，按時間升序排序
- `st.metric` delta 格式：`f"{rate:+.1f}%"`（讓 Streamlit 自動處理顏色箭頭）
- 加密貨幣代碼：yfinance 需加 `-USD` 後綴
- 匯率：yfinance `USDTWD=X`，快取 5 分鐘，失敗 fallback `USD_RATE`
- DataFrame 操作前先檢查欄位是否存在
- 日期統一用 `pd.to_datetime().dt.date`
- Plotly hover 用 `customdata` + `hovertemplate`
- Treemap 用 `sort=False` 保持資料順序（保守→樂透→進攻）

## 交易輸入 UX
- 使用 `st.form` + `st.dataframe(on_select="rerun", selection_mode="single-row")`
- 點選下方紀錄可帶入上方表單編輯
- form key 包含 edit_idx 以重置預設值：`f"stock_form_{edit_idx}"`

## 地雷
- `init_session_state()` 的 DataFrame 不能用空的，要帶預設資料（否則 CSV 存不出來）
- Treemap 預設按 value 大小排序，必須加 `sort=False`
- Yahoo Finance 可能被限速，需三層 fallback（fast_info → history → info）
- 舊 CSV 可能有 `投資類型` 欄位，載入時需自動 drop（向後相容）
- sidebar 儲存按鈕需加唯一 `key`，成功後 `st.rerun()`
- 圖表 Y 軸需額外 25% 空間避免數字被截斷

## 依賴
| 套件 | 用途 | 必要 |
|-----|------|------|
| streamlit | Web 框架 | 是 |
| pandas | 資料處理 | 是 |
| plotly | 圖表 | 是 |
| yfinance | 股價/匯率 | 否（fallback 預設值） |
| fear_and_greed | CNN 恐懼貪婪指數 | 否（不顯示儀表板） |
