# Meeting Notes — 軟體規格書

## 概述

即時擷取 macOS 系統音訊，將英文語音轉錄為文字並翻譯成中文，會議結束後輸出 Markdown 筆記。

## 資料流

```
系統音訊 (BlackHole 2ch, 48kHz)
  ↓
AudioCapture (sounddevice)
  ↓
AudioBuffer (scipy resample 48kHz→16kHz)
  ↓
SpeechSegmenter (webrtcvad)
  ├─ min_segment: 3.0s（碎片合併）
  ├─ max_segment: 20.0s（強制切段）
  └─ silence_threshold: 60 frames (~1.8s)
  ↓
LocalWhisperTranscriber (faster-whisper)
  ├─ initial_prompt: 領域詞彙注入
  ├─ no_speech_threshold: 0.6
  ├─ log_prob_threshold: -1.0
  └─ condition_on_previous_text: False
  ↓
text_cleanup (utils/text_cleanup.py)
  ├─ 口吃偽影移除 (regex)
  ├─ 重複字母幻覺清除
  └─ CORRECTIONS 常見錯誤修正
  ↓
FreeTranslator (deep-translator GoogleTranslator)
  ↓
Gemini AI 摘要
  ↓
MeetingSession → MarkdownExporter
  ↓
~/meeting-notes/{session_id}.json + .md
```

## 資料模型

### MeetingSession

| 欄位 | 型別 | 說明 |
|------|------|------|
| session_id | str | 格式 `YYYYMMDD_HHMMSS` |
| start_time | datetime | 錄音開始時間 |
| end_time | datetime | 錄音結束時間 |
| duration | str | 時長 `HH:MM:SS` |
| entries | list[Entry] | 轉錄條目 |
| summary | str | AI 摘要 |

### Entry

| 欄位 | 型別 | 說明 |
|------|------|------|
| original | str | 原文（英文或中文） |
| translated | str | 翻譯（中文，可為空） |
| timestamp | str | 時間戳 |
| audio_duration | float | 音訊段落時長（秒） |

## 執行緒架構

```
主執行緒: AudioCapture → SpeechSegmenter → transcribe_queue
轉錄執行緒: transcribe_queue → Whisper → text_cleanup → result_queue
翻譯執行緒: result_queue → Translator → Session.add_entry → 顯示
```

三個執行緒透過 `queue.Queue` 解耦，主執行緒不阻塞。

## 摘要 Prompt 結構

要求 Gemini 產出：
1. 會議主題
2. 主要討論內容（每點 2-4 句實質說明）
3. 重要決定與結論
4. 重點摘錄（數據、人名、技術名詞）
5. 待辦事項

## 影片轉錄（transcribe_video.py）

獨立腳本，支援長影片分段處理（預設每段 1800 秒 / 30 分鐘），避免記憶體溢位。

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `--lang` | en | 語言 |
| `--model` | base | Whisper 模型 |
| `--prompt` | DEFAULT_PROMPT_EN | 領域詞彙 |
| `--segment` | 1800 | 分段時長（秒） |

## 邊界處理

- 音訊段落 < 0.5 秒：丟棄不處理
- 超過 max_segment_seconds：強制切段（精度 ±0.5s）
- 翻譯失敗：translated 欄位留空，不中斷流程
- 摘要失敗：顯示錯誤訊息，不影響筆記輸出
- 模型載入：在錄音前預載，避免開頭音訊丟失
