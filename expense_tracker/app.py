import os
import time
from flask import Flask, request, abort, render_template
from dotenv import load_dotenv

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, ImageMessageContent
)
from linebot.v3.exceptions import InvalidSignatureError

from sheets import SheetsManager
from parser import parse_expense, format_expense_confirm
from ai_parser import parse_with_ai
from ocr import extract_amount_from_image, format_ocr_result

load_dotenv()

app = Flask(__name__)

# LINE Bot 設定
configuration = Configuration(
    access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
)
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# Google Sheets
sheets = None

# 等待收據圖片的群組/使用者（群組ID 或 房間ID -> 過期時間）
pending_receipt = {}

def get_sheets():
    global sheets
    if sheets is None:
        sheets = SheetsManager()
    return sheets


@app.route('/callback', methods=['POST'])
def callback():
    """LINE Bot Webhook"""
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """處理文字訊息 - 群組模式需要 / 前綴"""
    text = event.message.text.strip()
    user_id = event.source.user_id

    # 判斷是否為群組訊息
    is_group = hasattr(event.source, 'group_id') or hasattr(event.source, 'room_id')

    # 群組中，只處理 / 開頭的訊息
    if is_group and not text.startswith('/'):
        return  # 忽略一般聊天

    # 移除前綴 /
    if text.startswith('/'):
        text = text[1:].strip()

    # 如果移除前綴後是空的，不處理
    if not text:
        return

    # 取得使用者名稱
    sheets_mgr = get_sheets()
    sender_name = sheets_mgr.find_member_by_line_id(user_id)
    if not sender_name:
        sender_name = '我'

    reply = None

    # 取得群組/房間 ID
    chat_id = None
    if hasattr(event.source, 'group_id'):
        chat_id = event.source.group_id
    elif hasattr(event.source, 'room_id'):
        chat_id = event.source.room_id

    # 特殊指令
    if text == '結算' or text == '統計':
        reply = get_summary_text()
    elif text == '帳目' or text == '紀錄':
        reply = get_recent_expenses()
    elif text == '刪除' or text == '刪除最後一筆':
        reply = delete_last_expense()
    elif text == '收據' or text == '圖片':
        # 啟動收據模式，2 分鐘內的圖片會處理
        if chat_id:
            pending_receipt[chat_id] = time.time() + 120  # 2 分鐘後過期
            reply = "📷 請在 2 分鐘內傳送收據照片"
        else:
            # 私訊模式，直接處理圖片
            reply = "📷 請直接傳送收據照片"
    elif text.startswith('我是'):
        # 註冊名字：我是大哥
        name = text[2:].strip()
        if name:
            sheets_mgr.add_member(name, user_id)
            reply = f"✅ 已記住你是「{name}」"
        else:
            reply = "請輸入：/我是[你的名字]"
    elif text == '說明' or text == '幫助':
        reply = get_help_text()
    else:
        # 先嘗試基本格式解析，失敗則用 AI
        expense = parse_expense(text, sender_name)
        if not expense:
            expense = parse_with_ai(text, sender_name)

        if expense:
            sheets_mgr.add_expense(
                item=expense.item,
                amount=expense.amount,
                payer=expense.payer,
                participants=expense.participants,
                split_type=expense.split_type
            )
            reply = format_expense_confirm(expense)
        else:
            # 群組中不回覆無法理解的訊息，避免干擾
            if is_group:
                return
            reply = "❓ 無法理解\n\n試試這樣說：\n• /午餐600均分\n• /掛號費150 大哥付\n• /藥費500 二姐出"

    # 回覆
    if reply:
        with ApiClient(configuration) as api_client:
            messaging_api = MessagingApi(api_client)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply)]
                )
            )


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    """處理圖片訊息"""
    message_id = event.message.id
    user_id = event.source.user_id

    # 判斷是否為群組訊息
    is_group = hasattr(event.source, 'group_id') or hasattr(event.source, 'room_id')

    # 取得群組/房間 ID
    chat_id = None
    if hasattr(event.source, 'group_id'):
        chat_id = event.source.group_id
    elif hasattr(event.source, 'room_id'):
        chat_id = event.source.room_id

    # 群組中，檢查是否有等待收據
    if is_group:
        if chat_id not in pending_receipt:
            return  # 沒有等待收據，忽略圖片

        if time.time() > pending_receipt[chat_id]:
            # 已過期
            del pending_receipt[chat_id]
            return

        # 有效，清除等待狀態（只處理第一張）
        del pending_receipt[chat_id]

    reply = ""
    image_url = ""

    try:
        # 下載圖片
        from linebot.v3.messaging import MessagingApiBlob
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            response = blob_api.get_message_content(message_id)

            # 讀取圖片 bytes
            if hasattr(response, 'content'):
                image_content = response.content
            elif hasattr(response, 'iter_content'):
                image_content = b''.join(response.iter_content())
            else:
                image_content = bytes(response)

            print(f"圖片大小: {len(image_content)} bytes")

            # 上傳圖片到 Cloudinary
            try:
                from image_storage import upload_image
                image_url = upload_image(image_content)
                print(f"圖片已上傳: {image_url}")
            except Exception as e:
                print(f"上傳圖片失敗: {e}")
                import traceback
                traceback.print_exc()
                image_url = ""

            # OCR 辨識
            result = extract_amount_from_image(image_content)

            # 取得使用者名稱
            sheets_mgr = get_sheets()
            sender_name = sheets_mgr.find_member_by_line_id(user_id) or '我'

            if result['success']:
                reply = format_ocr_result(result)
                reply += f"\n\n📎 圖片已儲存" if image_url else ""
            else:
                # OCR 失敗，仍然記錄（金額為 0）
                sheets_mgr.add_expense(
                    item="待補金額",
                    amount=0,
                    payer=sender_name,
                    participants=[sender_name],
                    split_type="均分",
                    image_url=image_url
                )
                reply = "⚠️ 無法辨識金額\n\n已記錄圖片，請補充金額：\n/項目名稱 金額" if image_url else "⚠️ 無法辨識金額\n請手動輸入"

    except Exception as e:
        print(f"圖片處理錯誤: {e}")
        import traceback
        traceback.print_exc()
        reply = "⚠️ 圖片處理失敗\n請手動輸入"

    # 回覆
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


