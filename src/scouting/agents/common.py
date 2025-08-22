import os, json, sys, datetime
from dotenv import load_dotenv
import logging

load_dotenv()  # lee .env si existe

# ---------- logging JSON a stdout ----------
_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"), handlers=[_handler], format="%(message)s")
log = logging.getLogger("scouting")

def jlog(event: str, **kw):
    log.info(json.dumps({"ts": datetime.datetime.utcnow().isoformat()+"Z", "event": event, **kw}))

# ---------- env helpers ----------
def env_str(key: str, default: str="") -> str:
    v = os.getenv(key)
    return v if v not in (None, "") else default

def env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default

def get_indices_dir() -> str:
    # por defecto usamos data/processed/indices/current
    return env_str("INDICES_DIR", os.path.join("data","processed","indices","current"))

def get_openai_model_supervisor() -> str:
    return env_str("OPENAI_MODEL_SUPERVISOR", "gpt-4o-mini")

def get_openai_key() -> str:
    return env_str("OPENAI_API_KEY", "")

def get_telegram_token() -> str:
    return env_str("TELEGRAM_BOT_TOKEN", "")
