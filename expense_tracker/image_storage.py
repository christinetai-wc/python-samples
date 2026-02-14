"""
圖片儲存模組 - 使用 Cloudinary
"""
import os
import base64
import requests
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')


def upload_to_cloudinary(image_content: bytes) -> str:
    """
    上傳圖片到 Cloudinary
    回傳圖片網址，失敗回傳空字串
    """
    try:
        url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"

        # 轉換為 base64
        image_base64 = base64.b64encode(image_content).decode('utf-8')

        payload = {
            "file": f"data:image/jpeg;base64,{image_base64}",
            "upload_preset": "ml_default",  # Cloudinary 預設的 unsigned preset
        }

        # 如果有設定 API key，使用 signed upload（更安全）
        if CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
            import time
            import hashlib

            timestamp = str(int(time.time()))

            # 建立簽名
            params_to_sign = f"timestamp={timestamp}"
            signature = hashlib.sha1(
                f"{params_to_sign}{CLOUDINARY_API_SECRET}".encode()
            ).hexdigest()

            payload = {
                "file": f"data:image/jpeg;base64,{image_base64}",
                "timestamp": timestamp,
                "api_key": CLOUDINARY_API_KEY,
                "signature": signature,
            }

        response = requests.post(url, data=payload, timeout=30)
        response.raise_for_status()

        result = response.json()

        if 'secure_url' in result:
            return result['secure_url']
        else:
            print(f"Cloudinary 回傳異常: {result}")
            return ""

    except Exception as e:
        print(f"Cloudinary 上傳錯誤: {e}")
        return ""


def delete_from_cloudinary(public_id: str) -> bool:
    """
    從 Cloudinary 刪除圖片
    public_id 是圖片的識別碼（從 URL 可以取得）
    """
    try:
        import time
        import hashlib

        url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/destroy"

        timestamp = str(int(time.time()))
        params_to_sign = f"public_id={public_id}&timestamp={timestamp}"
        signature = hashlib.sha1(
            f"{params_to_sign}{CLOUDINARY_API_SECRET}".encode()
        ).hexdigest()

        payload = {
            "public_id": public_id,
            "timestamp": timestamp,
            "api_key": CLOUDINARY_API_KEY,
            "signature": signature,
        }

        response = requests.post(url, data=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        return result.get('result') == 'ok'

    except Exception as e:
        print(f"Cloudinary 刪除錯誤: {e}")
        return False


def upload_image(image_content: bytes) -> str:
    """
    上傳圖片並回傳網址
    """
    return upload_to_cloudinary(image_content)


def extract_public_id_from_url(url: str) -> str:
    """
    從 Cloudinary URL 提取 public_id
    例如：https://res.cloudinary.com/xxx/image/upload/v123/abc123.jpg
    回傳：abc123
    """
    import re
    # 匹配 /v數字/xxx.副檔名
    match = re.search(r'/v\d+/(.+)\.\w+$', url)
    if match:
        return match.group(1)
    return ""


def delete_image(url: str) -> bool:
    """
    根據圖片 URL 刪除 Cloudinary 上的圖片
    """
    if not url or 'cloudinary' not in url:
        return False

    public_id = extract_public_id_from_url(url)
    if public_id:
        return delete_from_cloudinary(public_id)
    return False
