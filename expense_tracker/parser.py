import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExpenseData:
    item: str           # 項目名稱
    amount: float       # 金額
    payer: str          # 付款人
    participants: list  # 參與者
    split_type: str     # 分攤方式：均分 / 指定

def parse_expense(text: str, sender_name: str = '我') -> Optional[ExpenseData]:
    """
    解析記帳文字

    格式範例：
    - 午餐 750           → 預設均分
    - 午餐 350 均分       → 均分
    - 午餐 350 均分 大哥 二姐 我  → 指定參與者均分
    - 掛號費 150 大哥出   → 大哥付的
    - 藥費 500 二姐付     → 二姐付的

    參數：
        text: 輸入文字
        sender_name: 發送者名稱（預設為「我」）

    回傳：
        ExpenseData 或 None（解析失敗）
    """
    text = text.strip()

    # 移除金額前的 $ 符號
    text = re.sub(r'\$\s*', '', text)

    # 情況1：只有「項目 金額」→ 預設均分
    pattern_simple = r'^(.+?)\s+(\d+(?:\.\d+)?)$'
    match_simple = re.match(pattern_simple, text)

    if match_simple:
        item = match_simple.group(1).strip()
        amount = float(match_simple.group(2))

        return ExpenseData(
            item=item,
            amount=amount,
            payer=sender_name,
            participants=[sender_name],
            split_type='均分'
        )

    # 情況2：「項目 金額 其他說明」
    pattern = r'^(.+?)\s+(\d+(?:\.\d+)?)\s+(.+)$'
    match = re.match(pattern, text)

    if not match:
        return None

    item = match.group(1).strip()
    amount = float(match.group(2))
    rest = match.group(3).strip()

    # 解析分攤方式和參與者
    parts = rest.split()

    if not parts:
        return None

    first_part = parts[0]

    # 均分
    if first_part == '均分':
        if len(parts) > 1:
            participants = parts[1:]
        else:
            participants = [sender_name]

        return ExpenseData(
            item=item,
            amount=amount,
            payer=sender_name,
            participants=participants,
            split_type='均分'
        )

    # 某人出/付（如：大哥出、二姐付）
    if first_part.endswith('出') or first_part.endswith('付'):
        payer = first_part[:-1]

        if len(parts) > 1:
            participants = parts[1:]
        else:
            participants = [payer]

        return ExpenseData(
            item=item,
            amount=amount,
            payer=payer,
            participants=participants,
            split_type='指定'
        )

    # 「均分」黏在一起，如「350均分」
    if '均分' in first_part:
        return ExpenseData(
            item=item,
            amount=amount,
            payer=sender_name,
            participants=[sender_name],
            split_type='均分'
        )

    # 其他情況：把 rest 當作參與者名單，預設均分
    participants = parts
    return ExpenseData(
        item=item,
        amount=amount,
        payer=sender_name,
        participants=participants,
        split_type='均分'
    )


def format_expense_confirm(data: ExpenseData) -> str:
    """格式化確認訊息"""
    participants_str = '、'.join(data.participants)
    msg = f"✅ 已記錄\n"
    msg += f"📝 {data.item}\n"
    msg += f"💰 ${data.amount:,.0f}\n"
    msg += f"💳 {data.payer} 付款\n"
    msg += f"👥 {participants_str} {data.split_type}"

    if data.split_type == '均分' and len(data.participants) > 1:
        share = data.amount / len(data.participants)
        msg += f"\n📊 每人 ${share:,.0f}"

    return msg


# 測試
if __name__ == '__main__':
    test_cases = [
        "午餐 750",              # 預設均分
        "午餐 350 均分",
        "午餐 350 均分 大哥 二姐 我",
        "掛號費 150 大哥出",
        "掛號費 150 大哥付",
        "看護費 2000 均分 大哥 二姐 我",
        "藥費 500.5 二姐出",
        "午餐 $600",             # 有 $ 符號
        "午餐 600 大哥 二姐 我",  # 只列參與者
    ]

    for text in test_cases:
        result = parse_expense(text, sender_name='我')
        print(f"輸入: {text}")
        print(f"結果: {result}")
        if result:
            print(format_expense_confirm(result))
        print("-" * 40)
