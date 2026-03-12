# sync-notion 開發紀錄

## 2026-03-07 — 專案建立與首次同步成功

### 動機

Neo 的課程同步原本使用 Claude Code MCP skill（`sync-notion`），透過 Google Calendar MCP + Notion MCP 逐步執行。因為 Claude 每次 tool call 之間都有思考開銷，每次同步需要 1–3 分鐘。決定改為獨立 Python 腳本，用 `asyncio` 平行查詢 API，預估 5–10 秒完成。

### 架構設計

分析了 `/Users/christine/self-study/.claude/skills/sync-cal/SKILL.md` 完整同步規則，以及各課程的個別規則檔（`sync_rule/` 目錄），設計出模組化架構：

- **資料驅動**：所有課程定義集中在 `config.py`，新增/修改課程只需改 config
- **雙資料源**：GCal 課程（6 種）透過 Google Calendar API 抓取，固定排課（4 種）依星期推算
- **平行查詢**：`asyncio.gather` 同時查 5 個 Google Calendar + 1 個 Notion 資料庫
- **比對引擎**：`differ.py` 比對所有來源與 Notion 現有紀錄，產生結構化的 `DiffResult`
- **互動確認**：支援全部確認、只新增、只更新、只補固定課等選項

### 實作過程

1. **建立所有模組**：`config.py`, `models.py`, `gcal_client.py`, `notion_client.py`, `scheduler.py`, `numbering.py`, `differ.py`, `display.py`, `index_updater.py`, `sync_cal.py`

2. **Google OAuth 設定**：
   - 在 Google Cloud Console 建立 OAuth 2.0 Desktop 憑證
   - 下載 `client_secret.json`
   - 遇到問題：`run_local_server()` 預設用 Safari 開瀏覽器，無法完成授權
   - 解決：設定 `open_browser=False`，手動在 Chrome 開啟授權 URL
   - 遇到問題：OAuth App 在測試模式，帳號沒加入測試用戶，出現 403 access_denied
   - 解決：到 OAuth consent screen 加入 `christinetai@gmail.com` 為測試用戶
   - 寫了獨立的 `do_auth.py` 方便除錯授權流程

3. **Notion Integration 設定**：
   - 建立 Notion Integration，取得 Token
   - 遇到問題：MCP data source ID (`202ecea7-a5c7-800a-bd51-000b1008a72e`) 和 Notion REST API database ID 不同
   - 解決：透過 Notion MCP search 找到正確的 database ID (`202ecea7a5c780499662cf347c379c57`)
   - 將「上課時間」資料庫分享給 Integration

4. **首次查詢成功**：
   - GCal: 8 筆事件
   - Notion: 18 筆紀錄
   - 固定排課: 12 筆預期
   - 正確辨識出 4 筆缺漏的固定排課

5. **修復 Notion 寫入 400 錯誤**：
   - 確認新增時 Notion API 回傳 400 Bad Request
   - 原因：`Task Category` 欄位是 `multi_select` 類型，程式誤用了 `select` 格式
   - 修復：`{"select": {"name": ...}}` → `{"multi_select": [{"name": ...}]}`
   - 同時修復讀取端 `_get_select` → `_get_multi_select`

### config.py 調整

使用者手動修改了部分設定：
- 補上各課程的 `cost` 值
- 籃球和 Charie英文 的 `numbering_resets` 改為 `True`（每期重置）

### 技術決策

| 決策 | 選擇 | 理由 |
|------|------|------|
| HTTP client (GCal) | aiohttp | 純 async，適合平行查多個 calendar |
| HTTP client (Notion) | httpx | 支援 async，API 更友善 |
| 終端輸出 | rich | 彩色表格、prompt 互動 |
| 認證管理 | google-auth-oauthlib | 官方 OAuth Desktop flow |
| 環境變數 | python-dotenv | 簡單 `.env` 檔管理 |
| 資料模型 | dataclass | 輕量，不需 ORM |

### 已知問題

- Google OAuth App 目前在測試模式（token 7 天過期），需要發佈或定期重新授權
- 編號邏輯中 `numbering_resets` 的期數計算尚未完整測試邊界情況

---

## 檔案清單

| 檔案 | 行數 | 用途 |
|------|------|------|
| sync_cal.py | 124 | CLI 入口、主流程編排 |
| config.py | 195 | 課程定義、常數 |
| models.py | 84 | 資料模型（5 個 dataclass + 1 個 Enum） |
| gcal_client.py | 151 | Google Calendar async 查詢 |
| notion_client.py | 214 | Notion REST API 操作 |
| scheduler.py | 44 | 固定排課日期推算 |
| numbering.py | 126 | 編號邏輯（連續/重置） |
| differ.py | 148 | 比對引擎 |
| display.py | 133 | Rich 終端輸出 + 互動確認 |
| index_updater.py | 34 | 更新 sync-rules-index.md |
| do_auth.py | 31 | 獨立 OAuth 授權腳本 |
| **合計** | **~1,284** | |
