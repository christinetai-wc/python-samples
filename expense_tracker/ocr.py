import os
import re
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')

def extract_amounts_from_text(text: str) -> list:
    """從文字中提取金額"""
    patterns = [
        r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.00
        r'NT\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # NT$1,234
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*元',  # 1,234元
        r'[總合小]計[：:]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # 總計：1234
        r'金額[：:]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # 金額：1234
        r'應付[：:]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # 應付：1234
    ]

    amounts = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            clean_amount = float(m.replace(',', ''))
            if clean_amount > 0:
                amounts.append(clean_amount)

    amounts = list(set(amounts))
    amounts.sort(reverse=True)
    return amounts


def extract_with_vision(image_content: bytes) -> dict:
    """使用 Google Cloud Vision API"""
    try:
        from google.cloud import vision
        import json

        # 優先從環境變數讀取 credentials（Render 部署用）
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            from google.oauth2.service_account import Credentials
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info)
            client = vision.ImageAnnotatorClient(credentials=creds)
        else:
            # 本機開發用 credentials.json 檔案
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv(
                'GOOGLE_APPLICATION_CREDENTIALS',
                '/Users/christine/python/expense_tracker/credentials.json'
            )
            client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_content)
        response = client.text_detection(image=image)

        if response.error.message:
            return {'success': False, 'error': response.error.message}

        texts = response.text_annotations
        if not texts:
            return {'success': False, 'error': '無法辨識文字'}

        full_text = texts[0].description
        amounts = extract_amounts_from_text(full_text)

        if amounts:
            return {
                'success': True,
                'amounts': amounts,
                'largest': amounts[0],
                'text': full_text
            }
        else:
            return {'success': False, 'error': '找不到金額', 'text': full_text}

    except Exception as e:
        print(f"Vision API 錯誤: {e}")
        return {'success': False, 'error': str(e)}


def extract_with_gemini(image_content: bytes) -> dict:
    """使用 Gemini API 辨識圖片"""
    try:
        image_base64 = base64.b64encode(image_content).decode('utf-8')

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

        payload = {
            "contents": [{
                "parts": [
                    {"text": "請辨識這張收據或發票圖片中的金額。只回覆數字金額，多個金額用逗號分隔。如果找不到金額，回覆「無」。"},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_base64
                        }
                    }
                ]
            }]
        }

        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()

        result = response.json()
        text = result['candidates'][0]['content']['parts'][0]['text'].strip()

        if text == '無' or not text:
            return {'success': False, 'error': '找不到金額'}

        # 解析回覆中的數字
        amounts = []
        numbers = re.findall(r'[\d,]+(?:\.\d+)?', text)
        for n in numbers:
            try:
                amount = float(n.replace(',', ''))
                if amount > 0:
                    amounts.append(amount)
            except:
                pass

        amounts = list(set(amounts))
        amounts.sort(reverse=True)

        if amounts:
            return {
                'success': True,
                'amounts': amounts,
                'largest': amounts[0],
                'text': text
            }
        else:
            return {'success': False, 'error': '找不到金額'}

    except Exception as e:
        print(f"Gemini API 錯誤: {e}")
        return {'success': False, 'error': str(e)}


def extract_amount_from_image(image_content: bytes) -> dict:
    """
    從圖片中辨識金額
    優先使用 Cloud Vision，失敗則用 Gemini
    """
    # 先試 Cloud Vision
    result = extract_with_vision(image_content)
    if result['success']:
        result['method'] = 'vision'
        return result

    print("Cloud Vision 失敗，嘗試 Gemini...")

    # 再試 Gemini
    result = extract_with_gemini(image_content)
    if result['success']:
        result['method'] = 'gemini'
        return result

    # 都失敗
    return {
        'success': False,
        'error': '無法辨識金額',
        'amounts': [0],
        'largest': 0
    }


def format_ocr_result(result: dict) -> str:
    """格式化 OCR 結果為回覆訊息"""
    if not result['success']:
        return f"⚠️ 無法辨識金額\n\n請回覆格式：\n項目名稱 金額 均分"

    if len(result['amounts']) == 1:
        return f"🔍 辨識到金額：${result['largest']:,.0f}\n\n請回覆格式：\n項目名稱 {int(result['largest'])} 均分"
    else:
        amounts_str = '、'.join([f"${a:,.0f}" for a in result['amounts'][:5]])
        return f"🔍 辨識到多個金額：{amounts_str}\n\n最大金額：${result['largest']:,.0f}\n\n請回覆格式：\n項目名稱 金額 均分"
