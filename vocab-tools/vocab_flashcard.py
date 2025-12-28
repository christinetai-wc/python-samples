import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import csv
import os
import threading
import tempfile
import random 
import time
from pathlib import Path

# 初始化主題與外觀
ctk.set_appearance_mode("System")  # 系統模式: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # 主題顏色: "blue" (standard), "green", "dark-blue"

BASE_DIR = Path(__file__).resolve().parent
ENABLE_SPEECH = 1

class FlashcardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("單字卡練習 (Vocabulary Flashcards)")
        self.root.geometry("900x700")
        
        # --- 初始化 pygame mixer (全域只做一次) ---
        try:
            import pygame
            pygame.mixer.init()
        except Exception as e:
            print(f"[系統提示] 無法初始化音效裝置: {e}")

        # 按下 ESC 鍵結束程式
        self.root.bind('<Escape>', lambda event: root.destroy())
        
        # 儲存所有單字數據
        self.all_data, self.dates_by_course = self.load_vocab_data()
        
        # 狀態變數
        self.current_vocab_list = []
        self.current_index = 0
        self.is_front_side = True
        self.is_test_mode = False
        self.menu_mode = 'practice' # 'practice' or 'test'
        self.test_results = []    

        # 創建主容器
        self.main_frame = ctk.CTkFrame(root, corner_radius=15)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 啟動顯示選單
        self.show_menu()
        
        # 防止重複觸發
        self.last_key_time = 0
        self.key_debounce_delay = 0.2

    # -------------------------------------------------------------
    # TTS 語音朗讀功能 (優化執行緒與 mixer 存取)
    # -------------------------------------------------------------
    def speak_text(self, text, lang='en'):
        if ENABLE_SPEECH != 1 or not text:
            return

        def play_audio():
            temp_filename = None
            try:
                from gtts import gTTS
                import pygame
                
                # 確保 mixer 已初始化
                if not pygame.mixer.get_init():
                    pygame.mixer.init()

                tts = gTTS(text=text, lang=lang)
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as fp:
                    temp_filename = fp.name
                    tts.save(temp_filename)

                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                    
                pygame.mixer.music.load(temp_filename)
                pygame.mixer.music.play()
                
                start_wait = time.time()
                while pygame.mixer.music.get_busy():
                    if time.time() - start_wait > 15: 
                        break
                    pygame.time.Clock().tick(10)
                
                pygame.mixer.music.unload() 
                
            except Exception as e:
                print(f"[TTS 錯誤] {e}")
            finally:
                if temp_filename and os.path.exists(temp_filename):
                    try:
                        time.sleep(0.5)
                        os.remove(temp_filename)
                    except:
                        pass

        thread = threading.Thread(target=play_audio, daemon=True)
        thread.start()

    def load_vocab_data(self):
        data = {} 
        dates_by_course = {} 
        filename = BASE_DIR / "vocab_list.csv"
        
        if not os.path.exists(filename):
            return {}, {}

        try:
            with open(filename, mode='r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    course = row.get('Course', 'Unknown Course')
                    date = row.get('Date', 'Unknown Date')
                    if course not in data:
                        data[course] = []
                        dates_by_course[course] = set()
                    data[course].append(row)
                    dates_by_course[course].add(date)
        except Exception as e:
            messagebox.showerror("錯誤", f"讀取失敗: {e}")
            return {}, {}
        return data, dates_by_course

    def save_vocab_data(self):
        filename = BASE_DIR / "vocab_list.csv"
        all_rows = []
        fieldnames = ['Course', 'Date', 'Word', 'POS', 'Chinese_1', 'Chinese_2', 'Example', 'Correct_Count', 'Total_Count']
        for course in self.all_data.values():
            all_rows.extend(course)
        try:
            with open(filename, mode='w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
        except Exception as e:
            messagebox.showerror("儲存錯誤", e)

    def update_test_stats(self):
        if not self.test_results: return
        for original_data, is_correct, _ in self.test_results:
            total = int(original_data.get('Total_Count', 0) or 0)
            correct = int(original_data.get('Correct_Count', 0) or 0)
            original_data['Total_Count'] = str(total + 1)
            if is_correct:
                original_data['Correct_Count'] = str(correct + 1)
        self.save_vocab_data()

    def clear_main_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    # ==========================================
    # 視圖 1: 課程選單
    # ==========================================
    def toggle_menu_mode(self):
        current_time = time.time()
        if current_time - self.last_key_time < self.key_debounce_delay: return
        self.menu_mode = 'test' if self.menu_mode == 'practice' else 'practice'
        self.last_key_time = current_time
        self.show_menu()

    def show_menu(self):
        self.clear_main_frame()
        self.is_test_mode = False 
        
        self.root.unbind('<Left>')
        self.root.unbind('<Right>')
        self.root.unbind('<space>')
        self.root.unbind('<Return>')
        self.root.unbind('<Up>')
        self.root.bind('<Left>', lambda e: self.toggle_menu_mode())
        self.root.bind('<Right>', lambda e: self.toggle_menu_mode())
        
        if not self.all_data:
            ctk.CTkLabel(self.main_frame, text="無單字數據，請確認 CSV 檔案。", font=("Arial", 20)).pack(pady=50)
            return

        mode_text = "📚 練習模式" if self.menu_mode == 'practice' else "📝 測驗模式"
        mode_color = "#3B8ED0" if self.menu_mode == 'practice' else "#E74C3C"
        
        ctk.CTkLabel(self.main_frame, text=mode_text, font=("Arial", 32, "bold"), text_color=mode_color).pack(pady=(30, 5))
        ctk.CTkLabel(self.main_frame, text="<-- 使用左右鍵切換模式 -->", font=("Arial", 14, "italic")).pack(pady=(0, 20))

        scroll_frame = ctk.CTkScrollableFrame(self.main_frame, corner_radius=0, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)

        course_names = sorted(self.all_data.keys())
        for i, course_name in enumerate(course_names):
            item_frame = ctk.CTkFrame(scroll_frame, corner_radius=10)
            item_frame.pack(fill="x", pady=10, padx=10)
            
            count = len(self.all_data[course_name])
            action_text = "練習所有" if self.menu_mode == 'practice' else "測驗所有"
            
            btn_main = ctk.CTkButton(item_frame, text=f"{course_name} ({count} 題) - {action_text}",
                                     font=("Arial", 18, "bold"),
                                     command=lambda c=course_name: self.handle_selection(c))
            btn_main.pack(fill="x", padx=15, pady=10)

            date_list = sorted(list(self.dates_by_course.get(course_name, [])))
            date_container = ctk.CTkFrame(item_frame, fg_color="transparent")
            date_container.pack(fill="x", padx=15, pady=(0, 10))

            for date in date_list:
                date_count = sum(1 for d in self.all_data[course_name] if d['Date'] == date)
                d_btn = ctk.CTkButton(date_container, text=f"{date} ({date_count})",
                                      width=150, height=32,
                                      font=("Arial", 13),
                                      fg_color="#5D6D7E",
                                      command=lambda c=course_name, d=date: self.handle_selection(c, d))
                d_btn.pack(side="left", padx=5, pady=5)

    def handle_selection(self, course_name, date=None):
        if self.menu_mode == 'practice':
            if date: self.start_practice_by_date(course_name, date)
            else: self.start_practice_all_course(course_name)
        else:
            self.start_test_mode(course_name, practice_date=date)

    # ==========================================
    # 測驗模式邏輯
    # ==========================================
    def start_test_mode(self, course_name, practice_date=None):
        all_words = self.all_data.get(course_name, [])
        if practice_date:
            all_words = [w for w in all_words if w.get('Date') == practice_date]
        
        if not all_words: return
        
        def get_score(w):
            t = int(w.get('Total_Count', 0) or 0)
            c = int(w.get('Correct_Count', 0) or 0)
            return (t, -(t-c))
            
        sorted_words = sorted(all_words, key=get_score)
        self.current_vocab_list = sorted_words[:10]
        random.shuffle(self.current_vocab_list)
        
        self.current_index = 0
        self.is_test_mode = True 
        self.test_results = [] 
        self.show_test_card()

    def show_test_card(self):
        self.clear_main_frame()
        top = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=10)
        
        # 狀態資訊容器
        info_frame = ctk.CTkFrame(top, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)
        
        self.status_label = ctk.CTkLabel(info_frame, text="", font=("Arial", 14))
        self.status_label.pack(anchor="w")
        
        # 進度條
        self.progress_bar = ctk.CTkProgressBar(info_frame, width=200, height=10)
        self.progress_bar.pack(anchor="w", pady=(5, 0))
        self.progress_bar.set(0)

        ctk.CTkButton(top, text="結束測驗", width=100, fg_color="#E74C3C", command=self.show_menu).pack(side="right")
        
        self.card_frame = ctk.CTkFrame(self.main_frame, corner_radius=20, border_width=2)
        self.card_frame.pack(fill="both", expand=True, padx=40, pady=20)
        
        self.card_content_label = ctk.CTkLabel(self.card_frame, text="", font=("Arial", 40, "bold"), wraplength=600)
        self.card_content_label.pack(expand=True)
        
        self.input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=40, pady=20)
        
        self.answer_entry = ctk.CTkEntry(self.input_frame, placeholder_text="請輸入中文翻譯...", 
                                         font=("Arial", 22), height=50)
        self.answer_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.answer_entry.focus_set()
        
        ctk.CTkButton(self.input_frame, text="送出 (Enter)", font=("Arial", 18, "bold"),
                      width=120, height=50, command=self.submit_test_answer).pack(side="left")

        self.root.bind('<Return>', lambda e: self.submit_test_answer())
        self.root.bind('<Up>', lambda e: self.show_menu())
        self.update_test_card_view()

    def update_test_card_view(self):
        total_count = len(self.current_vocab_list)
        if self.current_index >= total_count:
            self.show_test_results()
            return
            
        word_data = self.current_vocab_list[self.current_index]
        self.status_label.configure(text=f"測驗中: 第 {self.current_index + 1} / {total_count} 題")
        
        # 更新進度條 (0.0 ~ 1.0)
        progress_val = (self.current_index + 1) / total_count
        self.progress_bar.set(progress_val)
        
        self.card_content_label.configure(text=word_data['Word'])
        self.answer_entry.delete(0, tk.END)

    def submit_test_answer(self):
        user_input = self.answer_entry.get().strip()
        word_data = self.current_vocab_list[self.current_index]
        correct_ans = [word_data[k].strip() for k in ['Chinese_1', 'Chinese_2'] if word_data.get(k)]
        
        is_correct = False
        if user_input:
            for ans in correct_ans:
                if user_input in ans or ans in user_input:
                    is_correct = True
                    break
        
        self.test_results.append((word_data, is_correct, user_input))
        self.show_feedback(is_correct, correct_ans, user_input)

    def show_feedback(self, is_correct, correct_options, user_input):
        feedback = ctk.CTkToplevel(self.root)
        feedback.title("結果")
        feedback.geometry("400x250")
        feedback.attributes("-topmost", True)
        
        msg = "✔ 答對了！" if is_correct else "✘ 答錯了！"
        color = "#2ECC71" if is_correct else "#E74C3C"
        
        ctk.CTkLabel(feedback, text=msg, font=("Arial", 28, "bold"), text_color=color).pack(pady=20)
        ctk.CTkLabel(feedback, text=f"正確答案: {' / '.join(correct_options)}", font=("Arial", 16)).pack(pady=5)
        
        def proceed():
            feedback.destroy()
            self.current_index += 1
            self.update_test_card_view()

        ctk.CTkButton(feedback, text="下一題", command=proceed).pack(pady=20)
        feedback.bind('<Return>', lambda e: proceed())

    def show_test_results(self):
        self.update_test_stats()
        self.clear_main_frame()
        self.root.bind('<Return>', lambda e: self.show_menu())
        
        correct = sum(1 for _, r, _ in self.test_results if r)
        total = len(self.test_results)
        
        ctk.CTkLabel(self.main_frame, text="測驗結果", font=("Arial", 32, "bold")).pack(pady=20)
        ctk.CTkLabel(self.main_frame, text=f"總分: {correct} / {total}", font=("Arial", 24)).pack(pady=10)
        
        res_scroll = ctk.CTkScrollableFrame(self.main_frame, width=600, height=300)
        res_scroll.pack(pady=20, padx=40, fill="both", expand=True)
        
        for word_data, r, user_in in self.test_results:
            color = "#2ECC71" if r else "#E74C3C"
            prefix = "✔" if r else "✘"
            txt = f"{prefix} {word_data['Word']} - {word_data['Chinese_1']} (輸入: {user_in})"
            ctk.CTkLabel(res_scroll, text=txt, text_color=color, font=("Arial", 14)).pack(anchor="w", pady=2)

        ctk.CTkButton(self.main_frame, text="返回主選單 (Enter)", command=self.show_menu).pack(pady=20)

    # ==========================================
    # 練習模式邏輯
    # ==========================================
    def start_practice_all_course(self, course_name):
        self.current_vocab_list = self.all_data.get(course_name, [])
        random.shuffle(self.current_vocab_list)
        self.current_index = 0
        self.is_front_side = True
        self.show_flashcard()
        
    def start_practice_by_date(self, course_name, date):
        self.current_vocab_list = [w for w in self.all_data.get(course_name, []) if w['Date'] == date]
        random.shuffle(self.current_vocab_list)
        self.current_index = 0
        self.is_front_side = True
        self.show_flashcard()

    def show_flashcard(self):
        self.clear_main_frame()
        top = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=10)
        
        # 狀態資訊容器
        info_frame = ctk.CTkFrame(top, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        self.status_label = ctk.CTkLabel(info_frame, text="", font=("Arial", 14))
        self.status_label.pack(anchor="w")

        # 進度條
        self.progress_bar = ctk.CTkProgressBar(info_frame, width=200, height=10)
        self.progress_bar.pack(anchor="w", pady=(5, 0))
        self.progress_bar.set(0)

        ctk.CTkButton(top, text="返回選單", width=100, command=self.show_menu).pack(side="right")
        
        self.card_frame = ctk.CTkFrame(self.main_frame, corner_radius=20, border_width=2, fg_color="#FDFEFE")
        self.card_frame.pack(fill="both", expand=True, padx=40, pady=20)
        
        self.card_label = ctk.CTkLabel(self.card_frame, text="", font=("Arial", 40, "bold"), text_color="black", wraplength=600)
        self.card_label.pack(expand=True)
        self.card_frame.bind("<Button-1>", lambda e: self.flip_card())
        self.card_label.bind("<Button-1>", lambda e: self.flip_card())

        ctrl = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ctrl.pack(fill="x", pady=20)
        
        ctk.CTkButton(ctrl, text="上一張 (←)", command=self.prev_card).pack(side="left", expand=True, padx=10)
        self.btn_flip = ctk.CTkButton(ctrl, text="翻面 (Space)", fg_color="#5D6D7E", command=self.flip_card)
        self.btn_flip.pack(side="left", expand=True, padx=10)
        ctk.CTkButton(ctrl, text="下一張 (→)", command=self.next_card).pack(side="left", expand=True, padx=10)

        self.root.bind('<Left>', lambda e: self.prev_card())
        self.root.bind('<Right>', lambda e: self.next_card())
        self.root.bind('<space>', lambda e: self.flip_card())
        self.root.bind('<Up>', lambda e: self.show_menu())
        
        self.display_card()

    def display_card(self):
        word_data = self.current_vocab_list[self.current_index]
        total_count = len(self.current_vocab_list)
        self.status_label.configure(text=f"{word_data['Course']} | {word_data['Date']} | {self.current_index+1} / {total_count}")
        
        # 更新進度條
        progress_val = (self.current_index + 1) / total_count
        self.progress_bar.set(progress_val)
        
        if self.is_front_side:
            self.card_label.configure(text=word_data['Word'], font=("Arial", 50, "bold"))
            self.card_frame.configure(fg_color="#EBF5FB")
            self.speak_text(word_data['Word'], 'en')
        else:
            details = f"{word_data['Word']}\n\n[{word_data['POS']}]\n{word_data['Chinese_1']}\n{word_data['Chinese_2']}\n\n{word_data['Example']}"
            self.card_label.configure(text=details, font=("Arial", 20))
            self.card_frame.configure(fg_color="#F4F6F7")
            self.speak_text(f"{word_data['Chinese_1']}, {word_data['Chinese_2']}", 'zh-tw')
            self.root.after(2000, lambda: self.speak_text(word_data['Example'], 'en'))

    def flip_card(self):
        self.is_front_side = not self.is_front_side
        self.display_card()

    def next_card(self):
        self.current_index = (self.current_index + 1) % len(self.current_vocab_list)
        self.is_front_side = True
        self.display_card()

    def prev_card(self):
        self.current_index = (self.current_index - 1) % len(self.current_vocab_list)
        self.is_front_side = True
        self.display_card()

if __name__ == "__main__":
    root = ctk.CTk()
    app = FlashcardApp(root)
    root.mainloop()