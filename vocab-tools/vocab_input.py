import customtkinter as ctk
import csv
import datetime
import os
from pathlib import Path
from tkinter import messagebox

# --- V2 SDK 匯入路徑 ---
import google.genai as genai 

# 設定環境
BASE_DIR = Path(__file__).resolve().parent
# 注意：在正式環境中，建議使用環境變數管理 API KEY
GOOGLE_API_KEY = "Your GEMINI KEY"

# 設定外觀與主題
ctk.set_appearance_mode("System")  # 跟隨系統模式
ctk.set_default_color_theme("blue") # 藍色主題

# 初始化 Gemini Client
client = None
try:
    client = genai.Client(api_key=GOOGLE_API_KEY)
    print("API Client 初始化成功。")
except Exception as e:
    print(f"API Client 初始化錯誤: {e}")

class VocabApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 視窗基本設定
        self.title("課程單字記錄小幫手 (Gemini Powered)")
        self.geometry("750x850")
        
        # 鍵盤綁定: 按下 ESC 鍵結束程式
        self.bind('<Escape>', lambda event: self.destroy())

        # --- 1. 頂部課程資訊區 ---
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.pack(fill="x", padx=20, pady=(20, 10))

        # 課程欄位
        self.label_course = ctk.CTkLabel(self.header_frame, text="Course (課程):", font=("Arial", 13, "bold"))
        self.label_course.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="w")
        
        self.course_entry = ctk.CTkEntry(self.header_frame, width=180, placeholder_text="例如: English")
        self.course_entry.grid(row=0, column=1, padx=5, pady=15)
        self.course_entry.insert(0, "Eng")

        # 日期欄位
        self.label_date = ctk.CTkLabel(self.header_frame, text="Date (日期):", font=("Arial", 13, "bold"))
        self.label_date.grid(row=0, column=2, padx=(20, 5), pady=15, sticky="w")
        
        self.date_entry = ctk.CTkEntry(self.header_frame, width=180)
        self.date_entry.grid(row=0, column=3, padx=15, pady=15)
        self.date_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        # --- 2. 文字輸入與顯示區 ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.label_hint = ctk.CTkLabel(
            self.main_frame, 
            text="請輸入單字清單 (每行一個) 或 直接貼上課堂筆記：", 
            font=("Arial", 13)
        )
        self.label_hint.pack(pady=(15, 5), padx=15, anchor="w")

        self.input_text = ctk.CTkTextbox(self.main_frame, font=("Arial", 15), border_width=1)
        self.input_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # --- 3. 按鈕功能區 ---
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(fill="x", padx=20, pady=10)

        # 清除按鈕
        self.btn_clear = ctk.CTkButton(
            self.action_frame, 
            text="清除內容", 
            fg_color="#607D8B", 
            hover_color="#455A64", 
            command=self.clear_fields
        )
        self.btn_clear.pack(side="left", padx=5, expand=True, fill="x")

        # Gemini 處理按鈕
        self.btn_gemini = ctk.CTkButton(
            self.action_frame, 
            text="✨ Gemini AI 智慧補全", 
            fg_color="#673AB7", 
            hover_color="#512DA8", 
            command=self.run_gemini_processing
        )
        self.btn_gemini.pack(side="left", padx=5, expand=True, fill="x")

        # 儲存按鈕
        self.btn_save = ctk.CTkButton(
            self.action_frame, 
            text="儲存為 CSV 檔案", 
            fg_color="#2E7D32", 
            hover_color="#1B5E20", 
            command=self.save_to_file
        )
        self.btn_save.pack(side="left", padx=5, expand=True, fill="x")

        # --- 4. 底部狀態列 ---
        self.status_bar = ctk.CTkLabel(self, text="系統準備就緒", anchor="w", font=("Arial", 12))
        self.status_bar.pack(fill="x", side="bottom", padx=25, pady=5)

        # 初始檢查
        if client is None:
            self.update_status("警告：API 連線未建立，請檢查您的 Google API Key", "red")

    def update_status(self, text, color=None):
        """更新狀態列的文字與視覺反饋"""
        self.status_bar.configure(text=text)
        if color:
            self.status_bar.configure(text_color=color)
        else:
            # 根據目前主題恢復預設文字顏色
            default_color = "white" if ctk.get_appearance_mode() == "Dark" else "black"
            self.status_bar.configure(text_color=default_color)
        self.update() # 強制更新 UI

    def clear_fields(self):
        """清空輸入框"""
        self.input_text.delete("1.0", "end")
        self.update_status("已清除所有內容")

    def run_gemini_processing(self):
        """呼叫 Gemini API 進行單字整理"""
        raw_text = self.input_text.get("1.0", "end").strip()
        
        if not raw_text:
            messagebox.showwarning("提示", "輸入區目前是空的，請先輸入單字或貼上筆記。")
            return

        if client is None:
            messagebox.showerror("錯誤", "API Client 尚未初始化，無法執行 AI 功能。")
            return
        
        self.update_status("Gemini AI 正在解析單字並生成例句...請稍候", "#FF9800")
        self.btn_gemini.configure(state="disabled") # 防止重複點擊

        prompt = f"""
        You are a vocabulary organizing assistant.
        I will give you a list of words or messy notes. Your goal is to extract the vocabulary and fill in missing information.

        Input Text:
        {raw_text}

        Requirements:
        1. Identify the main English word each line.
        2. If a line includes definitions or example sentences, CORRECT them if there are errors.
        3. If definitions (Chinese_1, Chinese_2), POS, or example sentences are MISSING, provide them.
        4. Ensure the Part of Speech (POS) in Traditional Chinese (e.g., 名詞, 動詞, 形容詞).
        5. Ensure the (Chinese_1, Chinese_2) in Traditional Chinese.
        6. Output format MUST be strictly separated by a pipe symbol (|) for each line.
        7. Format: Word | POS | Chinese_1 | Chinese_2 | Example
        8. Do not output any header or markdown symbols, just the raw data lines.
        """

        try:
            # 使用最新穩定版模型
            response = client.models.generate_content(
                #model='models/gemini-2.5-flash-lite',
                model='models/gemini-2.5-flash',
                #model='gemini-2.0-flash-lite-preview-02-05',
                contents=prompt
            )
            processed_text = response.text.strip()
            
            # 清除 Markdown 可能帶有的符號 (防呆)
            if processed_text.startswith("```"):
                processed_text = "\n".join(processed_text.split("\n")[1:-1])

            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", processed_text)
            self.update_status("Gemini 處理完成！請確認內容無誤後點擊儲存", "#4CAF50")
            
        except Exception as e:
            self.update_status(f"API 呼叫失敗: {str(e)}", "red")
            messagebox.showerror("API Error", f"無法連接至 Gemini AI：\n{str(e)}")
        finally:
            self.btn_gemini.configure(state="normal")

    def save_to_file(self):
        """將整理好的單字存入 CSV 檔案"""
        course = self.course_entry.get().strip()
        date_str = self.date_entry.get().strip()
        content = self.input_text.get("1.0", "end").strip()

        if not content:
            messagebox.showwarning("提示", "目前沒有內容可供儲存。")
            return

        filename = BASE_DIR / "vocab_list.csv"
        file_exists = os.path.isfile(filename)

        try:
            # 使用 utf-8-sig 以便 Excel 正常開啟中文
            with open(filename, mode='a', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # 寫入標題列
                if not file_exists:
                    header = ["Course", "Date", "Word", "POS", "Chinese_1", "Chinese_2", "Example", "Correct_Count", "Total_Count"]
                    writer.writerow(header)

                lines = content.split('\n')
                saved_count = 0
                
                for line in lines:
                    line = line.strip()
                    if not line: continue

                    # 根據 '|' 分隔符號拆解
                    parts = [p.strip() for p in line.split('|')]
                    
                    if len(parts) >= 5:
                        # 完整格式：Word | POS | Ch1 | Ch2 | Ex
                        row = [course, date_str] + parts[:5] + [0, 0]
                        writer.writerow(row)
                        saved_count += 1
                    else:
                        # 格式不足時的備案：將第一個部分當成單字，其餘留空
                        row = [course, date_str, parts[0], "", "", "", "", 0, 0]
                        writer.writerow(row)
                        saved_count += 1

            self.update_status(f"儲存成功：已將 {saved_count} 個單字寫入 {filename.name}")
            messagebox.showinfo("儲存成功", f"已成功儲存 {saved_count} 筆資料至：\n{filename}")
            
        except Exception as e:
            self.update_status("檔案儲存失敗", "red")
            messagebox.showerror("存檔錯誤", f"無法寫入 CSV 檔案，請檢查檔案是否被其他程式開啟：\n{e}")

if __name__ == "__main__":
    app = VocabApp()
    app.mainloop()