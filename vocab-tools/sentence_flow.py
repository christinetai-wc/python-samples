import customtkinter as ctk
import csv
import os
import time
import threading
import json
import whisper
from gtts import gTTS
import pygame
import speech_recognition as sr
from pathlib import Path

# 初始化主題
ctk.set_appearance_mode("dark")  # 模式: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # 主題: "blue" (standard), "green", "dark-blue"

BASE_DIR = Path(__file__).resolve().parent

# 檔案路徑設定
CSV_FILE = BASE_DIR / 'sentence.csv'
PROGRESS_FILE = BASE_DIR / 'sentence_progress.json'
TEMP_AUDIO = BASE_DIR / 'temp_voice.mp3'
WHISPER_WAV = 'temp_whisper.wav'

class WhisperEnglishApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("英語句型練習器 - AI Whisper 強大版 (CTk)")
        self.geometry("800x750")
        
        # 音訊初始化
        pygame.mixer.init()
        self.recognizer = sr.Recognizer()
        
        # 1. 載入 Whisper 模型 (非同步)
        self.model = None
        self.status_text = ctk.StringVar(value="正在初始化 AI 模型...")
        threading.Thread(target=self.load_whisper_model, daemon=True).start()

        # 2. 載入資料與進度
        self.all_data = self.load_and_expand_csv()
        self.categories = list(self.all_data.keys())
        self.progress = self.load_progress()
        self.current_cat_idx = self.progress.get("current_cat_idx", 0)

        # 狀態控制
        self.is_processing = False 
        self.has_played_voice = False
        self.is_ready_for_next = False

        self.setup_ui()
        self.load_question()

        # 按鍵綁定
        self.bind_all('<Return>', self.handle_enter)
        self.bind_all('<space>', self.handle_space)
        self.bind_all('<Escape>', self.exit_program)
        self.bind_all('<Left>', self.prev_category)
        self.bind_all('<Right>', self.next_category)

    def load_whisper_model(self):
        """非同步載入 Whisper 模型"""
        try:
            # 建議使用 tiny 或 base 以提升速度
            self.model = whisper.load_model("base") 
            self.status_text.set("AI 模型載入完畢，請開始練習")
        except Exception as e:
            self.status_text.set(f"模型載入失敗: {e}")

    def setup_ui(self):
        # 頂部資訊容器
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(20, 5), fill="x", padx=60)

        # 類別進度文字
        self.info_label = ctk.CTkLabel(self.header_frame, text="", font=("Arial", 14), text_color="#BDC3C7")
        self.info_label.pack()

        # 進度條 (Progress Bar)
        self.progress_bar = ctk.CTkProgressBar(self.header_frame, width=400, height=10)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0) # 初始為 0

        self.cat_label = ctk.CTkLabel(self, text="", font=("微軟正黑體", 24, "bold"), text_color="#F1C40F")
        self.cat_label.pack()

        # 句子顯示區
        self.sentence_label = ctk.CTkLabel(self, text="", font=("Arial", 32, "bold"), wraplength=700)
        self.sentence_label.pack(pady=40)

        # 辨識稿外框
        self.transcript_frame = ctk.CTkFrame(self, corner_radius=10)
        self.transcript_frame.pack(pady=10, fill="x", padx=60)

        self.transcript_title = ctk.CTkLabel(self.transcript_frame, text="Whisper AI 辨識結果", font=("微軟正黑體", 12), text_color="#1ABC9C")
        self.transcript_title.pack(pady=(5, 0))

        self.transcript_label = ctk.CTkLabel(self.transcript_frame, text="等待錄音...", font=("Arial", 22, "italic"), text_color="#ECF0F1", wraplength=600)
        self.transcript_label.pack(pady=(5, 20))

        # 提示字
        self.target_label = ctk.CTkLabel(self, text="", font=("Arial", 18), text_color="#E67E22")
        self.target_label.pack(pady=5)

        # 輸入框
        self.entry = ctk.CTkEntry(self, font=("Arial", 28), width=300, height=50, placeholder_text="在此輸入拼寫", justify='center')
        self.entry.pack(pady=20)
        
        # 狀態列
        self.status_bar = ctk.CTkLabel(self, textvariable=self.status_text, font=("微軟正黑體", 14), text_color="#ECF0F1")
        self.status_bar.pack(side="bottom", pady=20)

    def handle_enter(self, event):
        if self.is_ready_for_next:
            self.go_next_question()
            return "break"
        if self.is_processing or self.model is None:
            return "break"
        
        user_input = self.entry.get().strip().lower()
        if user_input == self.target_word.lower():
            self.is_processing = True
            self.entry.configure(state="disabled")
            self.sentence_label.configure(text=self.full_sentence, text_color="#F1C40F")
            
            if not self.has_played_voice:
                threading.Thread(target=self.voice_flow, daemon=True).start()
            else:
                threading.Thread(target=self.recognize_flow, daemon=True).start()
        else:
            self.status_text.set("❌ 拼錯了，請再試一次")
            self.entry.delete(0, 'end')
        return "break"

    def handle_space(self, event):
        if self.has_played_voice and not self.is_processing:
            self.is_ready_for_next = False
            threading.Thread(target=self.recognize_flow, daemon=True).start()
            return "break"
        return None

    def voice_flow(self):
        self.status_text.set("🔊 播放發音中...")
        try:
            tts = gTTS(text=self.full_sentence, lang='en')
            tts.save(TEMP_AUDIO)
            pygame.mixer.music.load(str(TEMP_AUDIO))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy(): time.sleep(0.1)
            pygame.mixer.music.unload()
            self.has_played_voice = True
            self.recognize_flow()
        except Exception as e:
            print(f"TTS 錯誤: {e}")
            self.is_processing = False

    def recognize_flow(self):
        self.is_processing = True
        self.status_text.set("🎤 請朗讀整句...")
        self.transcript_label.configure(text="聽取中...", text_color="#F1C40F")
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
            
            with open(WHISPER_WAV, "wb") as f:
                f.write(audio.get_wav_data())

            self.status_text.set("⌛ Whisper 深度分析中...")
            result = self.model.transcribe(WHISPER_WAV, language="en")
            text = result["text"].strip()
            
            self.transcript_label.configure(text=f"\"{text}\"", text_color="#ECF0F1")
            
            # 簡單清理辨識文字並比對
            clean_text = text.lower().replace('.', '').replace(',', '').replace('!', '').replace('?', '')
            if self.target_word.lower() in clean_text:
                self.status_text.set("✅ 辨識成功！[Enter] 下一題")
                self.is_ready_for_next = True
            else:
                self.status_text.set("🤔 沒聽清楚關鍵字，按 Space 重錄")
            
        except Exception as e:
            self.transcript_label.configure(text=f"辨識出錯", text_color="#E74C3C")
            self.status_text.set("🔇 錄音或辨識失敗")
        
        self.is_processing = False

    def load_question(self):
        if not self.categories:
            self.status_text.set("無資料可顯示")
            return

        cat_name = self.categories[self.current_cat_idx]
        self.current_q_idx = self.progress["scores"].get(cat_name, 0)
        questions = self.all_data.get(cat_name, [])
        
        if self.current_q_idx >= len(questions): self.current_q_idx = 0
        
        q = questions[self.current_q_idx]
        self.target_word = q['target']
        self.full_sentence = q['template'].replace("___", self.target_word)

        # 更新進度資訊
        total_q = len(questions)
        current_display_idx = self.current_q_idx + 1
        self.info_label.configure(text=f"本類進度：{current_display_idx} / {total_q}")
        
        # 更新進度條百分比 (0.0 ~ 1.0)
        progress_pct = current_display_idx / total_q
        self.progress_bar.set(progress_pct)

        self.cat_label.configure(text=f"【 {cat_name} 】")
        self.sentence_label.configure(text=q['template'], text_color="#FFFFFF")
        self.transcript_label.configure(text="等待錄音...", text_color="#7F8C8D")
        self.target_label.configure(text=f"請拼寫： {self.target_word}")
        
        self.entry.configure(state="normal")
        self.entry.delete(0, 'end')
        self.entry.focus_set()
        self.status_text.set("請拼字後按 Enter")
        
        self.is_processing = False
        self.has_played_voice = False
        self.is_ready_for_next = False

    def go_next_question(self):
        cat_name = self.categories[self.current_cat_idx]
        self.current_q_idx += 1
        self.progress["scores"][cat_name] = self.current_q_idx
        self.save_progress()
        self.load_question()

    def load_and_expand_csv(self):
        expanded = {}
        if not os.path.exists(CSV_FILE): return {"尚未匯入 CSV": []}
        try:
            with open(CSV_FILE, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cat = row['category']
                    opts = row['options'].split('|')
                    if cat not in expanded: expanded[cat] = []
                    for o in opts: expanded[cat].append({"template": row['template'], "target": o.strip()})
        except Exception as e:
            print(f"CSV 讀取錯誤: {e}")
        return expanded

    def load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
            except: pass
        return {"current_cat_idx": 0, "scores": {}}

    def save_progress(self):
        self.progress["current_cat_idx"] = self.current_cat_idx
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f: json.dump(self.progress, f, ensure_ascii=False)

    def next_category(self, event=None):
        if not self.is_processing and self.categories:
            self.current_cat_idx = (self.current_cat_idx + 1) % len(self.categories)
            self.load_question()

    def prev_category(self, event=None):
        if not self.is_processing and self.categories:
            self.current_cat_idx = (self.current_cat_idx - 1) % len(self.categories)
            self.load_question()

    def exit_program(self, event=None):
        self.save_progress()
        pygame.mixer.quit()
        if os.path.exists(WHISPER_WAV):
            try: os.remove(WHISPER_WAV)
            except: pass
        if os.path.exists(TEMP_AUDIO):
            try: os.remove(TEMP_AUDIO)
            except: pass
        self.destroy()

if __name__ == "__main__":
    app = WhisperEnglishApp()
    app.mainloop()
