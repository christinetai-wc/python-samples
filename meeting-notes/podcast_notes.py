#!/usr/bin/env python3
"""Podcast 音訊下載 → Whisper 轉錄 → Gemini/Claude 整理筆記 → 存入 Notion"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 重用 yt_notes 的共用功能
from yt_notes import (
    create_notion_page,
    save_local,
    summarize_with_claude,
    summarize_with_gemini,
)

# 重用 transcribe_video 的轉錄功能
from transcribe_video import transcribe_segment, get_video_duration, extract_segment

# 載入文字後處理
from utils.text_cleanup import cleanup_text

SUMMARIZE_PROMPT_PODCAST = """請根據以下 Podcast 逐字稿，整理成一份詳細的繁體中文筆記。

節目名稱：{series}
單集標題：{title}

請包含以下各節（若該節無相關內容可省略）：

## 主題概述
說明這集 Podcast 的主要目的或背景（2-3 句）。

## 重點整理
詳細列出每個重點，每點說明核心內容，不要只寫標題，要有實質說明（每點 2-4 句）。

## 關鍵資訊
列出節目中提到的重要數據、人名、書名、產品名稱、專有名詞等。

## 結論與心得
總結這集的核心訊息。

逐字稿：
{text}

請用繁體中文回覆，內容務必詳盡具體。"""


def get_podcast_info(url: str) -> dict:
    """取得 Podcast 資訊"""
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--skip-download", url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 錯誤: {result.stderr.strip()}")
    return json.loads(result.stdout)


def download_audio(url: str, output_dir: str) -> Path:
    """下載 Podcast 音訊"""
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
        # fallback: 找任何音訊檔
        audio_files = list(Path(output_dir).glob("*.*"))
        audio_files = [f for f in audio_files if f.suffix in (".mp3", ".m4a", ".opus", ".webm", ".ogg")]

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
        # 短音訊直接轉錄
        print("正在轉錄...")
        segments, info = transcribe_segment(str(audio_path), lang, model_size)
        for seg in segments:
            text = cleanup_text(seg.text.strip())
            if text:
                all_texts.append(text)
    else:
        # 長音訊分段處理
        print(f"將分成 {num_chunks} 段轉錄")
        with tempfile.TemporaryDirectory() as temp_dir:
            for i in range(num_chunks):
                chunk_start = i * chunk_duration
                chunk_end = min(chunk_start + chunk_duration, total_duration)
                print(f"  轉錄第 {i+1}/{num_chunks} 段 ({int(chunk_start//60):02d}:{int(chunk_start%60):02d} - {int(chunk_end//60):02d}:{int(chunk_end%60):02d})...")

                chunk_audio = Path(temp_dir) / f"chunk_{i:03d}.mp3"
                extract_segment(str(audio_path), str(chunk_audio), chunk_start, chunk_end - chunk_start)

                segments, info = transcribe_segment(str(chunk_audio), lang, model_size)
                for seg in segments:
                    text = cleanup_text(seg.text.strip())
                    if text:
                        all_texts.append(text)

    elapsed = time.time() - start_time
    print(f"轉錄完成（{len(all_texts)} 句，耗時 {elapsed:.0f} 秒）")

    return " ".join(all_texts)


def summarize_podcast(text: str, title: str, series: str, ai: str) -> str:
    """用 AI 整理 Podcast 筆記"""
    prompt_text = SUMMARIZE_PROMPT_PODCAST.format(
        series=series, title=title, text=text,
    )

    if ai == "claude":
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("未設定 ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt_text}],
        )
        return message.content[0].text.strip()
    else:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("未設定 GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt_text)
        return response.text.strip()


def main():
    parser = argparse.ArgumentParser(description="Podcast → 轉錄 → 筆記 → Notion")
    parser.add_argument("url", help="Podcast 網址（Apple Podcasts、Spotify 等）")
    parser.add_argument("--lang", "-l", default="zh", help="音訊語言（預設 zh）")
    parser.add_argument("--model", "-m", default="base", help="Whisper 模型 tiny/base/small/medium（預設 base）")
    parser.add_argument("--ai", default="gemini", choices=["claude", "gemini"], help="AI 模型（預設 gemini）")
    parser.add_argument("--tag", "-t", action="append", default=[], help="Notion Tags（可多次指定）")
    parser.add_argument("--db", default=None, help="Notion Database ID（或設定 NOTION_YT_DATABASE_ID）")
    parser.add_argument("--no-notion", action="store_true", help="只產生本地筆記，不上傳 Notion")
    parser.add_argument("--save-local", action="store_true", help="同時儲存本地 Markdown")
    args = parser.parse_args()

    url = args.url

    # 1. 取得 Podcast 資訊
    print("正在取得 Podcast 資訊...")
    info = get_podcast_info(url)
    title = info.get("title", "未知標題")
    series = info.get("series", "")
    duration = info.get("duration_string", "")
    print(f"節目：{series}")
    print(f"標題：{title}")
    print(f"時長：{duration}")

    # 2. 下載音訊 + 轉錄
    with tempfile.TemporaryDirectory() as tmpdir:
        print("正在下載音訊...")
        audio_path = download_audio(url, tmpdir)
        print(f"音訊下載完成：{audio_path.name}")

        # 3. Whisper 轉錄
        print(f"正在用 Whisper ({args.model}) 轉錄...")
        text = transcribe_audio(audio_path, args.lang, args.model)

    if not text.strip():
        print("錯誤：轉錄內容為空")
        sys.exit(1)

    word_count = len(text)
    print(f"轉錄內容：{word_count} 字")

    # 4. AI 整理筆記
    print(f"正在用 {args.ai.capitalize()} 整理筆記...")
    notes = summarize_podcast(text, title, series, args.ai)
    print(f"筆記產生完成（{len(notes)} 字）")

    # 5. 頁面標題
    episode_num = info.get("episode_number", "")
    upload_date = info.get("upload_date", "")  # YYYYMMDD
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
    page_title = " ".join(parts)

    # 6. 儲存本地
    local_path = None
    if args.save_local or args.no_notion:
        local_path = save_local(page_title, notes, url)
        print(f"本地筆記：{local_path}")

    # 7. 上傳 Notion
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
