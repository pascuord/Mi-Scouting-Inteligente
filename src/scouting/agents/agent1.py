# src/scouting/agents/agente1.py
from __future__ import annotations
import json, re, datetime, unicodedata
import polars as pl
from typing import Tuple, Literal, List, Dict, Any


# --- Normalización países / gentilicios / ligas ---

ALIAS_TO_NACIONALIDAD = {
  "afghanistan": "Afghanistan",
  "albania": "Albania",
  "alemania": "Alemania",
  "angola": "Angola",
  "antigua y barbuda": "Antigua y Barbuda",
  "arabia saudi": "Arabia Saudí",
  "argelia": "Argelia",
  "argentina": "Argentina",
  "armenia": "Armenia",
  "australia": "Australia",
  "austria": "Austria",
  "azerbaiyan": "Azerbaiyán",
  "banglades": "Bangladés",
  "barbados": "Barbados",
  "benin": "Benín",
  "bermudas": "Bermudas",
  "bielorrusia": "Bielorrusia",
  "bolivia": "Bolivia",
  "bosnia-herzegovina": "Bosnia-Herzegovina",
  "brasil": "Brasil",
  "bulgaria": "Bulgaria",
  "burkina faso": "Burkina Faso",
  "burundi": "Burundi",
  "belgica": "Bélgica",
  "cabo verde": "Cabo Verde",
  "camerun": "Camerún",
  "canada": "Canadá",
  "chad": "Chad",
  "chequia": "Chequia",
  "checo": "Chequia",
  "chile": "Chile",
  "china": "China",
  "chipre": "Chipre",
  "colombia": "Colombia",
  "comoros": "Comoros",
  "congo": "Congo",
  "corea del sur": "Corea del Sur",
  "costa rica": "Costa Rica",
  "croacia": "Croacia",
  "cuba": "Cuba",
  "curazao": "Curazao",
  "cote d’ivoire": "Côte d’Ivoire",
  "dr congo": "DR Congo",
  "dinamarca": "Dinamarca",
  "ecuador": "Ecuador",
  "egipto": "Egipto",
  "el salvador": "El Salvador",
  "emiratos arabes unidos": "Emiratos Árabes Unidos",
  "eritrea": "Eritrea",
  "escocia": "Escocia",
  "eslovaquia": "Eslovaquia",
  "eslovenia": "Eslovenia",
  "espana": "España",
  "estados unidos": "Estados Unidos",
  "estonia": "Estonia",
  "etiopia": "Etiopía",
  "filipinas": "Filipinas",
  "finlandia": "Finlandia",
  "francia": "Francia",
  "guf": "GUF",
  "gabon": "Gabón",
  "gales": "Gales",
  "gambia": "Gambia",
  "georgia": "Georgia",
  "ghana": "Ghana",
  "gibraltar": "Gibraltar",
  "granada": "Granada",
  "grecia": "Grecia",
  "guadalupe": "Guadalupe",
  "guatemala": "Guatemala",
  "guinea": "Guinea",
  "guinea ecuatorial": "Guinea Ecuatorial",
  "guinea-bissau": "Guinea-Bissau",
  "guyana": "Guyana",
  "haiti": "Haití",
  "honduras": "Honduras",
  "hungria": "Hungría",
  "india": "India",
  "indonesia": "Indonesia",
  "inglaterra": "Inglaterra",
  "irak": "Irak",
  "irlanda": "Irlanda",
  "irlanda del norte": "Irlanda del Norte",
  "iran": "Irán",
  "islandia": "Islandia",
  "islas feroe": "Islas Feroe",
  "israel": "Israel",
  "italia": "Italia",
  "jamaica": "Jamaica",
  "japon": "Japón",
  "jordania": "Jordania",
  "kazajistan": "Kazajistán",
  "kenia": "Kenia",
  "kosovo": "Kosovo",
  "letonia": "Letonia",
  "liberia": "Liberia",
  "libia": "Libia",
  "lituania": "Lituania",
  "luxemburgo": "Luxemburgo",
  "libano": "Líbano",
  "macedonia del norte": "Macedonia del Norte",
  "madagascar": "Madagascar",
  "malasia": "Malasia",
  "malaui": "Malaui",
  "mali": "Mali",
  "malta": "Malta",
  "marruecos": "Marruecos",
  "martinica": "Martinica",
  "mauricio": "Mauricio",
  "mauritania": "Mauritania",
  "moldavia": "Moldavia",
  "montenegro": "Montenegro",
  "montserrat": "Montserrat",
  "mozambique": "Mozambique",
  "mexico": "México",
  "namibia": "Namibia",
  "nepal": "Nepal",
  "nicaragua": "Nicaragua",
  "nigeria": "Nigeria",
  "noruega": "Noruega",
  "nueva zelanda": "Nueva Zelanda",
  "niger": "Níger",
  "palestina": "Palestina",
  "panama": "Panamá",
  "paraguay": "Paraguay",
  "paises bajos": "Países Bajos",
  "peru": "Perú",
  "polonia": "Polonia",
  "portugal": "Portugal",
  "puerto rico": "Puerto Rico",
  "rae de hong kong (china)": "RAE de Hong Kong (China)",
  "republica centroafricana": "República Centroafricana",
  "republica dominicana": "República Dominicana",
  "ruanda": "Ruanda",
  "rumania": "Rumanía",
  "rusia": "Rusia",
  "smt": "SMT",
  "stl": "STL",
  "saint lucia": "Saint Lucia",
  "san cristobal y nieves": "San Cristóbal y Nieves",
  "san vicente y las granadinas": "San Vicente y las Granadinas",
  "senegal": "Senegal",
  "serbia": "Serbia",
  "sierra leona": "Sierra Leona",
  "singapur": "Singapur",
  "siria": "Siria",
  "somalia": "Somalia",
  "sri lanka": "Sri Lanka",
  "sudan": "Sudan",
  "sudafrica": "Sudáfrica",
  "suecia": "Suecia",
  "suiza": "Suiza",
  "surinam": "Surinam",
  "tai": "TAI",
  "tailandia": "Tailandia",
  "tanzania": "Tanzania",
  "togo": "Togo",
  "trinidad y tobago": "Trinidad y Tobago",
  "turquia": "Turquía",
  "tunez": "Túnez",
  "ucrania": "Ucrania",
  "uganda": "Uganda",
  "uruguay": "Uruguay",
  "uzbekistan": "Uzbekistán",
  "vanuatu": "Vanuatu",
  "venezuela": "Venezuela",
  "zambia": "Zambia",
  "zimbabue": "Zimbabue",
  "espanol": "España",
  "espanoles": "España",
  "spanish": "España",
  "frances": "Francia",
  "franceses": "Francia",
  "french": "Francia",
  "ingles": "Inglaterra",
  "ingleses": "Inglaterra",
  "britanico": "Inglaterra",
  "britanicos": "Inglaterra",
  "aleman": "Alemania",
  "alemanes": "Alemania",
  "german": "Alemania",
  "argentino": "Argentina",
  "argentinos": "Argentina",
  "brasileno": "Brasil",
  "brasilenos": "Brasil",
  "brasileño": "Brasil",
  "brasileños": "Brasil",
  "italiano": "Italia",
  "italianos": "Italia",
  "portugues": "Portugal",
  "portugueses": "Portugal",
  "marroqui": "Marruecos",
  "marroquí": "Marruecos",
  "mexicano": "México",
  "mexicanos": "México",
  "uruguayo": "Uruguay",
  "uruguayos": "Uruguay",
  "usa": "Estados Unidos",
  "eeuu": "Estados Unidos",
  "estadounidense": "Estados Unidos",
  "holanda": "Países Bajos",
  "holandes": "Países Bajos",
  "holandeses": "Países Bajos",
  "neerlandes": "Países Bajos",
  "neerlandeses": "Países Bajos",
  "irlandes": "Irlanda",
  "irlandés": "Irlanda"
}

