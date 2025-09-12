# src/scouting/agents/agente2.py
from __future__ import annotations
import json, re, unicodedata
from typing import List, Tuple, Literal, Dict, Any
import numpy as np
import re
import polars as pl
from sentence_transformers import SentenceTransformer, util
from typing import Set, Dict, List, Any, Literal
from collections import defaultdict


def _norm(s: str) -> str:
    t = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")

def _safe_json(d: Any) -> Dict[str, Any]:
    if isinstance(d, dict):
        return d
    if isinstance(d, str) and d.strip():
        try:
            return json.loads(d)
        except Exception:
            return {}
    return {}


STAT_DESCRIPTIONS_JUGADORES = {
    "Goals": "Total de goles anotados por el jugador. Refleja su capacidad como finalizador.",
    "xG": "Goles esperados generados según la calidad de los disparos. Mide su capacidad para encontrar buenas posiciones de remate.",
    "xGOT": "Goles esperados una vez que el disparo va a portería. Indica la calidad real de sus remates a puerta.",
    "xG excl. penalty": "Goles esperados sin incluir penaltis. Útil para evaluar la amenaza real en juego abierto.",
    "Shots": "Cantidad total de disparos realizados. Un valor alto indica protagonismo ofensivo.",
    "Shots on target": "Disparos que fueron entre los tres palos. Muestra precisión en la finalización.",
    
    "Assists": "Pases que acabaron en gol. Refleja capacidad para asistir con éxito.",
    "xA": "Asistencias esperadas según la posición y calidad del pase. Indica potencial creativo incluso si no hubo gol.",
    "Accurate passes": "Pases completados con éxito al compañero. Mide fiabilidad y precisión en circulación.",
    "Pass accuracy": "Porcentaje total de acierto en pases. Indica seguridad con el balón.",
    "Accurate long balls": "Pases largos completados con éxito. Refleja visión y precisión en desplazamientos largos.",
    "Long ball accuracy": "Porcentaje de acierto en balones largos. Cuanto más alto, mejor capacidad de distribución en largo.",
    "Chances created": "Ocasiones claras de gol generadas. Mide impacto creativo directo en ataque.",
    "Successful crosses": "Centros completados con éxito. Muy relevante en extremos y laterales ofensivos.",
    "Cross accuracy": "Porcentaje de centros que llegaron a un compañero. Indica precisión desde banda.",
    
    "Dribbles": "Regates exitosos frente a un rival. Mide capacidad de desequilibrio individual.",
    "Dribbles success rate": "Porcentaje de éxito en regates. Refleja eficiencia en el uno contra uno.",
    "Touches": "Número total de toques de balón. Indica participación en el juego.",
    "Touches in opposition box": "Toques dentro del área rival. Mide presencia ofensiva en zonas peligrosas.",
    "Dispossessed": "Veces que perdió el balón por presión rival. Un percentil alto indica que pierde muy pocos balones.",
    "Fouls won": "Faltas recibidas. Muestra cuánto desestabiliza al rival con el balón.",
    
    "Tackles won": "Entradas exitosas en las que recuperó el balón. Indica agresividad defensiva efectiva.",
    "Tackles won %": "Porcentaje de éxito en entradas. Cuanto más alto, más eficiente defensivamente.",
    "Duels won": "Duelos individuales ganados. Relevante para perfiles rocosos y dominantes.",
    "Duels won %": "Porcentaje de duelos individuales ganados. Mide fiabilidad en el cuerpo a cuerpo.",
    "Aerials won": "Duelos aéreos ganados. Fundamental en centrales dominantes o delanteros tanque.",
    "Aerials won %": "Porcentaje de éxito en duelos aéreos. Indica solidez por arriba.",
    "Interceptions": "Intercepciones de pases rivales. Refleja lectura táctica y posicionamiento defensivo.",
    "Blocked scoring attempt": "Disparos rivales bloqueados que iban a portería. Indica capacidad de sacrificio defensivo.",
    "Recoveries": "Balones recuperados para su equipo. Mide trabajo en la presión y compromiso defensivo.",
    "Possession won final 3rd": "Recuperaciones de balón en el último tercio ofensivo. Refleja presión alta efectiva.",
    "Dribbled past": "Veces que fue superado por regate. Un percentil alto indica que es muy difícil de superar en el uno contra uno.",
    
    "Rating": "Valoración general del rendimiento del jugador. Resume su impacto global en los partidos.",
    "Matches": "Número total de partidos jugados.",
    "Started": "Número de partidos en los que fue titular.",
    "Minutes": "Minutos acumulados durante la temporada.",
    "Yellow cards": "Tarjetas amarillas recibidas.",
    "Red cards": "Tarjetas rojas recibidas.",
    "Fouls committed": "Faltas cometidas. Un percentil alto indica que comete pocas, lo cual es positivo.",
}


STAT_DESCRIPTIONS_PORTEROS = {
    "Conceded": "Total de goles encajados. Un percentil alto indica que recibe pocos goles, señal de solidez defensiva.",
    "Goals conceded": "Total de goles encajados. Mismo significado que 'Conceded'.",
    "Saves": "Paradas realizadas. Indica capacidad para responder bajo presión y detener disparos peligrosos.",
    "Save percentage": "Porcentaje de paradas realizadas respecto a los tiros recibidos. Mide efectividad bajo palos.",
    "Goals prevented": "Diferencia entre goles esperados y goles encajados. Un valor alto indica que evita más goles de lo esperado.",
    "Clean sheets": "Partidos en los que no recibió goles. Mide solidez del portero y su defensa.",
    "Penalties saved": "Penaltis detenidos. Refleja reflejos y sangre fría en situaciones clave.",
    "Penalty goals faced": "Número total de penaltis recibidos. Contextualiza su exposición a estas jugadas.",
    "Penalty goals conceded": "Penaltis que encajó. Un percentil alto indica que recibe pocos.",
    "Penalty goals saves": "Penaltis que logró detener. Métrica alternativa al anterior.",
    "Error led to goal": "Errores que terminaron en gol en contra. Un percentil alto indica que comete muy pocos errores graves (perfil sobrio).",
    "Acted as sweeper": "Acciones fuera del área actuando como líbero. Refleja capacidad de anticipación y lectura del juego.",
    "High claims": "Balones altos interceptados en el área. Fundamental para porteros dominantes por alto.",
    "Accurate long balls": "Pases largos acertados. Indica precisión al iniciar jugada desde atrás.",
    "Long ball accuracy": "Porcentaje de acierto en balones largos. Mide fiabilidad en desplazamiento largo.",
    "Pass accuracy": "Porcentaje de acierto en los pases. Clave en porteros que juegan con los pies.",
    "Rating": "Valoración general del rendimiento del portero. Resume su impacto en el partido.",
    "Matches": "Número total de partidos jugados.",
    "Started": "Número de partidos como titular.",
    "Yellow cards": "Tarjetas amarillas recibidas.",
    "Red cards": "Tarjetas rojas recibidas.",
}



