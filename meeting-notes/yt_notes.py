#!/usr/bin/env python3
"""YouTube 字幕抓取 → Claude/Gemini 整理筆記 → 存入 Notion"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

# Notion API
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Notion rich_text 單段上限
RICH_TEXT_LIMIT = 2000


def get_video_info(url: str) -> dict:
    """取得影片標題等資訊"""
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--skip-download", url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 錯誤: {result.stderr.strip()}")
    return json.loads(result.stdout)


def download_subtitles(url: str, lang: str = "en") -> str:
    """下載字幕，回傳 VTT 內容"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 優先抓手動字幕，再抓自動產生
        cmd = [
            "yt-dlp",
            "--write-subs", "--write-auto-subs",
            "--sub-langs", lang,
            "--sub-format", "vtt",
            "--skip-download",
            "-o", f"{tmpdir}/%(id)s.%(ext)s",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"下載字幕失敗: {result.stderr.strip()}")

        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            raise RuntimeError(f"找不到 {lang} 字幕，請用 yt-dlp --list-subs <URL> 確認可用語言")

        return vtt_files[0].read_text(encoding="utf-8")


def parse_vtt(vtt_content: str) -> str:
    """解析 VTT 字幕為乾淨文字（去重複、去標籤）"""
    lines = vtt_content.split("\n")
    texts = []
    seen = set()

    for line in lines:
        line = line.strip()
        # 跳過 header、時間戳、空行
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if re.match(r"^\d{2}:\d{2}", line):
            continue
        # 跳過純數字行（cue index）
        if re.match(r"^\d+$", line):
            continue

        # 移除 HTML 標籤與 VTT position 標籤
        clean = re.sub(r"<[^>]+>", "", line)
        clean = clean.strip()

        if clean and clean not in seen:
            seen.add(clean)
            texts.append(clean)

    return " ".join(texts)


SUMMARIZE_PROMPT = """請根據以下 YouTube 影片字幕，整理成一份詳細的繁體中文筆記。

影片標題：{title}

請包含以下各節（若該節無相關內容可省略）：

## 主題概述
說明影片的主要目的或背景（2-3 句）。

## 重點整理
詳細列出每個重點，每點說明核心內容，不要只寫標題，要有實質說明（每點 2-4 句）。

## 關鍵資訊
列出影片中提到的重要數據、人名、產品名稱、技術名詞、網址等。

## 結論與心得
總結影片的核心訊息。

字幕內容：
{text}

請用繁體中文回覆，內容務必詳盡具體。"""


def summarize_with_claude(text: str, title: str) -> str:
    """用 Claude 產生結構化筆記"""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("未設定 ANTHROPIC_API_KEY（請在 .env 中設定）")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = SUMMARIZE_PROMPT.format(title=title, text=text[:100000])

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def summarize_with_gemini(text: str, title: str) -> str:
    """用 Gemini 產生結構化筆記"""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("未設定 GEMINI_API_KEY（請在 .env 中設定）")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = SUMMARIZE_PROMPT.format(title=title, text=text[:50000])

    response = model.generate_content(prompt)
    return response.text.strip()


def markdown_to_notion_blocks(md: str) -> list[dict]:
    """將 Markdown 轉換為 Notion API block 格式"""
    blocks = []
    lines = md.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # 標題
        if line.startswith("### "):
            blocks.append(_heading_block(3, line[4:].strip()))
        elif line.startswith("## "):
            blocks.append(_heading_block(2, line[3:].strip()))
        elif line.startswith("# "):
            blocks.append(_heading_block(1, line[2:].strip()))
        # 無序列表
        elif re.match(r"^[-*] ", line):
            text = line.lstrip("-* ").strip()
            blocks.append(_list_item_block("bulleted_list_item", text))
        # 有序列表
        elif re.match(r"^\d+\. ", line):
            text = re.sub(r"^\d+\.\s*", "", line).strip()
            blocks.append(_list_item_block("numbered_list_item", text))
        # 空行跳過
        elif not line.strip():
            pass
        # 一般段落
        else:
            # 收集連續非空行為同一段落
            para_lines = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not _is_block_start(lines[i + 1]):
                i += 1
                para_lines.append(lines[i])
            text = " ".join(l.strip() for l in para_lines)
            blocks.append(_paragraph_block(text))

        i += 1

    return blocks


def _is_block_start(line: str) -> bool:
    """判斷是否為新 block 的開頭"""
    if line.startswith(("#", "- ", "* ")):
        return True
    if re.match(r"^\d+\. ", line):
        return True
    return False


def _rich_text(text: str) -> list[dict]:
    """建立 rich_text 陣列，自動切分超過 2000 字的文字"""
    chunks = []
    while text:
        chunks.append({"type": "text", "text": {"content": text[:RICH_TEXT_LIMIT]}})
        text = text[RICH_TEXT_LIMIT:]
    return chunks