LEAGUE_SYNONYMS = {
    # España
    "laliga": "LaLiga", "la liga": "LaLiga", "liga española": "LaLiga",
    "laliga2": "LaLiga2", "la liga 2": "LaLiga2", "segunda division": "LaLiga2",

    # Alemania
    "bundesliga": "Bundesliga", "liga alemana": "Bundesliga",
    "2. bundesliga": "2. Bundesliga", "segunda alemana": "2. Bundesliga",
    "3. liga": "3. Liga", "tercera alemana": "3. Liga",

    # Arabia Saudi
    "saudi pro league": "Saudi Pro League", "liga saudita": "Saudi Pro League", "liga arabia": "Saudi Pro League",

    # Argentina
    "liga profesional": "Liga Profesional", "liga argentina": "Liga Profesional",

    # Australia
    "a-league": "A-League", "a league": "A-League", "liga australiana": "A-League",

    # Austria
    "bundesliga austria": "Bundesliga (Austria)", "liga austriaca": "Bundesliga (Austria)",

    # Bélgica
    "first division a": "First Division A", "liga belga": "First Division A",

    # Brasil
    "serie a brasil": "Serie A (Brasil)", "liga brasilena": "Serie A (Brasil)", "liga brasileña": "Serie A (Brasil)",
    "serie b brasil": "Serie B (Brasil)",

    # Canada
    "premier league canada": "Premier League (Canada)", "liga canadiense": "Premier League (Canada)",

    # Chile
    "primera division chile": "Primera Division (Chile)", "liga chilena": "Primera Division (Chile)",

    # China
    "super league china": "Super League (China)", "liga china": "Super League (China)",

    # Colombia
    "primera a colombia": "Primera A (Colombia)", "liga colombiana": "Primera A (Colombia)",

    # Corea del Sur
    "k league 1": "K League 1(Corea del Sur)", "k league 2": "K League 2 (Corea del Sur)", "liga coreana": "K League 1(Corea del Sur)",

    # Croacia
    "hnl": "HNL (Croacia)", "liga croata": "HNL (Croacia)",

    # Dinamarca
    "1. division dinamarca": "1. Division (Dinamarca)", "liga danesa": "1. Division (Dinamarca)",

    # Egipto
    "premier league egipto": "Premier League (Egipto)", "liga egipcia": "Premier League (Egipto)",

    # Escocia
    "premiership escocia": "Premiership (Escocia)", "liga escocesa": "Premiership (Escocia)",
    "championship escocia": "Championship (Escocia)",

    # USA
    "mls": "MLS", "major league soccer": "MLS", "liga estadounidense": "MLS",
    "usl championship": "USL Championship",

    # Finlandia
    "veikkausliiga": "Veikkausliiga", "liga finlandesa": "Veikkausliiga",

    # Francia
    "ligue1": "Ligue 1", "ligue 1": "Ligue 1", "liga francesa": "Ligue 1",
    "ligue2": "Ligue 2", "ligue 2": "Ligue 2",

    # Grecia
    "super league grecia": "Super League 1 (Grecia)", "liga griega": "Super League 1 (Grecia)",

    # India
    "indian super league": "Indian Super League", "liga india": "Indian Super League",

    # Inglaterra
    "premier league": "Premier League", "liga inglesa": "Premier League",
    "championship": "Championship",
    "league one": "League One", "league two": "League Two",

    # Irlanda
    "premier division irlanda": "Premier Division (Irlanda)", "liga irlandesa": "Premier Division (Irlanda)",

    # Islandia
    "besta deildin": "Besta deildin", "liga islandesa": "Besta deildin",

    # Italia
    "serie a": "Serie A", "liga italiana": "Serie A",
    "serie b": "Serie B",

    # Japon
    "j league": "J. League (Japón)", "liga japonesa": "J. League (Japón)",

    # Mexico
    "liga mx": "Liga MX (Mexico)", "liga mexicana": "Liga MX (Mexico)",

    # Noruega
    "eliteserien": "Eliteserien", "liga noruega": "Eliteserien",

    # Holanda
    "eredivisie": "Eredivisie", "liga holandesa": "Eredivisie", "liga neerlandesa": "Eredivisie",
    "eerste divisie": "Eerste Divisie",

    # Polonia
    "ekstraklasa": "Ekstraklasa", "liga polaca": "Ekstraklasa",

    # Portugal
    "liga portugal": "Liga Portugal", "liga portuguesa": "Liga Portugal",

    # Rusia
    "premier league rusia": "Premier League (Rusia)", "liga rusa": "Premier League (Rusia)",

    # Suecia
    "allsvenskan": "Allsvenskan", "liga sueca": "Allsvenskan",

    # Suiza
    "super league suiza": "Super League (Suiza)", "liga suiza": "Super League (Suiza)",
    "challenge league suiza": "Challenge League (Suiza)",

    # Thailandia
    "thai league": "Thai League", "liga tailandesa": "Thai League",

    # Turquia
    "super lig": "Super Lig (Turquía)", "liga turca": "Super Lig (Turquía)",
}

