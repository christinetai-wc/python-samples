#!/usr/bin/env python3
"""One-time OAuth2 authorization script."""
import sys
import os

# Force unbuffered output
os.environ["PYTHONUNBUFFERED"] = "1"

from google_auth_oauthlib.flow import InstalledAppFlow

print("🔐 Google Calendar OAuth 授權\n", flush=True)

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json",
    ["https://www.googleapis.com/auth/calendar.readonly"],
)

print("啟動本地伺服器等待授權...", flush=True)
print("請在 Chrome 打開以下網址（會自動顯示）\n", flush=True)

creds = flow.run_local_server(
    port=8090,
    open_browser=False,
    prompt="consent",
)

with open("token.json", "w") as f:
    f.write(creds.to_json())

print("\n✅ token.json 已儲存！授權完成。", flush=True)
