#!/usr/bin/env python3
"""YouTube / Podcast 網址 → 筆記 → Notion

自動判斷來源類型：
- YouTube：優先抓字幕，無字幕則 fallback Whisper 轉錄
- Podcast（Apple Podcasts 等）：下載音訊 → Whisper 轉錄
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import date as _date
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

# 重用 transcribe_video 的轉錄功能
from transcribe_video import transcribe_segment, get_video_duration, extract_segment
from utils.text_cleanup import cleanup_text

# Notion API
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
RICH_TEXT_LIMIT = 2000

# YouTube 網域判斷
YOUTUBE_DOMAINS = ("youtube.com", "youtu.be", "youtube-nocookie.com")

SUMMARIZE_PROMPT = """請根據以下{source_type}內容，整理成一份詳細的繁體中文筆記。

{header}

請包含以下各節（若該節無相關內容可省略）：

## 主題概述
說明主要目的或背景（2-3 句）。

## 重點整理
詳細列出每個重點，每點說明核心內容，不要只寫標題，要有實質說明（每點 2-4 句）。

## 關鍵資訊
列出提到的重要數據、人名、書名、產品名稱、專有名詞等。

## 結論與心得
總結核心訊息。

內容：
{text}

請用繁體中文回覆，內容務必詳盡具體。"""


# ── 來源判斷 ──────────────────────────────────────────────

def is_youtube(url: str) -> bool:
    """判斷是否為 YouTube 網址"""
    return any(domain in url for domain in YOUTUBE_DOMAINS)


# ── 資訊取得 ──────────────────────────────────────────────

def get_media_info(url: str) -> dict:
    """取得影片/Podcast 資訊"""
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--skip-download", url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 錯誤: {result.stderr.strip()}")
    return json.loads(result.stdout)


# ── 字幕相關 ──────────────────────────────────────────────

def download_subtitles(url: str, lang: str = "en") -> str | None:
    """下載字幕，回傳 VTT 內容。找不到則回傳 None"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--write-subs", "--write-auto-subs",
            "--sub-langs", lang,
            "--sub-format", "vtt",
            "--skip-download",
            "-o", f"{tmpdir}/%(id)s.%(ext)s",
            url,
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            return None
        return vtt_files[0].read_text(encoding="utf-8")


def parse_vtt(vtt_content: str) -> str:
    """解析 VTT 字幕為乾淨文字"""
    lines = vtt_content.split("\n")
    texts = []
    seen = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if re.match(r"^\d{2}:\d{2}", line):
            continue
        if re.match(r"^\d+$", line):
            continue
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if clean and clean not in seen:
            seen.add(clean)
            texts.append(clean)

    return " ".join(texts)


# ── 音訊下載與轉錄 ────────────────────────────────────────

def download_audio(url: str, output_dir: str) -> Path:
    """下載音訊"""
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "-o", f"{output_dir}/%(id)s.%(ext)s",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"下載音訊失敗: {result.stderr.strip()}")

    audio_files = list(Path(output_dir).glob("*.mp3"))
    if not audio_files:
        audio_files = [
            f for f in Path(output_dir).glob("*.*")
            if f.suffix in (".mp3", ".m4a", ".opus", ".webm", ".ogg")
        ]
    if not audio_files:
        raise RuntimeError("下載音訊失敗：找不到音訊檔案")

    return audio_files[0]


