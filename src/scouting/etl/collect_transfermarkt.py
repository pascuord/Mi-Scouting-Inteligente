# src/scouting/etl/collect_transfermarkt.py
"""
Scraper Transfermarkt (rápido y robusto):
- RateLimiter global (RPS) en vez de sleeps por todas partes
- Paralelismo con ThreadPool:
  - perfiles HTML (altura/pie/posiciones/contrato)
  - CEAPI JSON (market value evolution, transfer history)
- Checkpoint incremental por equipo (reanuda si Colab peta)
- Sin pandas (solo JSON)
"""

from __future__ import annotations

import os
import re
import json
import time
import random
import argparse
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import unidecode
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ==== Config =====
load_dotenv()

def get_data_dir() -> Path:
    env_data = os.getenv("DATA_DIR")
    if env_data and os.path.isabs(env_data):
        return Path(env_data)
    root_repo = Path(__file__).resolve().parents[3]
    local_data = root_repo / "data"
    if not local_data.exists() and os.path.exists("/data"):
        return Path("/data")
    return local_data

DATA_DIR = get_data_dir()
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"

RAW_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

RAW_OUT = RAW_DIR / "db_transfermarkt.json"
CHECKPOINT_TEMPLATE = INTERIM_DIR / "tm_{league}_jugadores.json"


# ---------------- Rate limiter ----------------
class RateLimiter:
    """
    Limitador global de requests: garantiza un máximo de RPS total
    incluso con múltiples hilos. Añade un jitter mínimo para no ser metronómico.
    """
    def __init__(self, rps: float):
        self.min_interval = 1.0 / max(rps, 0.01)
        self.lock = threading.Lock()
        self.next_allowed = time.monotonic()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            if now < self.next_allowed:
                sleep_s = self.next_allowed - now
                self.next_allowed += self.min_interval
            else:
                sleep_s = 0.0
                self.next_allowed = now + self.min_interval

        if sleep_s > 0:
            time.sleep(sleep_s)
        time.sleep(random.uniform(0.0, 0.05))  # jitter pequeño


_thread_local = threading.local()

def _get_thread_session(headers: dict) -> requests.Session:
    """
    Session por hilo (requests.Session no es 100% thread-safe si la compartes).
    """
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update(headers)
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=64,
            pool_maxsize=64,
            max_retries=0  # reintentos los controlamos nosotros
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _thread_local.session = s
    return s


