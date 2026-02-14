import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

class SheetsManager:
    def __init__(self):
        # 優先從環境變數讀取 credentials（Render 部署用）
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        else:
            # 本機開發用 credentials.json 檔案
            creds = Credentials.from_service_account_file(
                'credentials.json', scopes=SCOPES
            )
        self.client = gspread.authorize(creds)
        self.sheet_id = os.getenv('GOOGLE_SHEETS_ID')
        self.spreadsheet = self.client.open_by_key(self.sheet_id)
        self._ensure_sheets_exist()

    def _ensure_sheets_exist(self):
        """確保必要的工作表存在"""
        sheet_names = [ws.title for ws in self.spreadsheet.worksheets()]

        # 帳目紀錄
        if '帳目紀錄' not in sheet_names:
            ws = self.spreadsheet.add_worksheet(title='帳目紀錄', rows=1000, cols=10)
            ws.append_row(['日期時間', '項目', '金額', '付款人', '參與者', '分攤方式', '圖片連結'])

        # 成員清單
        if '成員清單' not in sheet_names:
            ws = self.spreadsheet.add_worksheet(title='成員清單', rows=100, cols=5)
            ws.append_row(['名稱', 'LINE_ID'])

    def add_expense(self, item: str, amount: float, payer: str,
                    participants: list, split_type: str, image_url: str = ''):
        """新增一筆支出"""
        ws = self.spreadsheet.worksheet('帳目紀錄')
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        participants_str = ','.join(participants)
        ws.append_row([now, item, amount, payer, participants_str, split_type, image_url])

    def get_all_expenses(self) -> list:
        """取得所有帳目"""
        ws = self.spreadsheet.worksheet('帳目紀錄')
        records = ws.get_all_records()
        return records

    def get_summary(self) -> dict:
        """計算每人應付/應收金額"""
        expenses = self.get_all_expenses()

        # 每人實際支出
        paid = {}
        # 每人應分攤
        owed = {}

        for exp in expenses:
            payer = exp['付款人']
            amount = float(exp['金額'])
            participants = exp['參與者'].split(',')

            # 記錄付款人支出
            paid[payer] = paid.get(payer, 0) + amount

            # 計算每人應分攤
            share = amount / len(participants)
            for p in participants:
                p = p.strip()
                owed[p] = owed.get(p, 0) + share

        # 計算每人結餘（正數=應收，負數=應付）
        all_people = set(paid.keys()) | set(owed.keys())
        balance = {}
        for person in all_people:
            balance[person] = paid.get(person, 0) - owed.get(person, 0)

        return {
            'paid': paid,      # 每人已付
            'owed': owed,      # 每人應付
            'balance': balance # 結餘
        }

    def add_member(self, name: str, line_id: str):
        """新增成員"""
        ws = self.spreadsheet.worksheet('成員清單')
        ws.append_row([name, line_id])

    def get_members(self) -> list:
        """取得所有成員"""
        ws = self.spreadsheet.worksheet('成員清單')
        return ws.get_all_records()

    def find_member_by_line_id(self, line_id: str) -> str:
        """根據 LINE ID 找成員名稱"""
        members = self.get_members()
        for m in members:
            if m['LINE_ID'] == line_id:
                return m['名稱']
        return None

    def delete_last_expense(self) -> dict:
        """
        刪除最後一筆帳目
        回傳被刪除的紀錄（含圖片連結），若無紀錄則回傳 None
        """
        ws = self.spreadsheet.worksheet('帳目紀錄')
        all_values = ws.get_all_values()

        # 第一行是標題，至少要有兩行才有資料
        if len(all_values) < 2:
            return None

        # 取得最後一行的資料
        last_row = all_values[-1]
        last_row_num = len(all_values)

        # 建立紀錄 dict
        headers = all_values[0]
        deleted_record = {}
        for i, header in enumerate(headers):
            if i < len(last_row):
                deleted_record[header] = last_row[i]

        # 刪除該行
        ws.delete_rows(last_row_num)

        return deleted_record