LIGA_COEFICIENTES = {
    # 🟩 Nivel 1 – Big Five europeas (referencia máxima)
    "Premier League": 1.00,
    "LaLiga": 1.00,
    "Bundesliga": 1.00,
    "Serie A": 1.00,
    "Ligue 1": 1.00,

    # 🟦 Nivel 2 – Ligas casi top (0.90–0.95)
    "Eredivisie": 0.92,
    "Liga Portugal": 0.92,
    "Serie A (Brasil)": 0.92,
    "Liga Profesional": 0.90,   # Argentina
    "First Division A": 0.90,   # Bélgica
    "Championship": 0.90,
    "Saudi Pro League": 0.88,

    # 🟨 Nivel 3 – Ligas competitivas medias (0.80–0.85)
    "Super Lig (Turquía)": 0.85,
    "Super League 1 (Grecia)": 0.84,
    "Ekstraklasa": 0.80,
    "Super League (Suiza)": 0.80,
    "Liga MX (Mexico)": 0.85,
    "Primera A (Colombia)": 0.82,
    "K League 1(Corea del Sur)": 0.80,
    "J. League (Japón)": 0.80,
    "Premier League (Egipto)": 0.78,
    "Allsvenskan": 0.78,
    "Eliteserien": 0.78,
    "1. Division (Dinamarca)": 0.78,

    # 🟧 Nivel 4 – Ligas menores / desarrollo (0.60–0.78)
    "Ligue 2": 0.78,
    "Serie B": 0.78,
    "LaLiga2": 0.78,
    "2. Bundesliga": 0.78,
    "Veikkausliiga": 0.70,
    "Premier Division (Irlanda)": 0.68,
    "Challenge League (Suiza)": 0.70,
    "3. Liga": 0.70,
    "MLS": 0.78,
    "Super League (China)": 0.70,
    "USL Championship": 0.65,
    "USL League One": 0.60,
    "Indian Super League": 0.62,
    "A-League": 0.65,
    "Thai League": 0.60,
    "Premier League (Canada)": 0.62,
    "K League 2 (Corea del Sur)": 0.70,
    "Besta deildin": 0.55,
}


def _stat_to_block(stat: str) -> str | None:
    for block, stats in STAT_BLOCKS.items():
        if stat in stats:
            return block
    return None


def _build_canon_map() -> Dict[str, str]:
    m={}
    def add(canon,*variants):
        for v in (variants+(canon,)):
            m[_norm(v)] = canon
    add("Successful crosses","Crosses","Successful cross","cross success","cross successful","centros")
    add("Cross accuracy","Crosses accuracy","precision de centros")
    add("Chances created","Key passes","Created chances","pases clave","ocasiones creadas")
    add("Accurate passes","Passes completed","Completed passes","pases completados")
    add("Accurate long balls","Accurate long pass","Long passes accurate","balones largos precisos")
    add("Long ball accuracy","Long passes accuracy","precision pases largos")
    add("Shots on target","Shots on target %","tiros a puerta")
    add("Dribbles","Successful dribbles","regates")
    add("Dribbles success rate","Dribble success %","porcentaje exito regates")
    add("Pass accuracy","Passes accuracy","precision de pase")
    add("Duels won","Ground duels won","duelos ganados")
    add("Duels won %","Ground duels won %","porcentaje duelos ganados")
    add("Aerials won","Aerial duels won","aerials")
    add("Aerials won %","Aerial duels won %","aerials %")
    add("Tackles won","Tackles","entradas ganadas")
    add("Tackles won %","Tackles success %")
    add("Interceptions","intercepciones")
    add("Recoveries","recuperaciones")
    add("Possession won final 3rd","recuperaciones ultimo tercio")
    add("Dispossessed","perdidas","lost possession")
    add("Dribbled past","veces superado","times dribbled past")
    add("Touches in opposition box","toques en area rival")
    add("xG","expected goals"); add("xGOT","xg on target","xg on-target"); add("xA","expected assists")
    add("Saves","saves total","total saves"); add("Save percentage","save %","save pct","save rate")
    add("Goals prevented","prevented goals","psxg - goals","post-shot xg minus goals")
    add("Clean sheets","clean-sheet","clean sheet")
    add("High claims","claims high","catches high","salidas por alto","crosses stopped")
    add("Accurate long balls","accurate long passes","long balls accurate")
    add("Long ball accuracy","long pass accuracy"); add("Pass accuracy","passing accuracy")
    add("Conceded","goals conceded","goals allowed"); add("Error led to goal","errors to goal","errors leading to goal")
    add("Penalties saved","pens saved"); add("Penalty goals faced","pens faced","penalties faced")
    add("Penalty goals conceded","pens conceded"); add("Penalty goals saves","penalty saves")
    add("Minutes","mins","minute","minutos")
    return m

CANON_MAP = _build_canon_map()
def _canonicalize_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    out={}
    for k,v in stats.items():
        out[CANON_MAP.get(_norm(k), k)] = v
    return out

STAT_ALIASES = {
    "Crosses":"Successful crosses","Successful cross":"Successful crosses",
    "Key passes":"Chances created","Created chances":"Chances created",
    "Passes completed":"Accurate passes","Accurate long pass":"Accurate long balls",
    "Shots on target %":"Shots on target",
}

