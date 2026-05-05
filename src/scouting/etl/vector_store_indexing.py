# src/scouting/etl/vector_store_indexing.py
from __future__ import annotations
import json, os, shutil, time
import faiss
import numpy as np
from typing import Any, Dict, List
from sentence_transformers import SentenceTransformer

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

# Logs utilitarios (opcional): si no los tienes, cámbialos por prints
try:
    from scouting.agents.common import get_indices_dir, jlog
except Exception:
    def get_indices_dir() -> str:
        return os.environ.get("INDICES_DIR", os.path.join(DATA_DIR, "processed", "indices"))
    def jlog(event: str, **kw):  # fallback
        print(json.dumps({"event": event, **kw}, ensure_ascii=False))

# --- Config ---
MODEL_NAME = "intfloat/multilingual-e5-base"

DB_JUGADORES = os.environ.get(
    "DB_JUGADORES",
    os.path.join(DATA_DIR, "processed", "merged", "db_jugadores.json")
)
DB_PORTEROS = os.environ.get(
    "DB_PORTEROS",
    os.path.join(DATA_DIR, "processed", "merged", "db_porteros.json")
)


# Nombres de salida (FAISS + metadata)
FAISS_FILENAMES = {
    "jug": ("faiss_jugadores.index", "metadata_jugadores.json"),
    "gk":  ("faiss_porteros.index",   "metadata_porteros.json"),
}

# Rutas donde intentaremos encontrar detalles por jugador (para enriquecer `info` si falta)
DETAILS_DIR_CANDIDATES = [
    os.path.join(DATA_DIR, "processed", "details"),
    os.path.join(DATA_DIR, "interim", "details"),
]

# ---------- helpers de normalización / enriquecimiento ----------

def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: str, obj: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _find_details_by_id(pid: Any, tipo: str) -> Dict | None:
    """
    Busca detalles por ID en distintas carpetas:
      /data/processed/details/{jugadores|porteros}/{id}.json
    """
    sub = "jugadores" if tipo == "jug" else "porteros"
    for base in DETAILS_DIR_CANDIDATES:
        cand = os.path.join(base, sub, f"{pid}.json")
        if os.path.exists(cand):
            try:
                return _load_json(cand)
            except Exception:
                pass
    return None

def _ensure_info_block(doc: Dict, tipo: str) -> Dict:
    """
    Devuelve un registro con shape:
      {"id": <id>, "nombre": <nombre>, "info": {...}}
    Si ya viene así, lo respeta. Si no, crea 'info' con lo que haya y enriquece si encuentra detalles por ID.
    """
    if isinstance(doc.get("info"), dict):
        # Garantizar clave 'nombre' raíz para metadatos
        return {"id": doc.get("id"), "nombre": doc.get("nombre") or doc["info"].get("nombre"), "info": doc["info"]}

    # No hay info; construimos un bloque base con mapping de claves más comunes
    if tipo == "jug":
        base_info = {
            "nombre": doc.get("nombre"),
            "nacionalidad": doc.get("nacionalidad"),
            "equipo": doc.get("equipo"),
            "liga": doc.get("liga"),
            "pais": doc.get("pais"),
            "temporada": doc.get("temporada"),
            "main_position": doc.get("main_position"),
            "other_positions": doc.get("other_positions"),
            "foot": doc.get("foot"),
            "age": doc.get("age"),
            "height": doc.get("height"),
            "market_value": doc.get("market_value"),
            "contract_details": doc.get("contract_details"),
            "market_value_evolution": doc.get("market_value_evolution"),
            "transfer_history": doc.get("transfer_history"),
            "estadísticas": doc.get("estadísticas"),
            "liga_stats": doc.get("liga_stats"),
            "temporada_stats": doc.get("temporada_stats"),
            "rasgos_jugador": doc.get("rasgos_jugador"),
        }
    else:
        base_info = {
            "nombre": doc.get("nombre"),
            "nacionalidad": doc.get("nacionalidad"),
            "equipo": doc.get("equipo"),
            "liga": doc.get("liga"),
            "pais": doc.get("pais"),
            "temporada": doc.get("temporada"),
            "main_position": doc.get("main_position"),
            "other_positions": doc.get("other_positions"),
            "foot": doc.get("foot"),
            "age": doc.get("age"),
            "height": doc.get("height"),
            "market_value": doc.get("market_value"),
            "contract_details": doc.get("contract_details"),
            "market_value_evolution": doc.get("market_value_evolution"),
            "transfer_history": doc.get("transfer_history"),
            "estadísticas": doc.get("estadísticas"),
            "liga_stats": doc.get("liga_stats"),
            "temporada_stats": doc.get("temporada_stats"),
            "rasgos_portero": doc.get("rasgos_portero"),
        }

    # Intentar enriquecer con detalles por ID (si existen)
    pid = doc.get("id")
    det = _find_details_by_id(pid, tipo)
    if isinstance(det, dict):
        # Mezcla no destructiva: preferimos valores que existan en 'det'
        for k, v in det.items():
            if v is not None:
                base_info[k] = v

    return {"id": doc.get("id"), "nombre": doc.get("nombre"), "info": base_info}

