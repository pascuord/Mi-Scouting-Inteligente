# src/scouting/agents/agente2.py
from __future__ import annotations
import json, re, unicodedata
from typing import List, Tuple, Literal, Dict, Any
import numpy as np
import polars as pl
from sentence_transformers import SentenceTransformer, util

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
    "Goals":"goles anotados","Assists":"asistencias entregadas a un compañero que terminó en gol",
    "xG":"goles esperados generados según la calidad de los disparos","xGOT":"goles esperados tras disparar a portería (xG on target)",
    "xG excl. penalty":"goles esperados sin contar penaltis","Shots":"disparos totales realizados",
    "Shots on target":"disparos que fueron entre los tres palos","xA":"asistencias esperadas según calidad y posición del pase",
    "Accurate passes":"pases acertados al compañero","Pass accuracy":"porcentaje de precisión en los pases",
    "Accurate long balls":"pases largos completados correctamente","Long ball accuracy":"porcentaje de acierto en los balones largos",
    "Chances created":"ocasiones de gol creadas para el equipo","Successful crosses":"centros al área que llegaron a un compañero",
    "Cross accuracy":"porcentaje de centros exitosos","Dribbles":"regates exitosos frente a un rival",
    "Dribbles success rate":"porcentaje de éxito en regates","Touches":"total de toques de balón realizados",
    "Touches in opposition box":"toques dentro del área rival","Dispossessed":"veces que perdió el balón por presión rival",
    "Fouls won":"faltas recibidas","Tackles won":"entradas exitosas en las que recuperó el balón",
    "Tackles won %":"porcentaje de éxito en entradas","Duels won":"duelos individuales ganados",
    "Duels won %":"porcentaje de duelos individuales ganados","Aerials won":"duelos aéreos ganados",
    "Aerials won %":"porcentaje de duelos aéreos ganados","Interceptions":"intercepciones de pases del rival",
    "Blocked scoring attempt":"disparos bloqueados que iban a puerta","Fouls committed":"faltas cometidas",
    "Recoveries":"balones recuperados para su equipo","Possession won final 3rd":"posesiones recuperadas en el último tercio del campo rival",
    "Dribbled past":"veces que fue superado por regate","Rating":"valoración general de rendimiento en el partido",
    "Matches":"partidos disputados","Started":"partidos en los que fue titular","Minutes":"minutos disputados",
    "Yellow cards":"tarjetas amarillas recibidas","Red cards":"tarjetas rojas recibidas"
}

STAT_DESCRIPTIONS_PORTEROS = {
    "Conceded":"goles encajados","Goals conceded":"goles encajados (alternativa)","Saves":"paradas realizadas",
    "Save percentage":"porcentaje de disparos detenidos","Goals prevented":"diferencia entre xG y goles recibidos (goles evitados)",
    "Clean sheets":"partidos en los que no recibió goles","Penalties saved":"penaltis detenidos",
    "Penalty goals faced":"penaltis a los que se enfrentó","Penalty goals conceded":"penaltis que encajó",
    "Penalty goals saves":"penaltis que logró detener","Error led to goal":"errores que terminaron en gol en contra",
    "Acted as sweeper":"acciones fuera del área actuando como líbero","High claims":"balones altos interceptados en el área",
    "Accurate long balls":"balones largos acertados","Long ball accuracy":"porcentaje de acierto en balones largos",
    "Pass accuracy":"porcentaje de acierto en los pases","Rating":"valoración general de rendimiento en el partido",
    "Matches":"partidos disputados","Started":"partidos como titular","Yellow cards":"tarjetas amarillas",
    "Red cards":"tarjetas rojas"
}

