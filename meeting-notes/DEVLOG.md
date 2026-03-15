# 開發日誌

## 2026-03-15

### 新增 yt_notes.py — YouTube 字幕筆記工具

新增獨立腳本 `yt_notes.py`，一鍵完成：YouTube 字幕下載 → AI 整理筆記 → 上傳 Notion。

#### 功能
- 用 `yt-dlp` 下載字幕（優先手動字幕，fallback 自動產生）
- 解析 VTT 字幕為乾淨文字（去重複、去 HTML 標籤）
- Gemini（預設）或 Claude 整理成結構化繁體中文筆記
- 自動建立 Notion 頁面（含影片 bookmark、Tags、日期）
- 上傳成功後自動刪除本地暫存檔

#### 技術決策
- AI 預設用 Gemini（免費額度高），Claude API 需另外付費
- Notion 用 httpx 直接呼叫 REST API，與 sync-notion 同模式
- Markdown → Notion blocks 轉換：支援 heading、paragraph、list，自動切分超過 2000 字的 rich_text
- Notion API 每次最多 100 blocks，超過自動分批追加

#### 目標 Notion Database
- 「課堂筆記」（Christine's Main Page 下）
- 欄位：Name（標題）、Tags（multi_select）、Date（日期）

---

## 2026-02-24

### 專案起源

需要一個工具，能在上英文線上課程或開會時，即時擷取系統音訊、轉錄英文語音並翻譯成中文，會議結束後自動產生筆記。

---

### 初版架構

```
meeting_notes/
├── audio/          # 音訊擷取、VAD 語音偵測、緩衝
├── transcription/  # Whisper 語音辨識
├── translation/    # 翻譯 + AI 摘要
├── output/         # Session 管理、Markdown 輸出
├── utils/
└── cli.py          # Click CLI 介面
```

**CLI 指令**：`start` / `devices` / `config` / `list` / `export` / `summarize`

---

### 技術決策與踩坑

#### 1. 語音辨識：OpenAI API → faster-whisper（本地）

- 原本使用 OpenAI Whisper API，結果 API 配額不足（429 錯誤）
- 改用 `faster-whisper` 本地執行，完全免費
- 缺點：首次使用需下載模型（快取至 `~/.cache/huggingface/hub/`）

#### 2. 音訊取樣率不匹配

- BlackHole 虛擬裝置預設 48000 Hz
- Whisper 需要 16000 Hz
- 解法：在 `audio/buffer.py` 加入 `scipy.signal.resample_poly` 做重新取樣

#### 3. 翻譯：OpenAI API → Google Translate（免費）

- 同樣因 API 配額問題，改用 `deep-translator` 套件的 `GoogleTranslator`
- 完全免費，無需 API Key

#### 4. AI 摘要：Gemini 模型名稱

- 嘗試多個模型名稱才找到正確的：
  - `gemini-1.5-flash` → 404
  - `gemini-2.0-flash` → 404
  - `gemini-2.5-flash-preview-09-2025` → 404
  - `gemini-2.5-flash` → ✅ 正常

#### 5. 中文支援

- 新增 `--lang zh` 選項，讓中文課程也可直接辨識，不需翻譯

---

### macOS 音訊設定

#### BlackHole 多重輸出裝置

要同時聽到聲音又能錄製系統音訊，需要在「音訊 MIDI 設定」建立多重輸出裝置：

- 勾選 BlackHole 2ch + 喇叭/耳機
- 系統輸出切換至多重輸出裝置
- 缺點：多重輸出裝置無法調整音量（需從 App 內部控制）

#### Bluetooth 耳機限制

- Bluetooth 耳機使用 A2DP（高音質）或 HFP（通話）兩種模式
- 加入多重輸出裝置後，macOS 可能強制切成 HFP 導致音質下降
- 建議：錄音時改用有線耳機或直接用喇叭

---

## 2026-02-25

### YouTube 影片處理

需求：把 YouTube 上的課程影片下載後轉錄。

- 安裝 `yt-dlp`
- 私人影片需加 `--cookies-from-browser chrome`
- 建立 `transcribe_video.py`：分段處理長影片（避免記憶體溢位），每段預設 30 分鐘

### 目錄結構調整

原本需要在 `python/` 目錄執行，調整為：

```
python/
└── meeting-notes/     ← 在這裡執行
    ├── run.py         ← 入口檔
    ├── cli.py
    ├── config.py
    ├── audio/
    ├── transcription/
    ├── translation/
    └── output/
```

執行方式從 `python -m meeting_notes` 改為 `python run.py`。

調整過程：
1. 將 `meeting_notes/` 套件移入 `meeting-notes/` 目錄
2. 所有 relative import（`from .xxx`、`from ..xxx`）改為直接 import
3. 建立 `run.py` 作為入口

---

### AI 摘要優化