LOWER_BETTER_IGNORE_RAW = {
    "Dribbled past","Fouls committed","Dispossessed","Conceded","Goals conceded",
    "Error led to goal","Yellow cards","Red cards","Penalty goals conceded"
}

INTENT_DESCRIPTIONS = {
    "desborde":"regatear, superar rivales en 1v1 y conducir para ganar línea de fondo",
    "centros":"centrar al área con precisión tras ganar banda",
    "creacion":"generar ocasiones de gol con pases clave y xA",
    "finalizacion":"rematar a puerta con precisión y generar xG/xGOT",
    "pase_progresion":"progresar con pase largo y mantener precisión en circulación",
    "posesion":"conservar la posesión y minimizar pérdidas",
    "duelos":"ganar duelos individuales a ras de suelo",
    "defensa":"entradas, intercepciones y que no le superen en 1v1",
    "presion":"recuperar en campo rival y acciones de presión",
    "aereo":"ganar duelos aéreos y juego por arriba",
    "toques_area":"llegar al área y tocar balón en zona peligrosa",
}
GK_INTENT_DESCRIPTIONS = {
    "paradas":"detener disparos con regularidad, alto porcentaje de paradas y goles evitados",
    "juego_aereo":"dominar el juego aereo con high claims y seguridad por arriba",
    "sweeper":"salir del area como libero, barrer balones y anticipar",
    "porteria_cero":"mantener la porteria a cero y encajar pocos goles",
    "salida_de_balon":"jugar con el balon en los pies, precision de pase y balones largos precisos",
    "estabilidad":"conceder pocos errores que acaben en gol y solidez general",
}
INTENT_TO_STATS_JUG = {
    "desborde":{"Dribbles":1.0,"Dribbles success rate":0.9,"Duels won":0.6,"Duels won %":0.5},
    "centros":{"Successful crosses":1.0,"Cross accuracy":0.85,"Accurate long balls":0.5,"Long ball accuracy":0.45},
    "creacion":{"Chances created":1.0,"xA":0.95,"Accurate passes":0.6},
    "finalizacion":{"Shots on target":1.0,"Shots":0.6,"xG":0.8,"xGOT":0.75},
    "pase_progresion":{"Accurate passes":0.6,"Accurate long balls":0.7,"Long ball accuracy":0.65},
    "posesion":{"Pass accuracy":0.9,"Dispossessed":0.85,"Touches":0.4},
    "duelos":{"Duels won":0.9,"Duels won %":0.8},
    "defensa":{"Tackles won":0.9,"Tackles won %":0.7,"Interceptions":0.7,"Dribbled past":0.7},
    "presion":{"Recoveries":0.8,"Possession won final 3rd":0.9,"Interceptions":0.6},
    "aereo":{"Aerials won":1.0,"Aerials won %":0.9},
    "toques_area":{"Touches in opposition box":1.0}
}
INTENT_TO_STATS_GK = {
    "paradas":{"Saves":1.0,"Save percentage":0.9,"Goals prevented":0.8},
    "juego_aereo":{"High claims":1.0},
    "salida_de_balon":{"Pass accuracy":0.6,"Accurate long balls":0.85,"Long ball accuracy":0.8},
    "porteria_cero":{"Clean sheets":0.8,"Conceded":0.6,"Error led to goal":0.6},
}
FORCE_JUG = {
    "regate":["Dribbles","Dribbles success rate"],"centrador":["Successful crosses","Cross accuracy"],
    "centros":["Successful crosses","Cross accuracy"],"banda":["Dribbles","Successful crosses"],
    "ocasion":["Chances created","xA"],"creador":["Chances created","xA"],
    "duelo":["Duels won","Duels won %"],"aereo":["Aerials won","Aerials won %"],
    "posesion":["Pass accuracy","Dispossessed"],"perder poco":["Dispossessed","Pass accuracy"],
    "pase largo":["Accurate long balls","Long ball accuracy"],"remate":["Shots on target","Shots"],
    "tiro":["Shots on target","Shots"],
}
FORCE_GK = {
    "juego aereo":["High claims"],"aereo":["High claims"],"salida":["Accurate long balls","Long ball accuracy","Pass accuracy"],
    "pie":["Pass accuracy","Accurate long balls"],"paradas":["Saves","Save percentage","Goals prevented"],
    "porterias a cero":["Clean sheets"],
}

STAT_BLOCKS = {
    "Shooting": {"Goals", "xG", "xGOT", "Shots", "Shots on target", "Penalty goals", "Non-penalty xG"},
    "Passing": {"Assists", "xA", "Accurate passes", "Pass accuracy", "Accurate long balls", "Long ball accuracy", "Chances created", "Successful crosses", "Cross accuracy"},
    "Possession": {"Dribbles", "Dribbles success rate", "Touches", "Touches in opposition box", "Dispossessed", "Fouls won", "Penalties awarded"},
    "Defending": {"Tackles won", "Tackles won %", "Duels won", "Duels won %", "Aerials won", "Aerials won %", "Interceptions", "Blocked scoring attempt", "Recoveries", "Dribbled past", "Possession won final 3rd", "Fouls committed"},
    "Discipline": {"Yellow cards", "Red cards"}
}