def _heading_block(level: int, text: str) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {"rich_text": _rich_text(text)}}


def _paragraph_block(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(text)}}


def _list_item_block(block_type: str, text: str) -> dict:
    return {"object": "block", "type": block_type, block_type: {"rich_text": _rich_text(text)}}


def create_notion_page(
    title: str,
    notes: str,
    video_url: str,
    database_id: str,
    tags: list[str] | None = None,
) -> str:
    """建立 Notion 頁面，回傳頁面 URL"""
    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("未設定 NOTION_TOKEN（請在 .env 中設定）")

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    # 將筆記轉為 Notion blocks
    blocks = markdown_to_notion_blocks(notes)

    # 在最前面嵌入影片
    link_block = {
        "object": "block",
        "type": "embed",
        "embed": {"url": video_url},
    }
    blocks.insert(0, link_block)

    # Notion API 每次最多 100 個 blocks
    first_batch = blocks[:100]
    remaining = blocks[100:]

    from datetime import date as _date

    body = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "Date": {"date": {"start": _date.today().isoformat()}},
            **({"Tags": {"multi_select": [{"name": t} for t in tags]}} if tags else {}),
        },
        "children": first_batch,
    }

    with httpx.Client(timeout=30) as client:
        # 建立頁面
        resp = client.post(f"{NOTION_API}/pages", headers=headers, json=body)
        resp.raise_for_status()
        page = resp.json()
        page_id = page["id"]
        page_url = page.get("url", "")

        # 追加剩餘 blocks
        while remaining:
            batch = remaining[:100]
            remaining = remaining[100:]
            resp = client.patch(
                f"{NOTION_API}/blocks/{page_id}/children",
                headers=headers,
                json={"children": batch},
            )
            resp.raise_for_status()

    return page_url


def save_local(title: str, notes: str, video_url: str) -> Path:
    """儲存筆記到本地檔案"""
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", title)[:80]
    filename = f"{safe_name} 筆記.md"
    filepath = Path(__file__).parent / filename

    content = f"# {title}\n\n> {video_url}\n\n{notes}\n"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="YouTube 字幕 → 筆記 → Notion")
    parser.add_argument("url", help="YouTube 影片網址")
    parser.add_argument("--lang", "-l", default="en", help="字幕語言（預設 en）")
    parser.add_argument("--db", default=None, help="Notion Database ID（或設定 NOTION_YT_DATABASE_ID）")
    parser.add_argument("--ai", default="gemini", choices=["claude", "gemini"], help="AI 模型（預設 gemini）")
    parser.add_argument("--tag", "-t", action="append", default=[], help="Notion Tags（可多次指定，如 -t 英文 -t Podcast）")
    parser.add_argument("--no-notion", action="store_true", help="只產生本地筆記，不上傳 Notion")
    parser.add_argument("--save-local", action="store_true", help="同時儲存本地 Markdown")
    args = parser.parse_args()

    url = args.url
    lang = args.lang

    # 1. 取得影片資訊
    print("正在取得影片資訊...")
    info = get_video_info(url)
    title = info.get("title", "未知標題")
    print(f"影片標題：{title}")

    # 2. 下載字幕
    print(f"正在下載 {lang} 字幕...")
    vtt = download_subtitles(url, lang)

    # 3. 解析字幕
    print("正在解析字幕...")
    text = parse_vtt(vtt)
    word_count = len(text.split())
    print(f"字幕內容：{word_count} 個詞")

    if not text.strip():
        print("錯誤：字幕內容為空")
        sys.exit(1)

    # 4. AI 整理筆記
    ai = args.ai
    print(f"正在用 {ai.capitalize()} 整理筆記...")
    if ai == "claude":
        notes = summarize_with_claude(text, title)
    else:
        notes = summarize_with_gemini(text, title)
    print(f"筆記產生完成（{len(notes)} 字）")

    # 5. 儲存本地（--no-notion 或 --save-local 時）
    local_path = None
    if args.save_local or args.no_notion:
        local_path = save_local(title, notes, url)
        print(f"本地筆記：{local_path}")

    # 6. 上傳 Notion
    if not args.no_notion:
        db_id = args.db or os.getenv("NOTION_YT_DATABASE_ID", "")
        if not db_id:
            print("錯誤：未指定 Notion Database ID")
            print("請用 --db <ID> 或設定環境變數 NOTION_YT_DATABASE_ID")
            sys.exit(1)

        print("正在建立 Notion 頁面...")
        page_url = create_notion_page(title, notes, url, db_id, tags=args.tag)
        print(f"Notion 頁面：{page_url}")

        # 上傳成功後刪除本地檔（除非有 --save-local）
        if local_path and not args.save_local:
            local_path.unlink()
            print("已刪除本地暫存檔")

    print("完成！")


if __name__ == "__main__":
    main()