def transcribe_audio(audio_path: Path, lang: str, model_size: str, chunk_duration: int = 1800) -> str:
    """轉錄音訊為文字（支援分段處理長音訊）"""
    total_duration = get_video_duration(str(audio_path))
    if not total_duration:
        raise RuntimeError("無法取得音訊時長，請確保已安裝 ffmpeg")

    duration_min = int(total_duration // 60)
    duration_sec = int(total_duration % 60)
    print(f"音訊時長：{duration_min} 分 {duration_sec} 秒")

    num_chunks = int((total_duration + chunk_duration - 1) / chunk_duration)
    all_texts = []
    start_time = time.time()

    if num_chunks == 1:
        print("正在轉錄...")
        segments, info = transcribe_segment(str(audio_path), lang, model_size)
        for seg in segments:
            text = cleanup_text(seg.text.strip())
            if text:
                all_texts.append(text)
    else:
        print(f"將分成 {num_chunks} 段轉錄")
        with tempfile.TemporaryDirectory() as temp_dir:
            for i in range(num_chunks):
                chunk_start = i * chunk_duration
                chunk_end = min(chunk_start + chunk_duration, total_duration)
                print(f"  轉錄第 {i+1}/{num_chunks} 段 ({int(chunk_start//60):02d}:{int(chunk_start%60):02d} - {int(chunk_end//60):02d}:{int(chunk_end%60):02d})...")

                chunk_audio = Path(temp_dir) / f"chunk_{i:03d}.webm"
                extract_segment(str(audio_path), str(chunk_audio), chunk_start, chunk_end - chunk_start)

                segments, info = transcribe_segment(str(chunk_audio), lang, model_size)
                for seg in segments:
                    text = cleanup_text(seg.text.strip())
                    if text:
                        all_texts.append(text)

    elapsed = time.time() - start_time
    print(f"轉錄完成（{len(all_texts)} 句，耗時 {elapsed:.0f} 秒）")

    return " ".join(all_texts)


# ── AI 整理筆記 ───────────────────────────────────────────

def summarize(text: str, title: str, ai: str, series: str = "") -> str:
    """用 AI 產生結構化筆記"""
    if series:
        source_type = "Podcast 逐字稿"
        header = f"節目名稱：{series}\n單集標題：{title}"
    else:
        source_type = "影片字幕"
        header = f"影片標題：{title}"

    prompt = SUMMARIZE_PROMPT.format(
        source_type=source_type, header=header, text=text,
    )

    if ai == "claude":
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("未設定 ANTHROPIC_API_KEY（請在 .env 中設定）")
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt[:100000]}],
        )
        return message.content[0].text.strip()
    else:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("未設定 GEMINI_API_KEY（請在 .env 中設定）")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt[:50000])
        return response.text.strip()


# ── Notion ────────────────────────────────────────────────

def markdown_to_notion_blocks(md: str) -> list[dict]:
    """將 Markdown 轉換為 Notion API block 格式"""
    blocks = []
    lines = md.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("### "):
            blocks.append(_heading_block(3, line[4:].strip()))
        elif line.startswith("## "):
            blocks.append(_heading_block(2, line[3:].strip()))
        elif line.startswith("# "):
            blocks.append(_heading_block(1, line[2:].strip()))
        elif re.match(r"^[-*] ", line):
            text = line.lstrip("-* ").strip()
            blocks.append(_list_item_block("bulleted_list_item", text))
        elif re.match(r"^\d+\. ", line):
            text = re.sub(r"^\d+\.\s*", "", line).strip()
            blocks.append(_list_item_block("numbered_list_item", text))
        elif not line.strip():
            pass
        else:
            para_lines = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not _is_block_start(lines[i + 1]):
                i += 1
                para_lines.append(lines[i])
            text = " ".join(l.strip() for l in para_lines)
            blocks.append(_paragraph_block(text))

        i += 1

    return blocks


def _is_block_start(line: str) -> bool:
    if line.startswith(("#", "- ", "* ")):
        return True
    if re.match(r"^\d+\. ", line):
        return True
    return False


def _rich_text(text: str) -> list[dict]:
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
    source_url: str,
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

    blocks = markdown_to_notion_blocks(notes)

    # 在最前面嵌入來源連結
    link_block = {
        "object": "block",
        "type": "embed",
        "embed": {"url": source_url},
    }
    blocks.insert(0, link_block)

    first_batch = blocks[:100]
    remaining = blocks[100:]

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
        resp = client.post(f"{NOTION_API}/pages", headers=headers, json=body)
        resp.raise_for_status()
        page = resp.json()
        page_id = page["id"]
        page_url = page.get("url", "")

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


# ── 本地儲存 ──────────────────────────────────────────────

def save_local(title: str, notes: str, source_url: str) -> Path:
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", title)[:80]
    filename = f"{safe_name} 筆記.md"
    filepath = Path(__file__).parent / filename
    content = f"# {title}\n\n> {source_url}\n\n{notes}\n"
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 標題組合 ──────────────────────────────────────────────

