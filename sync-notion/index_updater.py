"""Update sync-rules-index.md after sync completion."""

from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv

from config import INDEX_FILE_DEFAULT

load_dotenv()


def update_index(action_descriptions: list[str]) -> None:
    """Append a new row to the 更新紀錄 table in sync-rules-index.md."""
    index_path = os.getenv("SYNC_RULES_INDEX", INDEX_FILE_DEFAULT)

    if not os.path.exists(index_path):
        print(f"  [WARN] Index file not found: {index_path}")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    description = "; ".join(action_descriptions)
    entry = f"| {today} | {description} |"

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.rstrip() + f"\n{entry}\n"

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
