import os
import json
import requests
from dotenv import load_dotenv
from parser import ExpenseData

load_dotenv()

GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

def parse_with_ai(text: str, sender_name: str = '我') -> ExpenseData | None:
    """
    使用 Gemini AI 解析自然語言記帳輸入

    範例輸入：
    - 午餐$600均分
    - 今天午餐花了600塊 大家分
    - 掛號費150 大哥付的
    - 買藥500元 二姐出
    """

    prompt = f"""你是一個記帳助手。請從以下文字中提取記帳資訊，並以 JSON 格式回覆。

使用者輸入：「{text}」
發送者名稱：{sender_name}

請提取：
1. item: 項目名稱（如：午餐、掛號費、藥費）
2. amount: 金額（數字）
3. payer: 付款人（如果沒提到，預設為「{sender_name}」）
4. participants: 參與分攤的人（陣列，如果沒提到，預設為 ["{sender_name}"]）
5. split_type: 分攤方式（「均分」或「指定」）

規則：
- 如果提到「均分」「大家分」「一起付」→ split_type 為「均分」
- 如果提到「某人出」「某人付」→ split_type 為「指定」，payer 為該人
- 金額可能有 $ 或 元 等符號，請只取數字

只回覆 JSON，不要其他文字。如果無法解析，回覆 {{"error": "無法解析"}}

範例回覆：
{{"item": "午餐", "amount": 600, "payer": "我", "participants": ["我"], "split_type": "均分"}}
"""

    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        result = response.json()
        result_text = result['candidates'][0]['content']['parts'][0]['text'].strip()

        # 移除可能的 markdown 標記
        if result_text.startswith('```'):
            lines = result_text.split('\n')
            result_text = '\n'.join(lines[1:])
            result_text = result_text.rsplit('```', 1)[0]

        data = json.loads(result_text)

        if 'error' in data:
            return None

        return ExpenseData(
            item=data['item'],
            amount=float(data['amount']),
            payer=data['payer'],
            participants=data['participants'],
            split_type=data['split_type']
        )
    except Exception as e:
        print(f"AI 解析錯誤: {e}")
        return None


# 測試
if __name__ == '__main__':
    test_cases = [
        "午餐$600均分",
        "掛號費150 大哥付的",
        "買藥500元 二姐出",
    ]

    for text in test_cases:
        result = parse_with_ai(text, sender_name='我')
        print(f"輸入: {text}")
        print(f"結果: {result}")
        print("-" * 40)
