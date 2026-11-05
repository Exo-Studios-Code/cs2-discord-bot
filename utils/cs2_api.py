"""
CS2 API modul - Steam Web API + CS2 match sharing
Získává statistiky hráče a data ze zápasů.
"""

import aiohttp
import asyncio
import logging
import re
from typing import Optional, Dict, Any, Tuple

log = logging.getLogger("CS2Bot.API")

STEAM_API_BASE = "https://api.steampowered.com"
CS2_APP_ID = 730

# ─── SHARECODE DECODER ──────────────────────────────────────────

DICTIONARY = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"
SHARECODE_PATTERN = re.compile(r"^CSGO(-?[A-Za-z0-9]{5}){5}$")

def decode_sharecode(sharecode: str) -> Tuple[int, int, int]:
    """
    Dekóduje CS2 sharecode na match_id, reservation_id, tv_port.
    Sharecode formát: CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
    """
    code = sharecode.replace("CSGO", "").replace("-", "")
    chars = [DICTIONARY.index(c) for c in reversed(code)]

    big_num = 0
    for c in chars:
        big_num = big_num * len(DICTIONARY) + c

    # Extrahuj 3 složky
    match_id      = big_num & 0xFFFFFFFFFFFFFFFF
    reservation_id = (big_num >> 64) & 0xFFFFFFFFFFFFFFFF
    tv_port       = (big_num >> 128) & 0xFFFF

    return match_id, reservation_id, tv_port

def validate_sharecode(sharecode: str) -> bool:
    return bool(SHARECODE_PATTERN.match(sharecode))

def steam64_from_steamid3(steam_id3: str) -> Optional[str]:
    """Konvertuje SteamID3 [U:1:XXXXXXXX] na Steam64."""
    match = re.search(r"\[?U:1:(\d+)\]?", steam_id3)
    if match:
        return str(int(match.group(1)) + 76561197960265728)
    return None

def validate_steam64(steam_id: str) -> bool:
    """Validuje Steam64 ID."""
    try:
        sid = int(steam_id)
        return 76561197960265728 <= sid <= 76561202255233023
    except ValueError:
        return False

# ─── STEAM API ──────────────────────────────────────────────────

class SteamAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self.session

    async def _get(self, endpoint: str, params: Dict) -> Optional[Dict]:
        params["key"] = self.api_key
        session = await self._get_session()
        try:
            async with session.get(f"{STEAM_API_BASE}{endpoint}", params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 403:
                    log.warning("Steam API: 403 Forbidden (soukromý profil nebo špatný API klíč)")
                    return None
                else:
                    log.warning(f"Steam API: HTTP {resp.status}")
                    return None
        except asyncio.TimeoutError:
            log.error("Steam API: Timeout")
            return None
        except Exception as e:
            log.error(f"Steam API chyba: {e}")
            return None

    async def get_player_summary(self, steam_id: str) -> Optional[Dict[str, Any]]:
        """Základní info o hráči."""
        data = await self._get(
            "/ISteamUser/GetPlayerSummaries/v2/",
            {"steamids": steam_id}
        )
        if data:
            players = data.get("response", {}).get("players", [])
            return players[0] if players else None
        return None

    async def get_cs2_stats(self, steam_id: str) -> Optional[Dict[str, Any]]:
        """Celkové statistiky CS2."""
        data = await self._get(
            "/ISteamUserStats/GetUserStatsForGame/v2/",
            {"steamid": steam_id, "appid": CS2_APP_ID}
        )
        if not data:
            return None

        raw_stats = data.get("playerstats", {}).get("stats", [])
        stats = {s["name"]: s["value"] for s in raw_stats}

        # Parsuj klíčové statistiky
        parsed = parse_cs2_stats(stats)
        parsed["raw"] = stats
        return parsed

    async def get_achievements(self, steam_id: str) -> Optional[Dict]:
        """CS2 achievementy."""
        data = await self._get(
            "/ISteamUserStats/GetPlayerAchievements/v1/",
            {"steamid": steam_id, "appid": CS2_APP_ID}
        )
        return data

    async def get_next_match_code(self, steam_id: str, auth_token: str,
                                   known_code: str) -> Optional[str]:
        """
        Získá další match sharecode z Steam API.
        Vyžaduje: steam_id, match auth token (z CS2 nastavení), poslední known sharecode.
        """
        data = await self._get(
            "/ICSGOPlayers_730/GetNextMatchSharingCode/v1",
            {
                "steamid": steam_id,
                "steamidkey": auth_token,
                "knowncode": known_code
            }
        )
        if data:
            return data.get("result", {}).get("nextcode")
        return None

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

# ─── PARSER ─────────────────────────────────────────────────────

def parse_cs2_stats(raw: Dict[str, int]) -> Dict[str, Any]:
    """Parsuje surová Steam API data na čitelné statistiky."""
    kills         = raw.get("total_kills", 0)
    deaths        = raw.get("total_deaths", 0)
    matches       = raw.get("total_matches_played", 0)
    wins          = raw.get("total_matches_won", 0)
    hs            = raw.get("total_kills_headshot", 0)
    mvps          = raw.get("total_mvps", 0)
    shots_fired   = raw.get("total_shots_fired", 0)
    shots_hit     = raw.get("total_shots_hit", 0)
    damage        = raw.get("total_damage_done", 0)
    time_played   = raw.get("total_time_played", 0)

    kd            = round(kills / deaths, 2) if deaths > 0 else kills
    win_rate      = round(wins / matches * 100, 1) if matches > 0 else 0
    hs_rate       = round(hs / kills * 100, 1) if kills > 0 else 0
    accuracy      = round(shots_hit / shots_fired * 100, 1) if shots_fired > 0 else 0
    adr           = round(damage / matches, 1) if matches > 0 else 0
    hours         = round(time_played / 3600, 1)

    # Nejlepší mapa
    map_wins = {}
    for key, val in raw.items():
        if key.startswith("total_wins_map_"):
            map_name = key.replace("total_wins_map_", "").replace("cs_", "").replace("de_", "de_")
            map_wins[map_name] = val
    best_map = max(map_wins, key=map_wins.get) if map_wins else "Neznámá"

    # Nejoblíbenější zbraň
    weapon_kills = {}
    weapon_prefixes = [
        "total_kills_ak47", "total_kills_m4a1", "total_kills_awp",
        "total_kills_deagle", "total_kills_glock", "total_kills_mp9",
        "total_kills_famas", "total_kills_sg556", "total_kills_aug",
        "total_kills_p250", "total_kills_mac10", "total_kills_ump45"
    ]
    for key in weapon_prefixes:
        if key in raw:
            weapon = key.replace("total_kills_", "")
            weapon_kills[weapon] = raw[key]
    fav_weapon = max(weapon_kills, key=weapon_kills.get) if weapon_kills else "Neznámá"

    return {
        "total_kills": kills,
        "total_deaths": deaths,
        "total_matches": matches,
        "total_wins": wins,
        "total_mvps": mvps,
        "total_hs": hs,
        "shots_fired": shots_fired,
        "shots_hit": shots_hit,
        "total_damage": damage,
        "time_played": time_played,
        "kd_ratio": kd,
        "win_rate": win_rate,
        "hs_rate": hs_rate,
        "accuracy": accuracy,
        "adr": adr,
        "hours_played": hours,
        "best_map": best_map,
        "favorite_weapon": fav_weapon,
        "map_wins": map_wins,
        "weapon_kills": weapon_kills,
    }

# ─── PERFORMANCE RATING ─────────────────────────────────────────

def calculate_rating(stats: Dict) -> float:
    """
    Jednoduchý HLTV-like rating výpočet.
    Rating 1.0 = průměr, >1.0 = nadprůměr.
    """
    kd     = stats.get("kd_ratio", 1.0)
    hs_r   = stats.get("hs_rate", 0) / 100
    win_r  = stats.get("win_rate", 50) / 100
    adr    = stats.get("adr", 70)

    # Normalizace
    kd_norm   = min(kd / 1.0, 2.0) * 0.4
    hs_norm   = min(hs_r / 0.5, 2.0) * 0.1
    win_norm  = win_r * 0.3
    adr_norm  = min(adr / 70, 2.0) * 0.2

    return round(kd_norm + hs_norm + win_norm + adr_norm, 2)

def get_rank_from_rating(rating: float) -> Tuple[str, str]:
    """Odhadne rank na základě ratingu a K/D."""
    if rating >= 1.8:   return "Global Elite", "🟡"
    if rating >= 1.6:   return "Supreme", "🔴"
    if rating >= 1.4:   return "The Legendary Eagle Master", "🟠"
    if rating >= 1.2:   return "Distinguished Master Guardian", "🟠"
    if rating >= 1.0:   return "Master Guardian Elite", "🟢"
    if rating >= 0.85:  return "Master Guardian II", "🟢"
    if rating >= 0.7:   return "Gold Nova III", "🔵"
    if rating >= 0.6:   return "Gold Nova I", "🔵"
    return "Silver", "⚪"