LIGA_COEFICIENTES = {
    "Premier League":1.0,"LaLiga":1.0,"Bundesliga":1.0,"Serie A":1.0,"Ligue 1":1.0,
    "Championship":0.88,"Ligue 2":0.86,"Serie B":0.86,"LaLiga2":0.86,"Eredivisie":0.9,
    "Liga Portugal":0.9,"Super Lig (Turquía)":0.86,"Super League (Suiza)":0.86,"Ekstraklasa":0.84,
    "First Division A":0.88,"Super League 1 (Grecia)":0.84,"2. Bundesliga":0.86,
    "Serie A (Brasil)":0.9,"Saudi Pro League":0.88,"MLS":0.8,"Liga Profesional":0.8,
    "Primera A (Colombia)":0.78,"Liga MX (Mexico)":0.82,"Allsvenskan":0.78,"Super League (China)":0.75,
    "USL Championship":0.65,"USL League One":0.6,"Indian Super League":0.62,"A-League":0.64,
    "Thai League":0.6,"Premier League (Canada)":0.62,"Premier League (Egipto)":0.62,
    "K League 1(Corea del Sur)":0.8,"K League 2 (Corea del Sur)":0.7,"Besta deildin":0.55,
    "J. League (Japón)":0.8,"1. Division (Dinamarca)":0.78,"Eliteserien":0.78,"Veikkausliiga":0.7,
    "Premier Division (Irlanda)":0.68,"Challenge League (Suiza)":0.7,"3. Liga":0.7,
}

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

    def get_embedding(self, text: str):
        return self.encoder.encode(text, convert_to_tensor=True)

    def get_liga_coef(self, liga: str) -> float:
        return LIGA_COEFICIENTES.get((liga or "").strip(), 0.75)

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

    def _weights_via_intents(self, query: str, tipo: Literal["jugador","portero"]) -> Dict[str, float]:
        q_emb = self.get_embedding(query)
        if tipo == "jugador":
            sims = util.cos_sim(q_emb, self.emb_intents)[0].cpu().numpy()
            sims = np.clip(sims, 0, None); sims = sims / sims.sum() if sims.sum() > 0 else np.ones_like(sims)/len(sims)
            neg_mask = self._negations_mask(query)
            for i,name in enumerate(self.intent_names):
                if name in neg_mask: sims[i] *= neg_mask[name]
            weights: Dict[str,float] = {}
            for i,intent in enumerate(self.intent_names):
                contrib = float(sims[i])
                for stat,w in INTENT_TO_STATS_JUG.get(intent, {}).items():
                    weights[stat] = weights.get(stat,0.0) + max(0.0,w)*contrib
            s = sum(weights.values())
            return {k: v/s for k,v in weights.items()} if s>0 else {}
        sims = util.cos_sim(q_emb, self.emb_intents_gk)[0].cpu().numpy()
        sims = np.clip(sims, 0, None); sims = sims / sims.sum() if sims.sum() > 0 else np.ones_like(sims)/len(sims)
        weights: Dict[str,float] = {}
        for i,intent in enumerate(self.gk_intent_names):
            contrib = float(sims[i])
            for stat,w in INTENT_TO_STATS_GK.get(intent, {}).items():
                weights[stat] = weights.get(stat,0.0) + max(0.0,w)*contrib
        s = sum(weights.values())
        return {k: v/s for k,v in weights.items()} if s>0 else {}

    def _weights_via_embeddings(self, query: str, tipo: Literal["jugador","portero"]) -> Dict[str, float]:
        q_emb = self.get_embedding(query)
        names = self.stat_names_j if tipo=="jugador" else self.stat_names_gk
        embs  = self.emb_stats_j if tipo=="jugador" else self.emb_stats_gk
        sims = util.cos_sim(q_emb, embs)[0].cpu().numpy()
        sims = np.clip(sims, 0, None); sims = sims / sims.sum() if sims.sum() > 0 else np.ones_like(sims)/len(sims)
        return {names[i]: float(sims[i]) for i in range(len(names))}

    def _forced_stats_from_query(self, query: str, tipo: Literal["jugador","portero"]) -> List[str]:
        q = _norm(query); forced=[]
        mapping = FORCE_JUG if tipo=="jugador" else FORCE_GK
        for kw,stats in mapping.items():
            if kw in q: forced.extend(stats)
        return list(dict.fromkeys(forced))

    def _select_top_k_metrics_global(self, query: str, tipo: Literal["jugador","portero"], top_k: int = 8) -> Dict[str, float]:
        w_int = self._weights_via_intents(query, tipo)
        w_emb = self._weights_via_embeddings(query, tipo)
        alpha = 0.6
        all_keys = set(w_int) | set(w_emb)
        merged = {k: alpha*w_int.get(k,0.0) + (1-alpha)*w_emb.get(k,0.0) for k in all_keys}
        canonical: Dict[str,float] = {}
        for k,v in merged.items():
            k2 = STAT_ALIASES.get(k, k)
            canonical[k2] = canonical.get(k2,0.0) + v
        forced = self._forced_stats_from_query(query, tipo)
        for f in forced:
            f2 = STAT_ALIASES.get(f, f)
            canonical[f2] = max(canonical.get(f2,0.0), (max(canonical.values()) if canonical else 1.0))
        if not canonical:
            fallback = (["Saves","Save percentage","High claims","Accurate long balls","Long ball accuracy","Goals prevented","Pass accuracy","Clean sheets"]
                        if tipo=="portero"
                        else ["Dribbles","Successful crosses","Chances created","xA","Shots on target","Accurate passes","Accurate long balls","Duels won"])
            w = 1.0/len(fallback)
            return {k:w for k in fallback}
        total = sum(canonical.values())
        ranked = sorted(((k, v/total) for k,v in canonical.items()), key=lambda kv: kv[1], reverse=True)
        ordered=[]
        for f in forced:
            f2 = STAT_ALIASES.get(f, f)
            if f2 in [m for m,_ in ranked] and f2 not in ordered:
                ordered.append(f2)
        for k,_ in ranked:
            if k not in ordered: ordered.append(k)
        chosen = ordered[:top_k]
        raww = {k: canonical.get(k,0.0) for k in chosen}
        s = sum(raww.values())
        if s <= 0:
            w = 1.0/len(chosen)
            return {k:w for k in chosen}
        return {k: raww[k]/s for k in chosen}

    def _compute_stat_score(self, stat_name: str, stat_dict: Dict[str, Any], prefer_per90: bool) -> float:
        try:
            pctl  = float(stat_dict.get("percentile", 0) or 0)
            pctl90= float(stat_dict.get("percentile_per90", 0) or 0)
            val   = float(stat_dict.get("value", 0) or 0)
            val90 = float(stat_dict.get("value_per90", 0) or 0)
        except Exception:
            pctl=pctl90=val=val90=0.0
        if prefer_per90:
            w_pctl,w_pctl90,w_val,w_val90 = 0.25,0.45,0.20,0.10
        else:
            w_pctl,w_pctl90,w_val,w_val90 = 0.40,0.30,0.20,0.10
        if stat_name in LOWER_BETTER_IGNORE_RAW:
            w_val=w_val90=0.0
        return (w_pctl*pctl) + (w_pctl90*pctl90) + (w_val*val) + (w_val90*val90)

    def score_dataframe(self, df_filtrado: pl.DataFrame, query: str,
                        tipo: Literal["jugador","portero"]) -> Tuple[List[dict], pl.DataFrame]:
        min_minutos = self.extract_minutes_filter(query, tipo)

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
            coef = LIGA_COEFICIENTES.get(liga, 0.75)
            total_score *= coef
            if coef >= 0.95: nivel_liga = "alta exigencia competitiva"
            elif coef >= 0.8: nivel_liga = "nivel competitivo intermedio"
            else: nivel_liga = "liga de menor exigencia"

            rasgos = _safe_json(row.get("rasgos_jugador" if tipo=="jugador" else "rasgos_portero"))

            resultados.append({
                "nombre": row.get("nombre"),
                "equipo": row.get("equipo"),
                "liga": liga,
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
                "nivel_liga": nivel_liga
            })

        resultados = sorted(resultados, key=lambda x: x["score"], reverse=True)
        top3_nombres = [r["nombre"] for r in resultados[:3]]
        df_top3 = df.filter(pl.col("nombre").is_in(top3_nombres)) if df.height else df
        return resultados[:3], df_top3
