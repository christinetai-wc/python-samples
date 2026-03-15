# Meeting Notes — 操作指引

## 開發指令

```bash
# 列出音訊裝置
python run.py devices

# 開始錄音（英文轉中文）
python run.py start -m small

# 中文內容（不翻譯）
python run.py start -l zh -m small

# 只轉錄不翻譯
python run.py start -m small --no-translate

# 列出會議記錄
python run.py list

# 重新產生摘要
python run.py summarize -s SESSION_ID

# 匯出 Markdown
python run.py export -s SESSION_ID

# 轉錄影片檔案
python transcribe_video.py <影片路徑> --model small --lang en

# YouTube / Podcast → 筆記 → Notion（自動判斷來源）
python notes.py "YouTube網址"                      # YouTube（字幕優先）
python notes.py "Apple Podcasts網址" -t Podcast    # Podcast（Whisper 轉錄）
python notes.py "網址" -t 英文                     # 指定 Tag
python notes.py "網址" --no-notion                  # 只存本地
python notes.py "網址" --ai claude                  # 用 Claude 整理
python notes.py "網址" -m small                     # 用 small 模型轉錄
```

## 關鍵路徑與常數

| 項目 | 值 |
|------|---|
| 入口 | `run.py` → `cli.py` |
| 設定 | `config.py` — `Config` 類別 |
| 環境變數 | `.env`（Gemini API Key、Notion Token） |
| 輸出目錄 | `~/meeting-notes/` |
| Whisper 模型快取 | `~/.cache/huggingface/hub/` |
| 音訊裝置 | BlackHole 2ch（需搭配多重輸出裝置） |
| 靜音閾值 | `SILENCE_THRESHOLD = 60`（約 1.8 秒） |
| 最小段落 | `min_segment_seconds = 3.0` |
| 最大段落 | `max_segment_seconds = 20.0` |

## 模組結構

```
meeting-notes/
├── run.py                  # 入口
├── cli.py                  # Click CLI（start/devices/config/list/export/summarize）
├── config.py               # 設定管理
├── transcribe_video.py     # 影片轉錄腳本（獨立）
├── notes.py                # YouTube/Podcast → 筆記 → Notion（合併版）
├── audio/
│   ├── capture.py          # 音訊擷取（sounddevice + BlackHole）
│   ├── vad.py              # VAD 語音偵測 + SpeechSegmenter
│   └── buffer.py           # 音訊緩衝 + 重新取樣（48kHz→16kHz）
├── transcription/
│   ├── whisper_local.py    # 本地 faster-whisper（主力）
│   └── whisper_api.py      # OpenAI API（已棄用）
├── translation/
│   ├── google_translator.py # Google 翻譯 + Gemini 摘要
│   └── gpt_translator.py   # GPT 翻譯（已棄用）
├── output/
│   ├── session.py          # MeetingSession 管理
│   └── markdown.py         # Markdown 匯出
└── utils/
    ├── text_cleanup.py     # 後處理：口吃移除 + CORRECTIONS 修正
    └── exceptions.py       # 自訂例外
```

## 慣例

- CLI 用 `click` 套件
- 語音辨識用 `faster-whisper`（本地免費），不用 OpenAI API
- 翻譯用 `deep-translator` 的 GoogleTranslator（免費）
- 摘要用 Gemini API（需 `.env` 設定 `GEMINI_API_KEY`）
- `notes.py` 預設用 Gemini，可切換 Claude（需 `ANTHROPIC_API_KEY`）
- `notes.py` 自動判斷 YouTube/Podcast，YouTube 預設 lang=en，Podcast 預設 lang=zh
- Notion 上傳用 httpx 直接呼叫 REST API（同 sync-notion 模式）
- 轉錄流程：音訊擷取 → VAD 分段 → Whisper 辨識 → text_cleanup 後處理 → 翻譯 → 摘要

## 地雷

- Whisper 模型需預載（`transcriber._load_model()`），否則錄音開頭會丟失
- BlackHole 多重輸出裝置無法用系統音量鍵控制
- Bluetooth 耳機可能被切成 HFP 模式導致音質下降
- `condition_on_previous_text=False` 防止幻覺，不要改回 True
- `initial_prompt` 注入領域詞彙可大幅改善專有名詞辨識
- `zh` 模式 Whisper 傾向輸出簡體字，需搭配 opencc 轉繁體
