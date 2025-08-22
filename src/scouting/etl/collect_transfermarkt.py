# src/scouting/etl/collect_transfermarkt.py
"""
Scraper Transfermarkt adaptado a entorno local:
- Guardado en data/raw y checkpoints por liga en data/interim
- Reintentos robustos, pausas aleatorias
- Sin pandas (solo JSON)
"""
from __future__ import annotations
import os
import re
import json
import time
import random
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import unidecode

# --------- Config básica por .env ---------
load_dotenv()
RAW_DIR = os.getenv("RAW_DIR", "data/raw")
INTERIM_DIR = os.getenv("INTERIM_DIR", "data/interim")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(INTERIM_DIR, exist_ok=True)

RAW_OUT = os.path.join(RAW_DIR, "db_transfermarkt.json")
CHECKPOINT_TEMPLATE = os.path.join(INTERIM_DIR, "tm_{league}_jugadores.json")


def _sleep(a: float, b: float) -> None:
    """Pausa respetuosa aleatoria entre [a, b] segundos."""
    time.sleep(random.uniform(a, b))


class TransfermarktMassiveScraper:
    def __init__(self):
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
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        # Ligas principales (puedes ampliar cuando quieras)
        self.leagues: Dict[str, Dict[str, str]] = {
            "LaLiga": {"id": "ES1", "name": "laliga"},
            "LaLiga2":{"id": "ES2", "name": "laliga2"},
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
            "Super Lig (Turquía)": {"id": "TR1", "name": "super-lig"}
        }

    # ---------------- Utilidades ----------------
    def make_request(self, url: str, max_retries: int = 8) -> BeautifulSoup:
        """GET con reintentos y pequeñas pausas"""
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(full_url, timeout=30)
                resp.raise_for_status()
                _sleep(0.8, 2.2)
                return BeautifulSoup(resp.content, "html.parser")
            except Exception as e:
                if attempt == max_retries:
                    raise
                _sleep(1.0 * attempt, 1.5 * attempt)

    @staticmethod
    def parse_name(name: str) -> str:
        """Normaliza nombre a slug de URL de equipo en TM."""
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
        """Convierte '2024-2025' -> '2024' (TM usa la primera parte)."""
        if "/" in season:
            return season.split("/")[0]
        if "-" in season:
            return season.split("-")[0]
        try:
            return str(int(season) - 1)  # para formatos sueltos como "2025"
        except Exception:
            return season

    # ---------------- Extracciones ----------------
    def get_league_teams(self, league_name: str, season: str = "2025") -> List[Dict]:
        info = self.leagues.get(league_name)
        if not info:
            raise ValueError(f"Liga no encontrada: {league_name}")

        season_id = self.get_season_id(season)
        url = f"/{info['name']}/startseite/wettbewerb/{info['id']}/plus/?saison_id={season_id}"
        soup = self.make_request(url)
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
                    teams.append(
                        {
                            "name": team_name,
                            "id": team_id,
                            "url": team_url,
                            "league": league_name,
                            "season": season,
                        }
                    )
            except Exception:
                continue
        return teams

    def get_team_players(self, team_id: str, team_name: str, season: str = "2026") -> List[Dict]:
        print(f"  [INFO] Jugadores de {team_name}")
        season_id = self.get_season_id(season)
        team_url_name = self.parse_name(team_name)
        url = f"/{team_url_name}/kader/verein/{team_id}/plus/1/galerie/0?saison_id={season_id}"

        soup = self.make_request(url)
        players: List[Dict] = []

        table = soup.find("table", {"class": "items"})
        if not table:
            print(f"[WARN] No plantilla para {team_name}")
            return players

        tbody = table.find("tbody")
        if not tbody:
            return players

        rows = tbody.find_all("tr", recursive=False)
        for row in rows:
            try:
                cells = row.find_all("td", recursive=False)
                if len(cells) < 5:
                    continue

                # Nombre y perfil
                name_cell = cells[1]
                name_link = name_cell.find("a", href=re.compile(r"/profil/spieler/"))
                if not name_link:
                    continue

                player_name = name_link.get_text(strip=True)
                player_url = name_link["href"]
                m = re.search(r"/spieler/(\d+)", player_url)
                player_id = m.group(1) if m else None

                # Extra detalle (altura, pie, posiciones) desde perfil
                profile_soup = self.make_request(player_url)

                # Altura
                height = None
                try:
                    height_span = profile_soup.find("span", itemprop="height")
                    if height_span:
                        height = height_span.get_text(strip=True)
                except Exception:
                    pass

                # Pie dominante
                foot = None
                try:
                    foot_label = profile_soup.find("span", string=re.compile(r"Foot:"))
                    if foot_label:
                        foot_tag = foot_label.find_next("span", class_="info-table__content--bold")
                        if foot_tag:
                            foot = foot_tag.get_text(strip=True)
                except Exception:
                    pass

                # Posiciones
                main_position = ""
                other_positions: List[str] = []
                try:
                    main_dt = profile_soup.find("dt", string=re.compile(r"Main position:"))
                    if main_dt:
                        main_dd = main_dt.find_next("dd")
                        if main_dd:
                            main_position = main_dd.get_text(strip=True)
                    other_dts = profile_soup.find_all("dt", string=re.compile(r"Other position:"))
                    for dt_tag in other_dts:
                        siblings = dt_tag.find_parent("dl").find_all("dd")
                        for sib in siblings:
                            pos = sib.get_text(strip=True)
                            if pos and pos not in other_positions:
                                other_positions.append(pos)
                except Exception:
                    pass

                # Edad (si viene en la columna de fecha de nacimiento)
                age = None
                try:
                    dob_cell = cells[2].get_text(strip=True)
                    m_age = re.search(r"\((\d{1,2})\)", dob_cell)
                    if m_age:
                        age = int(m_age.group(1))
                except Exception:
                    pass

                # Valor de mercado
                market_value = ""
                mv_cell = row.find("td", class_="rechts hauptlink")
                if mv_cell:
                    mv_link = mv_cell.find("a")
                    if mv_link:
                        market_value = mv_link.get_text(strip=True)

                players.append(
                    {
                        "name": player_name,
                        "id": player_id,
                        "profile_url": f"{self.base_url}{player_url}",
                        "url": player_url,
                        "main_position": main_position,
                        "other_positions": other_positions,
                        "foot": foot,
                        "age": age,
                        "height": height,
                        "market_value": market_value,
                        "team_id": team_id,
                        "team_name": team_name,
                        "season": season,
                    }
                )
                _sleep(0.5, 1.5)
            except Exception:
                continue

        return players

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

    def _extract_market_value_evolution(self, player_id: str) -> List[Dict]:
        try:
            api_url = f"https://www.transfermarkt.com/ceapi/marketValueDevelopment/graph/{player_id}"
            resp = self.session.get(api_url, timeout=30, headers=self.headers)
            _sleep(0.8, 1.5)
            if resp.status_code != 200:
                return []
            raw_list = resp.json().get("list", [])
            out: List[Dict] = []
            current_year = datetime.now().year
            for entry in raw_list:
                date_str = entry.get("datum_mw")
                try:
                    # Ej: "Jul 12, 2024"
                    dt = datetime.strptime(date_str, "%b %d, %Y")
                except Exception:
                    continue
                if dt.year < current_year - 2:
                    continue
                out.append(
                    {
                        "date": dt.strftime("%Y-%m-%d"),
                        "value": entry.get("y", 0),
                        "age": int(entry.get("age", 0) or 0),
                        "club": entry.get("verein", ""),
                    }
                )
            out.sort(key=lambda x: x["date"], reverse=True)
            return out
        except Exception:
            return []

    def _extract_transfer_history(self, player_id: str) -> List[Dict]:
        try:
            api_url = f"https://www.transfermarkt.com/ceapi/transferHistory/list/{player_id}"
            resp = self.session.get(api_url, timeout=30, headers=self.headers)
            if resp.status_code != 200:
                return []
            data = resp.json()
            transfers: List[Dict] = []
            for t in data.get("transfers", []):
                raw_fee = t.get("fee", "")
                clean_fee = BeautifulSoup(raw_fee, "html.parser").get_text(strip=True)
                fee_lower = clean_fee.lower()
                is_loan = any(kw in fee_lower for kw in ["loan", "loan fee", "loan transfer"]) and "end of loan" not in fee_lower
                if (clean_fee == "-" and "loan" in t.get("type", "").lower()):
                    is_loan = True
                transfers.append(
                    {
                        "season": t.get("season", ""),
                        "date": t.get("date", ""),
                        "from_club": t.get("from", {}).get("clubName", ""),
                        "to_club": t.get("to", {}).get("clubName", ""),
                        "fee": clean_fee,
                        "loan": is_loan,
                    }
                )
            return transfers
        except Exception:
            return []

    def get_player_detailed_info(self, player_name: str, player_profile: str, player_id: str) -> Dict:
        soup = self.make_request(player_profile)
        return {
            "contract_details": self._extract_contract_info(soup),
            "market_value_evolution": self._extract_market_value_evolution(player_id),
            "transfer_history": self._extract_transfer_history(player_id),
        }

    # ---------------- Orquestación ----------------
    def scrape_league_massive(self, league_name: str, season: str = "2025") -> Dict:
        print(f"\n[LEAGUE] {league_name} — temporada {season}")
        result = {
            "league": league_name,
            "season": season,
            "teams": [],
            "players": [],
            "total_teams": 0,
            "total_players": 0,
            "scraping_date": datetime.now().isoformat(),
        }

        teams = self.get_league_teams(league_name, season)
        result["teams"] = teams
        result["total_teams"] = len(teams)

        all_players: List[Dict] = []
        for team in teams:
            try:
                players = self.get_team_players(team["id"], team["name"], season=season)
                for p in players:
                    try:
                        detail = self.get_player_detailed_info(p["name"], p["profile_url"], p["id"])
                        p.update(detail)
                        all_players.append(p)
                        _sleep(0.8, 2.0)
                    except Exception:
                        continue
                _sleep(2.0, 4.0)
            except Exception:
                continue

        result["players"] = all_players
        result["total_players"] = len(all_players)
        return result

    def scrape_multiple_leagues(self, leagues: List[str], season: str = "2025") -> Dict:
        results = {"scraping_date": datetime.now().isoformat(), "season": season, "leagues": {}}
        for league in leagues:
            try:
                data = self.scrape_league_massive(league, season)
                results["leagues"][league] = data
                # checkpoint por liga
                ckpt = CHECKPOINT_TEMPLATE.format(league=league.replace(" ", "_"))
                with open(ckpt, "w", encoding="utf8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"[CKPT] guardado {ckpt} (players={data['total_players']})")
                _sleep(5.0, 10.0)
            except Exception as e:
                print(f"[ERROR] procesando {league}: {e}")
                continue
        return results


def run() -> str:
    scraper = TransfermarktMassiveScraper()
    leagues_to_scrape = list(scraper.leagues.keys())  # puedes limitar para pruebas
    all_data = scraper.scrape_multiple_leagues(leagues_to_scrape)
    with open(RAW_OUT, "w", encoding="utf8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Guardado JSON completo en {RAW_OUT}")
    return RAW_OUT


if __name__ == "__main__":
    run()