def build_title(info: dict, is_yt: bool) -> str:
    """組合頁面標題"""
    title = info.get("title", "未知標題")

    if is_yt:
        return title

    # Podcast：【節目】EP集數 標題 (日期)
    series = info.get("series", "")
    episode_num = info.get("episode_number", "")
    upload_date = info.get("upload_date", "")
    if upload_date:
        upload_date = f"{upload_date[:4]}/{upload_date[4:6]}/{upload_date[6:]}"

    parts = []
    if series:
        parts.append(f"【{series}】")
    if episode_num:
        parts.append(f"EP{episode_num}")
    parts.append(title)
    if upload_date:
        parts.append(f"({upload_date})")
    return " ".join(parts)


# ── 主程式 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube / Podcast → 筆記 → Notion")
    parser.add_argument("url", help="YouTube 或 Podcast 網址")
    parser.add_argument("--lang", "-l", default=None, help="語言（YouTube 預設 en，Podcast 預設 zh）")
    parser.add_argument("--model", "-m", default="base", help="Whisper 模型 tiny/base/small/medium（預設 base）")
    parser.add_argument("--ai", default="gemini", choices=["claude", "gemini"], help="AI 模型（預設 gemini）")
    parser.add_argument("--tag", "-t", action="append", default=[], help="Notion Tags（可多次指定）")
    parser.add_argument("--db", default=None, help="Notion Database ID（或設定 NOTION_YT_DATABASE_ID）")
    parser.add_argument("--no-notion", action="store_true", help="只產生本地筆記，不上傳 Notion")
    parser.add_argument("--save-local", action="store_true", help="同時儲存本地 Markdown")
    args = parser.parse_args()

    url = args.url
    is_yt = is_youtube(url)

    # 預設語言：YouTube=en, Podcast=zh
    lang = args.lang or ("en" if is_yt else "zh")

    # 1. 取得資訊
    source_label = "影片" if is_yt else "Podcast"
    print(f"正在取得{source_label}資訊...")
    info = get_media_info(url)
    title = info.get("title", "未知標題")
    series = info.get("series", "")
    duration = info.get("duration_string", "")

    if series:
        print(f"節目：{series}")
    print(f"標題：{title}")
    if duration:
        print(f"時長：{duration}")

    # 2. 取得文字內容
    text = None

    # YouTube：先嘗試字幕
    if is_yt:
        vtt = download_subtitles(url, lang)
        if vtt:
            print("正在解析字幕...")
            text = parse_vtt(vtt)
            if text.strip():
                word_count = len(text.split())
                print(f"字幕內容：{word_count} 個詞")
            else:
                text = None

    # 無字幕或 Podcast：Whisper 轉錄
    if not text:
        if is_yt:
            print("找不到字幕，改用 Whisper 轉錄...")
        with tempfile.TemporaryDirectory() as tmpdir:
            print("正在下載音訊...")
            audio_path = download_audio(url, tmpdir)
            print(f"音訊下載完成：{audio_path.name}")
            whisper_lang = "zh" if lang.startswith("zh") else lang
            print(f"正在用 Whisper ({args.model}) 轉錄...")
            text = transcribe_audio(audio_path, whisper_lang, args.model)

    if not text.strip():
        print("錯誤：內容為空")
        sys.exit(1)

    # 3. AI 整理筆記
    print(f"正在用 {args.ai.capitalize()} 整理筆記...")
    notes = summarize(text, title, args.ai, series=series)
    print(f"筆記產生完成（{len(notes)} 字）")

    # 4. 組合標題
    page_title = build_title(info, is_yt)

    # 5. 儲存本地
    local_path = None
    if args.save_local or args.no_notion:
        local_path = save_local(page_title, notes, url)
        print(f"本地筆記：{local_path}")

    # 6. 上傳 Notion
    if not args.no_notion:
        db_id = args.db or os.getenv("NOTION_YT_DATABASE_ID", "")
        if not db_id:
            print("錯誤：未指定 Notion Database ID")
            print("請用 --db <ID> 或設定環境變數 NOTION_YT_DATABASE_ID")
            sys.exit(1)

        print("正在建立 Notion 頁面...")
        page_url = create_notion_page(page_title, notes, url, db_id, tags=args.tag)
        print(f"Notion 頁面：{page_url}")

        if local_path and not args.save_local:
            local_path.unlink()
            print("已刪除本地暫存檔")

    print("完成！")


if __name__ == "__main__":
    main()
