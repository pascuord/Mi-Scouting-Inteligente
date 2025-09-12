from __future__ import annotations
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv
import unidecode
from collections import defaultdict
from rapidfuzz import fuzz, process

# -------- Config y rutas --------
load_dotenv()

def get_absolute_path(path_str: str, default: str) -> Path:
    path = Path(path_str)
    # Si es relativo, interpretarlo como absoluto dentro del contenedor
    return path if path.is_absolute() else Path(default)

# En local: ./data/...     En Docker: /data/...
DATA_DIR = get_absolute_path(os.getenv("DATA_DIR", "/data"), "/data")
RAW_DIR = get_absolute_path(os.getenv("RAW_DIR", str(DATA_DIR / "raw")), DATA_DIR / "raw")
INTERIM_DIR = get_absolute_path(os.getenv("INTERIM_DIR", str(DATA_DIR / "interim")), DATA_DIR / "interim")
PROCESSED_DIR = get_absolute_path(os.getenv("PROCESSED_DIR", str(DATA_DIR / "processed")), DATA_DIR / "processed")
MERGED_DIR = get_absolute_path(os.getenv("MERGED_DIR", str(PROCESSED_DIR / "merged")), PROCESSED_DIR / "merged")


FOTMOB_PATH = Path("/data/raw/db_fotmob.json")
TM_PATH = Path("/data/raw/db_transfermarkt.json")

OUT_COMBINADA = MERGED_DIR / "db_combinada.json"
OUT_JUGADORES = MERGED_DIR / "db_jugadores.json"
OUT_PORTEROS  = MERGED_DIR / "db_porteros.json"
MERGED_DIR.mkdir(parents=True, exist_ok=True)

# -------- Apodos y utilidades --------
APODOS_HARDCODE = {
    'ezequiel avila': 'chimy avila',
    'flavien boyomo': 'enzo boyomo',
    'abderrahman': 'abde',
    'abdessamad': 'abde',
    'francisco': 'fran',
    'enrique': 'kike',
    'jose': 'pepe',
    'franciso': 'paco',
    'jose': 'jose maria'
}

def clean_name(name):
    if not name: return ""
    name = unidecode.unidecode(name.lower())
    name = re.sub(r'[^a-z0-9 ]', '', name)
    return re.sub(r'\s+', ' ', name).strip()

def tokenize(name): return clean_name(name).split()
def last_token(name): return tokenize(name)[-1] if tokenize(name) else ""

def pos_bucket(pos):
    pos = (pos or '').lower()
    if 'goalkeeper' in pos or 'portero' in pos: return 'GK'
    if any(k in pos for k in ['cb','rb','lb','df','def','back']): return 'DEF'
    if any(k in pos for k in ['mid','cm','am','dm','medio']): return 'MID'
    if any(k in pos for k in ['fw','st','wing','del','att','ext']): return 'FWD'
    return 'UNK'

def equipo_match(e1, e2): return clean_name(e1 or '') == clean_name(e2 or '')

def nombre_es_apodo(nombre_fm, nombre_tm):
    nombre_fm_clean = clean_name(nombre_fm)
    nombre_tm_clean = clean_name(nombre_tm)
    for original, apodo in APODOS_HARDCODE.items():
        if nombre_fm_clean.startswith(original) and nombre_tm_clean.startswith(apodo): return True
        if nombre_tm_clean.startswith(original) and nombre_fm_clean.startswith(apodo): return True
    return False

def nombre_tokens_parcial(tokens_fm, tokens_tm):
    set_fm = set(tokens_fm)
    set_tm = set(tokens_tm)
    comunes = set_fm & set_tm
    return len(comunes) >= 2 or set_fm.issubset(set_tm) or set_tm.issubset(set_fm)

def nombre_subtokens_con_apellido(tokens_fm, tokens_tm):
    if not tokens_fm or not tokens_tm: return False
    ap1, ap2 = tokens_fm[-1], tokens_tm[-1]
    if ap1 != ap2: return False
    nombre_fm = tokens_fm[0]
    return nombre_fm in tokens_tm or nombre_fm[:4] in tokens_tm[0][:4]

def score_candidato(p_fm, p_tm):
    score = 0
    if p_fm.get('age') and p_tm.get('age') and abs(p_fm['age'] - p_tm['age']) <= 1: score += 1
    if p_fm.get('main_position') and p_tm.get('main_position'):
        if pos_bucket(p_fm['main_position']) == pos_bucket(p_tm['main_position']): score += 1
    if p_fm.get('height') and p_tm.get('height') and p_fm['height'] == p_tm['height']: score += 1
    if equipo_match(p_fm.get('equipo'), p_tm.get('team_name')): score += 2
    return score

def is_portero(player):
    pos = (player.get('main_position') or '').lower()
    return 'goalkeeper' in pos or 'portero' in pos

# -------- Formatos TM --------
def load_transfermarkt_players(tm_json: Any) -> List[Dict[str, Any]]:
    if isinstance(tm_json, list): return tm_json
    if isinstance(tm_json, dict):
        if 'players' in tm_json and isinstance(tm_json['players'], list):
            return tm_json['players']
        if 'leagues' in tm_json:
            leagues = tm_json['leagues']
            players = []
            for val in leagues.values():
                arr = val.get('players') if isinstance(val, dict) else []
                if isinstance(arr, list): players.extend(arr)
            return players
        players = []
        for val in tm_json.values():
            if isinstance(val, dict) and 'players' in val:
                players.extend(val['players'])
        return players
    return []

