# src/scouting/etl/collect_fotmob.py
import os
import re
import json
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime

import requests
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ==== Config =====
load_dotenv()
RAW_DIR = Path(os.getenv("RAW_DIR", "data/raw"))
INTERIM_DIR = Path(os.getenv("INTERIM_DIR", "data/interim"))
RAW_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

# Fallback: si no hay .env, usamos el token previo
#Este token se debe actualizar antes del uso, ya que cambia cada 24h, habrá que ir a un jugador en fotmob, click derecho, inspeccionar, darle a network, el filtro fetch,
#A continuación algún click en la página del jugador, y en currency mismo que saldrá en network, nos metemos y dentro de esta al bajar encontramos el xmas actualizado
X_MAS_ENV = os.getenv("X_MAS_TOKEN", "").strip()
x_mas_fallback = "eyJib2R5Ijp7InVybCI6Ii9hcGkvY3VycmVuY3kiLCJjb2RlIjoxNzUzNzc5MTk0MjYyLCJmb28iOiJwcm9kdWN0aW9uOmU1OTAxODhlNWNlZmQxOTI3ZjU5NzE3MDBjNWU4MTc1ZGI3MjkyODUtdW5kZWZpbmVkIn0sInNpZ25hdHVyZSI6IkY5NjM2MjU0RTFFOEJEQzUwRDRGOTFDRTkwNTIwRTE0In0="
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
            {"id": 87, "nombre": "LaLiga", "pais": "España", "temporada": "2024-2025"},
          {"id": 140, "nombre": "LaLiga2", "pais": "España", "temporada": "2024-2025"},
          {"id": 54, "nombre": "Bundesliga", "pais": "Alemania", "temporada": "2024-2025"},
          {"id": 146, "nombre": "2. Bundesliga", "pais": "Alemania", "temporada": "2024-2025"},
          {"id": 208, "nombre": "3. Liga", "pais": "Alemania", "temporada": "2024-2025"},
          {"id": 536, "nombre": "Saudi Pro League", "pais": "Arabia Saudi", "temporada": "2024-2025"},
          {"id": 112, "nombre": "Liga Profesional", "pais": "Argentina", "temporada": "2025"},
          {"id": 113, "nombre": "A-League ", "pais": "Australia", "temporada": "2024-2025"},
          {"id": 38, "nombre": "Bundesliga (Austria)", "pais": "Austria", "temporada": "2024-2025"},
          {"id": 40, "nombre": "First Division A", "pais": "Belgica", "temporada": "2024-2025"},
          {"id": 268, "nombre": "Serie A (Brasil)", "pais": "Brasil", "temporada": "2025"},
          {"id": 8814, "nombre": "Serie B (Brasil)", "pais": "Brasil", "temporada": "2025"},
          {"id": 9986, "nombre": "Premier League (Canada)", "pais": "Canada", "temporada": "2025"},
          {"id": 273, "nombre": "Primera Division (Chile)", "pais": "Chile", "temporada": "2025"},
          {"id": 120, "nombre": "Super League (China)", "pais": "China", "temporada": "2025"},
          {"id": 274, "nombre": "Primera A (Colombia)", "pais": "Colombia", "temporada": "2025-Clausura"},
          {"id": 9080, "nombre": "K League 1(Corea del Sur)", "pais": "Corea del Sur", "temporada": "2025"},
          {"id": 9116, "nombre": "K League 2 (Corea del Sur)", "pais": "Corea del Sur", "temporada": "2025"},
          {"id": 252, "nombre": "HNL (Croacia)", "pais": "Croacia", "temporada": "2024-2025"},
          {"id": 85, "nombre": "1. Division (Dinamarca)", "pais": "Dinamarca", "temporada": "2024-2025"},
          {"id": 519, "nombre": "Premier League (Egipto)", "pais": "Egipto", "temporada": "2024-2025"},
          {"id": 64, "nombre": "Premiership (Escocia)", "pais": "Escocia", "temporada": "2024-2025"},
          {"id": 123, "nombre": "Championship (Escocia)", "pais": "Escocia", "temporada": "2024-2025"},
          {"id": 130, "nombre": "MLS", "pais": "USA", "temporada": "2025"},
          {"id": 8972, "nombre": "USL Championship", "pais": "USA", "temporada": "2025"},
          {"id": 51, "nombre": "Veikkausliiga", "pais": "Finlandia", "temporada": "2025"},
          {"id": 53, "nombre": "Ligue 1", "pais": "Francia", "temporada": "2024-2025"},
          {"id": 110, "nombre": "Ligue 2", "pais": "Francia", "temporada": "2024-2025"},
          {"id": 135, "nombre": "Super League 1 (Grecia)", "pais": "Grecia", "temporada": "2024-2025"},
          {"id": 9478, "nombre": "Indian Super League", "pais": "India", "temporada": "2024-2025"},
          {"id": 47, "nombre": "Premier League", "pais": "Inglaterra", "temporada": "2024-2025"},
          {"id": 48, "nombre": "Championship", "pais": "Inglaterra", "temporada": "2024-2025"},
          {"id": 108, "nombre": "League One", "pais": "Inglaterra", "temporada": "2024-2025"},
          {"id": 109, "nombre": "League Two", "pais": "Inglaterra", "temporada": "2024-2025"},
          {"id": 126, "nombre": "Premier Division (Irlanda)", "pais": "Irlanda", "temporada": "2025"},
          {"id": 215, "nombre": "Besta deildin", "pais": "Islandia", "temporada": "2025"},
          {"id": 55, "nombre": "Serie A", "pais": "Italia", "temporada": "2024-2025"},
          {"id": 86, "nombre": "Serie B", "pais": "Italia", "temporada": "2024-2025"},
          {"id": 223, "nombre": "J. League (Japón)", "pais": "Japon", "temporada": "2025"},
          {"id": 230, "nombre": "Liga MX (Mexico)", "pais": "Mexico", "temporada": "2025-2026-Apertura"},
          {"id": 59, "nombre": "Eliteserien", "pais": "Noruega", "temporada": "2025"},
          {"id": 57, "nombre": "Eredivisie", "pais": "Holanda", "temporada": "2024-2025"},
          {"id": 111, "nombre": "Eerste Divisie", "pais": "Holanda", "temporada": "2024-2025"},
          {"id": 196, "nombre": "Ekstraklasa", "pais": "Polonia", "temporada": "2024-2025"},
          {"id": 61, "nombre": "Liga Portugal", "pais": "Portugal", "temporada": "2024-2025"},
          {"id": 63, "nombre": "Premier League (Rusia)", "pais": "Rusia", "temporada": "2024-2025"},
          {"id": 67, "nombre": "Allsvenskan", "pais": "Suecia", "temporada": "2025"},
          {"id": 69, "nombre": "Super League (Suiza)", "pais": "Suiza", "temporada": "2024-2025"},
          {"id": 163, "nombre": "Challenge League (Suiza)", "pais": "Suiza", "temporada": "2025"},
          {"id": 8984, "nombre": "Thai League", "pais": "Thailandia", "temporada": "2024-2025"},
          {"id": 71, "nombre": "Super Lig (Turquía)", "pais": "Turquía", "temporada": "2024-2025"}
        ]

    # ==================== Funciones originales (idénticas) ==================== #
    def get_equipos_de_liga(self, id_liga, temporada):
        url_liga = f"{self.base_url}/es/leagues/{id_liga}/overview/?season={temporada}"
        print(f"\n[INFO] Buscando equipos para liga {id_liga} ({temporada})")
        resp = self.session.get(url_liga, headers=self.headers, timeout=30)
        soup = BeautifulSoup(resp.content, "html.parser")
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
        soup = BeautifulSoup(resp.content, "html.parser")
        jugadores = []
        for fila in soup.find_all('tr'):
            link = fila.find('a', href=True)
            if not link:
                continue
            href = link['href']
            match = re.match(r"^/es/players/(\d+)", href)
            if not match:
                continue
            id_jugador = int(match.group(1))
            nombre_span = link.find('span')
            nombre = nombre_span.text.strip() if nombre_span else ""
            columnas = fila.find_all('td')
            posicion = ""
            for c in columnas:
                if c.has_attr('title'):
                    pos = c['title'].strip().lower()
                    if pos and len(pos) <= 25:
                        posicion = pos
                        break
                elif c.text.strip():
                    txt = c.text.strip().lower()
                    if txt in ("portero","defensa","delantero","centrocampista","entrenador"):
                        posicion = txt
                        break
            if "entrenador" in posicion or "manager" in posicion or not posicion:
                continue
            if any(j["id_jugador"] == id_jugador for j in jugadores):
                continue
            jugadores.append({
                "id_jugador": id_jugador,
                "nombre": nombre,
                "id_equipo": id_equipo,
                "equipo": nombre_equipo,
                "posicion": posicion
            })
        print(f"      [INFO] {len(jugadores)} jugadores (sin staff) encontrados.")
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
                        "id_equipo": eq["id_equipo"],
                        "equipo": eq["nombre_equipo"],
                        "id_liga": liga["id"],
                        "liga": liga["nombre"],
                        "pais": liga["pais"],
                        "temporada": liga["temporada"],
                        "url_jugador": f"{self.base_url}/es/players/{jug['id_jugador']}"
                    })
        # Guardamos en data/raw
        out_all = RAW_DIR / "jugadores_fotmob_all.json"
        out_all.write_text(json.dumps(jugadores_totales, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n🎉 Guardados {len(equipos_totales)} equipos y {len(jugadores_totales)} jugadores en total.")
        return jugadores_totales

    # ==================== Async stats + checkpoints ==================== #
    async def get_fotmob_stats_async(self, session, player_id, season_id):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://www.fotmob.com/players/{player_id}",
            "x-mas": self.x_mas,
        }
        url = f"https://www.fotmob.com/api/data/playerStats?playerId={player_id}&seasonId={season_id}&isFirstSeason=false"
        try:
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status == 429:
                    await asyncio.sleep(2)
                    async with session.get(url, headers=headers, timeout=15) as retry_response:
                        if retry_response.status == 200:
                            return await retry_response.json()
                        else:
                            print(f"Error {retry_response.status} para jugador {player_id}")
                            return None
                elif response.status == 200:
                    return await response.json()
                else:
                    print(f"Error {response.status} para jugador {player_id}")
                    return None
        except Exception as e:
            print(f"Excepción para jugador {player_id}: {e}")
            return None

    def get_traits_and_season_id(self, url_jugador):
        resp = self.session.get(url_jugador, headers=self.headers, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")
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
        selected_option = soup.select_one('option[selected]')
        selected_text = selected_option.text.strip() if selected_option else ""
        palabras_torneo = ["cup", "fifa", "euro", "olympics", "copa"]
        selected_lower = selected_text.lower() if selected_text else ""
        season_id = "1-0" if any(p in selected_lower for p in palabras_torneo) else "0-0"
        return traits, season_id

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
            try:
                player_id = jugador["id_jugador"]
                traits, season_id = self.get_traits_and_season_id(jugador["url_jugador"])
                statsdata = await self.get_fotmob_stats_async(session, player_id, season_id)
                if not statsdata:
                    return None
                stats = self.extract_all_stats(statsdata)
                if len(stats) < 9:
                    return None
                es_portero = "Saves" in stats or "Save percentage" in stats or "Clean sheets" in stats
                datos_salida = jugador.copy()
                datos_salida["estadísticas"] = stats
                if es_portero:
                    datos_salida["rasgos_portero"] = traits
                else:
                    datos_salida["rasgos_jugador"] = traits
                return datos_salida
            except Exception as e:
                print(f"Error procesando jugador {jugador.get('nombre', 'unknown')}: {e}")
                return None

    async def process_players_by_liga_async(self, jugadores_liga, liga_nombre):
        print(f"\n🚀 Iniciando procesamiento asíncrono para {liga_nombre}")
        print(f"Total jugadores a procesar: {len(jugadores_liga)}")
        semaphore = asyncio.Semaphore(8)
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=8)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
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
    print("Archivos generados:")
    print(f"- {out_db} (con estadísticas)")
    print(f"- {RAW_DIR / 'jugadores_fotmob_all.json'} (lista completa)")
    print(f"- {INTERIM_DIR / 'liga_*_procesada.json'} (checkpoints por liga)")

    return jugadores_filtrados


if __name__ == "__main__":
    # Import aquí para evitar error si alguien ejecuta sin aiohttp instalado:
    import aiohttp  # noqa: F401
    asyncio.run(main_async())
