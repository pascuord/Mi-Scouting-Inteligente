import os, json, sys, datetime
from dotenv import load_dotenv
import logging
from typing import Final

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq

load_dotenv()  # lee .env si existe

# ---------- logging JSON a stdout ----------
_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"), handlers=[_handler], format="%(message)s")
log = logging.getLogger("scouting")
DEFAULT_LLM_PROVIDER: Final[str] = "openai"

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
    # por defecto usamos data/processed/indices
    return env_str("INDICES_DIR", os.path.join("data","processed","indices"))

def get_current_indices_dir() -> str:
    return os.path.join(get_indices_dir(), "current")

def get_openai_model_supervisor() -> str:
    return env_str("OPENAI_MODEL_SUPERVISOR", "gpt-4o-mini")

def get_openai_key() -> str:
    # Credencial sensible gestionada siempre desde variables de entorno.
    return os.getenv("OPENAI_API_KEY", "")

def get_llm_provider() -> str:
    return env_str("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).lower()

def get_telegram_token() -> str:
    return env_str("TELEGRAM_BOT_TOKEN", "")

def build_global_llm(temperature: float = 0.0) -> BaseChatModel:
    provider = get_llm_provider()
    if provider == "openai":
        return ChatOpenAI(
            model=get_openai_model_supervisor(),
            temperature=temperature,
            api_key=get_openai_key(),
        )
    if provider == "groq":
        return ChatGroq(
            model_name=env_str("GROQ_MODEL_SUPERVISOR", "llama-3.3-70b-versatile"),
            temperature=temperature,
            groq_api_key=os.getenv("GROQ_API_KEY"),
        )
    raise ValueError(f"Proveedor LLM no soportado: {provider}")
