# 住院費用分帳系統

透過 LINE Bot 記錄媽媽住院費用，支援文字和圖片輸入，自動計算分帳結果。

## 指令一覽

所有指令都用 `/` 開頭（群組中必須，私訊可省略）

### 記帳
| 指令 | 說明 |
|------|------|
| `/午餐 750` | 午餐 $750，預設均分 |
| `/掛號費 150 大哥付` | 掛號費 $150，大哥付的 |
| `/藥費 500 二姐出` | 藥費 $500，二姐出的 |
| `/看護費 2000 大哥 二姐 我` | 看護費 $2000，指定三人分攤 |

### 查詢
| 指令 | 功能 |
|------|------|
| `/結算` | 查看每人應付/應收金額 |
| `/帳目` | 查看最近 10 筆帳目 |
| `/刪除` | 刪除最後一筆（含圖片） |
| `/說明` | 顯示使用說明 |

### 收據圖片
| 指令 | 功能 |
|------|------|
| `/收據` | 啟動收據模式，2 分鐘內傳圖片 |
| `/我是大哥` | 設定你的名字 |

## 圖片記帳

**群組中**：
1. 先輸入 `/收據`
2. 2 分鐘內傳送收據照片（只處理第一張）
3. 系統辨識金額並回覆

**私訊**：直接傳送圖片即可

處理流程：
1. 上傳圖片到 Cloudinary（永久保存）
2. 嘗試 OCR 辨識金額（Cloud Vision → Gemini）
3. 辨識成功：回覆金額，請補充項目名稱
4. 辨識失敗：先記錄圖片（金額=0），請手動補充

## 資料儲存

- **Google Sheets**：帳目紀錄、成員清單
- **Cloudinary**：收據圖片（可透過 Dashboard 管理/刪除）

## 網頁介面

開啟 `http://localhost:8080` 可查看帳目明細和結算摘要。

## 本機啟動

```bash
cd /Users/christine/python/expense_tracker
source /Users/christine/venvs/myenv/bin/activate
python app.py
```

另開終端機啟動 ngrok：
```bash
ngrok http 8080
```

將 ngrok 網址設定到 LINE Bot Webhook URL。

## 環境變數 (.env)

```
LINE_CHANNEL_SECRET=xxx
LINE_CHANNEL_ACCESS_TOKEN=xxx
GOOGLE_SHEETS_ID=xxx
GOOGLE_GEMINI_API_KEY=xxx
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
CLOUDINARY_CLOUD_NAME=xxx
CLOUDINARY_API_KEY=xxx
CLOUDINARY_API_SECRET=xxx
```

## 檔案結構

```
expense_tracker/
├── app.py              # Flask 主程式 + LINE Bot
├── sheets.py           # Google Sheets 操作
├── parser.py           # 文字解析
├── ai_parser.py        # Gemini AI 解析
├── ocr.py              # 圖片金額辨識
├── image_storage.py    # Cloudinary 圖片上傳
├── templates/
│   └── index.html      # 網頁介面
├── credentials.json    # Google API 憑證
├── .env                # 環境變數
└── requirements.txt    # Python 套件
```