def get_summary_text() -> str:
    """產生結算摘要文字"""
    sheets_mgr = get_sheets()
    summary = sheets_mgr.get_summary()

    if not summary['balance']:
        return "📊 目前沒有帳目紀錄"

    lines = ["📊 結算摘要\n"]

    # 每人已付
    lines.append("💳 已付金額：")
    for person, amount in summary['paid'].items():
        lines.append(f"  {person}：${amount:,.0f}")

    lines.append("\n💰 應付金額：")
    for person, amount in summary['owed'].items():
        lines.append(f"  {person}：${amount:,.0f}")

    lines.append("\n📈 結餘（正=應收，負=應付）：")
    for person, amount in summary['balance'].items():
        sign = "+" if amount > 0 else ""
        lines.append(f"  {person}：{sign}${amount:,.0f}")

    return '\n'.join(lines)


def get_recent_expenses() -> str:
    """取得最近帳目"""
    sheets_mgr = get_sheets()
    expenses = sheets_mgr.get_all_expenses()

    if not expenses:
        return "📝 目前沒有帳目紀錄"

    # 取最近 10 筆
    recent = expenses[-10:]
    recent.reverse()

    lines = ["📝 最近帳目\n"]
    for exp in recent:
        lines.append(f"• {exp['項目']} ${exp['金額']:,} ({exp['付款人']}付)")

    total = sum(float(e['金額']) for e in expenses)
    lines.append(f"\n總計：${total:,.0f}")

    return '\n'.join(lines)


def delete_last_expense() -> str:
    """刪除最後一筆帳目"""
    from image_storage import delete_image

    sheets_mgr = get_sheets()
    deleted = sheets_mgr.delete_last_expense()

    if not deleted:
        return "📝 沒有帳目可刪除"

    # 如果有圖片，一併刪除
    image_url = deleted.get('圖片連結', '')
    image_deleted = False
    if image_url:
        image_deleted = delete_image(image_url)

    # 組合回覆訊息
    reply = f"🗑️ 已刪除\n"
    reply += f"📝 {deleted.get('項目', '?')}\n"
    reply += f"💰 ${float(deleted.get('金額', 0)):,.0f}\n"
    reply += f"💳 {deleted.get('付款人', '?')} 付款"

    if image_url:
        if image_deleted:
            reply += "\n🖼️ 圖片已刪除"
        else:
            reply += "\n⚠️ 圖片刪除失敗"

    return reply


def get_help_text() -> str:
    """說明文字"""
    return """📖 使用說明

【記帳】用 / 開頭
• /午餐 750
• /掛號費 150 大哥付
• /藥費 500 二姐出

【查詢】
• /結算 - 每人應付/應收
• /帳目 - 最近紀錄
• /刪除 - 刪除最後一筆
• /說明 - 顯示此說明

【收據】
• /收據 → 2分鐘內傳圖片
• /我是大哥 - 設定名字"""


# === 網頁路由 ===

@app.route('/')
def index():
    """網頁首頁 - 顯示帳目"""
    sheets_mgr = get_sheets()
    expenses = sheets_mgr.get_all_expenses()
    summary = sheets_mgr.get_summary()

    # 計算總金額
    total = sum(float(e['金額']) for e in expenses) if expenses else 0

    return render_template('index.html',
                           expenses=expenses,
                           summary=summary,
                           total=total)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