原始 prompt 只要求「3-5 個討論點」，產出內容過於簡短。

改為要求結構化輸出：
- **會議主題**
- **主要討論內容**（每點 2-4 句實質說明）
- **重要決定與結論**
- **重點摘錄**（數據、人名、技術名詞）
- **待辦事項**

---

### 已知限制

| 項目 | 限制 |
|------|------|
| 語言 | Whisper 的 `zh` 傾向輸出簡體字，需用 `opencc` 轉繁體 |
| 音量 | 多重輸出裝置無法用系統音量鍵控制 |
| 模型 | `small` 模型約 466 MB，首次使用需下載 |
| Windows | 需改用 VB-Cable，無法直接移植 |

---

### 套件清單

```
faster-whisper     # 本地語音辨識
deep-translator    # Google 翻譯（免費）
google-generativeai # Gemini AI 摘要
sounddevice        # 音訊擷取
webrtcvad          # 語音活動偵測
scipy              # 音訊重新取樣
click              # CLI 介面
yt-dlp             # YouTube 下載
ffmpeg             # 影片音訊處理
```

---

## 2026-03-01

### 轉錄品質分析與改進

用 YouTube CC 字幕作為 ground truth，對比程式即時錄音轉錄結果，發現嚴重品質問題。

#### 測試影片

"The most powerful AI Agent I've ever used in my life" (~12 分鐘)

#### 比對結果（改進前）

| 指標 | YouTube CC | 程式轉錄 |
|---|---|---|
| 總詞彙數 | 2,529 | 1,533（**丟失 39.4%**） |
| 碎片條目（≤3 詞） | 0 | 44（21.4%） |
| 開頭缺失 | 0 秒 | **42 秒** |
| 幻覺偽影 | 0 | 2 條嚴重重複 |

#### 問題分析與修復

**1. 前 42 秒完全缺失**

- 原因：Whisper 模型使用 lazy loading，錄音開始後才開始載入，音訊被丟棄
- 修復：`cli.py` — 在 `capture.start()` 前預載模型 `transcriber._load_model()`

**2. VAD 分段過於碎片化**

- 原因：`SILENCE_THRESHOLD = 30`（約 900ms）太短，正常句間停頓就被切斷
- 修復：
  - `config.py` — 靜音閾值從 30 改為 60 frames（約 1.8 秒）
  - `audio/vad.py` — `SpeechSegmenter` 新增 `min_segment_seconds=3.0`（太短的段落自動合併），`max_segment_seconds=30.0`（避免連續語音過長）

**3. 專有名詞辨識錯誤**

- 原因：base 模型詞彙量有限 + 碎片化缺乏上下文
- 辨識錯誤範例：agentic AI→a genetic AI, ChatGPT→Chad GBT, Claude Cowork→Claude Kohler
- 修復：
  - `transcription/whisper_local.py` — 加入 `initial_prompt` 注入領域詞彙（`DEFAULT_PROMPT_EN`）
  - `cli.py` — 新增 `--prompt` 選項讓使用者自訂提示詞

**4. Whisper 幻覺（口吃重複）**

- 現象：`"t- t- t- t- t-..."` 重複 27 次
- 修復：
  - `transcription/whisper_local.py` — 加入 `no_speech_threshold=0.6`, `log_prob_threshold=-1.0`, `condition_on_previous_text=False`
  - `utils/text_cleanup.py` — 新增後處理模組，用 regex 清理殘餘重複偽影

**5. 新增文字後處理模組**

- 新檔案 `utils/text_cleanup.py`
- `cleanup_text()` 流程：移除口吃偽影 → 套用常見錯誤修正映射表 → 清理空白
- `CORRECTIONS` 字典可持續擴充

#### 修改檔案清單

| 檔案 | 修改內容 |
|---|---|
| `cli.py` | 預載模型、整合 text_cleanup、新增 `--prompt` 選項 |
| `config.py` | `SILENCE_THRESHOLD` 30→60 |
| `audio/vad.py` | `SpeechSegmenter` 重構：最小/最大段落時長、碎片合併邏輯 |
| `transcription/whisper_local.py` | `initial_prompt`、防幻覺參數、`DEFAULT_PROMPT_EN` |
| `utils/text_cleanup.py` | 新增：口吃移除 + 常見錯誤修正 |

#### 預期改善效果

| 指標 | 改進前 | 預期改進後 |
|---|---|---|
| 內容覆蓋率 | 60.6% | 85-95% |
| 碎片率 | 21.4% | < 5% |
| 開頭缺失 | 42 秒 | 0 秒 |
| 幻覺偽影 | 2 條 | 0 條 |

#### 待驗證

- [ ] 實際錄音測試（需要有 BlackHole 的 macOS 環境）
- [ ] small 模型 vs base 模型在即時錄音場景的速度差異
- [ ] 靜音閾值 60 是否仍適用於快節奏的對話場景（可能需要可調）