INTENT_ALIASES = {
    # ---- Ataque y definición ----
    "goleador": "finalizacion", "killer": "finalizacion", "finalizador": "finalizacion", "rematador": "finalizacion", "delantero killer": "finalizacion", "buena definicion": "finalizacion",

    # ---- Regate y desborde ----
    "regateador": "desborde", "habilidoso": "desborde", "eléctrico": "desborde", "conduce bien": "desborde", "buen 1v1": "desborde",

    # ---- Centros y banda ----
    "centrador": "centros", "banda": "centros", "lateral ofensivo": "centros",

    # ---- Creatividad y pase ----
    "asistente": "creacion", "creador": "creacion", "playmaker": "creacion", "media punta": "creacion",

    # ---- Pases largos y progresión ----
    "pase largo": "pase_progresion", "cambio de juego": "pase_progresion", "distribuidor": "pase_progresion",

    # ---- Conservación y seguridad ----
    "seguro": "posesion", "no pierde balones": "posesion", "sobrio": "posesion",

    # ---- Duelo físico ----
    "tanque": "duelos", "duro": "duelos", "fuerte": "duelos", "solido": "duelos", "rocoso": "duelos", "dominante": "duelos",

    # ---- Defensa general ----
    "defensor": "defensa", "central": "defensa", "lateral defensivo": "defensa",

    # ---- Presión y recuperación ----
    "presionador": "presion", "presionante": "presion", "bueno en presión": "presion", "intenso": "presion", "agresivo sin balón": "presion", "recuperador": "recuperacion", "recuperaciones": "recuperacion",

    # ---- Juego aéreo ----
    "cabezazos": "aereo", "buen juego aéreo": "aereo",

    # ---- Aparición ofensiva ----
    "llegador": "toques_area", "pisar área": "toques_area",

    # ---- Porteros ----
    "portero sobrio": "estabilidad", "sin alardes": "estabilidad",
    "dominante por arriba": "juego_aereo", "seguro por alto": "juego_aereo",
    "libero": "sweeper", "porterolibero": "sweeper", "sale del área": "sweeper",
    "buen pie": "salida_de_balon", "saca bien": "salida_de_balon", "distribuye bien": "salida_de_balon",
    "evita goles": "paradas", "buen portero": "paradas", "porterazo": "paradas",
    "porterías a cero": "porteria_cero", "solidez": "porteria_cero",
}

INTENT_TO_STATS_JUG = {
    # --- Finalización, tiro ---
    "finalizacion": {
        "Shots on target": 1.0, "xG": 0.9, "xGOT": 0.85, "Shots": 0.6
    },

    # --- Desborde y regate ---
    "desborde": {
        "Dribbles": 1.0, "Dribbles success rate": 0.9, "Duels won": 0.6, "Duels won %": 0.5
    },

    # --- Centros desde banda ---
    "centros": {
        "Successful crosses": 1.0, "Cross accuracy": 0.9, "Accurate long balls": 0.5, "Long ball accuracy": 0.4
    },

    # --- Creatividad y pase final ---
    "creacion": {
        "Chances created": 1.0, "xA": 0.95, "Accurate passes": 0.5
    },

    # --- Pase largo y salida ---
    "pase_progresion": {
        "Accurate long balls": 1.0, "Long ball accuracy": 0.85, "Pass accuracy": 0.6
    },

    # --- Conservación y seguridad ---
    "posesion": {
        "Pass accuracy": 0.9, "Dispossessed": 0.9, "Touches": 0.3
    },

    # --- Duelo físico ---
    "duelos": {
        "Duels won": 1.0, "Duels won %": 0.9, "Tackles won": 0.6
    },

    # --- Defensa y contención ---
    "defensa": {
        "Tackles won": 1.0, "Tackles won %": 0.85, "Interceptions": 0.8, "Dribbled past": 0.7
    },

    # --- Presión alta y recuperación ---
    "presion": {
        "Possession won final 3rd": 1.0, "Interceptions": 0.8, "Recoveries": 0.75
    },

    "recuperacion": {
        "Interceptions": 0.9, "Recoveries": 1
    },

    # --- Juego aéreo ---
    "aereo": {
        "Aerials won": 1.0, "Aerials won %": 0.95
    },

    # --- Aparición ofensiva ---
    "toques_area": {
        "Touches in opposition box": 1.0
    }
}

INTENT_TO_STATS_GK = {
    # --- Paradas puras ---
    "paradas": {
        "Saves": 1.0, "Save percentage": 0.9, "Goals prevented": 0.85
    },

    # --- Juego aéreo seguro ---
    "juego_aereo": {
        "High claims": 1.0
    },

    # --- Salida y distribución con el pie ---
    "salida_de_balon": {
        "Accurate long balls": 1.0, "Long ball accuracy": 0.85, "Pass accuracy": 0.6
    },

    # --- Porterías a cero y solidez ---
    "porteria_cero": {
        "Clean sheets": 1.0, "Conceded": 0.8
    },

    # --- Sobriedad y sin errores ---
    "estabilidad": {
        "Error led to goal": 1.0, "Conceded": 0.7, "Save percentage": 0.6
    },

    # --- Portero-líbero ---
    "sweeper": {
        "Acted as sweeper": 1.0, "High claims": 0.4
    }
}


# mismo modelo que ya tienes instalado (rápido y suficiente para similitudes de texto)
encoder = SentenceTransformer("intfloat/multilingual-e5-base")

MINUTES_FILTER_DEFAULT_JUG = 500 
MINUTES_FILTER_DEFAULT_GK = 0
MINUTES_PREFER_PER90_THRESHOLD = 750

