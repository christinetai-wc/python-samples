# 會議英翻中筆記工具

即時擷取系統音訊，將英文語音轉錄為文字並翻譯成中文，會議結束後輸出 Markdown 筆記。

## 功能特色

- 擷取 macOS 系統音訊（Zoom、Google Meet、YouTube 等）
- 本地 Whisper 語音辨識（免費，無需 API）
- Google 翻譯英翻中（免費）
- Gemini AI 自動產生會議摘要
- YouTube 字幕自動抓取、整理筆記、上傳 Notion
- 輸出 Markdown 格式筆記

## 前置需求

### 1. 安裝 BlackHole 虛擬音訊裝置

```bash
brew install blackhole-2ch
```

### 2. 設定多重輸出裝置

1. 開啟「音訊 MIDI 設定」（在 Spotlight 搜尋）
2. 左下角 + → 建立多重輸出裝置
3. 勾選「BlackHole 2ch」和你的喇叭/耳機
4. 系統設定 → 聲音 → 輸出 → 選擇「多重輸出裝置」

### 3. 設定環境變數

複製 `.env.example` 為 `.env`，填入 Gemini API Key（用於產生摘要）：

```bash
cp .env.example .env
```

編輯 `.env`：
```
GEMINI_API_KEY=your_api_key_here
```

## 使用方式

所有指令都在 `meeting-notes` 目錄下執行：

```bash
cd /Users/christine/python/meeting-notes
```

### 列出音訊裝置

```bash
python run.py devices
```

### 開始錄音

```bash
# 推薦指令（英文轉中文，small 模型準確度較佳）
python run.py start -m small

# 快速測試（速度快，準確度較低）
python run.py start

# 中文內容（不翻譯，直接轉錄）
python run.py start -l zh -m small

# 只轉錄不翻譯
python run.py start -m small --no-translate
```

按 `Ctrl+C` 結束錄音，自動轉錄、翻譯並用 Gemini 產生摘要，輸出 Markdown 筆記。

### 列出會議記錄

```bash
python run.py list
```

### 重新產生摘要

```bash
python run.py summarize -s SESSION_ID
```

### 匯出 Markdown

```bash
python run.py export -s SESSION_ID
```

### 顯示設定

```bash
python run.py config
```

## Whisper 模型大小

| 模型 | 速度 | 準確度 | 建議用途 |
|------|------|--------|----------|
| tiny | 最快 | 較低 | 測試用 |
| base | 快 | 中等 | 一般使用（預設） |
| small | 中等 | 較高 | 推薦，準確度與速度平衡 |
| medium | 慢 | 高 | 需要高準確度 |

## 輸出範例

筆記儲存於 `~/meeting-notes/`，格式如下：

```markdown
# 會議筆記

**日期**: 2026-02-24
**時長**: 01:23:45
**Session ID**: 20260224_143022

---

## 摘要

本次會議討論了...

---

## 逐字稿

### [00:00:15]
**EN**: Good morning everyone.
**中**: 大家早安。

### [00:00:32]
**EN**: Let's start with the agenda.
**中**: 讓我們開始今天的議程。
```

## 轉錄影片檔案

使用 `transcribe_video.py` 可將影片/音訊檔案轉錄為逐字稿（中文）。支援長影片分段處理，避免記憶體溢位。

### 前置需求

```bash
brew install ffmpeg
```

### 基本用法

```bash
python transcribe_video.py <影片路徑>
```

輸出檔案會自動存為 `影片名稱_transcript.txt`。

### 完整參數

```bash
python transcribe_video.py <影片路徑> [輸出路徑] [模型大小] [分段時長(秒)]
```

| 參數 | 說明 | 預設值 |
|------|------|--------|
| 影片路徑 | 必填，影片或音訊檔案路徑 | - |
| 輸出路徑 | 逐字稿輸出路徑 | 影片同目錄 `_transcript.txt` |
| 模型大小 | tiny / base / small / medium | base |
| 分段時長 | 每段多少秒 | 1800（30 分鐘） |

### 範例

```bash
# 基本轉錄
python transcribe_video.py ~/Videos/lecture.mp4

# 指定輸出路徑和模型
python transcribe_video.py ~/Videos/lecture.mp4 ~/Documents/lecture.txt small

# 長影片用 15 分鐘分段
python transcribe_video.py ~/Videos/long_video.webm output.txt base 900
```

### 輸出格式

```
# 轉錄逐字稿
# 來源：lecture.mp4
# 語言：zh（信心：99%）

[00:00] 大家好，歡迎來到今天的課程
[00:05] 我們今天要討論的主題是...
[01:23] 首先讓我們看一下這個範例
```

## 處理 YouTube 影片

使用 `yt-dlp` 下載後再轉錄：

```bash
# 安裝 yt-dlp
brew install yt-dlp

# 只下載音訊（推薦，檔案較小）
yt-dlp -x --audio-format mp3 -o "audio.%(ext)s" "影片網址"

# 下載影片（保留原始格式）
yt-dlp -o "video.%(ext)s" "影片網址"

# 如果是私人影片，需要 cookie
yt-dlp --cookies-from-browser chrome -x --audio-format mp3 -o "audio.%(ext)s" "影片網址"

# 轉錄
python transcribe_video.py audio.mp3
```

### yt-dlp 常用參數

| 參數 | 說明 |
|------|------|
| `-x` | 只擷取音訊 |
| `--audio-format mp3` | 轉換為 mp3 格式 |
| `--cookies-from-browser chrome` | 使用 Chrome 的 cookie（私人影片用） |
| `-o "名稱.%(ext)s"` | 指定輸出檔名 |

## YouTube / Podcast → 筆記 → Notion

使用 `notes.py` 自動從 YouTube 或 Podcast 產生繁體中文筆記，上傳到 Notion。
自動判斷來源：YouTube 優先抓字幕（無字幕則 Whisper 轉錄），Podcast 直接 Whisper 轉錄。

### 前置需求

在 `.env` 中設定：
```
GEMINI_API_KEY=your_key        # AI 整理筆記
NOTION_TOKEN=secret_xxx        # Notion API
NOTION_YT_DATABASE_ID=xxx      # 目標 Database ID
```

### 使用方式

```bash
# YouTube（自動抓字幕）
python notes.py "YouTube網址"

# Podcast（自動下載音訊 + Whisper 轉錄）
python notes.py "Apple Podcasts網址" -t Podcast

# 指定語言
python notes.py "網址" --lang zh

# 指定 Notion Tag
python notes.py "網址" -t 英文

# 只產生本地筆記，不上傳
python notes.py "網址" --no-notion

# 用 small 模型提升轉錄準確度
python notes.py "網址" -m small
```
