# src/scouting/agents/agente1.py
from __future__ import annotations
import json, re, datetime, unicodedata
import polars as pl
from typing import Tuple, Literal, List, Dict, Any

class Agente1HardFilter:
    DEBUG =True  # ponlo a False en producción

    @staticmethod
    def _norm(s: str) -> str:
        t = unicodedata.normalize("NFD", (s or "").lower())
        return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")


    # --- Parser robusto ---
    def parse_market_value_polars(self, val: str | None) -> float | None:
        if val is None:
            return None
        s = str(val).lower().strip()

        # Normalizar símbolos y palabras
        s = s.replace("€", "").replace("eur", "").replace("euros", "").replace("euro", "")
        s = s.replace("million", "m").replace("millones", "m").replace("millon", "m").replace("mill.", "m")
        s = s.replace("mil ", "k").replace(" mil", "k")
        s = re.sub(r"\s+", "", s)

        if s in {"", "none", "null"}:
            return None
        if s in {"free", "libre", "gratis"}:
            return 0.0

        # Ej: 23m, 0.5m, 500k
        m = re.match(r"^(\d+(?:[\.,]\d+)?)([mk]?)$", s)
        if m:
            num = float(m.group(1).replace(",", "."))
            suf = m.group(2)
            if suf == "m":
                return num * 1_000_000
            if suf == "k":
                return num * 1_000
            # sin sufijo: puede ser euros directos
            return num

        # Ej: 500.000
        s_digits = re.sub(r"[^\d]", "", s)
        if s_digits.isdigit():
            return float(s_digits)

        return None

    # --- Detección de valor máximo en query ---
    def extraer_valor_maximo(self, query: str) -> float | None:
        """
        Devuelve el tope de precio en euros.
        Prioriza capturas con unidad. Si hay mezcla con/ sin unidad, escoge el valor
        con unidad; si hay varios, el máximo (lo más laxo y casi siempre el correcto).
        Usa ventana para escalar comparadores sin unidad por contexto ("millones"/"mil").
        """
        q = self._norm(query).replace(",", ".").replace("€", " euros ")

        def _vent(i, j, pad=18):
            return q[max(0, i-pad):min(len(q), j+pad)]

        with_unit = []   # valores ya escalados a € que vienen con unidad explícita
        bare_vals = []   # números sin unidad (se escalarán por contexto si aplica)

        # 1) Capturas con unidad explícita
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(m|millon|millones|k|mil)\b", q):
            v = float(m.group(1)); suf = m.group(2)
            if suf in {"m", "millon", "millones"}: v *= 1_000_000
            elif suf in {"k", "mil"}:               v *= 1_000
            # descarta falsos positivos de años en la ventana
            win = _vent(*m.span(), 14)
            if "ano" in win or "anos" in win or "años" in win:
                continue
            with_unit.append(v)

        # 2) “X euros”
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:de\s*)?(?:euro|euros)\b", q):
            v = float(m.group(1))
            win = _vent(*m.span(), 14)
            if "ano" in win or "anos" in win or "años" in win:
                continue
            with_unit.append(v)

        # 3) Comparadores (permiten unidad opcional); si no hay unidad, lo metemos en bare_vals
        for m in re.finditer(r"(?:no\s*mas\s*de|menos\s*de|menor\s*de|inferior\s*a|hasta|<=|≤|<)\s*(\d+(?:\.\d+)?)\s*(m|millon|millones|k|mil|euro|euros)?", q):
            num = float(m.group(1)); suf = m.group(2)
            if suf:
                if suf in {"m", "millon", "millones"}: num *= 1_000_000
                elif suf in {"k", "mil"}:               num *= 1_000
                # euros -> tal cual
                with_unit.append(num)
            else:
                # sin unidad: miramos contexto cercano para escalar (e.g., “menos de 4 ... millones”)
                win = _vent(*m.span(), 18)
                if any(w in win for w in [" m", "m ", "millon", "millones"]):
                    num *= 1_000_000
                elif any(w in win for w in [" k", "k ", "mil"]):
                    num *= 1_000
                bare_vals.append(num)

        # 4) Frases especiales
        if "medio mill" in q:  # “medio millon/millón”
            with_unit.append(500_000.0)

        # Decisión final:
        if with_unit:
            # si hay varias, coge la MAYOR (lo más laxo y evita quedarte con un 4 mal interpretado)
            return max(with_unit)
        if bare_vals:
            # sin unidad en ninguna captura; coge la mayor (más laxo y estable)
            return max(bare_vals)

        return None





    def extraer_edades(self, query: str) -> Tuple[int | None, int | None]:
        q = self._norm(query)
        edad_max = edad_min = None
        def ok_context(span: tuple[int,int]) -> bool:
            i, j = span; ventana = q[max(0,i-18):min(len(q),j+18)]
            pistas_edad = any(w in ventana for w in ["edad","anos","años","u","sub","joven","veteran"])
            pistas_contrato = any(w in ventana for w in ["contrato","contract"])
            return pistas_edad and not pistas_contrato
        for m in re.finditer(r"(?:entre\s*)?(\d{1,2})\s*(?:-|a|y|hasta)\s*(\d{1,2})\s*(?:anos|años)?", q):
            if ok_context(m.span()):
                a,b = int(m.group(1)), int(m.group(2)); edad_min, edad_max = min(a,b), max(a,b)
        for pat in [r"(?:menor|menos)\s*de\s*(\d{1,2})\s*(?:anos|años)", r"hasta\s*(\d{1,2})\s*(?:anos|años)", r"\bsub[ -]?(\d{2})\b", r"\bu\s?(\d{2})\b", r"\b(\d{1,2})\s*(?:anos|años)\s*o\s*menos", r"edad\s*maxima\s*(\d{1,2})"]:
            for m in re.finditer(pat, q):
                if ok_context(m.span()): edad_max = min(edad_max, int(m.group(1))) if edad_max is not None else int(m.group(1))
        for pat in [r"(?:mayor|mas)\s*de\s*(\d{1,2})\s*(?:anos|años)", r"a\s*partir\s*de\s*(\d{1,2})\s*(?:anos|años)", r"\b(\d{1,2})\s*(?:anos|años)\s*o\s*mas", r"edad\s*minima\s*(\d{1,2})"]:
            for m in re.finditer(pat, q):
                if ok_context(m.span()): edad_min = max(edad_min, int(m.group(1))) if edad_min is not None else int(m.group(1))
        if ("joven" in q or "juvenil" in q or "promesa" in q) and edad_max is None: edad_max = 24
        if ("experimentado" in q or "veteran" in q or "senior" in q) and edad_min is None: edad_min = 28
        if edad_max and edad_max > 50: edad_max = None
        if edad_min and edad_min < 15: edad_min = None
        if edad_max and edad_min and edad_max < edad_min: edad_min, edad_max = edad_max, edad_min
        return edad_min, edad_max

    def extraer_posiciones(self, query: str) -> List[str]:
        q = self._norm(query); posiciones = []
        side_right = any(w in q for w in ["derecha","derecho","banda derecha","right","rw"])
        side_left  = any(w in q for w in ["izquierda","izquierdo","banda izquierda","left","lw"])
        syn = {
            "centre-back": ["defensa central","central","zaguero","stoper","stopper","libero","defensor central"],
            "left-back": ["lateral izquierdo","carrilero izquierdo","defensa izquierdo","wing-back izquierdo"],
            "right-back": ["lateral derecho","carrilero derecho","defensa derecho","wing-back derecho"],
            "defensive midfield": ["pivote","mediocentro defensivo","centrocampista defensivo","mediocampista defensivo","volante de contencion","volante de contención","cinco"],
            "central midfield": ["mediocentro","centrocampista","mediocampista","interior","medio"],
            "attacking midfield": ["mediapunta","enganche","trequartista","diez","centrocampista ofensivo","mediocampista ofensivo"],
            "left winger": ["extremo izquierdo","ala izquierda"],
            "right winger": ["extremo derecho","ala derecha"],
            "winger": ["extremo","banda","carrilero"],
            "second striker": ["segundo delantero","media punta"],
            "centre-forward": ["delantero centro","punta","nueve","9","centrodelantero"],
            "forward": ["delantero","atacante","ariete"],
            "goalkeeper": ["portero","arquero","guardameta","keeper"]
        }
        for canon, terms in syn.items():
            if any(t in q for t in terms): posiciones.append(canon)
        if "winger" in posiciones or any(t in q for t in syn["winger"]):
            if side_right: posiciones.append("right winger")
            elif side_left: posiciones.append("left winger")
        return list(dict.fromkeys(posiciones))

    @staticmethod
    def extraer_pie(query: str) -> Literal["left", "right", "both", None]:
        q = unicodedata.normalize("NFD", (query or "").lower())
        q = "".join(ch for ch in q if unicodedata.category(ch) != "Mn")
        if "zurdo" in q or "pie izquierdo" in q or "left-foot" in q: return "left"
        if "diestro" in q or "pie derecho" in q or "right-foot" in q: return "right"
        return None

    def extraer_altura(self, query: str) -> Tuple[float | None, float | None]:
        q = self._norm(query); min_m = max_m = None
        if any(w in q for w in ["alto","grande","corpulento","imponente"]): min_m = 1.83
        if any(w in q for w in ["bajo","pequeno","bajito","chico"]): max_m = 1.77
        for m in re.finditer(r"\b(\d{3})\s*cm\b", q):
            altura = int(m.group(1)) / 100.0
            if "menos" in q or "menor" in q: max_m = altura
            elif "mas" in q or "mayor" in q: min_m = altura
        for m in re.finditer(r"\b(\d(?:[.,]\d{1,2})?)\s*(?:m(?:etros?)?)\b", q):
            altura = float(m.group(1).replace(",", "."))
            if "menos" in q or "menor" in q: max_m = altura
            elif "mas" in q or "mayor" in q: min_m = altura
            else: min_m = max(min_m or altura, altura)
        m = re.search(r"\b(\d)'\s*(\d{1,2})", q)
        if m:
            feet = int(m.group(1)); inches = int(m.group(2))
            altura = feet * 0.3048 + inches * 0.0254
            if "menos" in q or "menor" in q: max_m = altura
            elif "mas" in q or "mayor" in q: min_m = altura
            else: min_m = max(min_m or altura, altura)
        if min_m is not None and (min_m < 1.4 or min_m > 2.2): min_m = None
        if max_m is not None and (max_m < 1.4 or max_m > 2.2): max_m = None
        if min_m is not None and max_m is not None and max_m < min_m: min_m, max_m = max_m, min_m
        if self.DEBUG: print(f"[A1][Altura] FINAL min={min_m} max={max_m}")
        return min_m, max_m

    def extraer_contrato_max(self, query: str) -> float | None:
        q = self._norm(query)
        m = re.search(r"(?:menos|menor|inferior)\s*de\s*(\d+(?:\.\d+)?)\s*anos", q)
        if m:
            try: return float(m.group(1))
            except: pass
        return None

    def filtrar(self, df_pre_filtrado: pl.DataFrame, query: str, tipo: Literal["jugador","portero"]) -> Tuple[pl.DataFrame, str]:
        q = self._norm(query)
        df = df_pre_filtrado
        if self.DEBUG: print(f"[A1] query='{query}' rows_iniciales={df.height}")
        
        # ---- VER ESQUEMA REAL RECIBIDO ----
        if self.DEBUG:
            print("[A1][DEBUG] columnas DF:", df.columns)

        # ---- RENOMBRA SI LLEGAN CON OTROS NOMBRES ----
        # (ej: si tu ETL dejó 'posicion' o 'posiciones' en lugar de main_position, etc.)
        rename_candidates = {}
        cols = set(df.columns)

        # main_position
        for c in ["main_position", "posicion", "position", "primary_position"]:
            if c in cols:
                rename_candidates[c] = "main_position"
                break

        # other_positions
        for c in ["other_positions", "posiciones_secundarias", "secondary_positions", "positions"]:
            if c in cols:
                rename_candidates[c] = "other_positions"
                break

        # age
        for c in ["age", "edad"]:
            if c in cols:
                rename_candidates[c] = "age"
                break

        # market_value
        for c in ["market_value", "valor_mercado", "valor"]:
            if c in cols:
                rename_candidates[c] = "market_value"
                break

        # height
        for c in ["height", "altura"]:
            if c in cols:
                rename_candidates[c] = "height"
                break

        # foot
        for c in ["foot", "pie", "dominant_foot"]:
            if c in cols:
                rename_candidates[c] = "foot"
                break

        # contract_details
        for c in ["contract_details", "contrato", "detalles_contrato"]:
            if c in cols:
                rename_candidates[c] = "contract_details"
                break

        if rename_candidates:
            # Evita renombrar una columna ya con el nombre destino
            rename_map = {k: v for k, v in rename_candidates.items() if k != v}
            if rename_map:
                df = df.rename(rename_map)
                if self.DEBUG:
                    print("[A1][DEBUG] rename_map aplicado:", rename_map)
                    print("[A1][DEBUG] columnas DF tras rename:", df.columns)

        # ---- TIPADO mínimo para filtros numéricos ----
        if "age" in df.columns:
            df = df.with_columns(pl.col("age").cast(pl.Int64, strict=False))
        if "market_value" in df.columns:
            # market_value_num se calcula más abajo si hay tope
            pass
        if "height" in df.columns:
            df = df.with_columns(pl.col("height").cast(pl.Utf8, strict=False))
        if "foot" in df.columns:
            df = df.with_columns(pl.col("foot").cast(pl.Utf8, strict=False))

        # ---- other_positions puede venir como string JSON -> lo pasamos a list[str] ----
        def _parse_other_positions(x):
            if x is None:
                return []
            if isinstance(x, list):
                return [str(y) for y in x]
            if isinstance(x, str):
                s = x.strip()
                if not s:
                    return []
                # intenta JSON primero
                try:
                    j = json.loads(s)
                    if isinstance(j, list):
                        return [str(y) for y in j]
                    if isinstance(j, str):
                        return [p.strip() for p in j.split(",") if p.strip()]
                except Exception:
                    # fallback: coma separada
                    if "," in s:
                        return [p.strip() for p in s.split(",") if p.strip()]
                    return [s]
            return []

        if "other_positions" in df.columns:
            df = df.with_columns(
                pl.col("other_positions")
                .map_elements(_parse_other_positions, return_dtype=pl.List(pl.Utf8))
                .alias("other_positions")
            )


        edad_min, edad_max = self.extraer_edades(q)
        if self.DEBUG: print(f"[A1][Edad] min={edad_min} max={edad_max}")
        if "age" in df.columns:
            if edad_max is not None:
                tol = 1 if edad_max < 30 else 0
                antes = df.height; df = df.filter(pl.col("age") <= (edad_max + tol))
                if self.DEBUG: print(f"[A1][Edad] <= {edad_max}+{tol}: {antes} -> {df.height}")
            if edad_min is not None:
                antes = df.height; df = df.filter(pl.col("age") >= edad_min)
                if self.DEBUG: print(f"[A1][Edad] >= {edad_min}: {antes} -> {df.height}")

        valor_max = self.extraer_valor_maximo(query)
        if self.DEBUG: print(f"[A1][Valor] max_detectado={valor_max}")
        if valor_max is not None:
            if "market_value_num" not in df.columns and "market_value" in df.columns:
                df = df.with_columns(
                    pl.col("market_value").map_elements(self.parse_market_value_polars, return_dtype=pl.Float64).alias("market_value_num")
                )
            if "market_value_num" in df.columns:
                antes = df.height
                df = df.filter(pl.col("market_value_num").is_not_null() & (pl.col("market_value_num") <= valor_max))
                if self.DEBUG: print(f"[A1][Valor] <= {valor_max}: {antes} -> {df.height}")


        posiciones_norm = self.extraer_posiciones(q)
        if self.DEBUG: print(f"[A1][Posicion] detectadas={posiciones_norm}")
        if posiciones_norm and "main_position" in df.columns:
            df = df.with_columns([
                pl.col("main_position").cast(pl.Utf8).str.to_lowercase().alias("main_position_lower"),
                pl.when(pl.col("other_positions").is_null()).then(pl.lit([], dtype=pl.List(pl.Utf8))).otherwise(pl.col("other_positions").cast(pl.List(pl.Utf8))).alias("other_positions_safe"),
            ])
            df = df.with_columns(
                pl.col("other_positions_safe").list.eval(
                    pl.when(pl.element().is_null()).then(pl.lit("")).otherwise(pl.element().cast(pl.Utf8).str.to_lowercase())
                ).alias("other_positions_lower")
            )
            antes = df.height
            df = df.filter(
                pl.col("main_position_lower").is_in(posiciones_norm)
                | (pl.col("other_positions_lower").list.eval(pl.element().is_in(posiciones_norm)).list.sum() > 0)
            )
            if self.DEBUG: print(f"[A1][Posicion] filtro: {antes} -> {df.height}")

        pie = self.extraer_pie(q)
        if self.DEBUG: print(f"[A1][Pie] detectado={pie}")
        if pie and "foot" in df.columns:
            if pie == "left":
                antes = df.height; df = df.filter(pl.col("foot").str.to_lowercase().is_in(["left","both"]))
                if self.DEBUG: print(f"[A1][Pie] left/both: {antes} -> {df.height}")
            elif pie == "right":
                antes = df.height; df = df.filter(pl.col("foot").str.to_lowercase().is_in(["right","both"]))
                if self.DEBUG: print(f"[A1][Pie] right/both: {antes} -> {df.height}")

        hmin, hmax = self.extraer_altura(q)
        if self.DEBUG: print(f"[A1][Altura] min={hmin} max={hmax}")
        if (hmin is not None or hmax is not None) and "height" in df.columns:
            if "height_num" not in df.columns:
                df = df.with_columns(
                    pl.col("height")
                    .str.replace_all(r"[^0-9\.,]", "")
                    .str.replace_all(",", ".")
                    .map_elements(lambda s: float(s)/100.0 if s and float(s) > 2.5 else float(s) if s else None, return_dtype=pl.Float64)
                    .alias("height_num")
                )
            if hmin is not None:
                antes = df.height; df = df.filter(pl.col("height_num") >= hmin)
                if self.DEBUG: print(f"[A1][Altura] >= {hmin}: {antes} -> {df.height}")
            if hmax is not None:
                antes = df.height; df = df.filter(pl.col("height_num") <= hmax)
                if self.DEBUG: print(f"[A1][Altura] <= {hmax}: {antes} -> {df.height}")

        contrato_max = self.extraer_contrato_max(q)
        if self.DEBUG: print(f"[A1][Contrato] max_detectado={contrato_max}")
        if "contract_details" in df.columns and "años_contrato" not in df.columns:
            hoy = datetime.date.today()
            def years_left(contract_json: Any) -> float | None:
                try:
                    d = json.loads(contract_json) if isinstance(contract_json, str) else (contract_json or {})
                    fecha = d.get("contract_expires")
                    if not fecha: return None
                    dt = datetime.datetime.strptime(fecha, "%b %d, %Y").date()
                    return (dt - hoy).days / 365.0
                except Exception:
                    return None
            df = df.with_columns(pl.col("contract_details").map_elements(years_left, return_dtype=pl.Float64).alias("años_contrato"))
        if contrato_max is not None and "años_contrato" in df.columns:
            antes = df.height; df = df.filter(pl.col("años_contrato") < contrato_max)
            if self.DEBUG: print(f"[A1][Contrato] < {contrato_max}: {antes} -> {df.height}")

        print(f"Agente 1: Filtrados {df.height} jugadores tras aplicar filtros clave.")
        return df, tipo