class ScoreEvaluatorAgent:
    def __init__(self):
        self.encoder = encoder
        self.stat_names_j = list(STAT_DESCRIPTIONS_JUGADORES.keys())
        self.stat_texts_j = [STAT_DESCRIPTIONS_JUGADORES[k] for k in self.stat_names_j]
        self.emb_stats_j = self.encoder.encode(self.stat_texts_j, convert_to_tensor=True)

        self.stat_names_gk = list(STAT_DESCRIPTIONS_PORTEROS.keys())
        self.stat_texts_gk = [STAT_DESCRIPTIONS_PORTEROS[k] for k in self.stat_names_gk]
        self.emb_stats_gk = self.encoder.encode(self.stat_texts_gk, convert_to_tensor=True)

        self.intent_names = list(INTENT_DESCRIPTIONS.keys())
        self.intent_texts = [INTENT_DESCRIPTIONS[k] for k in self.intent_names]
        self.emb_intents = self.encoder.encode(self.intent_texts, convert_to_tensor=True)

        self.gk_intent_names = list(GK_INTENT_DESCRIPTIONS.keys())
        self.gk_intent_texts = [GK_INTENT_DESCRIPTIONS[k] for k in self.gk_intent_names]
        self.emb_intents_gk = self.encoder.encode(self.gk_intent_texts, convert_to_tensor=True)
        self.REQUIRED_BLOCKS = {
                        "finalizacion": "Shooting", "rematador": "Shooting", "goleador": "Shooting", "killer": "Shooting", "disparo": "Shooting",
                        "creador": "Passing", "asistencias": "Passing", "pase": "Passing", "creativo": "Passing", "centrador": "Passing",
                        "regate": "Possession", "conduce": "Possession", "habilidoso": "Possession",
                        "defensivo": "Defending", "central": "Defending", "recuperacion": "Defending", "presionante": "Defending",
                    }


    def get_embedding(self, text: str):
        return self.encoder.encode(text, convert_to_tensor=True)

    def _read_minutes_real(self, stats: Dict[str, Any]) -> int:
        try:
            return int((stats.get("Minutes") or {}).get("value", 0) or 0)
        except Exception:
            return 0

    def extract_minutes_filter(self, query: str, tipo: Literal["jugador","portero"]) -> int:
        q = _norm(query)
        if re.search(r"no (me )?importan los minutos|sin restriccion de minutos|minutos irrelevantes|minutos no importan", q):
            return 0
        m = re.search(r"(\d{2,5})\s*(minutos|min)\b", q)
        if m: return int(m.group(1))
        return MINUTES_FILTER_DEFAULT_JUG if tipo == "jugador" else MINUTES_FILTER_DEFAULT_GK

    def _negations_mask(self, query: str) -> Dict[str, float]:
        q = _norm(query); mask={}
        neg_map = {"aereo":["aereo","aereos","juego aereo"],"centros":["centros","centrar"],
                   "desborde":["regate","dribble","regatear"],"defensa":["defender","defensivo","entradas","tackles"],
                   "duelos":["duelos"],"posesion":["posesion","perdidas"]}
        for fam,kws in neg_map.items():
            if any((" no "+k in q) or (" sin "+k in q) for k in kws):
                mask[fam] = 0.15
        return mask

    def _weights_via_intents(self, query: str, tipo: Literal["jugador", "portero"]) -> Dict[str, float]:
        q_emb = self.get_embedding(query)

        if tipo == "jugador":
            # Usamos alias ya normalizados
            intent_canon_names = [INTENT_ALIASES.get(name, name) for name in self.intent_names]
            intent_canon_texts = [INTENT_DESCRIPTIONS.get(name, "") for name in intent_canon_names]
            emb_canon_intents = self.encoder.encode(intent_canon_texts, convert_to_tensor=True)

            sims = util.cos_sim(q_emb, emb_canon_intents)[0].cpu().numpy()
            sims = np.clip(sims, 0, None)
            sims = sims / sims.sum() if sims.sum() > 0 else np.ones_like(sims) / len(sims)

            neg_mask = self._negations_mask(query)
            for i, name in enumerate(intent_canon_names):
                if name in neg_mask:
                    sims[i] *= neg_mask[name]

            weights: Dict[str, float] = {}
            for i, intent in enumerate(intent_canon_names):
                contrib = float(sims[i])
                for stat, w in INTENT_TO_STATS_JUG.get(intent, {}).items():
                    weights[stat] = weights.get(stat, 0.0) + max(0.0, w) * contrib

            s = sum(weights.values())
            return {k: v / s for k, v in weights.items()} if s > 0 else {}

        else:
            sims = util.cos_sim(q_emb, self.emb_intents_gk)[0].cpu().numpy()
            sims = np.clip(sims, 0, None)
            sims = sims / sims.sum() if sims.sum() > 0 else np.ones_like(sims) / len(sims)

            weights: Dict[str, float] = {}
            for i, intent in enumerate(self.gk_intent_names):
                intent_canon = INTENT_ALIASES.get(intent, intent)
                contrib = float(sims[i])
                for stat, w in INTENT_TO_STATS_GK.get(intent_canon, {}).items():
                    weights[stat] = weights.get(stat, 0.0) + max(0.0, w) * contrib

            s = sum(weights.values())
            return {k: v / s for k, v in weights.items()} if s > 0 else {}


    def _weights_via_embeddings(self, query: str, tipo: Literal["jugador","portero"]) -> Dict[str, float]:
        q_emb = self.get_embedding(query)
        names = self.stat_names_j if tipo=="jugador" else self.stat_names_gk
        embs  = self.emb_stats_j if tipo=="jugador" else self.emb_stats_gk
        sims = util.cos_sim(q_emb, embs)[0].cpu().numpy()
        sims = np.clip(sims, 0, None); sims = sims / sims.sum() if sims.sum() > 0 else np.ones_like(sims)/len(sims)
        return {names[i]: float(sims[i]) for i in range(len(names))}

    def _forced_stats_from_query(self, query: str, tipo: Literal["jugador","portero"]) -> List[str]:
        query_lower = _norm(query)
        forced = set()
        words = set(query_lower.split())
        if tipo == "portero":
            for word in words:
                canon = INTENT_ALIASES.get(word, word)
                for k, stats in FORCE_GK.items():
                    if canon in _norm(k):
                        forced.update(stats)
        else:
            for word in words:
                canon = INTENT_ALIASES.get(word, word)
                for k, stats in FORCE_JUG.items():
                    if canon in _norm(k):
                        forced.update(stats)
        return list(forced)


    def _enforce_block_balance(self, query: str, weights: Dict[str, float], tipo: Literal["jugador","portero"]) -> Dict[str, float]:
        if tipo == "portero":
            return weights  # No aplicamos balance de bloques en porteros

        # Mapeo de stats a bloques
        block_stats: Dict[str, Set[str]] = defaultdict(set)
        for stat in weights:
            block = _stat_to_block(stat)
            if block:
                block_stats[block].add(stat)

        # Si hay al menos 2 bloques ya representados, lo dejamos estar
        if len(block_stats) >= 2:
            return weights

        # --- Si hay pocos bloques, intentamos enriquecer con otros bloques coherentes ---
        query_lower = _norm(query)
        required_blocks = set()

        for key, block in self.REQUIRED_BLOCKS.items():  # ← lo definiremos abajo
            if key in query_lower:
                required_blocks.add(block)

        for block in required_blocks:
            if block not in block_stats:
                candidates = STAT_BLOCKS[block]
                for c in candidates:
                    if c not in weights:
                        weights[c] = 0.2 * max(weights.values())  # Añade con peso bajo

        return weights





    def _select_top_k_metrics_global(self, query: str, tipo: Literal["jugador","portero"], top_k: int = 8) -> Dict[str, float]:
        w_int = self._weights_via_intents(query, tipo)
        w_emb = self._weights_via_embeddings(query, tipo)
        alpha = 0.7
        all_keys = set(w_int) | set(w_emb)
        merged = {k: alpha*w_int.get(k, 0.0) + (1 - alpha)*w_emb.get(k, 0.0) for k in all_keys}
        canonical = _canonicalize_stats(merged)

        forced = self._forced_stats_from_query(query, tipo)
        for f in forced:
            f2 = STAT_ALIASES.get(f, f)
            canonical[f2] = max(canonical.get(f2, 0.0), (max(canonical.values()) if canonical else 1.0))

        canonical = self._enforce_block_balance(query, canonical, tipo)
        canonical = self._exclude_conflicting_metrics(query, canonical)


        query_lower = _norm(query)
        # Filtro adicional: eliminar Tackles si no es defensa/central/lateral
        if not any(palabra in query_lower for palabra in ["defensa", "central", "lateral"]):
            canonical.pop("Tackles won", None)
            canonical.pop("Tackles won %", None)

        if not canonical:
            fallback = (
                ["Saves", "Save percentage", "High claims", "Accurate long balls", "Long ball accuracy", "Goals prevented", "Pass accuracy", "Clean sheets"]
                if tipo == "portero"
                else ["Dribbles", "Successful crosses", "Chances created", "xA", "Shots on target", "Accurate passes", "Accurate long balls", "Duels won"]
            )
            w = 1.0 / len(fallback)
            return {k: w for k in fallback}

        

        # ---------- Alias robustos para nombres de métricas ----------
        METRIC_ALIASES = {
            "Dribbles": ["Dribbles", "Successful dribbles", "Dribbles total"],
            "Dribbles success rate": ["Dribbles success rate", "Dribble success %", "Dribbles %"],

            "Goals": ["Goals", "Non-penalty goals", "Goals (np)", "Goals total"],
            "xG excl. penalty": ["xG excl. penalty", "xG (non-penalty)", "npxG"],
            "Shots on target": ["Shots on target", "Shots OT", "SOT"],
            "Shots": ["Shots", "Shots total", "Total shots"],


            "Successful crosses": ["Successful crosses", "Crosses completed"],
            "Cross accuracy": ["Cross accuracy", "Crosses accuracy %"],
            "Accurate long balls": ["Accurate long balls", "Long balls completed", "Successful long balls"],

            "Interceptions": ["Interceptions"],
            "Recoveries": ["Recoveries", "Ball recoveries"],
            "Possession won final 3rd": ["Possession won final 3rd", "Possession won in final third", "Possession won (final 3rd)"],
            "Duels won": ["Duels won", "Ground duels won", "Offensive duels won", "Duels won %"],
            "Aerials won": ["Aerials won", "Aerials won %"],

        }

        def pick_metric(name: str, canonical: Dict[str, float]) -> str | None:
            """
            Devuelve el 'display name' elegido (primer alias encontrado).
            Si no existe ninguno en canonical, crea el principal con peso mínimo.
            """
            aliases = METRIC_ALIASES.get(name, [name])
            for a in aliases:
                if a in canonical:
                    return a
            # Si no existe: damos de alta el principal con peso mínimo para garantizar inserción
            main = aliases[0]
            if main not in canonical:
                canonical[main] = 1e-6  # stub mínimo
            return main

        # --- DETECCIÓN DE INTENCIONES CLAVE (regex con límites de palabra) ---
        # regate
        has_regate = bool(re.search(r"\bregate(?:ar|ando|ador(?:a)?s?)?\b", query_lower))

        # gol
        has_gol = bool(re.search(r"\bgol(?:eador(?:a)?|es)?\b|\brematador(?:a)?s?\b", query_lower))

        # centros: solo si se habla de centrar/centros, NO por 'mediocentro/centrocampista/delantero centro/defensa central'
        match_centros = bool(re.search(
            r"(?:\bcentr(?:ar|e|ando|ador(?:a)?s?)\b|\bcentros?\b|centre bien|buen[oa]s?\s+centros?)",
            query_lower
        ))
        falsos_centros = bool(re.search(
            r"\bmediocentro(?:campista)?\b|\bcentrocampista\b|\bdelantero\s+centro\b|\bdefensa\s+central\b",
            query_lower
        ))
        has_centros = match_centros and not falsos_centros

        # Candado extra: si NO hay verbos/expresión explícita de centrar, apaga centros
        if has_centros:
            explicito_centrar = bool(re.search(r"\bcentr(?:ar|e|ando|ador(?:a)?s?)\b|centre bien|buen[oa]s?\s+centros?", query_lower))
            if not explicito_centrar:
                has_centros = False

        # recuperaciones
        has_recuperaciones = bool(re.search(
            r"\brecuper(?:aci(?:ó|o)nes|ar|ando|ador(?:a)?s?)\b|\brecupere\b",
            query_lower
        ))

        # presiones / pressing alto
        has_presiones = bool(re.search(
            r"\bpresi(?:ó|o)n(?:es)?\b|\bpresion(?:ar|ando|ante|ador(?:a)?)\b|\bpressing\b|\bpresione\b",
            query_lower
        ))
        # Detección
        has_duelos = bool(re.search(r"\bduelos?\b", query_lower))

        # Boost más notorio
        if has_duelos:
            for alias in METRIC_ALIASES["Duels won"]:
                if alias in canonical:
                    canonical[alias] *= 1.35


        # Orden fijo de bloques: regate > gol > centros > recuperaciones > presiones > duelos
        bloques = []
        if has_regate:          bloques.append("regate")
        if has_gol:             bloques.append("gol")
        if has_centros:         bloques.append("centros")
        if has_recuperaciones:  bloques.append("recuperaciones")
        if has_presiones:       bloques.append("presiones")
        if has_duelos:          bloques.append("duelos") 


        # ---------- Contenidos de cada bloque (3 métricas cada uno) ----------
        BLOQUE_METRICAS = {
            "regate":  ["Dribbles", "Dribbles success rate", "Duels won"],
            "gol":     ["Goals", "xG excl. penalty", "Shots on target"],
            "centros": ["Successful crosses", "Cross accuracy", "Accurate long balls"],
            "recuperaciones": ["Recoveries", "Interceptions"],
            "presiones":      ["Possession won final 3rd", "Interceptions"],
            "duelos": ["Duels won"],
        }


        # ---------- Limpieza de tackles si no es defensa ----------
        if not any(palabra in query_lower for palabra in ["defensa", "central", "lateral"]):
            canonical.pop("Tackles won", None)
            canonical.pop("Tackles won %", None)

        if not canonical:
            fallback = (
                ["Saves", "Save percentage", "High claims", "Accurate long balls", "Long ball accuracy", "Goals prevented", "Pass accuracy", "Clean sheets"]
                if tipo == "portero"
                else ["Dribbles", "Successful crosses", "Chances created", "xA", "Shots on target", "Accurate passes", "Accurate long balls", "Duels won"]
            )
            w = 1.0 / len(fallback)
            return {k: w for k in fallback}
        
        # Downweights si NO hay intención explícita
        if not has_gol:
            # Baja tiros y sus derivados
            for alias in METRIC_ALIASES.get("Shots on target", []):
                if alias in canonical: canonical[alias] *= 0.6
            for key in ["Goals", "xG excl. penalty"]:
                for a in METRIC_ALIASES.get(key, [key]):
                    if a in canonical: canonical[a] *= 0.7

        if not has_centros:
            # Baja solo métricas de cruce; dejamos 'Accurate long balls' intacto (útil para DMs)
            for a in METRIC_ALIASES.get("Successful crosses", []):
                if a in canonical: canonical[a] *= 0.65
            for a in METRIC_ALIASES.get("Cross accuracy", []):
                if a in canonical: canonical[a] *= 0.65


        # ---------- Ranking por pesos para definir pesos de slots ----------
        total = sum(canonical.values())
        ranked = sorted(((k, v / total) for k, v in canonical.items()), key=lambda kv: kv[1], reverse=True)

        base_metrics = [k for k, _ in ranked]
        slot_weights = [w for _, w in ranked]
        while len(base_metrics) < top_k:
            base_metrics.append(None)
        while len(slot_weights) < top_k:
            slot_weights.append(slot_weights[-1] if slot_weights else 1.0 / top_k)

        slots = base_metrics[:top_k]  # copia de los candidatos iniciales por peso

        # ---------- Forced primero (si los hay), manteniendo slots ----------
        def move_to_front(slots_list, item):
            if item in slots_list:
                slots_list.remove(item)
            slots_list.insert(0, item)

        ordered_forced = []
        for f in forced:
            f2 = STAT_ALIASES.get(f, f)
            if f2 in canonical and f2 not in ordered_forced:
                ordered_forced.append(f2)
        for it in reversed(ordered_forced):
            move_to_front(slots, it)

        # ---------- Inserción con desplazamiento y sin duplicados ----------
        def insert_with_shift(sl, item, pos):
            if item in sl:
                sl.remove(item)
            pos = max(0, min(pos, top_k - 1))
            sl.insert(pos, item)
            del sl[top_k:]  # truncamos si excede

        # Posición inicial para bloques: 1 (segunda métrica); si hay varios bloques, se acumulan
        pos_cursor = 1
        for bloque in bloques:
            for m in BLOQUE_METRICAS[bloque]:
                chosen_name = pick_metric(m, canonical)
                if chosen_name:
                    insert_with_shift(slots, chosen_name, pos_cursor)
                    pos_cursor += 1

        # ---------- Relleno con el resto por peso, sin duplicar ----------
        for k, _ in ranked:
            if k not in slots and len(slots) < top_k:
                slots.append(k)
        slots = (slots + [None]*top_k)[:top_k]

        # ---------- Métrica -> peso de su ranura; renormalizar ----------
        out = {}
        for i, m in enumerate(slots):
            if m is not None:
                out[m] = slot_weights[i] if i < len(slot_weights) else (1.0 / top_k)

        s = sum(out.values())
        if s <= 0:
            w = 1.0 / max(1, len(out))
            return {k: w for k in out}
        return {k: v / s for k, v in out.items()}




    

    def _enforce_block_balance(self, query: str, stats_dict: Dict[str, float], tipo: Literal["jugador","portero"]) -> Dict[str, float]:
        q = _norm(query)
        block_counts = {"Shooting":0, "Passing":0, "Possession":0, "Defending":0}
        for stat in stats_dict:
            b = _stat_to_block(stat)
            if b in block_counts:
                block_counts[b] += 1

        counts_required = {"Shooting": 3, "Passing": 3, "Possession": 2, "Defending": 3}
        block_hits = {block: any(k in q for k in kws) for block, kws in {
            "Shooting": ["rematador","goleador","killer","disparo"],
            "Passing": ["asistencias","creador","pase","vision"],
            "Possession": ["regate","habil","conduce","posesion"],
            "Defending": ["defensivo","central","recuperacion","bloqueos"]
        }.items()}

        for block, required_count in counts_required.items():
            if not block_hits.get(block): continue
            current = [s for s in stats_dict if _stat_to_block(s) == block]
            missing = required_count - len(current)
            if missing > 0:
                candidate_stats = list(STAT_BLOCKS[block])
                embs_all = self.emb_stats_j if tipo == "jugador" else self.emb_stats_gk
                stats_names = self.stat_names_j if tipo == "jugador" else self.stat_names_gk
                emb_query = self.get_embedding(query)
                sims = util.cos_sim(emb_query, embs_all)[0].cpu().numpy()
                best_stats = [
                    stats_names[i] for i in np.argsort(sims)[::-1]
                    if stats_names[i] in candidate_stats and stats_names[i] not in stats_dict
                ][:missing]
                for s in best_stats:
                    stats_dict[s] = min(0.25, max(stats_dict.values(), default=0.1))

        return stats_dict

    def _exclude_conflicting_metrics(self, query: str, weights: Dict[str, float]) -> Dict[str, float]:
        cleaned = weights.copy()
        q_lower = _norm(query)

        # 1. Evitar tener tanto "Dribbles" como "Dribbled past"
        if "Dribbles" in cleaned and "Dribbled past" in cleaned:
            cleaned.pop("Dribbled past")  # Prioriza habilidad ofensiva

        # 2. Si está "Dispossessed", quitamos "Dribbles" si no se menciona "regate" en query
        if "Dribbles" in cleaned and "Dispossessed" in cleaned:
            if "regate" not in q_lower and "dribble" not in q_lower:
                cleaned.pop("Dribbles")

        # 3. Evitar tener "Duels won" y "Duels won %"
        if "Duels won" in cleaned and "Duels won %" in cleaned:
            if cleaned["Duels won"] > cleaned["Duels won %"]:
                cleaned.pop("Duels won %")
            else:
                cleaned.pop("Duels won")

        # 4. Evitar exceso de métricas de remate
        remate = ["xG", "xGOT", "Shots on target", "Goals", "Shots"]
        activos = [r for r in remate if r in cleaned]
        if len(activos) > 3:
            # Nos quedamos con los 3 de mayor peso
            top = sorted(((k, cleaned[k]) for k in activos), key=lambda kv: kv[1], reverse=True)[:3]
            top_names = {k for k,_ in top}
            for k in activos:
                if k not in top_names:
                    cleaned.pop(k)

        # 5. "Accurate long balls" vs "Long ball accuracy"
        if "Accurate long balls" in cleaned and "Long ball accuracy" in cleaned:
            if cleaned["Accurate long balls"] >= cleaned["Long ball accuracy"]:
                cleaned.pop("Long ball accuracy")
            else:
                cleaned.pop("Accurate long balls")

        # 6. "Pass accuracy" + "Accurate passes"
        if "Pass accuracy" in cleaned and "Accurate passes" in cleaned:
            if "posesion" in q_lower or "precision" in q_lower:
                pass  # permitimos ambas si hay motivación
            elif cleaned["Pass accuracy"] >= cleaned["Accurate passes"]:
                cleaned.pop("Accurate passes")
            else:
                cleaned.pop("Pass accuracy")

        return cleaned



    def _compute_stat_score(self, stat_name: str, stat_dict: Dict[str, Any], prefer_per90: bool) -> float:
        try:
            pctl  = float(stat_dict.get("percentile", 0) or 0)
            pctl90= float(stat_dict.get("percentile_per90", 0) or 0)
            val   = float(stat_dict.get("value", 0) or 0)
            val90 = float(stat_dict.get("value_per90", 0) or 0)
        except Exception:
            pctl=pctl90=val=val90=0.0
        if prefer_per90:
            w_pctl,w_pctl90,w_val,w_val90 = 0.25,0.45,0.10,0.20
        else:
            w_pctl,w_pctl90,w_val,w_val90 = 0.45,0.3,0.15,0.10
        if stat_name in LOWER_BETTER_IGNORE_RAW:
            w_val=w_val90=0.0
        return (w_pctl*pctl) + (w_pctl90*pctl90) + (w_val*val) + (w_val90*val90)

    def score_dataframe(self, df_filtrado: pl.DataFrame, query: str,
                        tipo: Literal["jugador","portero"]) -> Tuple[List[dict], pl.DataFrame]:
        min_minutos = self.extract_minutes_filter(query, tipo)
        print("ANTES del filtro por minutos:", df_filtrado.height)
        print("Minutos requeridos:", min_minutos)

        def keep_row(stats_json):
            stats = _safe_json(stats_json)
            mins = self._read_minutes_real(stats)
            return mins >= min_minutos

        if "estadísticas" in df_filtrado.columns:
            df = df_filtrado.filter(pl.col("estadísticas").map_elements(keep_row, return_dtype=pl.Boolean))
        else:
            df = df_filtrado

        top_stats_weights_global = self._select_top_k_metrics_global(query, tipo, top_k=8)
        chosen_metrics = list(top_stats_weights_global.keys())

        resultados=[]
        for row in df.iter_rows(named=True):
            stats_raw = _canonicalize_stats(_safe_json(row.get("estadísticas", {})))
            minutes_real = self._read_minutes_real(stats_raw)
            prefer_per90 = minutes_real < MINUTES_PREFER_PER90_THRESHOLD

            detalle={}
            total_score=0.0
            for stat in chosen_metrics:
                raw_stat = _safe_json(stats_raw.get(stat, {}))
                peso = float(top_stats_weights_global[stat])
                score = self._compute_stat_score(stat, raw_stat, prefer_per90)
                ponderado = score * peso
                detalle[stat] = {"score":float(score),"peso":peso,"ponderado":float(ponderado),"raw":raw_stat}
                total_score += ponderado

            liga = row.get("liga","") or ""
            liga_stats = row.get("liga_stats")
            coef = LIGA_COEFICIENTES.get(liga_stats, 0.75)
            total_score *= coef
            if coef >= 0.95: nivel_liga = "alta exigencia competitiva"
            elif coef >= 0.8: nivel_liga = "nivel competitivo intermedio"
            else: nivel_liga = "liga de menor exigencia"

            rasgos = _safe_json(row.get("rasgos_jugador" if tipo=="jugador" else "rasgos_portero"))

            resultados.append({
                "nombre": row.get("nombre"),
                "equipo": row.get("equipo"),
                "liga": liga,
                "nacionalidad": row.get("nacionalidad"),
                "main_position": row.get("main_position"),
                "other_positions": row.get("other_positions", []),
                "age": row.get("age"),
                "market_value": row.get("market_value"),
                "score": float(total_score),
                "metricas_clave": {k: float(v) for k,v in top_stats_weights_global.items()},
                "detalle": detalle,
                "rasgos": rasgos,
                "height": row.get("height"),
                "foot": row.get("foot"),
                "minutes_real": minutes_real,
                "años_contrato": row.get("años_contrato"),
                "nivel_liga": nivel_liga,
                "estadisticas":row.get("estadísticas"),
                "liga_stats": liga_stats,
                "temporada_stats": row.get("temporada_stats"),
            })

        print(len(resultados))
        resultados = sorted(resultados, key=lambda x: x["score"], reverse=True)
        top3_nombres = [r["nombre"] for r in resultados[:3]]
        df_top3 = df.filter(pl.col("nombre").is_in(top3_nombres)) if df.height else df
        return resultados[:3], df_top3
