# src/scouting/etl/merge_data.py
"""
Une FotMob (db_fotmob.json) y Transfermarkt (db_transfermarkt.json) con INNER JOIN por nombre limpio.
- Entrada flexible: soporta varios formatos de db_transfermarkt.json:
    1) lista de jugadores
    2) {"leagues": { <liga>: {"players": [...] } } }
    3) {"players": [...]}
    4) otros dicts comunes (intenta detectar)
- Output:
    data/processed/merged/db_combinada.json
    data/processed/merged/db_jugadores.json
    data/processed/merged/db_porteros.json
"""

from __future__ import annotations
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv
import unidecode

# -------- Config y rutas --------
load_dotenv()
RAW_DIR = Path(os.getenv("RAW_DIR", "data/raw"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "data/processed"))
MERGED_DIR = Path(os.getenv("MERGED_DIR", str(PROCESSED_DIR / "merged")))

FOTMOB_PATH = RAW_DIR / "db_fotmob.json"
TM_PATH = RAW_DIR / "db_transfermarkt.json"

OUT_COMBINADA = MERGED_DIR / "db_combinada.json"
OUT_JUGADORES = MERGED_DIR / "db_jugadores.json"
OUT_PORTEROS  = MERGED_DIR / "db_porteros.json"

MERGED_DIR.mkdir(parents=True, exist_ok=True)


# -------- Helpers --------
def clean_text(s: str) -> str:
    if not s:
        return ""
    s = unidecode.unidecode(str(s)).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_portero_tm(main_position: str | None) -> bool:
    pos = (main_position or "").lower()
    return "goalkeeper" in pos or "portero" in pos or pos == "gk"

def pick_best_tm_match(candidates: List[Dict[str, Any]], fm_team: str | None) -> Dict[str, Any] | None:
    """Si hay varios TM con el mismo nombre limpio, escogemos el que mejor coincida por equipo."""
    if not candidates:
        return None
    if not fm_team:
        return candidates[0]
    fm_team_c = clean_text(fm_team)
    for c in candidates:
        if clean_text(c.get("team_name")) == fm_team_c:
            return c
    for c in candidates:
        tm_team = clean_text(c.get("team_name", ""))
        if fm_team_c and (fm_team_c in tm_team or tm_team in fm_team_c):
            return c
    return candidates[0]

def load_transfermarkt_players(tm_json: Any) -> List[Dict[str, Any]]:
    """
    Devuelve una lista de jugadores cualquiera que sea la forma del JSON de TM.
    Casos soportados:
     - list -> se devuelve tal cual
     - dict con 'leagues' -> aplana todos los players
     - dict con 'players' -> se devuelve ese array
     - dict genérico -> intenta encontrar arrays 'players' en valores
    """
    # Caso 1: ya es lista
    if isinstance(tm_json, list):
        print("[merge_data] Detectado formato TM: lista de jugadores")
        return tm_json

    # Caso 2: dict con 'players' directamente
    if isinstance(tm_json, dict) and "players" in tm_json and isinstance(tm_json["players"], list):
        print("[merge_data] Detectado formato TM: dict con clave 'players'")
        return tm_json["players"]

    # Caso 3: dict con 'leagues'
    if isinstance(tm_json, dict) and "leagues" in tm_json:
        leagues = tm_json["leagues"]
        players: List[Dict[str, Any]] = []
        if isinstance(leagues, dict):
            print("[merge_data] Detectado formato TM: dict con 'leagues' (objeto)")
            for _, data in leagues.items():
                arr = (data or {}).get("players")
                if isinstance(arr, list):
                    players.extend(arr)
        elif isinstance(leagues, list):
            print("[merge_data] Detectado formato TM: dict con 'leagues' (lista)")
            for league_entry in leagues:
                arr = (league_entry or {}).get("players")
                if isinstance(arr, list):
                    players.extend(arr)
        return players

    # Caso 4: dict genérico -> buscar arrays 'players' en valores
    if isinstance(tm_json, dict):
        print("[merge_data] Formato TM genérico: intentamos localizar 'players' en sub-objetos")
        players: List[Dict[str, Any]] = []
        for _, v in tm_json.items():
            if isinstance(v, dict) and "players" in v and isinstance(v["players"], list):
                players.extend(v["players"])
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "players" in item and isinstance(item["players"], list):
                        players.extend(item["players"])
        return players

    print("[merge_data] Formato TM no reconocido: devolviendo lista vacía")
    return []