# ---------------- Scraper ----------------
class TransfermarktMassiveScraper:
    def __init__(
        self,
        rps: float = 1.2,
        workers_profiles: int = 6,
        workers_ceapi: int = 12,
        timeout: Tuple[float, float] = (10.0, 35.0),  # (connect, read)
        resume: bool = True,
    ):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
        self.base_url = "https://www.transfermarkt.com"
        self.limiter = RateLimiter(rps)
        self.workers_profiles = max(1, int(workers_profiles))
        self.workers_ceapi = max(1, int(workers_ceapi))
        self.timeout = timeout
        self.resume = resume

        # cache por liga: cuando detectamos qué saison_id funciona para una liga, lo reutilizamos
        self._league_saison_cache: dict[str, str] = {}

        # Ligas (tu lista)
        self.leagues: Dict[str, Dict[str, str]] = {
            "LaLiga": {"id": "ES1", "name": "laliga"},
            "LaLiga2": {"id": "ES2", "name": "laliga2"},
            "Premier League": {"id": "GB1", "name": "premier-league"},
            "Championship": {"id": "GB2", "name": "championship"},
            "League One": {"id": "GB3", "name": "league-one"},
            "League Two": {"id": "GB4", "name": "league-two"},
            "Serie A": {"id": "IT1", "name": "serie-a"},
            "Serie B": {"id": "IT2", "name": "serie-b"},
            "Bundesliga": {"id": "L1", "name": "bundesliga"},
            "2. Bundesliga": {"id": "L2", "name": "2-bundesliga"},
            "3. Liga": {"id": "L3", "name": "3-liga"},
            "Ligue 1": {"id": "FR1", "name": "ligue-1"},
            "Ligue 2": {"id": "FR2", "name": "ligue-2"},
            "Bundesliga (Austria)": {"id": "A1", "name": "bundesliga"},
            "Saudi Pro League": {"id": "SA1", "name": "saudi-pro-league"},
            "Liga Profesional": {"id": "ARG1", "name": "torneo-apertura"},
            "A-League": {"id": "AUS1", "name": "a-league-men"},
            "Jupiler Pro League": {"id": "BE1", "name": "jupiler-pro-league"},
            "Brasileiro Serie A": {"id": "BRA1", "name": "campeonato-brasileiro-serie-a"},
            "Brasileiro Serie B": {"id": "BRA2", "name": "campeonato-brasileiro-serie-b"},
            "Premier League (Canadá)": {"id": "CDN1", "name": "canadian-premier-league"},
            "Primera Division (Chile)": {"id": "CLPD", "name": "primera-division-de-chile"},
            "Super League (China)": {"id": "CSL", "name": "chinese-super-league"},
            "Primera A (Colombia)": {"id": "COL1", "name": "liga-dimayor-ii"},
            "K League 1(Corea del Sur)": {"id": "RSK1", "name": "k-league-1"},
            "K League 2(Corea del Sur)": {"id": "RSK2", "name": "k-league-2"},
            "HNL (Croacia)": {"id": "KR1", "name": "1-hnl"},
            "Superliga (Dinamarca)": {"id": "DK1", "name": "superligaen"},
            "Premier League (Egipto)": {"id": "EGY1", "name": "egyptian-premier-league"},
            "Premiership (Escocia)": {"id": "SC1", "name": "scottish-premiership"},
            "Championship (Escocia)": {"id": "SC2", "name": "scottish-championship"},
            "MLS": {"id": "MLS1", "name": "major-league-soccer"},
            "USL Championship": {"id": "USL", "name": "usl-championship"},
            "Veikkausliiga": {"id": "FI1", "name": "veikkausliiga"},
            "Super League 1 (Grecia)": {"id": "GR1", "name": "super-league-1"},
            "Indian Super League": {"id": "IND1", "name": "indian-super-league"},
            "Premier Division (Irlanda)": {"id": "IR1", "name": "premier-league"},
            "Besta deildin": {"id": "IS1", "name": "pepsi-max-deild"},
            "J. League (Japón)": {"id": "JAP1", "name": "j1-league"},
            "Liga MX (Mexico)": {"id": "MEXA", "name": "liga-mx-apertura"},
            "Eliteserien": {"id": "NO1", "name": "eliteserien"},
            "Eredivisie": {"id": "NL1", "name": "eredivisie"},
            "Eerste Divisie": {"id": "NL2", "name": "eerste-divisie"},
            "Ekstraklasa": {"id": "PL1", "name": "pko-ekstraklasa"},
            "Liga Portugal": {"id": "PO1", "name": "liga-nos"},
            "Premier League (Rusia)": {"id": "RU1", "name": "premier-liga"},
            "Allsvenskan": {"id": "SE1", "name": "allsvenskan"},
            "Super League (Suiza)": {"id": "C1", "name": "super-league"},
            "Challenge League (Suiza)": {"id": "C2", "name": "challenge-league"},
            "Thai League": {"id": "THA1", "name": "thai-league"},
            "Super Lig (Turquía)": {"id": "TR1", "name": "super-lig"},
        }

    # ------------- Utils -------------
    def _full_url(self, url: str) -> str:
        return url if url.startswith("http") else f"{self.base_url}{url}"

    def _request_html(self, url: str, max_retries: int = 8) -> BeautifulSoup:
        full_url = self._full_url(url)
        for attempt in range(1, max_retries + 1):
            try:
                self.limiter.wait()
                sess = _get_thread_session(self.headers)
                resp = sess.get(full_url, timeout=self.timeout)
                if resp.status_code in (429, 403, 503):
                    raise RuntimeError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                return BeautifulSoup(resp.content, "html.parser")
            except Exception:
                if attempt == max_retries:
                    raise
                time.sleep(min(30.0, 1.2 * attempt + random.uniform(0.0, 1.0)))

    def _request_json(self, url: str, max_retries: int = 6) -> dict:
        full_url = self._full_url(url)
        for attempt in range(1, max_retries + 1):
            try:
                self.limiter.wait()
                sess = _get_thread_session(self.headers)
                resp = sess.get(full_url, timeout=self.timeout)
                if resp.status_code in (429, 403, 503):
                    raise RuntimeError(f"HTTP {resp.status_code}")
                if resp.status_code != 200:
                    return {}
                return resp.json()
            except Exception:
                if attempt == max_retries:
                    return {}
                time.sleep(min(30.0, 1.0 * attempt + random.uniform(0.0, 1.0)))

    def _slug_from_team_url(self, team_url: str) -> str:
        # team_url típico: "/brighton-amp-hove-albion/startseite/verein/1237"
        m = re.match(r"^/([^/]+)/", team_url or "")
        return m.group(1) if m else ""

    def _ensure_team_slug(self, team: dict) -> None:
        """
        Parchea equipos de checkpoints antiguos: si no hay slug, lo derivamos del href guardado (team['url']).
        Esto arregla casos como Brighton (amp vs &).
        """
        if team.get("slug"):
            return
        url = team.get("url", "") or ""
        slug = self._slug_from_team_url(url)
        if slug:
            team["slug"] = slug
            return
        # último recurso
        name = team.get("name", "") or ""
        team["slug"] = self.parse_name(name)

    def _season_id_candidates(self, league_name: str, season: str) -> list[str]:
        cached = self._league_saison_cache.get(league_name)
        if cached:
            return [cached]

        base = self.get_season_id(season)
        if base.isdigit():
            b = int(base)
            return [str(b), str(b - 1)]
        return [base]

    @staticmethod
    def parse_name(name: str) -> str:
        name = unidecode.unidecode(name)
        name = (
            name.replace(".", "")
            .replace("'", "")
            .replace("ø", "o")
            .replace("å", "a")
            .replace("/", "-")
        )
        name = re.sub(r"\s+", " ", name).strip()
        return "-".join(name.lower().split())

    @staticmethod
    def get_season_id(season: str) -> str:
        # OJO: para "2026" -> "2025" (como ya estabas usando)
        if "/" in season:
            return season.split("/")[0]
        if "-" in season:
            return season.split("-")[0]
        try:
            return str(int(season) - 1)
        except Exception:
            return season

    # ------------- Extracciones -------------
    def get_league_teams(self, league_name: str, season: str = "2026") -> List[Dict]:
        info = self.leagues.get(league_name)
        if not info:
            raise ValueError(f"Liga no encontrada: {league_name}")

        season_id = self.get_season_id(season)
        url = f"/{info['name']}/startseite/wettbewerb/{info['id']}/plus/?saison_id={season_id}"
        soup = self._request_html(url)

        teams: List[Dict] = []
        table = soup.find("table", {"class": "items"})
        if not table:
            print(f"[WARN] No se encontró tabla de equipos para {league_name}")
            return teams
        tbody = table.find("tbody")
        if not tbody:
            return teams

        for row in tbody.find_all("tr", recursive=False):
            try:
                team_cell = row.find("td", {"class": "hauptlink"})
                if not team_cell:
                    continue
                team_link = team_cell.find("a")
                if not team_link:
                    continue
                team_name = team_link.get("title", "").strip()
                team_url = team_link.get("href", "")
                m = re.search(r"/verein/(\d+)", team_url)
                team_id = m.group(1) if m else None
                if team_name and team_id:
                    team_slug = self._slug_from_team_url(team_url)
                    teams.append({
                        "name": team_name,
                        "id": team_id,
                        "url": team_url,
                        "slug": team_slug,
                        "league": league_name,
                        "season": season,
                    })
            except Exception:
                continue
        return teams

    def _extract_contract_info(self, soup: BeautifulSoup) -> dict:
        info = {"joined": None, "contract_expires": None, "last_renewal": None}
        try:
            spans = soup.select(".info-table__content")
            label = None
            for span in spans:
                text = span.get_text(strip=True)
                if any(k in text for k in ("Joined", "Contract expires", "Last contract extension")):
                    label = text
                    continue
                if label and "info-table__content--bold" in (span.get("class") or []):
                    if "Joined" in label:
                        info["joined"] = text
                    elif "Contract expires" in label:
                        info["contract_expires"] = text
                    elif "Last contract extension" in label:
                        info["last_renewal"] = text
                    label = None
        except Exception:
            pass
        return info

    def _parse_profile(self, player: dict) -> dict:
        player_url = player.get("url")
        if not player_url:
            return {}

        try:
            profile_soup = self._request_html(player_url)

            height = None
            height_span = profile_soup.find("span", itemprop="height")
            if height_span:
                height = height_span.get_text(strip=True)

            foot = None
            foot_label = profile_soup.find("span", string=re.compile(r"Foot"))
            if foot_label:
                foot_tag = foot_label.find_next("span", class_=re.compile(r"info-table__content"))
                if foot_tag:
                    foot = foot_tag.get_text(strip=True)

            citizenship = None
            # Buscamos la etiqueta "Citizenship" o "Nacionalidad"
            cit_label = profile_soup.find("span", string=re.compile(r"Citizenship|Nacionalidad"))
            if cit_label:
                cit_tag = cit_label.find_next("span", class_=re.compile(r"info-table__content"))
                if cit_tag:
                    citizenship = cit_tag.get_text(strip=True)
                    # A veces hay varias (ej. "Spain, Brazil"), las dejamos como string

            main_position = ""
            other_positions: List[str] = []
            main_dt = profile_soup.find("dt", string=re.compile(r"Main position"))
            if main_dt:
                main_dd = main_dt.find_next("dd")
                if main_dd:
                    main_position = main_dd.get_text(strip=True)

            other_dts = profile_soup.find_all("dt", string=re.compile(r"Other position"))
            for dt_tag in other_dts:
                dl = dt_tag.find_parent("dl")
                if not dl:
                    continue
                dds = dl.find_all("dd")
                for dd in dds:
                    pos = dd.get_text(strip=True)
                    if pos and pos not in other_positions and pos != main_position:
                        other_positions.append(pos)

            contract_details = self._extract_contract_info(profile_soup)

            return {
                "profile_url": f"{self.base_url}{player_url}",
                "height": height,
                "foot": foot,
                "citizenship": citizenship,
                "main_position": main_position,
                "other_positions": other_positions,
                "contract_details": contract_details,
            }
        except Exception:
            return {}

    def _parse_roster_table(self, table: BeautifulSoup, team_id: str, team_name: str, season: str) -> List[Dict]:
        players: List[Dict] = []
        tbody = table.find("tbody")
        if not tbody:
            return players

        rows = tbody.find_all("tr", recursive=False)
        for row in rows:
            try:
                cells = row.find_all("td", recursive=False)
                if len(cells) < 5:
                    continue

                name_cell = cells[1]
                name_link = name_cell.find("a", href=re.compile(r"/profil/spieler/"))
                if not name_link:
                    continue

                player_name = name_link.get_text(strip=True)
                player_url = name_link["href"]
                m = re.search(r"/spieler/(\d+)", player_url)
                player_id = m.group(1) if m else None

                age = None
                try:
                    dob_cell = cells[2].get_text(strip=True)
                    m_age = re.search(r"\((\d{1,2})\)", dob_cell)
                    if m_age:
                        age = int(m_age.group(1))
                except Exception:
                    pass

                market_value = ""
                mv_cell = row.find("td", class_="rechts hauptlink")
                if mv_cell:
                    mv_link = mv_cell.find("a")
                    if mv_link:
                        market_value = mv_link.get_text(strip=True)

                players.append({
                    "name": player_name,
                    "id": player_id,
                    "url": player_url,
                    "age": age,
                    "market_value": market_value,
                    "team_id": team_id,
                    "team_name": team_name,
                    "season": season,
                })
            except Exception:
                continue

        return players

    def get_team_roster(self, team: Dict, season: str = "2026") -> List[Dict]:
        """
        Descarga roster del equipo (sin perfil).
        FIXES:
        - Si el checkpoint viejo no tiene slug, lo derivamos de team['url'] (evita Brighton & → amp).
        - Fallback de saison_id: prueba base y base-1.
        - Fallback plus=1/0.
        """
        team_id = team.get("id")
        team_name = team.get("name", "")
        league_name = team.get("league", "") or ""

        if not team_id:
            return []

        # 🔧 parchea slug aunque venga de CKPT antiguo
        self._ensure_team_slug(team)
        team_slug = team.get("slug") or self.parse_name(team_name)

        season_ids = self._season_id_candidates(league_name, season)

        last_err: Optional[Exception] = None

        for sid in season_ids:
            for plus in (1, 0):
                url = f"/{team_slug}/kader/verein/{team_id}/plus/{plus}/galerie/0?saison_id={sid}"
                try:
                    soup = self._request_html(url)
                except Exception as e:
                    last_err = e
                    continue

                table = soup.find("table", {"class": "items"})
                if not table:
                    continue

                # ✅ si esto funciona, cacheamos el sid para la liga
                if league_name and sid.isdigit():
                    self._league_saison_cache[league_name] = sid

                players = self._parse_roster_table(table, team_id, team_name, season)
                if players:
                    return players

        if last_err:
            raise last_err

        print(f"[WARN] No plantilla para {team_name}")
        return []

    def _extract_market_value_evolution(self, player_id: str) -> List[Dict]:
        try:
            api_url = f"https://www.transfermarkt.com/ceapi/marketValueDevelopment/graph/{player_id}"
            data = self._request_json(api_url)
            raw_list = (data or {}).get("list", [])
            out: List[Dict] = []
            current_year = datetime.now().year

            for entry in raw_list:
                date_str = entry.get("datum_mw")
                try:
                    dt = datetime.strptime(date_str, "%b %d, %Y")
                except Exception:
                    continue
                if dt.year < current_year - 2:
                    continue
                out.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "value": entry.get("y", 0),
                    "age": int(entry.get("age", 0) or 0),
                    "club": entry.get("verein", ""),
                })
            out.sort(key=lambda x: x["date"], reverse=True)
            return out
        except Exception:
            return []

    def _extract_transfer_history(self, player_id: str) -> List[Dict]:
        try:
            api_url = f"https://www.transfermarkt.com/ceapi/transferHistory/list/{player_id}"
            data = self._request_json(api_url)
            transfers: List[Dict] = []
            for t in (data or {}).get("transfers", []):
                raw_fee = t.get("fee", "")
                clean_fee = BeautifulSoup(raw_fee, "html.parser").get_text(strip=True)
                fee_lower = clean_fee.lower()
                is_loan = any(kw in fee_lower for kw in ["loan", "loan fee", "loan transfer"]) and "end of loan" not in fee_lower
                if (clean_fee == "-" and "loan" in t.get("type", "").lower()):
                    is_loan = True
                transfers.append({
                    "season": t.get("season", ""),
                    "date": t.get("date", ""),
                    "from_club": t.get("from", {}).get("clubName", ""),
                    "to_club": t.get("to", {}).get("clubName", ""),
                    "fee": clean_fee,
                    "loan": is_loan,
                })
            return transfers
        except Exception:
            return []

    def _fetch_ceapi_details(self, player_id: str) -> dict:
        return {
            "market_value_evolution": self._extract_market_value_evolution(player_id),
            "transfer_history": self._extract_transfer_history(player_id),
        }

    # ------------- Paralelización -------------
    def enrich_profiles_parallel(self, players: List[Dict]) -> None:
        if not players:
            return
        with ThreadPoolExecutor(max_workers=self.workers_profiles) as ex:
            futs = {ex.submit(self._parse_profile, p): p for p in players if p.get("url")}
            for fut in as_completed(futs):
                p = futs[fut]
                try:
                    p.update(fut.result())
                except Exception:
                    pass

    def enrich_ceapi_parallel(self, players: List[Dict]) -> None:
        if not players:
            return
        with ThreadPoolExecutor(max_workers=self.workers_ceapi) as ex:
            futs = {ex.submit(self._fetch_ceapi_details, p["id"]): p for p in players if p.get("id")}
            for fut in as_completed(futs):
                p = futs[fut]
                try:
                    p.update(fut.result())
                except Exception:
                    pass

    # ------------- Checkpoint -------------
    def _safe_league_filename(self, league_name: str) -> str:
        return f"tm_{league_name.replace(' ', '_')}_jugadores.json"

    def _ckpt_path(self, league_name: str) -> Path:
        return CHECKPOINT_TEMPLATE.parent / self._safe_league_filename(league_name)

    def _load_ckpt(self, league_name: str) -> Optional[dict]:
        path = self._ckpt_path(league_name)
        if self.resume and path.exists():
            try:
                return json.loads(path.read_text(encoding="utf8"))
            except Exception:
                return None
        return None

    def _save_ckpt(self, league_name: str, data: dict) -> None:
        path = self._ckpt_path(league_name)
        tmp = path.with_suffix(path.suffix + ".tmp")  # .json.tmp
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf8")
        tmp.replace(path)
        print(f"[CKPT] {path} (players={data.get('total_players', 0)} teams_done={data.get('teams_done', 0)})")

    # ------------- Orquestación -------------
    def scrape_league_massive(self, league_name: str, season: str = "2026") -> Dict:
        print(f"\n[LEAGUE] {league_name} — temporada {season}")

        existing = self._load_ckpt(league_name)
        if existing and existing.get("season") == season:
            result = existing
            all_players: List[Dict] = result.get("players", [])
            done_team_ids = set(result.get("done_team_ids", []))
            print(f"[RESUME] Reanudando {league_name}: players={len(all_players)} teams_done={len(done_team_ids)}")
        else:
            result = {
                "league": league_name,
                "season": season,
                "teams": [],
                "players": [],
                "total_teams": 0,
                "total_players": 0,
                "teams_done": 0,
                "done_team_ids": [],
                "scraping_date": datetime.now().isoformat(),
            }
            all_players = []
            done_team_ids = set()

        teams = result.get("teams") or self.get_league_teams(league_name, season)

        # 🔧 Parchea slugs en equipos (por si vienen de CKPT antiguo)
        for t in teams:
            t.setdefault("league", league_name)
            t.setdefault("season", season)
            self._ensure_team_slug(t)

        result["teams"] = teams
        result["total_teams"] = len(teams)

        for i, team in enumerate(teams, start=1):
            team_id = team.get("id")
            team_name = team.get("name", "")
            if not team_id or team_id in done_team_ids:
                continue

            print(f"  [TEAM {i}/{len(teams)}] {team_name}")

            try:
                roster = self.get_team_roster(team, season=season)

                self.enrich_profiles_parallel(roster)
                self.enrich_ceapi_parallel(roster)

                all_players.extend(roster)

                done_team_ids.add(team_id)
                result["done_team_ids"] = list(done_team_ids)
                result["teams_done"] = len(done_team_ids)
                result["players"] = all_players
                result["total_players"] = len(all_players)
                result["scraping_date"] = datetime.now().isoformat()

                self._save_ckpt(league_name, result)

            except Exception as e:
                print(f"  [WARN] Error equipo {team_name}: {e}")
                result["players"] = all_players
                result["total_players"] = len(all_players)
                result["scraping_date"] = datetime.now().isoformat()
                self._save_ckpt(league_name, result)
                continue

        result["players"] = all_players
        result["total_players"] = len(all_players)
        return result

    def scrape_multiple_leagues(self, leagues: List[str], season: str = "2026") -> Dict:
        results = {"scraping_date": datetime.now().isoformat(), "season": season, "leagues": {}}
        for league in leagues:
            try:
                data = self.scrape_league_massive(league, season)
                results["leagues"][league] = data
            except Exception as e:
                print(f"[ERROR] procesando {league}: {e}")
                continue
        return results


