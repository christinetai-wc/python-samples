import os
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/drive'
]

class DriveManager:
    def __init__(self):
        creds = Credentials.from_service_account_file(
            'credentials.json', scopes=SCOPES
        )
        self.service = build('drive', 'v3', credentials=creds)
        self.folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

    def upload_image(self, image_content: bytes, filename: str = None) -> str:
        """
        上傳圖片到 Google Drive 共用資料夾

        回傳：圖片的公開連結
        """
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"receipt_{timestamp}.jpg"

        if not self.folder_id:
            print("未設定 GOOGLE_DRIVE_FOLDER_ID")
            return ""

        file_metadata = {
            'name': filename,
            'parents': [self.folder_id]
        }

        media = MediaInMemoryUpload(
            image_content,
            mimetype='image/jpeg',
            resumable=False  # 小檔案不需要 resumable
        )

        # 上傳到共用資料夾
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True
        ).execute()

        file_id = file.get('id')

        # 設定為任何人可檢視
        try:
            self.service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'},
                supportsAllDrives=True
            ).execute()
        except Exception as e:
            print(f"設定權限失敗（可能資料夾已公開）: {e}")

        # 回傳直接檢視連結
        return f"https://drive.google.com/file/d/{file_id}/view"


# 測試
if __name__ == '__main__':
    drive = DriveManager()
    print("Drive 連線成功")
    print("資料夾 ID:", drive.folder_id)