# Mapa liga -> país canon
LEAGUE_TO_COUNTRY = {
    "LaLiga": "espana", "LaLiga2": "espana",
    "Bundesliga": "alemania", "2. Bundesliga": "alemania", "3. Liga": "alemania",
    "Saudi Pro League": "arabia saudi",
    "Liga Profesional": "argentina",
    "A-League": "australia",
    "Bundesliga (Austria)": "austria",
    "First Division A": "belgica",
    "Serie A (Brasil)": "brasil", "Serie B (Brasil)": "brasil",
    "Premier League (Canada)": "canada",
    "Primera Division (Chile)": "chile",
    "Super League (China)": "china",
    "Primera A (Colombia)": "colombia",
    "K League 1(Corea del Sur)": "corea del sur", "K League 2 (Corea del Sur)": "corea del sur",
    "HNL (Croacia)": "croacia",
    "1. Division (Dinamarca)": "dinamarca",
    "Premier League (Egipto)": "egipto",
    "Premiership (Escocia)": "escocia", "Championship (Escocia)": "escocia",
    "MLS": "usa", "USL Championship": "usa",
    "Veikkausliiga": "finlandia",
    "Ligue 1": "francia", "Ligue 2": "francia",
    "Super League 1 (Grecia)": "grecia",
    "Indian Super League": "india",
    "Premier League": "inglaterra", "Championship": "inglaterra", "League One": "inglaterra", "League Two": "inglaterra",
    "Premier Division (Irlanda)": "irlanda",
    "Besta deildin": "islandia",
    "Serie A": "italia", "Serie B": "italia",
    "J. League (Japón)": "japon",
    "Liga MX (Mexico)": "mexico",
    "Eliteserien": "noruega",
    "Eredivisie": "holanda", "Eerste Divisie": "holanda",
    "Ekstraklasa": "polonia",
    "Liga Portugal": "portugal",
    "Premier League (Rusia)": "rusia",
    "Allsvenskan": "suecia",
    "Super League (Suiza)": "suiza", "Challenge League (Suiza)": "suiza",
    "Thai League": "thailandia",
    "Super Lig (Turquía)": "turquia",
}


def _canon_country_token(token: str) -> str | None:
    """Devuelve la nacionalidad exacta (e.g., 'España') si el token coincide con un alias."""
    ss = token.strip().lower()
    ss = unicodedata.normalize("NFD", ss)
    ss = "".join(ch for ch in ss if unicodedata.category(ch) != "Mn")
    ss = re.sub(r"[^\w]", "", ss)  # 🔥 elimina puntuación como comas, puntos, etc.
    nacionalidad = ALIAS_TO_NACIONALIDAD.get(ss)
    return nacionalidad


def _norm_text(s: str) -> str:
    t = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")