def _json_to_text(k: str, v: Any) -> str:
    """Convierte recursivamente JSON a texto plano tipo 'k: v' para embeddings."""
    if isinstance(v, dict):
        inner = ", ".join([_json_to_text(kk, vv) for kk, vv in v.items()])
        return f"{k}: {inner}" if k else inner
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            inner = "; ".join([_json_to_text("", vv) for vv in v])
        else:
            inner = str(v)
        return f"{k}: {inner}" if k else inner
    return f"{k}: {v}" if k else str(v)

def jugador_to_text(info: Dict) -> str:
    """
    Genera un texto rico desde `info` (no del doc raíz), para que el embedding
    incluya posiciones, pie, edad, altura, valor, stats, etc.
    """
    lines = []
    for k, v in info.items():
        try:
            lines.append(_json_to_text(k, v))
        except Exception:
            continue
    return "\n".join(lines)

# ---------- pipeline de indexado ----------

def index_to_faiss(json_file: str, out_dir: str, faiss_name: str, meta_name: str, encoder: SentenceTransformer, tipo: str):
    docs = _load_json(json_file)
    if not isinstance(docs, list):
        raise ValueError(f"{json_file} no es una lista JSON")

    # Asegurar shape con 'info'
    records: List[Dict] = [_ensure_info_block(doc, tipo) for doc in docs]

    # Textos para embeddings desde info
    textos = [jugador_to_text(rec["info"]) for rec in records]
    jlog("index_load", file=json_file, count=len(textos))

    # Embeddings (normalizados -> cos-sim ~ inner product)
    embeddings = encoder.encode(textos, batch_size=32, show_progress_bar=True, normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype=np.float32)

    # Metadatos (id, nombre, info completo)
    metadatas = [{"id": rec.get("id"), "nombre": rec.get("nombre") or rec["info"].get("nombre", ""), "info": rec["info"]} for rec in records]
    _save_json(os.path.join(out_dir, meta_name), metadatas)

    # FAISS
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, os.path.join(out_dir, faiss_name))
    jlog("index_write", dir=out_dir, faiss=faiss_name, meta=meta_name)

def sync_current(version_dir: str, base_dir: str):
    current = os.path.join(base_dir, "current")
    os.makedirs(current, exist_ok=True)
    # limpiar current
    for fname in os.listdir(current):
        try:
            os.remove(os.path.join(current, fname))
        except Exception:
            pass
    # copiar versión
    for fname in os.listdir(version_dir):
        shutil.copy2(os.path.join(version_dir, fname), os.path.join(current, fname))
    jlog("index_sync_current", version=os.path.basename(version_dir), current=current)

def run():
    base_dir = os.path.normpath(get_indices_dir())
    ts = time.strftime("%Y-%m-%d_%H%M%S")
    version_dir = os.path.join(base_dir, ts)
    os.makedirs(version_dir, exist_ok=True)

    jlog("index_start", model=MODEL_NAME, out=version_dir)
    encoder = SentenceTransformer(MODEL_NAME)

    # jugadores (tipo = "jug")
    if os.path.exists(DB_JUGADORES):
        faiss_name, meta_name = FAISS_FILENAMES["jug"]
        index_to_faiss(DB_JUGADORES, version_dir, faiss_name, meta_name, encoder, tipo="jug")
    else:
        jlog("index_warn_missing", file=DB_JUGADORES)

    # porteros (tipo = "gk")
    if os.path.exists(DB_PORTEROS):
        faiss_name, meta_name = FAISS_FILENAMES["gk"]
        index_to_faiss(DB_PORTEROS, version_dir, faiss_name, meta_name, encoder, tipo="gk")
    else:
        jlog("index_warn_missing", file=DB_PORTEROS)

    sync_current(version_dir, base_dir)
    jlog("index_done")
    print(f"[vector_store_indexing] OK -> {version_dir} + current")

if __name__ == "__main__":
    run()