def run_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default="2026")
    parser.add_argument("--rps", type=float, default=1.2, help="Requests por segundo global (total entre hilos).")
    parser.add_argument("--workers_profiles", type=int, default=6)
    parser.add_argument("--workers_ceapi", type=int, default=12)
    parser.add_argument("--resume", action="store_true", help="Reanudar desde checkpoint si existe.")
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.set_defaults(resume=True)
    parser.add_argument("--leagues", nargs="*", default=None, help="Lista de ligas (si no, todas).")
    args = parser.parse_args()

    scraper = TransfermarktMassiveScraper(
        rps=args.rps,
        workers_profiles=args.workers_profiles,
        workers_ceapi=args.workers_ceapi,
        resume=args.resume,
    )

    leagues_to_scrape = args.leagues or list(scraper.leagues.keys())
    all_data = scraper.scrape_multiple_leagues(leagues_to_scrape, season=args.season)

    RAW_OUT.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf8")
    print(f"\n[OK] Guardado JSON completo en {RAW_OUT}")
    return RAW_OUT

def run(
    season: str = "2026",
    rps: float = 1.6,
    workers_profiles: int = 6,
    workers_ceapi: int = 12,
    resume: bool = True,
    leagues: Optional[List[str]] = None,
) -> str:
    """
    Wrapper compatible con el main_etl antiguo.
    NO parsea argv (a diferencia de run_cli).
    """
    scraper = TransfermarktMassiveScraper(
        rps=rps,
        workers_profiles=workers_profiles,
        workers_ceapi=workers_ceapi,
        resume=resume,
    )
    leagues_to_scrape = leagues or list(scraper.leagues.keys())
    all_data = scraper.scrape_multiple_leagues(leagues_to_scrape, season=season)

    RAW_OUT.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf8")
    print(f"\n[OK] Guardado JSON completo en {RAW_OUT}")
    return str(RAW_OUT)


if __name__ == "__main__":
    run_cli()