class Agente1HardFilter:
    DEBUG = True  # ponlo a False en producción

    def __init__(self, llm=None):
        self.llm = llm
        # Mapeo de posiciones en español a inglés (estándar del dataframe)
        self.posiciones_es_to_en = {
            "defensa central": "centre-back",
            "central": "centre-back",
            "zaguero": "centre-back",
            "stoper": "centre-back",
            "stopper": "centre-back",
            "libero": "centre-back",
            "defensor central": "centre-back",
            "lateral izquierdo": "left-back",
            "carrilero izquierdo": "left midfield",
            "defensa izquierdo": "left-back",
            "wing-back izquierdo": "left-back",
            "lateral derecho": "right-back",
            "carrilero derecho": "right midfield",
            "defensa derecho": "right-back",
            "wing-back derecho": "right-back",
            "lateral": "full-back",
            "carrilero": "left midfield",
            "wing-back": "full-back",
            "pivote": "defensive midfield",
            "mediocentro defensivo": "defensive midfield",
            "centrocampista defensivo": "defensive midfield",
            "mediocampista defensivo": "defensive midfield",
            "volante de contencion": "defensive midfield",
            "volante de contención": "defensive midfield",
            "cinco": "defensive midfield",
            "mediocentro": "central midfield",
            "centrocampista": "central midfield",
            "mediocampista": "central midfield",
            "interior": "central midfield",
            "medio": "central midfield",
            "mediapunta": "attacking midfield",
            "enganche": "attacking midfield",
            "trequartista": "attacking midfield",
            "diez": "attacking midfield",
            "centrocampista ofensivo": "attacking midfield",
            "mediocampista ofensivo": "attacking midfield",
            "extremo izquierdo": "left winger",
            "ala izquierda": "left winger",
            "extremo derecho": "right winger",
            "ala derecha": "right winger",
            "extremo": "winger",
            "banda": "winger",
            "segundo delantero": "second striker",
            "delantero centro": "centre-forward",
            "nueve": "centre-forward",
            "9": "centre-forward",
            "centrodelantero": "centre-forward",
            "delantero": "forward",
            "atacante": "forward",
            "ariete": "forward",
            "portero": "goalkeeper",
            "arquero": "goalkeeper",
            "guardameta": "goalkeeper",
            "keeper": "goalkeeper"
        }

    # --- Normalización países / gentilicios / ligas ---


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
        for m in re.finditer(r"[<≤]\s*(\d+(?:\.\d+)?)(m|millones?|k|mil|euro|euros)?", q):
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

        # 4) Frases tipo "precio máximo X millones", "coste hasta X", etc.
        for m in re.finditer(
            r"(?:precio|valor|coste|cueste|cuesta|vale|máximo|maximo|por|hasta)\s*(?:de\s*)?(\d+(?:\.\d+)?)\s*(m|millones?|k|mil|euro|euros)?",
            q
        ):
            num = float(m.group(1))
            suf = m.group(2)
            if suf:
                if suf in {"m", "millon", "millones"}: num *= 1_000_000
                elif suf in {"k", "mil"}:              num *= 1_000
            else:
                win = _vent(*m.span(), 18)
                if any(w in win for w in [" m", "m ", "millon", "millones"]):
                    num *= 1_000_000
                elif any(w in win for w in [" k", "k ", "mil"]):
                    num *= 1_000
            with_unit.append(num)

        # 5) Frases especiales
        # Cap por semántica "barato"
        if any(w in q for w in ["muy barato", "baratisimo", "baratísimo"]):
            return 300_000.0
        if any(w in q for w in ["barato", "asequible", "low cost", "económico", "economico"]):
            return 1_000_000.0


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
        # Operadores simbólicos con o sin 'años'
        m = re.search(r"[<≤]\s*(\d{1,2})\s*(?:anos|años)?", q)
        if m:
            edad_max = min(edad_max, int(m.group(1))) if edad_max is not None else int(m.group(1))

        m = re.search(r"[>≥]\s*(\d{1,2})\s*(?:anos|años)?", q)
        if m:
            edad_min = max(edad_min, int(m.group(1))) if edad_min is not None else int(m.group(1))

        if ("joven" in q or "juvenil" in q or "promesa" in q) and edad_max is None: edad_max = 24
        if ("experimentado" in q ) and edad_min is None: edad_min = 27
        if ("veteran" in q or "senior" in q) and edad_min is None: edad_min = 30
        
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
            "full-back": ["lateral ","carrilero ","wing-back"],
            "left midfield": ["carrilero izquierdo","wing-back izquierdo"],
            "right midfield": ["carrilero derecho", "wing-back derecho"],
            "defensive midfield": ["pivote","mediocentro defensivo","centrocampista defensivo","mediocampista defensivo","volante de contencion","volante de contención","cinco", "centrocampista"],
            "central midfield": ["mediocentro","centrocampista","mediocampista","interior","medio",],
            "attacking midfield": ["mediapunta","enganche","trequartista","diez","centrocampista ofensivo","mediocampista ofensivo", "centrocampista"],
            "left winger": ["extremo izquierdo","ala izquierda"],
            "right winger": ["extremo derecho","ala derecha"],
            "winger": ["extremo","banda","carrilero"],
            "second striker": ["segundo delantero","mediapunta"],
            "centre-forward": ["delantero centro","nueve","9","centrodelantero"],
            "forward": ["delantero","atacante","ariete"],
            "goalkeeper": ["portero","arquero","guardameta","keeper"]
        }
        for canon, terms in syn.items():
            if any(t in q for t in terms): posiciones.append(canon)
        if "winger" in posiciones or any(t in q for t in syn["winger"]):
            if side_right: posiciones.append("right winger")
            elif side_left: posiciones.append("left winger")
            else: 
                posiciones.append("left winger")
                posiciones.append("right winger")
        if "full-back" in posiciones or any(t in q for t in syn["full-back"]):
            if side_right: posiciones.append("right-back")
            elif side_left: posiciones.append("left-back")
            else: 
                posiciones.append("left-back")
                posiciones.append("right-back")
        if "forward" in posiciones or any(t in q for t in syn["forward"]):
            posiciones.append("centre-forward")
            posiciones.append("second striker")

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
        if any(w in q for w in ["alto","grande","corpulento","imponente"]): 
            min_m = 1.83
            return min_m, max_m
        
        if any(w in q for w in ["bajo","pequeno","bajito","chico"]): 
            max_m = 1.75
            return min_m, max_m
        # Regex para capturar cosas como "1.83m", "183cm", "2 m", etc.
        for match in re.finditer(r"(\d+(?:[\.,]\d+)?)(\s*)(cm|m)?\b", q, re.IGNORECASE):
            num_str, _, unidad = match.groups()
            if unidad and unidad not in ("m", "cm"):
                return min_m, max_m  # ← ignorar cosas como "M" (mayúscula), "mil", etc.
            try:
                num = float(num_str.replace(",", "."))
            except ValueError:
                continue

            if unidad == "cm" or (unidad is None and num > 100):
                altura = num / 100
                if "menos" in q or "menor" in q: max_m = altura
                elif "mas" in q or "mayor" in q: min_m = altura
                
            elif unidad == "m":
                altura = num
                if "menos" in q or "menor" in q: max_m = altura
                elif "mas" in q or "mayor" in q: min_m = altura


        
        if min_m is not None and (min_m < 1.4 or min_m > 2.2): min_m = None
        if max_m is not None and (max_m < 1.4 or max_m > 2.2): max_m = None
        if min_m is not None and max_m is not None and max_m < min_m: min_m, max_m = max_m, min_m
        if self.DEBUG: print(f"[A1][Altura] FINAL min={min_m} max={max_m}")
        return min_m, max_m

    def extraer_contrato_max(self, query: str) -> float | None:
        q = self._norm(query)

        # Patrones explícitos con "último año" o "último año de contrato"
        if re.search(r"(?:ultim|últim)o\s+a(?:n|ñ)o(?:s)?(?:\s+de\s+contrato)?", q):
            return 1.0

        # Solo interpretamos "menos de X años" como contrato si hay contexto claro de contrato.
        if any(w in q for w in ["contrato", "contract", "quede", "queden", "de contrato", "año de contrato", "años de contrato"]):
            m = re.search(r"(?:menos|menor|inferior)\s*de\s*(\d+(?:\.\d+)?)\s*a(?:n|ñ)os", q)
            if m:
                try: return float(m.group(1))
                except: pass

        # patrón: "le quedan menos de dos años", "menos de 2 años de contrato"
        for m in re.finditer(r"(?:menos\s+de\s+)(\d+)\s+a(?:n|ñ)os", q):
            if any(w in q for w in ["contrato", "quede", "queden", "de contrato"]):
                max_anios = int(m.group(1))
                return max_anios
        
        for m in re.finditer(r"(?:qu(?:e|é)\s+(?:le\s+)?quede[n]?\s+(?:menos\s+de\s+)?)(\d+)\s+a(?:n|ñ)os(?:\s+de\s+contrato)?", q):
            max_anios = int(m.group(1))
            return max_anios

        NUMERAL_MAP = {
            "un": 1, "uno": 1, "una": 1,
            "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
            "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
        }

        # en el parser
        for word, val in NUMERAL_MAP.items():
            if re.search(rf"menos\s+de\s+{word}\s+a(?:n|ñ)os(?:\s+de\s+contrato)?", q) and any(w in q for w in ["contrato", "quede", "queden", "de contrato"]):
                return val
            if re.search(rf"qu(?:e|é)\s+(?:le\s+)?quede[n]?\s+menos\s+de\s+{word}\s+a(?:n|ñ)os(?:\s+de\s+contrato)?", q):
                return val

        return None
    
    def extraer_nacionalidades(self, query: str) -> List[str]:
        """
        Detecta intenciones de nacionalidad: 'jugador ingles', 'de origen frances', 'portugueses', etc.
        Devuelve lista de países canónicos (claves de COUNTRY_ALIASES), p.ej. ['inglaterra','francia'].
        """
        q = _norm_text(query)
        targets: set[str] = set()

        # patrones básicos con 'jugador(es)' y 'origen'
        for m in re.finditer(r"(?:jugador(?:es)?\s*(?:de\s*)?(?:origen\s*)?)([a-záéíóúñ]+)", q):
            canon = _canon_country_token(m.group(1))
            if canon: targets.add(canon)

        # 'jugador ingles', 'defensa frances', sin 'jugador' explícito (permitimos en adyacencias)
        for m in re.finditer(r"\b([a-záéíóúñ]+)(?:es)?\b", q):
            token = m.group(1)
            # solo si está cerca de 'jugador', 'defensa', 'central', etc.
            i, j = m.span()
            win = q[max(0, i-15):min(len(q), j+15)]
            if any(w in win for w in ["jugador","central","defensa","delantero","portero","lateral","extremo","pivote","mediocentro"]):
                canon = _canon_country_token(token)
                if canon: targets.add(canon)

        # Búsqueda ampliada en toda la query
        tokens = q.split()
        for i, token in enumerate(tokens):
            canon = _canon_country_token(token)
            if canon:
                # Omite país si aparece en contexto de liga/ubicación (ej. "en <país>" o "liga <país>"):
                if i > 0 and tokens[i-1] in {"en", "jugando", "juegue"}:
                    continue
                if i > 1 and tokens[i-2] == "liga":
                    continue
                targets.add(canon)



        return list(targets)


    def extraer_ligas(self, query: str) -> List[str]:
        """
        Detecta nombres de ligas por alias y devuelve los nombres tal cual aparecen en tu DF ('liga').
        """
        q = _norm_text(query)
        hits: set[str] = set()
        # busca frases 'de la X', 'en la X', etc., y alias sueltos
        for alias, canon in LEAGUE_SYNONYMS.items():
            if alias in q:
                hits.add(canon)
        # también patrones 'de (la) liga X' si llegan con ruido
        for m in re.finditer(r"liga\s+([a-z0-9\. ]{2,20})", q):
            alias = _norm_text(m.group(1)).strip()
            alias = alias.replace(".", "").replace("  "," ")
            if alias in LEAGUE_SYNONYMS:
                hits.add(LEAGUE_SYNONYMS[alias])
        return list(hits)


    def extraer_paises_de_liga(self, query: str) -> List[str]:
        """
        Detecta 'liga española/inglesa/...', 'liga de francia', 'que juegue en alemania', etc.
        Devuelve países canónicos (claves COUNTRY_ALIASES) para filtrar por columna 'pais'.
        """
        q = _norm_text(query)
        targets: set[str] = set()

        # "liga española", "liga inglesa", ...
        for adj, canon in LEAGUE_TO_COUNTRY.items():
            if f"liga {adj}" in q or f"la liga {adj}" in q:
                targets.add(canon)

        # "liga de francia", "liga de alemania"
        for m in re.finditer(r"(?:de\s+(?:la\s+)?)liga\s+([a-záéíóúñ ]+)", q):
            cand = _canon_country_token(m.group(1).strip())
            if cand: targets.add(cand)

        # "que juegue en alemania", "en francia", "jugando en portugal", etc.
        for m in re.finditer(r"(?:en|jugando en|que juegue en)\s+([a-záéíóúñ ]+)", q):
            cand = _canon_country_token(m.group(1).strip())
            if cand: targets.add(cand)

        return list(targets)


    def extraer_criterios_llm(self, query: str) -> dict:
        """
        Usa el LLM para extraer criterios de filtrado de la query.
        Devuelve un dict con claves: edad_min, edad_max, valor_max_euros, posiciones, nacionalidad, pie_dominante, altura_min_cm, altura_max_cm, contrato_max_anios, etc.
        """
        if not self.llm:
            return {}  # fallback vacío si no hay LLM

        prompt = f"""
Eres un extractor de criterios para scouting de fútbol.
Dada una query en español, extrae SOLO JSON válido con claves para filtros duros.
Claves posibles: edad_min (int o null), edad_max (int o null), valor_max_euros (float o null), posiciones (lista de str en INGLÉS o null), nacionalidad (str o null), pie_dominante (str: 'left'/'right' o null), altura_min_cm (int o null), altura_max_cm (int o null), contrato_max_anios (float o null), liga (str o null).
REGLAS:
- Solo extrae si es relevante para scouting (edad, valor, posición, nacionalidad, pie, altura, contrato, liga).
- Normaliza posiciones a INGLÉS estándar (valores posibles: 'centre-back', 'left-back', 'right-back', 'full-back', 'left midfield', 'right midfield', 'defensive midfield', 'central midfield', 'attacking midfield', 'left winger', 'right winger', 'winger', 'second striker', 'centre-forward', 'forward', 'goalkeeper').
- Para valores, incluye unidad implícita (e.g., 'millones' -> multiplica por 1e6).
- Nacionalidad como país canónico (e.g., 'inglés' -> 'Inglaterra').
- DESAMBIGUACIÓN GEOGRÁFICA: Distingue siempre la nacionalidad del jugador de la liga en la que juega. Ej: En "pivote belga de la liga italiana", la nacionalidad es 'Bélgica' y la liga es 'Italia'.
- NORMALIZACIÓN DE LIGAS: Si se pide una liga, debes devolver SU NOMBRE EXACTO según este formato oficial: 'LaLiga', 'Super League (Suiza)', 'Super Lig (Turquía)', 'Premiership (Escocia)'. Si no sabes el formato exacto, devuelve el nombre del país (ej. 'España').
- Si no hay criterio, pon null.
- Sé conservador: no inventes criterios no mencionados.

EJEMPLOS:
- "Extremo izquierdo menor de 25 años con valor menor de 10 millones" -> {{"edad_max": 25, "valor_max_euros": 10000000.0, "posiciones": ["left winger"], "edad_min": null, "nacionalidad": null, "liga": null, "pie_dominante": null, "altura_min_cm": null, "altura_max_cm": null, "contrato_max_anios": null}}
- "Portero barato zurdo de España" -> {{"valor_max_euros": 1000000.0, "posiciones": ["goalkeeper"], "nacionalidad": "España", "liga": null, "pie_dominante": "left", "edad_min": null, "edad_max": null, "altura_min_cm": null, "altura_max_cm": null, "contrato_max_anios": null}}
- "Mediocentro belga de la liga española" -> {{"edad_max": null, "valor_max_euros": null, "posiciones": ["central midfield"], "edad_min": null, "nacionalidad": "Bélgica", "liga": "LaLiga", "pie_dominante": null, "altura_min_cm": null, "altura_max_cm": null, "contrato_max_anios": null}}

Query: {query}
Responde SOLO JSON.
"""

        try:
            raw = self.llm.invoke(prompt).content.strip()
            if raw.startswith("```json"):
                raw = raw.replace("```json", "", 1)
            if raw.endswith("```"):
                raw = raw[::-1].replace("```", "", 1)[::-1]
            raw = raw.strip()
            data = json.loads(raw)
            return data
        except Exception as e:
            if self.DEBUG:
                print(f"[A1][LLM] Error extrayendo criterios: {e}")
            return {}

    def normalizar_posiciones(self, posiciones: list[str]) -> list[str]:
        """
        Normaliza posiciones (de español a inglés si es necesario, y a lowercase).
        Usa el mapeo interno de posiciones_es_to_en.
        """
        normalized = []
        for pos in (posiciones or []):
            pos_lower = pos.lower().strip()
            # Primero intenta normalizar usando el mapeo español->inglés
            if pos_lower in self.posiciones_es_to_en:
                normalized.append(self.posiciones_es_to_en[pos_lower])
            else:
                # Si no está en el mapeo, asume que ya está en inglés y lo usa directamente
                normalized.append(pos_lower)
        # Deduplica manteniendo orden
        return list(dict.fromkeys(normalized))

    def filtrar(self, df_pre_filtrado: pl.DataFrame, query: str, tipo: Literal["jugador","portero"]) -> Tuple[pl.DataFrame, str]:
        q = self._norm(query)
        df = df_pre_filtrado
        if self.DEBUG: print(f"[A1] query='{query}' rows_iniciales={df.height}")
        
        # Extraer criterios con LLM
        criterios_llm = self.extraer_criterios_llm(query)
        if self.DEBUG: print(f"[A1][LLM] criterios extraídos: {criterios_llm}")
        
        # Fallback a métodos regex si LLM falla o está vacío
        if not criterios_llm:
            criterios_llm = {
                "edad_min": None,
                "edad_max": None,
                "valor_max_euros": None,
                "posiciones": [],
                "nacionalidad": None,
                "pie_dominante": None,
                "altura_min_cm": None,
                "altura_max_cm": None,
                "contrato_max_anios": None,
            }
            # Usar métodos actuales como fallback
            criterios_llm["edad_min"], criterios_llm["edad_max"] = self.extraer_edades(q)
            criterios_llm["valor_max_euros"] = self.extraer_valor_maximo(query)
            criterios_llm["posiciones"] = self.extraer_posiciones(q)
            criterios_llm["pie_dominante"] = self.extraer_pie(q)
            criterios_llm["altura_min_cm"], criterios_llm["altura_max_cm"] = self.extraer_altura(q)
            criterios_llm["contrato_max_anios"] = self.extraer_contrato_max(q)
            # Nacionalidad y liga no están en LLM aún, pero podemos agregar
            nacionalidades = self.extraer_nacionalidades(q)
            if nacionalidades:
                criterios_llm["nacionalidad"] = nacionalidades[0]  # tomar primera
            if self.DEBUG: print(f"[A1][Fallback] usando métodos regex: {criterios_llm}")
        
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


        edad_min, edad_max = criterios_llm.get("edad_min"), criterios_llm.get("edad_max")
        if self.DEBUG: print(f"[A1][Edad] min={edad_min} max={edad_max}")
        if "age" in df.columns:
            if edad_max is not None:
                #tol = 1 if edad_max < 30 else 0
                antes = df.height; df = df.filter(pl.col("age") <= (edad_max))
                if self.DEBUG: print(f"[A1][Edad] <= {edad_max}: {antes} -> {df.height}")
            if edad_min is not None:
                antes = df.height; df = df.filter(pl.col("age") >= edad_min)
                if self.DEBUG: print(f"[A1][Edad] >= {edad_min}: {antes} -> {df.height}")

        valor_max = criterios_llm.get("valor_max_euros")
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


        posiciones_norm = criterios_llm.get("posiciones", [])
        # Normalizar posiciones (español -> inglés si es necesario)
        posiciones_norm = self.normalizar_posiciones(posiciones_norm)
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

        pie = criterios_llm.get("pie_dominante")
        if self.DEBUG: print(f"[A1][Pie] detectado={pie}")
        if pie and "foot" in df.columns:
            if pie == "left":
                antes = df.height; df = df.filter(pl.col("foot").str.to_lowercase().is_in(["left","both"]))
                if self.DEBUG: print(f"[A1][Pie] left/both: {antes} -> {df.height}")
            elif pie == "right":
                antes = df.height; df = df.filter(pl.col("foot").str.to_lowercase().is_in(["right","both"]))
                if self.DEBUG: print(f"[A1][Pie] right/both: {antes} -> {df.height}")

        # Filtro por nacionalidad
        nacionalidad = criterios_llm.get("nacionalidad")
        if self.DEBUG: print(f"[A1][Nacionalidad] detectada={nacionalidad}")
        if nacionalidad:
            nacionalidad_norm = _norm_text(nacionalidad)
            if "nacionalidad" in df.columns:
                df = df.with_columns(
                    pl.col("nacionalidad")
                    .cast(pl.Utf8, strict=False)
                    .map_elements(_norm_text, return_dtype=pl.Utf8)
                    .alias("nacionalidad_norm")
                )
                antes = df.height
                df = df.filter(pl.col("nacionalidad_norm") == nacionalidad_norm)
                if self.DEBUG: print(f"[A1][Nacionalidad] == {nacionalidad} (nacionalidad): {antes} -> {df.height}")
            elif "pais" in df.columns:
                df = df.with_columns(
                    pl.col("pais")
                    .cast(pl.Utf8, strict=False)
                    .map_elements(_norm_text, return_dtype=pl.Utf8)
                    .alias("pais_norm")
                )
                antes = df.height
                df = df.filter(pl.col("pais_norm") == nacionalidad_norm)
                if self.DEBUG: print(f"[A1][Nacionalidad] == {nacionalidad} (pais fallback): {antes} -> {df.height}")

        hmin, hmax = criterios_llm.get("altura_min_cm"), criterios_llm.get("altura_max_cm")
        if hmin: hmin /= 100.0  # convertir cm a m
        if hmax: hmax /= 100.0
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

        contrato_max = criterios_llm.get("contrato_max_anios")
        if self.DEBUG: print(f"[A1][Contrato] max_detectado={contrato_max}")
        if "contract_details" in df.columns and "años_contrato" not in df.columns:
            hoy = datetime.date.today()
            def years_left(contract_json: Any) -> float | None:
                try:
                    d = json.loads(contract_json) if isinstance(contract_json, str) else (contract_json or {})
                    fecha = d.get("contract_expires") or d.get("expires") or d.get("contract_end")
                    if not fecha:
                        return None
                    fecha = str(fecha).strip()
                    for fmt in ["%b %d, %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %B %Y", "%Y/%m/%d", "%d.%m.%Y"]:
                        try:
                            dt = datetime.datetime.strptime(fecha, fmt).date()
                            return (dt - hoy).days / 365.0
                        except Exception:
                            continue
                    return None
                except Exception:
                    return None
            df = df.with_columns(pl.col("contract_details").map_elements(years_left, return_dtype=pl.Float64).alias("años_contrato"))
        if contrato_max is not None and "años_contrato" in df.columns:
            if self.DEBUG:
                sample_ok = df.filter(pl.col("años_contrato").is_not_null()).select(["contract_details", "años_contrato"]).head(3).to_dicts()
                sample_null = df.filter(pl.col("años_contrato").is_null()).select(["contract_details", "años_contrato"]).head(3).to_dicts()
                print(f"[A1][Contrato][DEBUG] contrato_max={contrato_max}")
                print(f"[A1][Contrato][DEBUG] sample parsed contract_details/años_contrato (not null): {sample_ok}")
                print(f"[A1][Contrato][DEBUG] sample unparsed contract_details/años_contrato (null): {sample_null}")
            antes = df.height
            df = df.filter(pl.col("años_contrato").is_not_null() & (pl.col("años_contrato") < contrato_max))
            if self.DEBUG: print(f"[A1][Contrato] < {contrato_max}: {antes} -> {df.height}")


        # ---- Nacionalidad ----
        nacionalidades_canon = self.extraer_nacionalidades(query)
        if self.DEBUG: print(f"[A1][Nacionalidad] detectadas={nacionalidades_canon}")
        if nacionalidades_canon and "nacionalidad" in df.columns:
            df = df.with_columns(
                pl.col("nacionalidad")
                .cast(pl.Utf8, strict=False)
                .map_elements(_norm_text, return_dtype=pl.Utf8)
                .alias("nacionalidad_norm")
            )

            nacionalidades_norm = set(_norm_text(n) for n in nacionalidades_canon)
            if self.DEBUG: print(f"[A1][Nacionalidad] búsqueda normalizadas={nacionalidades_norm}")

            antes = df.height
            df = df.filter(
                (pl.col("nacionalidad_norm").is_in(nacionalidades_norm)) &
                (pl.col("nacionalidad_norm") != "")
            )
            if self.DEBUG: print(f"[A1][Nacionalidad] filtro: {antes} -> {df.height}")


        # ---- Liga explícita ----
        ligas = self.extraer_ligas(query)
        if self.DEBUG: print(f"[A1][Liga] detectadas={ligas}")
        if ligas and "liga" in df.columns:
            df = df.with_columns(pl.col("liga").cast(pl.Utf8, strict=False).alias("liga"))
            antes = df.height
            df = df.filter(pl.col("liga").is_in(ligas))
            if self.DEBUG: print(f"[A1][Liga] filtro: {antes} -> {df.height}")

        # ---- País de la liga (solo si no contradice ligas o si no hay ligas) ----
        paises_liga = self.extraer_paises_de_liga(query)
        

        def filtrar_por_pais_liga(df, paises_liga: list[str], campo_df: str = "pais") -> tuple:
            """
            Filtra el DataFrame por país de la liga, usando los alias definidos en ALIAS_TO_NACIONALIDAD.
            Retorna (df_filtrado, lista_paises_detectados)
            """
            # Construir mapa invertido solo una vez (alias normalizado → nombre canónico)
            NOMBRE_NORMALIZADO_TO_CANON = {}
            for k, v in ALIAS_TO_NACIONALIDAD.items():
                norm_k = _norm_text(k)
                norm_v = _norm_text(v)
                NOMBRE_NORMALIZADO_TO_CANON[norm_k] = v
                NOMBRE_NORMALIZADO_TO_CANON[norm_v] = v  # Incluimos también el valor canónico

            # Normalizar entrada y resolver a canon
            canon_targets = set()
            for p in paises_liga:
                canon = NOMBRE_NORMALIZADO_TO_CANON.get(_norm_text(p))
                if canon:
                    canon_targets.add(canon)

            if not canon_targets:
                if self.DEBUG: print("[A1][PaisLiga] sin targets detectados: no se filtra por país")
                return df, []


            df_filtrado = df.filter(df[campo_df].is_in(canon_targets))
            return df_filtrado, list(canon_targets)
        
        # paises_liga detectado antes por Agente1
        # FIX: Inicializamos 'antes_pais' con el tamaño actual del DataFrame antes del filtro.
        # Esto evita un 'UnboundLocalError' que haría crashear el bot al imprimir los logs (DEBUG)
        # en caso de que la consulta del usuario no haya activado ningún filtro numérico previo.
        antes_pais = df.height  # <-- CREAMOS LA VARIABLE AQUÍ
        df, paises_detectados = filtrar_por_pais_liga(df, paises_liga)
        
        if self.DEBUG: 
            print(f"[A1][PaisLiga] detectados={paises_detectados}")
            print(f"[A1][PaisLiga] filtro: {antes_pais} -> {df.height}")

        print(f"Agente 1: Filtrados {df.height} jugadores tras aplicar filtros clave.")
        return df, tipo