---

## 2026-03-04

### transcribe_video.py 同步改進

將 3/1 對即時錄音 pipeline 的改進同步到影片轉錄腳本，使離線轉錄也能享有相同的品質提升。

#### 改動內容

| 項目 | 改進前 | 改進後 |
|------|--------|--------|
| 語言 | 寫死 `zh` | 新增 `--lang` 選項，預設 `en` |
| 提示詞 | 無 | 加入 `DEFAULT_PROMPT_EN` + `--prompt` 自訂 |
| 防幻覺 | 無 | `no_speech_threshold=0.6`, `log_prob_threshold=-1.0`, `condition_on_previous_text=False` |
| 後處理 | 無 | 整合 `utils/text_cleanup.py`（口吃移除 + 常見錯誤修正） |
| CLI 介面 | 位置參數 `sys.argv` | 改用 `argparse`，更直觀 |
| 輸出 | 原始文字直出 | 清理後輸出，空行自動跳過，顯示修正句數 |

#### 新的使用方式

```bash
# 英文影片（預設）
python transcribe_video.py ~/meeting-notes/video.webm

# 中文影片
python transcribe_video.py ~/meeting-notes/video.webm --lang zh

# 指定模型 + 自訂領域詞彙
python transcribe_video.py ~/meeting-notes/video.webm --model small --prompt "React,Next.js,Vercel"
```

#### 待驗證

- [ ] 用測試影片 (D_YzcH0VsGY) 比對改進前後的轉錄品質差異
- [ ] 確認 text_cleanup 在影片轉錄場景的修正效果

---

## 2026-03-04 (二) — 即時錄音實測結果

### 測試環境
- 影片：同一支 YouTube (D_YzcH0VsGY)，透過 Chrome 播放 + BlackHole 擷取
- 錄音時長：2 分 49 秒（僅測試前段）
- Session: 20260304_223812

### 量化比較（舊測試 0301 vs 新測試 0304）

| 指標 | 舊測試 (0301) | 新測試 (0304) | 變化 |
|------|-------------|-------------|------|
| 首段延遲 | 42 秒 | 41 秒 | -1 秒（幾乎無差） |
| 轉錄條目數 | 206 (12:39) | 18 (2:49) | — 時長不同 |
| 平均片段時長 | 2.0 秒 | 7.1 秒 | ✅ 大幅改善 (+5.1s) |
| 最短片段 | 0.5 秒 | 3.0 秒 | ✅ 無碎片（min_segment 生效） |
| 短片段 (<3s) | 169 個 (82%) | 0 個 (0%) | ✅ 碎片問題完全解決 |
| 平均每段字數 | 7.4 字 | 20.0 字 | ✅ +170% |
| ChatGPT 辨識 | ❌ chat GPT | ✅ ChatGPT | ✅ initial_prompt 生效 |
| agentic AI | ❌ a genetic AI | ✅ agentic AI | ✅ initial_prompt 生效 |
| Gemini | — (未出現) | ✅ Gemini | ✅ |
| 口吃/幻覺 | 2 個 | 0 個 | ✅ 防幻覺參數生效 |
| 詞彙覆蓋率 | 75.8% | 76.6% | 持平 (+0.8%) |

### 分析

**顯著改善的項目：**
1. **碎片化完全解決** — 舊測試有 82% 的片段 <3 秒，新測試 0%。`min_segment_seconds=3.0` + `SILENCE_THRESHOLD=60` 組合效果非常好
2. **專有名詞辨識** — `initial_prompt` 讓 Whisper 正確辨識了 ChatGPT、agentic AI、Gemini 等關鍵術語，之前全部辨識錯誤
3. **幻覺消除** — `no_speech_threshold` + `condition_on_previous_text=False` 清除了口吃重複問題

**仍需改善的項目：**
1. **首段延遲仍為 41 秒** — 模型預載應該已生效（不再有 42 秒的載入延遲），但影片前 40 秒本身音量較低或有背景音樂，VAD 可能未偵測到語音。需確認是模型載入問題還是 VAD 敏感度問題
2. **碎片化率百分比** — 雖然短片段為 0，但仍有 28% (5/18) 的條目不以句號結尾。這是因為 `max_segment_seconds=30s` 強制切段造成（00:01:38 有 25.2 秒的超長段），屬正常現象
3. **一個超長片段** — 00:01:38 產出 82 字、25.2 秒的段落。可考慮降低 `max_segment_seconds` 到 20 秒

### 結論
整體改進效果顯著，專有名詞和碎片化是最大的突破。首段延遲的 41 秒需要進一步調查是否為 VAD 敏感度問題。

