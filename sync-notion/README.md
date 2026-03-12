# sync-notion

Neo 自學課程行事曆同步工具 — 自動比對 Google Calendar / 固定排課與 Notion「上課時間」資料庫，產生差異報告並一鍵同步。

## 為什麼需要這個工具？

原本使用 Claude Code MCP skill 逐步呼叫 Google Calendar MCP + Notion MCP 完成同步，每次需要 1–3 分鐘（Claude 思考開銷）。改用 Python 腳本 + asyncio 平行查詢，同步只需 5–10 秒。

## 功能

- 平行查詢多個 Google Calendar + Notion 資料庫
- 自動推算固定排課日期（無 GCal 的課程）
- 智慧編號：連續編號或每期重置
- 彩色差異報告（Rich 終端輸出）
- 互動式確認後批次新增/更新 Notion
- 更新 `sync-rules-index.md` 變更紀錄

## 安裝

```bash
cd /Users/christine/python/sync-notion
pip install -r requirements.txt
```

### 依賴套件

| 套件 | 用途 |
|------|------|
| google-auth | Google OAuth2 認證 |
| google-auth-oauthlib | OAuth Desktop flow |
| aiohttp | 非同步 GCal API 查詢 |
| httpx | 非同步 Notion API 操作 |
| rich | 終端彩色輸出 |
| python-dotenv | 環境變數管理 |

## 設定

### 1. Google Calendar OAuth

1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立專案
2. 啟用 Google Calendar API
3. 建立 OAuth 2.0 Desktop 憑證
4. 下載 JSON 存為 `client_secret.json`（放在專案根目錄）
5. 執行授權：

```bash
python sync_cal.py --auth
# 依提示在瀏覽器開啟 URL 完成授權
# 成功後產生 token.json
```

### 2. Notion Integration

1. 到 [notion.so/my-integrations](https://www.notion.so/my-integrations) 建立 Integration
2. 取得 Integration Token
3. 在 Notion 將「上課時間」資料庫分享給該 Integration
4. 建立 `.env` 檔：

```
NOTION_TOKEN=ntn_xxxxx
NOTION_DATABASE_ID=你的資料庫ID
SYNC_RULES_INDEX=/Users/christine/self-study/sync_rule/sync-rules-index.md
```

> **注意**：Notion 資料庫 ID 可從瀏覽器 URL 取得，格式為 32 位 hex（非 MCP data source ID）。

## 使用方式

```bash
# 同步未來 2 週（預設）
python sync_cal.py

# 只看今天
python sync_cal.py today

# 未來 14 天
python sync_cal.py 2weeks

# 首次 Google OAuth 授權
python sync_cal.py --auth
```

### 輸出範例

```
🔄 同步課程（未來2週） 03/08–03/22

查詢 Google Calendar + Notion...
  GCal: 8 筆事件, Notion: 18 筆紀錄
  固定排課: 12 筆預期

📋 syncCal 結果（未來2週）

✅ 已存在，略過：
  - Sophie數學 (3)       3/11 週二 14:00
  - 自然課 (5)           3/12 週三 09:00

➕ 待新增（確認後新增）：
  - 舞蹈 (7)             3/15 週六 10:00–12:00  Cost:850

❓ 無 GCal 課程缺漏，確認是否新增？
  - EMO                  3/11 週二 20:00–21:00  Cost:320

確認執行以上變更嗎？
  y = 全部確認 / n = 取消 / add = 只新增 / update = 只更新時間 / fixed = 只補固定課
```

## 課程定義

### GCal 課程（6 種）

從 Google Calendar 事件自動抓取，以事件名稱關鍵字篩選：

| 課程 | 篩選詞 | 編號方式 | 分類 |
|------|--------|---------|------|
| Sophie數學 | "Neo" | 每10堂重置 | 數學 |
| 自然課 | "自學團" | 每6堂重置 | 自然 |
| 舞蹈 | "Lulu" | 每10堂重置 | 運動 |
| 音樂創作 | "綾小路老師音樂" | 每6堂重置 | 音樂 |
| 兒童瑜珈 | "兒童瑜珈" | 每6堂重置 | 運動 |
| 程式設計課 | "承軒程式課" | 連續編號 | 科技 |

### 固定排課（4 種）

無 GCal 事件，依星期自動推算：

| 課程 | 星期 | 時間 | 編號方式 | 分類 |
|------|------|------|---------|------|
| EMO | 二、四 | 20:00 | 無 | 英文 |
| 麗芳自學課 | 三、五 | 09:00 | 無 | 社會 |
| 籃球 | 五 | 19:40 | 每10堂重置 | 運動 |
| Charie英文 | 六 | 15:00 | 每24堂重置 | 英文 |

## Notion 欄位對應

| 欄位 | 類型 | 範例 |
|------|------|------|
| Task Name | title | "自然課 (5)" |
| Task Category | multi_select | "自然" |
| Start time | date (datetime) | "2026-03-11T14:00:00+08:00" |
| hours | number | 2 |
| Cost | number（可選） | 1400 |
| Task Description | rich_text（可選） | "第2期 共六堂 $8400" |
| Done | checkbox | false |

## 比對邏輯

### GCal 課程

| 狀態 | 條件 | 動作 |
|------|------|------|
| ✅ 已存在 | 同 prefix + 同日期 | 略過 |
| ⚠️ 時間變動 | 同 prefix + 同日但 start time 不同 | 更新 Notion |
| ➕ 待新增 | GCal 有但 Notion 無 | 新增 Notion |
| ❓ 已取消 | Notion 有 (Done=❌) 但 GCal 無 | 提示確認 |

### 固定排課

| 狀態 | 條件 | 動作 |
|------|------|------|
| ✅ 已存在 | 同 prefix + 同日期 | 略過 |
| ❓ 缺漏 | 推算有但 Notion 無 | 提示確認新增 |

## 專案結構

```
sync-notion/
├── sync_cal.py          # CLI 入口 + 主流程
├── config.py            # 課程定義（資料驅動）
├── models.py            # 資料模型（dataclass）
├── gcal_client.py       # Google Calendar API（async）
├── notion_client.py     # Notion API（查詢 + 新增/更新）
├── scheduler.py         # 固定排課日期推算
├── numbering.py         # 編號邏輯（連續/每期重置）
├── differ.py            # 比對邏輯（產生差異報告）
├── display.py           # 終端彩色輸出 + 互動確認
├── index_updater.py     # 更新 sync-rules-index.md
├── do_auth.py           # 獨立 OAuth 授權腳本
├── requirements.txt     # 依賴套件
├── .env                 # 環境變數（gitignored）
├── .gitignore
├── README.md
└── DEVLOG.md            # 開發紀錄
```

## 注意事項

- `client_secret.json` 和 `token.json` 已加入 `.gitignore`，不會上傳
- `.env` 包含 Notion Token，也已 gitignore
- Google OAuth App 目前在測試模式，只有加入測試用戶的帳號可授權
- Token 過期時程式會自動 refresh，不需重新授權
