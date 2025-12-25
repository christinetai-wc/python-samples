# Vocab Tools

本目錄包含與單字及句子練習相關的小工具，方便英語學習者管理單字與句子，並進行練習與測驗。

## 工具列表

### 1. `vocab_input.py`
- 功能：輸入單字，一行一個單字，程式透過 Gemini 補上中文意思與例句，生成 `vocab_list.csv`。
- 使用方式：
```bash
python vocab_input.py
### 2. vocab_flashcard.py

功能：從 vocab_list.csv 讀取單字，列出分類、科目及上課日期，可切換練習模式（有語音）與考試模式。

使用方式：

python vocab_flashcard.py

### 3. sentence_flow.py

功能：從 sentence.csv 讀取句子，提供拼字填空練習，完成後朗讀句子確認發音。

使用方式：

python sentence_flow.py

檔案格式
vocab_list.csv

欄位：單字、中文意思、例句、分類、科目、上課日期

sentence.csv

欄位：category, template, options

範例：

category,template,options
基礎描述句,This ___ is very important.,test|rule|decision|habit|lesson

注意事項

執行工具前，請確保有對應的 CSV 檔案。
