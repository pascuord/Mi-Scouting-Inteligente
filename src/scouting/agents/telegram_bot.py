# src/scouting/agents/telegram_bot.py
from __future__ import annotations
import os
import requests
from dotenv import load_dotenv

from scouting.agents.pipeline import pipeline
import json
LAST_UPDATE_FILE = "/data/last_update_id.txt"

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"



def _load_last_update_id() -> int | None:
    try:
        with open(LAST_UPDATE_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None

def _save_last_update_id(uid: int) -> None:
    try:
        with open(LAST_UPDATE_FILE, "w", encoding="utf-8") as f:
            f.write(str(uid))
    except Exception as e:
        print(f"[telegram] no pude guardar last_update_id: {e}")

def get_last_message():
    if not BOT_TOKEN:
        print("[WARN] Falta TELEGRAM_BOT_TOKEN en .env")
        return None, None

    last_id = _load_last_update_id()
    params = {}
    if last_id is not None:
        params["offset"] = last_id + 1

    try:
        r = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=15)
        updates = r.json()
    except Exception as e:
        print(f"[telegram] error getUpdates: {e}")
        return None, None

    if not updates.get("ok"):
        return None, None
    results = updates.get("result", [])
    if not results:
        return None, None

    last_update = results[-1]
    upd_id = last_update.get("update_id")
    msg = last_update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text")

    # guardar offset para no repetir
    if upd_id is not None:
        _save_last_update_id(upd_id)

    return chat_id, text


def run_handler():
    chat_id, query = get_last_message()
    if not chat_id or not query:
        print("No hay mensaje nuevo.")
        return
    print(f"[telegram] Recibido de {chat_id}: {query}")
    pipeline.invoke({"query": query, "chat_id": str(chat_id)})

if __name__ == "__main__":
    run_handler()