# -------- Run --------
def run():
    fotmob = json.loads(FOTMOB_PATH.read_text(encoding="utf-8"))
    tm_json = json.loads(TM_PATH.read_text(encoding="utf-8"))
    tm_players = load_transfermarkt_players(tm_json)

    tm_by_name = defaultdict(list)
    index_por_apellido = defaultdict(list)
    for p in tm_players:
        cname = clean_name(p.get('name', ''))
        ap = last_token(p.get('name', ''))
        if cname: tm_by_name[cname].append(p)
        if ap: index_por_apellido[ap].append(p)

    combined, not_found = [], []

    for p_fm in fotmob:
        cname_fm = clean_name(p_fm.get('nombre', ''))
        candidatos = tm_by_name.get(cname_fm, [])

        if not candidatos:
            best_match = process.extractOne(
                p_fm.get('nombre', ''),
                [p.get('name', '') for p in tm_players],
                scorer=fuzz.WRatio
            )
            if best_match and best_match[1] >= 99:
                idx = [p.get('name', '') for p in tm_players].index(best_match[0])
                candidatos = [tm_players[idx]]

        if not candidatos:
            not_found.append(p_fm)
            continue

        p_tm_best = max(candidatos, key=lambda p: score_candidato(p_fm, p))
        tm_id = p_tm_best.get('profile_url') or p_tm_best.get('name')

        if is_portero(p_tm_best):
            out = {
                **p_fm,
                'url_jugador_transfermarkt': tm_id,
                'main_position': p_tm_best.get('main_position'),
                'foot': p_tm_best.get('foot'),
                'age': p_tm_best.get('age'),
                'height': p_tm_best.get('height'),
                'market_value': p_tm_best.get('market_value'),
                'contract_details': p_tm_best.get('contract_details'),
                'market_value_evolution': p_tm_best.get('market_value_evolution'),
                'transfer_history': p_tm_best.get('transfer_history'),
            }
        else:
            out = {
                **p_fm,
                'url_jugador_transfermarkt': tm_id,
                'main_position': p_tm_best.get('main_position'),
                'other_positions': p_tm_best.get('other_positions'),
                'foot': p_tm_best.get('foot'),
                'age': p_tm_best.get('age'),
                'height': p_tm_best.get('height'),
                'market_value': p_tm_best.get('market_value'),
                'contract_details': p_tm_best.get('contract_details'),
                'market_value_evolution': p_tm_best.get('market_value_evolution'),
                'transfer_history': p_tm_best.get('transfer_history'),
            }
        combined.append(out)

    # -------- Recuperación avanzada --------
    ya_emparejados_tm_ids = {p['url_jugador_transfermarkt'] for p in combined}
    extra_matches = []

    for p_fm in not_found:
        nombre_fm = p_fm.get('nombre', '')
        tokens_fm = tokenize(nombre_fm)
        ap_fm = tokens_fm[-1] if tokens_fm else ''
        candidatos = index_por_apellido.get(ap_fm, [])

        mejores = []
        for p_tm in candidatos:
            tokens_tm = tokenize(p_tm.get('name', ''))
            if not tokens_tm: continue
            if nombre_es_apodo(nombre_fm, p_tm.get('name', '')) or \
               (nombre_subtokens_con_apellido(tokens_fm, tokens_tm) and equipo_match(p_fm.get('equipo'), p_tm.get('team_name'))) or \
               (nombre_tokens_parcial(tokens_fm, tokens_tm) and equipo_match(p_fm.get('equipo'), p_tm.get('team_name'))):
                mejores.append((score_candidato(p_fm, p_tm), p_tm))

        if not mejores:
            continue

        mejores.sort(key=lambda x: x[0], reverse=True)
        _, p_tm_best = mejores[0]
        tm_id = p_tm_best.get('profile_url') or p_tm_best.get('name')
        if tm_id in ya_emparejados_tm_ids:
            continue

        ya_emparejados_tm_ids.add(tm_id)
        is_gk = pos_bucket(p_tm_best.get('main_position')) == 'GK'
        out = {
            **p_fm,
            'url_jugador_transfermarkt': tm_id,
            'main_position': p_tm_best.get('main_position'),
            'other_positions': p_tm_best.get('other_positions'),
            'foot': p_tm_best.get('foot'),
            'age': p_tm_best.get('age'),
            'height': p_tm_best.get('height'),
            'market_value': p_tm_best.get('market_value'),
            'contract_details': p_tm_best.get('contract_details'),
            'market_value_evolution': p_tm_best.get('market_value_evolution'),
            'transfer_history': p_tm_best.get('transfer_history'),
        }
        extra_matches.append(out)

    combined_total = combined + extra_matches
    OUT_COMBINADA.write_text(json.dumps(combined_total, ensure_ascii=False, indent=2), encoding="utf-8")

    porteros = [p for p in combined_total if is_portero(p)]
    jugadores = [p for p in combined_total if not is_portero(p)]
    OUT_PORTEROS.write_text(json.dumps(porteros, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_JUGADORES.write_text(json.dumps(jugadores, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ TOTAL FINALES: {len(combined_total)} jugadores (porteros: {len(porteros)}, jugadores: {len(jugadores)})")
    print(f"🧩 Usando recuperación avanzada: {len(extra_matches)} jugadores recuperados")
    print(f"📁 OUT: {OUT_COMBINADA}")
    print(f"📁 OUT: {OUT_PORTEROS}")
    print(f"📁 OUT: {OUT_JUGADORES}")
    print(f"📂 MERGED_DIR absoluto: {MERGED_DIR.resolve()}")

    return OUT_JUGADORES, OUT_PORTEROS

if __name__ == "__main__":
    run()