### 下一步
- [x] 調查首段 41 秒延遲：是模型載入還是 VAD 門檻太高？ → 確認為操作延遲（見 0305 測試）
- [x] 考慮 max_segment_seconds 從 30s 降到 20s → 已改
- [x] 跑完整 12 分鐘測試，比較全片覆蓋率 → 見 0305 測試
- [ ] 測試 `--model small` 是否能進一步提升準確率

---

## 2026-03-05 — 完整 12 分鐘實測 (--debug 模式)

### 測試環境
- 同一支 YouTube 影片，完整播放 12 分鐘
- 加了 `--debug` flag，首段延遲降到 17 秒（確認之前 41 秒是操作時間差）
- `max_segment_seconds` 已從 30s 降到 20s
- Session: 20260305_082030

### 三次測試演進比較

| 指標 | 0301(舊) | 0304(中/2m49s) | 0305(新) | 趨勢 |
|------|---------|---------------|---------|------|
| 首段延遲 | 42 秒 | 41 秒 | 17 秒 | ✅ -25秒 |
| 轉錄條目 | 206 | 18 | 96 | — |
| 總字數 | 1533 | 360 | 2297 | ✅ +50% |
| 詞彙覆蓋率 | 67.2% | 31.1% | 89.5% | ✅ +22% |
| 平均片段時長 | 2.0s | 7.1s | 7.2s | ✅ |
| 短片段(<3s) | 169(82%) | 0(0%) | 0(0%) | ✅ |
| 長片段(>20s) | 0 | 1 | 3 | ⚠️ |
| 平均每段字數 | 7.4 | 20.0 | 23.9 | ✅ |
| ChatGPT | ❌ | ✅ | ✅ | ✅ |
| agentic AI | ❌ | ✅ | ✅ | ✅ |
| 口吃/幻覺 | 2 | 0 | 0 | ✅ |
| 轉錄錯誤 | — | — | ~13個 | ⚠️ |

### 已確認解決的問題
1. **首段延遲** — 17 秒 vs 之前 42 秒。之前的 41-42 秒確認為操作時間差（啟動程式→切換 Chrome→按播放），不是程式問題
2. **碎片化** — 短片段持續為 0%，確認修復穩定
3. **專有名詞** — ChatGPT, agentic AI, Gemini, Manus, Claude Co-Work, Dan Martel, Sam Godet 全部正確
4. **口吃幻覺** — 完整 12 分鐘無口吃問題
5. **覆蓋率大幅提升** — 67.2% → 89.5%

### 新發現的問題

#### 問題 1：新的轉錄錯誤（需擴充 CORRECTIONS）
完整影片出現了 0304 短測試中看不到的新錯誤：

| 錯誤 | 正確 | 原因 |
|------|------|------|
| `clot code` | Claude Code | 同音異寫 |
| `OpenClop` | OpenClaw | 同音異寫 |
| `9-set shift` | mindset shift | 同音異寫 |
| `Radio of Notion` | the CEO of Notion | 同音異寫 |
| `General Taston` | general tasks and | 同音異寫 |
| `build free` | build for you | 同音異寫 |
| `onslapped` | on Slack to | 同音異寫 |
| `maze ball` | amazing | 同音異寫 |
| `a master of nut` | a master of none | 同音異寫 |
| `rrrrrrrrrr` | (重複字母幻覺) | Whisper 幻覺 |

**已修正**: text_cleanup.py CORRECTIONS 表已擴充，並新增重複字母幻覺清除規則

#### 問題 2：長片段仍有 3 個 >20s
max_segment_seconds=20s 後仍有 3 個略超 20s 的段落（20.0s, 20.1s, 20.4s），這是因為 `_get_buffer_duration()` 在 `is_speech=True` 時才檢查，精度約 ±0.5s，可接受

#### 問題 3：時間戳有 15~22 秒的 gap
多處出現時間戳跳躍 15~22 秒，與長片段的 `audio_duration` 對應。這是因為長段落轉錄需要時間，timestamp 記錄的是「段落結束後送進 transcribe_queue 的時間」而非語音開始時間。屬結構性問題，不影響內容品質

#### 問題 4：`initial_prompt` 仍有未覆蓋的名詞
`Claude Code` 和 `OpenClaw` 不在 DEFAULT_PROMPT_EN 中，需加入

### 改善計劃

#### 立即可做
- [x] 擴充 CORRECTIONS：+10 個新映射
- [x] 新增重複字母幻覺清除 regex
- [ ] DEFAULT_PROMPT_EN 加入 `Claude Code`, `OpenClaw`, `Claude Cowork`

#### 下一階段
- [ ] 測試 `--model small`：base 模型的同音異寫問題可能因模型能力不足所致
- [ ] 考慮用 LLM 做後處理：CORRECTIONS 表只能處理已知錯誤，LLM 可以推理上下文修正未知錯誤
- [ ] timestamp 改為記錄語音開始時間（而非段落結束時間），更準確反映實際時序
