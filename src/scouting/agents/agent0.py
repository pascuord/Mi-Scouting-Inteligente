import os
import json
import polars as pl
import numpy as np
from typing import Tuple, Literal, Any, Dict, List
from sentence_transformers import SentenceTransformer
import faiss
from datetime import datetime

# ---- Modelo de embeddings ----
encoder = SentenceTransformer("intfloat/multilingual-e5-base")

def _now():
    return datetime.utcnow().isoformat() + "Z"

def _extract_info_from_meta(m: Any) -> Dict[str, Any]:
    """
    Acepta varios formatos de metadatos y devuelve un dict "plano"
    con los campos del jugador.
    Prioridades:
    - m["info"]                    # formato antiguo
    - m["metadata"]                # a veces se guarda como 'metadata'
    - m["document"] / m["doc"]     # otros formatos
    - si ya es plano (tiene campos como 'nombre', 'equipo', etc.), lo devuelve tal cual
    """
    if isinstance(m, dict):
        # Casos tipificados
        for key in ("info", "metadata", "document", "doc"):
            if key in m and isinstance(m[key], dict):
                return m[key]

        # Si ya se parece a un doc plano (heurística: tiene 'nombre' o 'equipo' o 'estadísticas')
        keys = set(m.keys())
        if {"nombre", "equipo"} & keys or "estadísticas" in keys or "stats" in keys:
            return m

    # Fallback mínimo: lo envolvemos
    return {"raw": m}

def _normalize_for_polars(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in doc.items():
        # Trata campos complejos como JSON string (seguro para Polars)
        if k in {
            "estadísticas",
            "rasgos_jugador",
            "rasgos_portero",
            "contract_details",
            "market_value_evolution",
            "transfer_history",
            "detalle",
        }:
            if v in (None, [], {}, [None]) or (isinstance(v, list) and all(x is None for x in v)):
                out[k] = None
            else:
                try:
                    out[k] = json.dumps(v, ensure_ascii=False)
                except Exception:
                    out[k] = None
        else:
            # Para todo lo demás, evitamos valores como [], [None], etc.
            if v in ([], {}, [None]) or (isinstance(v, list) and all(x is None for x in v)):
                out[k] = None
            else:
                out[k] = v
    return out



class Agente0VectorRetriever:
    def __init__(self, top_k: int = 3500):
        self.top_k = top_k
        self.encoder = encoder

        # Base de índices: desde env o por defecto
        self.base = os.getenv("INDICES_DIR", "/data_local/processed/indices")

        self.indices = {
            "jugador": {
                "faiss": os.path.join(self.base, "faiss_jugadores.index"),
                "meta":  os.path.join(self.base, "metadata_jugadores.json"),
            },
            "portero": {
                "faiss": os.path.join(self.base, "faiss_porteros.index"),
                "meta":  os.path.join(self.base, "metadata_porteros.json"),
            },
        }

        # Log de arranque, útil en Docker
        print(json.dumps({"ts": _now(), "event": "agent0_init", "base": self.base}))

    # --- detección simple por texto ---
    def detectar_tipo(self, query: str) -> Literal["jugador", "portero"]:
        if any(p in (query or "").lower() for p in ["portero", "arquero", "goalkeeper", "keeper"]):
            return "portero"
        return "jugador"

    # --- cargar metadatos robusto ---
    def _load_metadatas(self, path: str) -> List[Any]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # si viene envuelto
        if isinstance(data, dict):
            for k in ("metadatas", "items", "data", "docs"):
                if k in data and isinstance(data[k], list):
                    return data[k]
            # si es un dict que parece "entrada única", lo converimos en lista
            return [data]

        if isinstance(data, list):
            return data

        # último recurso
        return [data]

    def recuperar(self, query: str, tipo: str | None = None) -> Tuple[pl.DataFrame, str]:
        if tipo is None:
            tipo = self.detectar_tipo(query)

        faiss_path = self.indices[tipo]["faiss"]
        meta_path  = self.indices[tipo]["meta"]

        # --- carga FAISS ---
        if not os.path.exists(faiss_path):
            raise FileNotFoundError(f"[Agente0] No existe el índice FAISS: {faiss_path}")
        index = faiss.read_index(faiss_path)

        # --- carga metadatos ---
        if not os.path.exists(meta_path):
            raise FileNotFoundError(f"[Agente0] No existe el metadata JSON: {meta_path}")
        metadatas = self._load_metadatas(meta_path)
        if not isinstance(metadatas, list) or len(metadatas) == 0:
            raise ValueError(f"[Agente0] Metadata vacío o con formato inesperado: {meta_path}")

        # --- embedd query y búsqueda ---
        emb = self.encoder.encode(query, normalize_embeddings=True)
        emb = np.array([emb]).astype("float32")
        D, I = index.search(emb, self.top_k)

        # --- construir docs robustamente ---
        docs_raw: List[Dict[str, Any]] = []
        for idx in I[0]:
            if 0 <= idx < len(metadatas):
                try:
                    info = _extract_info_from_meta(metadatas[idx])
                    docs_raw.append(info)
                except Exception:
                    continue

        if not docs_raw:
            # Diagnóstico: muestra claves de la primera entrada
            example_keys = []
            try:
                first = metadatas[0]
                if isinstance(first, dict):
                    example_keys = list(first.keys())
            except Exception:
                pass
            diag = {
                "ts": _now(),
                "event": "agent0_no_docs_extracted",
                "tipo": tipo,
                "meta_path": meta_path,
                "first_meta_keys": example_keys,
                "metas_len": len(metadatas),
            }
            print(json.dumps(diag))
            raise KeyError(
                "[Agente0] No se pudo extraer ningún documento de metadatos. "
                "Revisa las claves disponibles en metadata_* y ajusta el extractor."
            )

        # normalizar para Polars
        docs = [_normalize_for_polars(doc) for doc in docs_raw]
        df = pl.DataFrame(docs)

        return df, tipo
