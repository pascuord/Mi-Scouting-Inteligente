# src/scouting/agents/telegram_bot.py
from __future__ import annotations
import os
import requests
from dotenv import load_dotenv
import time

from scouting.agents.pipeline import pipeline
import json
def get_data_dir() -> str:
    # 1. Prioridad: Variable de entorno (si es absoluta)
    env_data = os.getenv("DATA_DIR")
    if env_data and os.path.isabs(env_data):
        return env_data
    
    # 2. Fallback: Buscar carpeta 'data' en la raíz del repo
    import pathlib
    root_repo = pathlib.Path(__file__).resolve().parents[3]
    local_data = root_repo / "data"
    
    # Si no existe y estamos en Docker, quizás /data sí exista
    if not local_data.exists() and os.path.exists("/data"):
        return "/data"
        
    return str(local_data)

DATA_DIR = get_data_dir()
LAST_UPDATE_FILE = os.path.join(DATA_DIR, "last_update_id.txt")

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
    """Procesa el último mensaje si existe."""
    chat_id, query = get_last_message()
    if chat_id and query:
        print(f"[telegram] 📥 Recibido de {chat_id}: {query}")
        # Aquí es donde ocurre la magia del TFM
        pipeline.invoke({"query": query, "chat_id": str(chat_id)})
        return True
    return False

def start_bot():
    """Bucle infinito para mantener el bot vivo."""
    print("🚀 Scouting Bot ONLINE y escuchando mensajes...")
    print("Pulse Ctrl+C para detener.")
    
    while True:
        try:
            # Intentamos procesar. Si no hay mensaje, no pasa nada.
            hay_mensaje = run_handler()
            
            # Si procesamos un mensaje, esperamos poco para ver si hay más.
            # Si no hay nada, esperamos 2 segundos para no banear la IP.
            time.sleep(1 if hay_mensaje else 2)
            
        except KeyboardInterrupt:
            print("\n🛑 Bot detenido manualmente.")
            break
        except Exception as e:
            print(f"⚠️ Error inesperado: {e}")
            time.sleep(5) # Esperamos un poco más si hay error de conexión

if __name__ == "__main__":
    start_bot()
