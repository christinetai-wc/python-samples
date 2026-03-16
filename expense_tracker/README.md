# 住院費用分帳系統 - Google Apps Script 版本

使用 Google Apps Script 部署的 LINE Bot，24 小時運行，不需要本機電腦。

## 功能

### 記帳指令
| 指令 | 說明 |
|------|------|
| `/午餐 750` | 記帳，預設所有成員均分 |
| `/掛號費 150 大哥付` | 指定付款人 |
| `/看護費 2000 均分 大哥 二姐` | 指定參與者 |

### 轉帳指令
| 指令 | 說明 |
|------|------|
| `/轉帳 5000 大哥` | 我給大哥 5000 |
| `/轉帳 5000 二姐給大哥` | 二姐給大哥 5000 |
| `/轉帳 5000 二姐 大哥` | 同上（另一種格式） |
| `/轉帳紀錄` | 查看轉帳紀錄 |
| `/刪除轉帳` | 刪除最後一筆轉帳 |

### 查詢指令
| 指令 | 說明 |
|------|------|
| `/結算` | 查看每人應付金額和轉帳明細（扣除已轉帳） |
| `/帳目` | 查看最近 10 筆紀錄 |
| `/刪除` | 刪除最後一筆帳目 |

### 其他指令
| 指令 | 說明 |
|------|------|
| `/收據` | 2 分鐘內傳圖片進行 OCR |

| `/說明` | 顯示使用說明 |

### 結算邏輯
- 總開銷 ÷ 所有成員 = 每人應負擔
- 自動計算誰該轉帳給誰、多少錢
- 扣除已記錄的轉帳，顯示「還需轉帳」金額

## 優點

| 項目 | Flask 版 | GAS 版 |
|------|----------|--------|
| 需要電腦開機 | ✅ 需要 | ❌ 不需要 |
| 需要 ngrok | ✅ 需要 | ❌ 不需要 |
| 固定網址 | ❌ 每次不同 | ✅ 固定 |
| 圖片儲存 | Cloudinary | Google Drive |
| 費用 | 免費 | 免費 |

## 部署步驟

### 1. 建立 Google Apps Script 專案

1. 前往 [Google Apps Script](https://script.google.com/)
2. 點擊「新專案」
3. 將專案命名為「住院費用分帳」

### 2. 複製程式碼

將以下檔案的內容複製到 GAS 專案中：

1. **Code.gs** - 主程式（預設檔案，直接貼上）
2. **Parser.gs** - 點擊 `+` → `指令碼`，命名為 `Parser`
3. **SheetsManager.gs** - 點擊 `+` → `指令碼`，命名為 `SheetsManager`
4. **ImageHandler.gs** - 點擊 `+` → `指令碼`，命名為 `ImageHandler`

### 3. 設定 CONFIG

在 `Code.gs` 最上方的 `CONFIG` 區塊，填入你的設定：

```javascript
const CONFIG = {
  LINE_CHANNEL_ACCESS_TOKEN: '你的 LINE Channel Access Token',
  LINE_CHANNEL_SECRET: '你的 LINE Channel Secret',
  SPREADSHEET_ID: '18KE2dJHoyL6doRd2UEqb_4Xb6Er7Xvon9TSoQEDJw7w',  // 你現有的 Sheets ID
  GEMINI_API_KEY: '你的 Gemini API Key',
  IMAGE_FOLDER_ID: ''  // 可選，留空會自動建立資料夾
};
```

### 4. 部署為網頁應用程式

1. 點擊「部署」→「新增部署作業」
2. 類型選擇「網頁應用程式」
3. 設定：
   - 說明：`住院費用分帳 v1`
   - 執行身分：`我`
   - 存取權限：`所有人`
4. 點擊「部署」
5. **複製網頁應用程式網址**（格式：`https://script.google.com/macros/s/xxxxx/exec`）

### 5. 設定 LINE Bot Webhook

1. 前往 [LINE Developers Console](https://developers.line.biz/)
2. 選擇你的 Messaging API channel
3. 在「Messaging API」標籤頁
4. 將「Webhook URL」設為剛才複製的 GAS 網址
5. 開啟「Use webhook」
6. 點擊「Verify」測試連線

### 6. 授權

首次執行時，GAS 會要求授權：
1. 執行 `testWebhook` 函數（點擊執行按鈕）
2. 按照提示完成 Google 帳號授權
3. 允許存取 Google Sheets 和 Google Drive

## 檔案結構

```
gas/
├── Code.gs              # 主程式（設定 + Webhook 路由，只分派不處理）
├── LineApi.gs           # LINE API 共用（reply / push / download）
├── ExpenseTracker.gs    # 住院費用分帳 + 轉帳 + 收據 OCR
├── MedicineReminder.gs  # 吃藥提醒 + 排程 + 漏吃追蹤
├── FlashCard.gs         # 家長群組（自動記錄 LINE User ID）
├── StudyRecorder.gs     # 自學群組（記錄訊息到 Google Drive）
├── Parser.gs            # 文字解析（記帳）
├── SheetsManager.gs     # Google Sheets CRUD
├── ImageHandler.gs      # 圖片上傳 + Gemini OCR
└── README.md            # 本文件
```

## 測試函數

在 GAS 編輯器中可以執行以下測試函數：

| 函數 | 檔案 | 說明 |
|------|------|------|
| `testWebhook()` | Code.gs | 測試設定是否正確 |
| `testAuthorization()` | Code.gs | 測試所有 API 授權 |
| `testReplyAPI()` | Code.gs | 測試 LINE API 連線 |
| `testSummary()` | Code.gs | 測試結算功能（顯示轉帳明細） |
| `testParser()` | Parser.gs | 測試文字解析（顯示預設參與者） |
| `testSheets()` | SheetsManager.gs | 測試 Sheets 操作 |

## 注意事項

1. **執行配額**：GAS 有每日執行時間限制（免費帳號 90 分鐘/天），一般使用足夠

2. **回應時間**：GAS 可能比 Flask 稍慢，但通常在 2-3 秒內回應

3. **更新程式碼**：修改後需要重新部署
   - 點擊「部署」→「管理部署作業」
   - 點擊編輯按鈕（鉛筆圖示）
   - 版本選擇「新版本」
   - 點擊「部署」

4. **查看日誌**：
   - 點擊「執行」→「執行紀錄」查看執行歷史
   - 使用 `console.log()` 輸出除錯訊息

## 從 Flask 版遷移

如果你之前使用 Flask 版本：

1. **Google Sheets**：直接使用同一個 SPREADSHEET_ID，資料會保留
2. **LINE Bot**：只需更新 Webhook URL
3. **圖片**：新圖片會存到 Google Drive，舊的 Cloudinary 圖片仍可查看

## 常見問題

### Q: 出現「找不到 Spreadsheet」錯誤
A: 確認 SPREADSHEET_ID 正確，並且已與 GAS 使用相同的 Google 帳號

### Q: LINE Bot 沒有回應
A:
1. 檢查 Webhook URL 是否正確
2. 在 LINE Developers 點擊「Verify」測試
3. 查看 GAS 執行紀錄確認是否有收到請求

### Q: 圖片無法辨識
A: 確認 GEMINI_API_KEY 正確，可在 [Google AI Studio](https://aistudio.google.com/) 取得

### Q: 如何檢視儲存的圖片？
A: 前往 Google Drive，找到「ExpenseReceipts」資料夾
