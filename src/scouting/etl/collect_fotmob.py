# src/scouting/etl/collect_fotmob.py
import os
import re
import json
import time
import asyncio
import logging
import random
from pathlib import Path
from datetime import datetime

import requests
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from curl_cffi.requests import AsyncSession
import brotli  

# ==============================================================================
# NOTA DE ARQUITECTURA: OPTIMIZACIÓN DEL SCRAPER DE FOTMOB (V3)
# ==============================================================================
# Este script implementa una estrategia avanzada de extracción asíncrona para 
# evadir bloqueos (Error 403) y minimizar la carga en los servidores de FotMob:
#
# 1. Bypass de Next.js (__NEXT_DATA__): Se ha eliminado la necesidad de hacer 
#    múltiples peticiones por jugador o depender exclusivamente del parseo frágil 
#    del DOM (HTML). En su lugar, se intercepta el JSON oculto de Next.js en el 
#    código fuente, obteniendo todas las métricas avanzadas de una sola vez.
#    -> Beneficio técnico: Acceso directo a datos estructurados puros, inmunidad 
#       total ante rediseños visuales de la interfaz (desacoplamiento UI) y 
#       reducción drástica del "footprint" de red al evitar peticiones en cascada.
#
# 2. Consolidación de Peticiones: Lógicas anteriores como `_parse_season_dom_map` 
#    se han integrado directamente en `process_player_async`. Ahora, con una 
#    ÚNICA petición HTTP por jugador, se extraen: Rasgos (Traits), Mapeo de 
#    temporadas y Estadísticas completas.
#
# 3. Impersonación y Concurrencia: Se utiliza `curl_cffi` (impersonate="chrome110") 
#    para generar una huella digital idéntica a un navegador real, junto con 
#    semáforos asíncronos (`asyncio.Semaphore`) y tiempos de espera aleatorios 
#    para garantizar una recolección masiva, estable y libre de baneos.
# ==============================================================================

def _decode_response_to_html(resp: requests.Response) -> str:
    enc = (resp.headers.get("Content-Encoding") or "").lower()
    if enc == "br":
        try:
            return brotli.decompress(resp.content).decode(resp.encoding or "utf-8", errors="replace")
        except Exception:
            return resp.text
    else:
        return resp.text

def _soup_from_response(resp: requests.Response) -> BeautifulSoup:
    html = _decode_response_to_html(resp)
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")

# ==== Config =====
load_dotenv()

def get_data_dir() -> Path:
    # 1. Prioridad: Variable de entorno (si es absoluta)
    env_data = os.getenv("DATA_DIR")
    if env_data and os.path.isabs(env_data):
        return Path(env_data)
    
    # 2. Fallback: Buscar carpeta 'data' en la raíz del repo
    # Asumimos que este archivo está en src/scouting/etl/
    root_repo = Path(__file__).resolve().parents[3]
    local_data = root_repo / "data"
    
    # Si no existe y estamos en Docker, quizás /data sí exista
    if not local_data.exists() and os.path.exists("/data"):
        return Path("/data")
        
    return local_data

DATA_DIR = get_data_dir()
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"

RAW_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

X_MAS_ENV = os.getenv("X_MAS_TOKEN", "").strip()
x_mas_fallback = "eyJib2R5Ijp7InVybCI6Ii9hcGkvY3VycmVuY3kiLCJjb2RlIjoxNzY1Nzk1MzgxOTM5LCJmb28iOiJwcm9kdWN0aW9uOjAzNTY1MDkxM2Y1M2I5YzMwOWUxMzU1YzJjYTZmNTc1ZjE4YmZkOTEifSwic2lnbmF0dXJlIjoiQjM5NzZCOUQwQTM1MEU4NTczQjlFMjVFOUZBNTJBQzYifQ=="
X_MAS = X_MAS_ENV or x_mas_fallback