def run() -> Dict[str, int]:
    # --- Cargar datos ---
    if not FOTMOB_PATH.exists():
        raise FileNotFoundError(f"No existe {FOTMOB_PATH}. Ejecuta collect_fotmob primero.")
    if not TM_PATH.exists():
        raise FileNotFoundError(f"No existe {TM_PATH}. Ejecuta collect_transfermarkt primero.")

    fotmob: List[Dict[str, Any]] = json.loads(FOTMOB_PATH.read_text(encoding="utf-8"))
    tm_json: Any = json.loads(TM_PATH.read_text(encoding="utf-8"))
    tm_players: List[Dict[str, Any]] = load_transfermarkt_players(tm_json)

    # --- Indexar TM por nombre limpio ---
    tm_index: Dict[str, List[Dict[str, Any]]] = {}
    for p in tm_players:
        name = p.get("name") or ""
        k = clean_text(name)
        if not k:
            continue
        tm_index.setdefault(k, []).append(p)

    # --- Inner join ---
    combined: List[Dict[str, Any]] = []
    misses_fm = 0

    for p_fm in fotmob:
        nombre_fm = p_fm.get("nombre") or ""
        k = clean_text(nombre_fm)
        if not k:
            continue
        tm_candidates = tm_index.get(k)
        if not tm_candidates:
            misses_fm += 1
            continue

        p_tm = pick_best_tm_match(tm_candidates, p_fm.get("equipo"))

        # Construcción registro final (portero vs jugador)
        if is_portero_tm(p_tm.get("main_position")):
            out = {
                "nombre": p_fm.get("nombre"),
                "equipo": p_fm.get("equipo") or p_tm.get("team_name"),
                "liga": p_fm.get("liga"),
                "pais": p_fm.get("pais"),
                "temporada": p_fm.get("temporada") or p_tm.get("season"),
                "url_jugador_fotmob": p_fm.get("url_jugador"),
                "url_jugador_transfermarkt": p_tm.get("profile_url"),
                "main_position": p_tm.get("main_position"),
                "foot": p_tm.get("foot"),
                "age": p_tm.get("age"),
                "height": p_tm.get("height"),
                "market_value": p_tm.get("market_value"),
                "contract_details": p_tm.get("contract_details"),
                "market_value_evolution": p_tm.get("market_value_evolution"),
                "transfer_history": p_tm.get("transfer_history"),
                "estadísticas": p_fm.get("estadísticas"),
                "rasgos_portero": p_fm.get("rasgos_portero"),
            }
        else:
            out = {
                "nombre": p_fm.get("nombre"),
                "equipo": p_fm.get("equipo") or p_tm.get("team_name"),
                "liga": p_fm.get("liga"),
                "pais": p_fm.get("pais"),
                "temporada": p_fm.get("temporada") or p_tm.get("season"),
                "url_jugador_fotmob": p_fm.get("url_jugador"),
                "url_jugador_transfermarkt": p_tm.get("profile_url"),
                "main_position": p_tm.get("main_position"),
                "other_positions": p_tm.get("other_positions"),
                "foot": p_tm.get("foot"),
                "age": p_tm.get("age"),
                "height": p_tm.get("height"),
                "market_value": p_tm.get("market_value"),
                "contract_details": p_tm.get("contract_details"),
                "market_value_evolution": p_tm.get("market_value_evolution"),
                "transfer_history": p_tm.get("transfer_history"),
                "estadísticas": p_fm.get("estadísticas"),
                "rasgos_jugador": p_fm.get("rasgos_jugador"),
            }
        combined.append(out)

    # --- Guardar combinada ---
    OUT_COMBINADA.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Separar porteros / jugadores ---
    porteros: List[Dict[str, Any]] = []
    jugadores: List[Dict[str, Any]] = []
    for p in combined:
        if is_portero_tm(p.get("main_position")):
            porteros.append(p)
        else:
            jugadores.append(p)

    OUT_PORTEROS.write_text(json.dumps(porteros, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JUGADORES.write_text(json.dumps(jugadores, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = {
        "fotmob_total": len(fotmob),
        "tm_total": len(tm_players),
        "combinados": len(combined),
        "fm_sin_match": misses_fm,
        "porteros": len(porteros),
        "jugadores": len(jugadores),
    }

    print(
        f"[merge_data] fotmob={stats['fotmob_total']} tm={stats['tm_total']} "
        f"-> combinados={stats['combinados']} (fm_sin_match={stats['fm_sin_match']}) | "
        f"porteros={stats['porteros']} jugadores={stats['jugadores']}"
    )
    print(f"[merge_data] OUT: {OUT_COMBINADA}")
    print(f"[merge_data] OUT: {OUT_PORTEROS}")
    print(f"[merge_data] OUT: {OUT_JUGADORES}")
    return OUT_JUGADORES, OUT_PORTEROS


if __name__ == "__main__":
    run()