class FotmobMassiveScraper:
    def __init__(self):
        self.base_url = "https://www.fotmob.com"
        self.x_mas = X_MAS
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Puedes reducir a pocas ligas para probar
        self.leagues = [
            {"id": 87, "nombre": "LaLiga", "pais": "España", "temporada": "2025-2026"},
          {"id": 140, "nombre": "LaLiga2", "pais": "España", "temporada": "2025-2026"},
          {"id": 54, "nombre": "Bundesliga", "pais": "Alemania", "temporada": "2025-2026"},
          {"id": 146, "nombre": "2. Bundesliga", "pais": "Alemania", "temporada": "2025-2026"},
          {"id": 208, "nombre": "3. Liga", "pais": "Alemania", "temporada": "2025-2026"},
          {"id": 536, "nombre": "Saudi Pro League", "pais": "Arabia Saudi", "temporada": "2025-2026"},
          {"id": 112, "nombre": "Liga Profesional", "pais": "Argentina", "temporada": "2025"},
          {"id": 113, "nombre": "A-League ", "pais": "Australia", "temporada": "2025-2026"},
          {"id": 38, "nombre": "Bundesliga (Austria)", "pais": "Austria", "temporada": "2025-2026"},
          {"id": 40, "nombre": "First Division A", "pais": "Belgica", "temporada": "2025-2026"},
          {"id": 268, "nombre": "Serie A (Brasil)", "pais": "Brasil", "temporada": "2025"},
          {"id": 8814, "nombre": "Serie B (Brasil)", "pais": "Brasil", "temporada": "2025"},
          {"id": 9986, "nombre": "Premier League (Canada)", "pais": "Canada", "temporada": "2025"},
          {"id": 273, "nombre": "Primera Division (Chile)", "pais": "Chile", "temporada": "2025"},
          {"id": 120, "nombre": "Super League (China)", "pais": "China", "temporada": "2025"},
          {"id": 274, "nombre": "Primera A (Colombia)", "pais": "Colombia", "temporada": "2025-Clausura"},
          {"id": 9080, "nombre": "K League 1(Corea del Sur)", "pais": "Corea del Sur", "temporada": "2025"},
          {"id": 9116, "nombre": "K League 2 (Corea del Sur)", "pais": "Corea del Sur", "temporada": "2025"},
          {"id": 252, "nombre": "HNL (Croacia)", "pais": "Croacia", "temporada": "2025-2026"},
          {"id": 85, "nombre": "1. Division (Dinamarca)", "pais": "Dinamarca", "temporada": "2025-2026"},
          {"id": 519, "nombre": "Premier League (Egipto)", "pais": "Egipto", "temporada": "2025-2026"},
          {"id": 64, "nombre": "Premiership (Escocia)", "pais": "Escocia", "temporada": "2025-2026"},
          {"id": 123, "nombre": "Championship (Escocia)", "pais": "Escocia", "temporada": "2025-2026"},
          {"id": 130, "nombre": "MLS", "pais": "USA", "temporada": "2025"},
          {"id": 8972, "nombre": "USL Championship", "pais": "USA", "temporada": "2025"},
          {"id": 51, "nombre": "Veikkausliiga", "pais": "Finlandia", "temporada": "2025"},
          {"id": 53, "nombre": "Ligue 1", "pais": "Francia", "temporada": "2025-2026"},
          {"id": 110, "nombre": "Ligue 2", "pais": "Francia", "temporada": "2025-2026"},
          {"id": 135, "nombre": "Super League 1 (Grecia)", "pais": "Grecia", "temporada": "2025-2026"},
          {"id": 9478, "nombre": "Indian Super League", "pais": "India", "temporada": "2025-2026"},
          {"id": 47, "nombre": "Premier League", "pais": "Inglaterra", "temporada": "2025-2026"},
          {"id": 48, "nombre": "Championship", "pais": "Inglaterra", "temporada": "2025-2026"},
          {"id": 108, "nombre": "League One", "pais": "Inglaterra", "temporada": "2025-2026"},
          {"id": 109, "nombre": "League Two", "pais": "Inglaterra", "temporada": "2025-2026"},
          {"id": 126, "nombre": "Premier Division (Irlanda)", "pais": "Irlanda", "temporada": "2025"},
          {"id": 215, "nombre": "Besta deildin", "pais": "Islandia", "temporada": "2025"},
          {"id": 55, "nombre": "Serie A", "pais": "Italia", "temporada": "2025-2026"},
          {"id": 86, "nombre": "Serie B", "pais": "Italia", "temporada": "2025-2026"},
          {"id": 223, "nombre": "J. League (Japón)", "pais": "Japon", "temporada": "2025"},
          {"id": 230, "nombre": "Liga MX (Mexico)", "pais": "Mexico", "temporada": "2025-2026-Apertura"},
          {"id": 59, "nombre": "Eliteserien", "pais": "Noruega", "temporada": "2025"},
          {"id": 57, "nombre": "Eredivisie", "pais": "Holanda", "temporada": "2025-2026"},
          {"id": 111, "nombre": "Eerste Divisie", "pais": "Holanda", "temporada": "2025-2026"},
          {"id": 196, "nombre": "Ekstraklasa", "pais": "Polonia", "temporada": "2025-2026"},
          {"id": 61, "nombre": "Liga Portugal", "pais": "Portugal", "temporada": "2025-2026"},
          {"id": 63, "nombre": "Premier League (Rusia)", "pais": "Rusia", "temporada": "2025-2026"},
          {"id": 67, "nombre": "Allsvenskan", "pais": "Suecia", "temporada": "2025"},
          {"id": 69, "nombre": "Super League (Suiza)", "pais": "Suiza", "temporada": "2025-2026"},
          {"id": 163, "nombre": "Challenge League (Suiza)", "pais": "Suiza", "temporada": "2025"},
          {"id": 8984, "nombre": "Thai League", "pais": "Thailandia", "temporada": "2025-2026"},
          {"id": 71, "nombre": "Super Lig (Turquía)", "pais": "Turquía", "temporada": "2025-2026"} 
        ]

    def _get_random_proxy(self):
        proxies = [
            # Añade tus proxies aquí en el formato "http://usuario:pass@ip:puerto" o "http://ip:puerto"
        ]
        return random.choice(proxies) if proxies else None

    # ==================== Funciones síncronas de setup ==================== #
    def get_equipos_de_liga(self, id_liga, temporada):
        url_liga = f"{self.base_url}/es/leagues/{id_liga}/overview/?season={temporada}"
        print(f"\n[INFO] Buscando equipos para liga {id_liga} ({temporada})")
        resp = self.session.get(url_liga, headers=self.headers, timeout=30)
        soup = _soup_from_response(resp)
        equipos = []
        for script in soup.find_all("script"):
            text = script.string
            if not text:
                continue
            match = re.search(r'"table":\{"all":(\[.*?])', text)
            if match:
                all_teams_json = match.group(1)
                equipos_raw = json.loads(all_teams_json)
                for equipo in equipos_raw:
                    equipos.append({
                        "id_equipo": equipo["id"],
                        "nombre_equipo": equipo["name"]
                    })
                print(f"  [INFO] {len(equipos)} equipos encontrados en la liga.")
                return equipos
        print(f"  [WARN] No se encontraron equipos para liga {id_liga}")
        return []

    def get_jugadores_de_equipo(self, id_equipo, nombre_equipo):
        url_squad = f"{self.base_url}/es/teams/{id_equipo}/squad"
        print(f"    [INFO] Buscando jugadores en: {nombre_equipo} ({id_equipo})")
        time.sleep(0.5)
        resp = self.session.get(url_squad, headers=self.headers, timeout=30)
        soup = _soup_from_response(resp)
        jugadores = []

        # 1. Intentar estructura moderna (divs con clases de FotMob)
        player_rows = soup.find_all(lambda tag: tag.name == 'div' and any("SquadPlayerLink" in cls for cls in (tag.get("class") or [])))
        
        # 2. Si no hay divs, intentar con la estructura de tabla clásica (tr)
        if not player_rows:
            player_rows = soup.find_all('tr')

        for row in player_rows:
            link = row.find('a', href=True)
            if not link:
                continue
            href = link['href']
            match = re.search(r"/players/(\d+)", href)
            if not match:
                continue
            
            id_jugador = int(match.group(1))
            
            # Extraer nombre (suele ser el primer span o el texto del link)
            nombre_span = link.find('span')
            nombre = nombre_span.text.strip() if nombre_span else link.text.strip()
            
            # Posición y Nacionalidad
            posicion = ""
            nacionalidad = ""
            
            # Buscamos el link de país
            country_link = row.find(lambda tag: tag.name == 'a' and any("PlayerCountryLink" in cls for cls in (tag.get("class") or [])))
            if country_link:
                nacionalidad = country_link.text.strip()
            
            # Si no encontramos nacionalidad así, buscamos por imagen o clases
            if not nacionalidad:
                country_container = row.find(lambda tag: any("PlayerCountry" in str(cls) for cls in (tag.get("class") or [])))
                if country_container:
                    nacionalidad = country_container.text.strip()

            # Posición: suele ser un span corto (ej. "POR", "DEF") o un title
            all_spans = [s.text.strip() for s in row.find_all('span') if s.text.strip()]
            for txt in all_spans:
                txt_low = txt.lower()
                if txt_low in ("portero", "defensa", "delantero", "centrocampista", "por", "def", "cen", "del", "gk", "df", "mf", "fw"):
                    posicion = txt_low
                    break
            
            if not posicion:
                # Intentar buscar en atributos title
                for tag in row.find_all(True, title=True):
                    pos = tag['title'].strip().lower()
                    if pos and len(pos) <= 25:
                        posicion = pos
                        break

            if "entrenador" in posicion or "manager" in posicion:
                continue
            
            if any(j["id_jugador"] == id_jugador for j in jugadores):
                continue

            jugadores.append({
                "id_jugador": id_jugador,
                "nombre": nombre,
                "id_equipo": id_equipo,
                "equipo": nombre_equipo,
                "posicion": posicion,
                "nacionalidad": nacionalidad
            })
            
        print(f"      [INFO] {len(jugadores)} jugadores encontrados.")
        return jugadores

    def scrape_fotmob_ligas(self, ligas):
        jugadores_totales = []
        equipos_totales = []
        for liga in ligas:
            equipos = self.get_equipos_de_liga(liga["id"], liga["temporada"])
            equipos_totales.extend([
                {"id_equipo": eq["id_equipo"], "nombre_equipo": eq["nombre_equipo"],
                 "id_liga": liga["id"], "nombre_liga": liga["nombre"], "pais": liga["pais"], "temporada": liga["temporada"]}
                for eq in equipos
            ])
            for eq in equipos:
                jugadores = self.get_jugadores_de_equipo(eq["id_equipo"], eq["nombre_equipo"])
                for jug in jugadores:
                    jugadores_totales.append({
                        "id_jugador": jug["id_jugador"],
                        "nombre": jug["nombre"],
                        "nacionalidad": jug["nacionalidad"],
                        "id_equipo": eq["id_equipo"],
                        "equipo": eq["nombre_equipo"],
                        "id_liga": liga["id"],
                        "liga": liga["nombre"],
                        "pais": liga["pais"],
                        "temporada": liga["temporada"],
                        "url_jugador": f"{self.base_url}/es/players/{jug['id_jugador']}"
                    })
        out_all = RAW_DIR / "jugadores_fotmob_all.json"
        out_all.write_text(json.dumps(jugadores_totales, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n🎉 Guardados {len(equipos_totales)} equipos y {len(jugadores_totales)} jugadores en total.")
        return jugadores_totales

    # ==================== Async stats + evasión ==================== #
    async def get_fotmob_stats_async(self, session, player_id, season_id, *, max_attempts: int = 5):
        headers = {
            "User-Agent": self.headers["User-Agent"],
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Referer": f"https://www.fotmob.com/es/players/{player_id}",
            "x-mas": self.x_mas,
            "Origin": "https://www.fotmob.com"
        }
        url = f"https://www.fotmob.com/api/data/playerStats?playerId={player_id}&seasonId={season_id}&isFirstSeason=false"

        for attempt in range(max_attempts):
            await asyncio.sleep(random.uniform(1.0, 3.0))
            proxy = self._get_random_proxy()
            proxy_dict = {"http": proxy, "https": proxy} if proxy else None

            try:
                # Nota: curl_cffi no usa 'async with' para la petición directa
                response = await session.get(url, headers=headers, proxies=proxy_dict, timeout=25)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403:
                    print(f"[WARN] 403 en jugador {player_id} (Intento {attempt+1}).")
                    await asyncio.sleep(random.uniform(5.0, 10.0))
                elif response.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(2)
            except Exception:
                await asyncio.sleep(2)

        return None

    async def get_traits_and_season_id_async(self, session, url_jugador):
        await asyncio.sleep(random.uniform(0.5, 2.0))
        proxy = self._get_random_proxy()
        proxy_dict = {"http": proxy, "https": proxy} if proxy else None
        
        try:
            resp = await session.get(url_jugador, headers=self.headers, proxies=proxy_dict, timeout=30)
            if resp.status_code != 200:
                return {}, "0-0", {}
            
            html = resp.text
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            return {}, "0-0", {}

        traits = {}
        for span in soup.select('span.css-1g16yy4-TraitText.e17fib5q6'):
            trait_name = span.text.strip()
            trait_percent = span.find_next("span", class_="css-1ozcgmv-TraitPercentage")
            if trait_percent:
                cleaned = trait_percent.text.replace('\xa0', '').replace('%', '').strip()
                try:
                    traits[trait_name] = int(cleaned)
                except:
                    pass

        season_id = "0-0"
        season_dom_map = {}
        try:
            for opt in soup.select("select option[value]"):
                val = (opt.get("value") or "").strip()
                if not re.fullmatch(r"\d+-\d+", val):
                    continue
                label = (opt.get("label") or opt.text or "").strip()
                og = opt.find_parent("optgroup")
                group = (og.get("label") or "").strip() if og else ""
                season_dom_map[val] = {"label": label, "group": group}
        except Exception:
            pass

        return traits, season_id, season_dom_map

    def extract_all_stats(self, data):
        stats_dict = {}
        if not data or "statsSection" not in data:
            return {}
        top_card = data.get("topStatCard", {})
        for item in top_card.get("items", []):
            stats_dict[item["title"]] = {
                "value": item.get("statValue"),
                "per90": item.get("per90"),
                "percentile": item.get("percentileRank"),
                "percentile_per90": item.get("percentileRankPer90")
            }
        for group in data["statsSection"]["items"]:
            for stat in group.get("items", []):
                key = stat["title"]
                stats_dict[key] = {
                    "value": stat.get("statValue"),
                    "per90": stat.get("per90"),
                    "percentile": stat.get("percentileRank"),
                    "percentile_per90": stat.get("percentileRankPer90")
                }
        return stats_dict

    async def process_player_async(self, session, semaphore, jugador):
        async with semaphore:
            player_id = jugador["id_jugador"]
            url_jugador = f"https://www.fotmob.com/es/players/{player_id}"
            
            for attempt in range(3):
                # Un pequeño retraso para no saturar
                await asyncio.sleep(random.uniform(1.0, 2.5))
                proxy = self._get_random_proxy()
                proxy_dict = {"http": proxy, "https": proxy} if proxy else None

                try:
                    # 1 ÚNICA PETICIÓN: Pedimos la web normal del jugador
                    resp = await session.get(url_jugador, headers=self.headers, proxies=proxy_dict, timeout=30)
                    
                    if resp.status_code != 200:
                        if resp.status_code in (403, 429):
                            await asyncio.sleep(5) # Si nos limitan, esperamos
                        continue

                    html = resp.text
                    soup = BeautifulSoup(html, "lxml")

                    # --- PASO 1: Extraer Rasgos (Tu código original) ---
                    traits = {}
                    for span in soup.select('span.css-1g16yy4-TraitText.e17fib5q6'):
                        trait_name = span.text.strip()
                        trait_percent = span.find_next("span", class_="css-1ozcgmv-TraitPercentage")
                        if trait_percent:
                            cleaned = trait_percent.text.replace('\xa0', '').replace('%', '').strip()
                            try:
                                traits[trait_name] = int(cleaned)
                            except:
                                pass

                    # --- PASO 2: Extraer Ligas / Temporadas ---
                    season_id = "0-0"
                    season_dom_map = {}
                    for opt in soup.select("select option[value]"):
                        val = (opt.get("value") or "").strip()
                        if not re.fullmatch(r"\d+-\d+", val): continue
                        label = (opt.get("label") or opt.text or "").strip()
                        og = opt.find_parent("optgroup")
                        group = (og.get("label") or "").strip() if og else ""
                        season_dom_map[val] = {"label": label, "group": group}

                    # --- PASO 3: EL BYPASS (Buscar las Stats en el JSON oculto de Next.js) ---
                    statsdata = None
                    script_tag = soup.find('script', id='__NEXT_DATA__')
                    
                    if script_tag:
                        json_data = json.loads(script_tag.string)
                        
                        # Función recursiva para buscar el bloque "statsSection" en todo el árbol JSON
                        def find_stats(node):
                            if isinstance(node, dict):
                                if "statsSection" in node or "topStatCard" in node:
                                    return node
                                for v in node.values():
                                    res = find_stats(v)
                                    if res: return res
                            elif isinstance(node, list):
                                for item in node:
                                    res = find_stats(item)
                                    if res: return res
                            return None
                            
                        statsdata = find_stats(json_data)

                    # Si el jugador no tiene stats procesables
                    if not statsdata:
                        return None 

                    stats = self.extract_all_stats(statsdata)
                    if not stats or len(stats) < 9:
                        return None

                    # --- PASO 4: Formatear salida ---
                    liga_stats, temporada_stats = None, None
                    info = season_dom_map.get(season_id) if isinstance(season_dom_map, dict) else None
                    if info:
                        label = (info.get("label") or "").strip()
                        group = (info.get("group") or "").strip()
                        temporada_stats = group or (re.search(r"20\d{2}\s*/\s*20\d{2}", label or "") or [None])[0]
                        liga_stats = label if label else None

                    es_portero = any(k in stats for k in ("Saves", "Save percentage", "Clean sheets"))

                    datos_salida = jugador.copy()
                    datos_salida["estadísticas"] = stats
                    datos_salida["season_id_stats"] = season_id
                    datos_salida["liga_stats"] = liga_stats
                    datos_salida["temporada_stats"] = temporada_stats

                    if es_portero:
                        datos_salida["rasgos_portero"] = traits
                    else:
                        datos_salida["rasgos_jugador"] = traits

                    # AÑADE ESTO: El chivato de éxito
                    print(f"  [OK] Datos extraídos: {jugador['nombre']} ({jugador['equipo']})")
                    return datos_salida

                except Exception as e:
                    # En caso de error de conexión, reintenta
                    await asyncio.sleep(2)

            # AÑADE ESTO: El chivato de fallo o falta de stats
            print(f"  [SKIPPED] No hay stats para {jugador.get('nombre','unknown')}.")
            return None


    async def process_players_by_liga_async(self, jugadores_liga, liga_nombre):
        print(f"\n🚀 Iniciando procesamiento asíncrono para {liga_nombre}")
        print(f"Total jugadores a procesar: {len(jugadores_liga)}")
        
        semaphore = asyncio.Semaphore(4) 
        
        # AQUÍ ESTÁ LA MAGIA: Impersonate="chrome110" simula la huella digital exacta de Chrome
        async with AsyncSession(impersonate="chrome110") as session:
            tasks = [self.process_player_async(session, semaphore, jugador) for jugador in jugadores_liga]
            jugadores_procesados = []
            batch_size = 50
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i+batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                for result in batch_results:
                    if result and not isinstance(result, Exception):
                        jugadores_procesados.append(result)
                await asyncio.sleep(0.5)
                
        print(f"✅ Liga {liga_nombre} completada: {len(jugadores_procesados)} jugadores con stats válidas")
        checkpoint_filename = INTERIM_DIR / f"liga_{liga_nombre.replace(' ', '_')}_procesada.json"
        checkpoint_filename.write_text(json.dumps(jugadores_procesados, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"💾 Checkpoint guardado: {checkpoint_filename}")
        return jugadores_procesados

    async def process_all_leagues_with_checkpoints_async(self, jugadores_totales):
        print("\n" + "="*60)
        print("🎯 INICIANDO PROCESAMIENTO OPTIMIZADO CON CHECKPOINTS")
        print("="*60)
        jugadores_por_liga = {}
        for jugador in jugadores_totales:
            liga = jugador["liga"]
            jugadores_por_liga.setdefault(liga, []).append(jugador)

        todos_los_jugadores_filtrados = []
        for liga_nombre, jugadores_liga in jugadores_por_liga.items():
            try:
                checkpoint_filename = INTERIM_DIR / f"liga_{liga_nombre.replace(' ', '_')}_procesada.json"
                if checkpoint_filename.exists():
                    print(f"\n⚡ Encontrado checkpoint para {liga_nombre}, cargando...")
                    jugadores_procesados = json.loads(checkpoint_filename.read_text(encoding="utf-8"))
                    print(f"✅ Cargados {len(jugadores_procesados)} jugadores de checkpoint")
                else:
                    jugadores_procesados = await self.process_players_by_liga_async(jugadores_liga, liga_nombre)
                todos_los_jugadores_filtrados.extend(jugadores_procesados)
            except Exception as e:
                print(f"❌ Error procesando liga {liga_nombre}: {e}")
                continue
        return todos_los_jugadores_filtrados


async def main_async():
    print("🚀 Iniciando FotMob Massive Scraper Optimizado")
    print("=" * 50)
    scraper = FotmobMassiveScraper()

    print("\n📝 PASO 1: Recolectando jugadores de todas las ligas...")
    jugadores_totales = scraper.scrape_fotmob_ligas(scraper.leagues)
    print(f"✅ Total jugadores recolectados: {len(jugadores_totales)}")

    print("\n⚡ PASO 2: Procesando estadísticas de forma asíncrona...")
    jugadores_filtrados = await scraper.process_all_leagues_with_checkpoints_async(jugadores_totales)

    print("\n💾 PASO 3: Guardando resultado final...")
    out_db = RAW_DIR / "db_fotmob.json"
    out_db.write_text(json.dumps(jugadores_filtrados, ensure_ascii=False, indent=2), encoding="utf8")

    print(f"\n🎉 ¡COMPLETADO! Total jugadores procesados: {len(jugadores_filtrados)}")

    return jugadores_filtrados


if __name__ == "__main__":
    import aiohttp  # noqa: F401
    asyncio.run(main_async())