"""
External APIs modul
====================
Podporované zdroje dat:

1. LEETIFY  (api.cs-prod.leetify.com)  — VEŘEJNÉ API, klíč volitelný
   Vrací: preaim (crosshair placement %), aim_rating, utility_rating,
          positioning_rating, clutch_rating, opening_duel_win_rate,
          ct_rating, t_rating, Premier rank, per-match ratings

2. CSSTATS.GG  (csstats.gg)  — sharecode upload → parsed match data
   Vrací: rating, K/D, HS%, ADR, KAST per match (z demo analýzy)

3. FACEIT  (open.faceit.com/data/v4)  — VYŽADUJE klíč (zdarma)
   Vrací: Level, ELO, win rate, K/D, HS%, longest streak, recent form

Všechny zdroje jsou staženy paralelně a výsledky agregovány.
"""

import aiohttp
import asyncio
import logging
import os
import re
from typing import Optional, Dict, Any, List

log = logging.getLogger("CS2Bot.ExternalAPI")

_TIMEOUT = aiohttp.ClientTimeout(total=12)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ════════════════════════════════════════════════════════════════
#  1. LEETIFY  —  https://api.cs-prod.leetify.com/api
# ════════════════════════════════════════════════════════════════

class LeetifyAPI:
    """
    Leetify Public CS API.
    Klíč zdarma na: https://leetify.com/app/developer
    Bez klíče funguje, ale s přísnějšími rate limity.

    Endpointy:
      GET /api/profiles/{steam64}           → profil + ratings + posledních 20 zápasů
      GET /api/profiles/{steam64}/matches   → plná match historie
      GET /api/matches/{leetify_match_id}   → detail zápasu
    """
    BASE = "https://api.cs-prod.leetify.com/api"

    def __init__(self):
        key = os.getenv("LEETIFY_API_KEY", "")
        self._extra_headers = {"Authorization": f"Bearer {key}"} if key else {}

    async def get_profile(self, steam_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.BASE}/profiles/{steam_id}"
        try:
            async with aiohttp.ClientSession(
                headers={**_HEADERS, **self._extra_headers}
            ) as s:
                async with s.get(url, timeout=_TIMEOUT) as r:
                    if r.status == 404:
                        log.info("[Leetify] Profil nenalezen pro %s", steam_id)
                        return None
                    if r.status != 200:
                        log.warning("[Leetify] HTTP %s", r.status)
                        return None
                    data = await r.json(content_type=None)
                    return self._parse_profile(data, steam_id)
        except asyncio.TimeoutError:
            log.warning("[Leetify] Timeout")
            return None
        except Exception as e:
            log.error("[Leetify] Chyba: %s", e)
            return None

    async def get_matches(self, steam_id: str, limit: int = 10) -> List[Dict]:
        url = f"{self.BASE}/profiles/{steam_id}/matches"
        try:
            async with aiohttp.ClientSession(
                headers={**_HEADERS, **self._extra_headers}
            ) as s:
                async with s.get(url, timeout=_TIMEOUT) as r:
                    if r.status != 200:
                        return []
                    data = await r.json(content_type=None)
                    return self._parse_matches(data, steam_id, limit)
        except Exception as e:
            log.error("[Leetify] Match chyba: %s", e)
            return []

    def _parse_profile(self, data: Dict, steam_id: str) -> Dict[str, Any]:
        ratings  = data.get("ratings", {})
        ranks    = data.get("ranks", {})
        stats    = data.get("stats", {})
        games    = data.get("games", {})

        # preaim = procento kolikrát byl crosshair na enemy před spotnutím
        preaim = stats.get("preaim")
        if preaim is None:
            preaim = stats.get("preAim")  # fallback jiný key

        return {
            "source":               "leetify",
            # ─── Ratings (0–10 škála, benchmark 5.0 = průměr) ───
            "aim_rating":           _r(ratings.get("aim")),
            "utility_rating":       _r(ratings.get("utility")),
            "positioning_rating":   _r(ratings.get("positioning")),
            "clutch_rating":        _r(ratings.get("clutch")),
            "leetify_rating":       _r(ratings.get("leetify")),
            # ─── CT vs T výkon ───────────────────────────────────
            "ct_rating":            _r(data.get("ctRating") or data.get("recentGameRatings", {}).get("ct")),
            "t_rating":             _r(data.get("tRating")  or data.get("recentGameRatings", {}).get("t")),
            # ─── Klíčové metriky ─────────────────────────────────
            "preaim_pct":           _r(preaim),          # crosshair placement %
            "opening_duel_wr":      _pct(data.get("openingDuelWinRate")),
            "trade_kill_ratio":     _r(stats.get("tradeKillRatio") or stats.get("tradeKill")),
            "flash_success_rate":   _pct(stats.get("flashSuccessRate") or stats.get("flashSuccess")),
            "utility_damage_per_round": _r(stats.get("utilityDamagePerRound") or stats.get("utilityDamage")),
            "enemies_flashed_per_round": _r(stats.get("enemiesFlashedPerRound") or stats.get("enemiesFlashed")),
            # ─── Rank ────────────────────────────────────────────
            "premier_rank":         ranks.get("premier") or ranks.get("premierRank"),
            "games_tracked":        games.get("total", 0),
            "profile_url":          f"https://leetify.com/app/profile/{steam_id}",
        }

    def _parse_matches(self, data: Any, steam_id: str, limit: int) -> List[Dict]:
        """Zpracuje seznam zápasů z Leetify."""
        if isinstance(data, list):
            raw_matches = data
        elif isinstance(data, dict):
            raw_matches = data.get("data", data.get("matches", []))
        else:
            return []

        out = []
        for m in raw_matches[:limit]:
            # Najdi stats pro tohoto hráče
            player_stats = {}
            for ps in m.get("stats", []):
                if str(ps.get("steamId64", "")) == str(steam_id):
                    player_stats = ps
                    break

            out.append({
                "match_id":      m.get("id"),
                "map_name":      m.get("mapName", m.get("map_name", "?")),
                "finished_at":   m.get("finishedAt", m.get("finished_at", "")),
                "outcome":       m.get("outcome", "?"),
                # Hráčovy stats
                "kills":         player_stats.get("totalKills", player_stats.get("total_kills", 0)),
                "deaths":        player_stats.get("totalDeaths", player_stats.get("total_deaths", 0)),
                "assists":       player_stats.get("totalAssists", player_stats.get("total_assists", 0)),
                "rating":        _r(player_stats.get("leetifyRating", player_stats.get("leetify_rating"))),
                "hs_pct":        _pct(player_stats.get("headshotPercentage", player_stats.get("headshot_percentage"))),
                "adr":           _r(player_stats.get("adr")),
                "kast":          _pct(player_stats.get("kast")),
                "preaim":        _r(player_stats.get("preaim")),
                "match_url":     f"https://leetify.com/app/match-details/{m.get('id', '')}",
            })
        return out


# ════════════════════════════════════════════════════════════════
#  2. CSSTATS.GG  —  sharecode upload + player page
# ════════════════════════════════════════════════════════════════

class CSStatsAPI:
    """
    csstats.gg — sharecode upload + player stats.
    Sharecode upload spustí demo parsing na jejich serverech.
    Výsledky pak dostupné na player page.

    Sharecode upload: POST https://www.csstats.gg/api/sharecode/add
    Player page:       GET https://csstats.gg/player/{steam64}
    """
    UPLOAD_URL = "https://www.csstats.gg/api/sharecode/add"
    PLAYER_URL = "https://csstats.gg/player/{steam_id}"

    async def upload_sharecode(self, sharecode: str) -> Dict[str, Any]:
        """Nahraje sharecode na csstats.gg pro zpracování dema."""
        payload = {"code": sharecode}
        try:
            async with aiohttp.ClientSession(headers=_HEADERS) as s:
                async with s.post(
                    self.UPLOAD_URL, json=payload, timeout=_TIMEOUT
                ) as r:
                    text = await r.text()
                    if r.status in (200, 201, 202):
                        try:
                            data = await r.json(content_type=None)
                            status = data.get("status", data.get("result", "queued"))
                        except Exception:
                            status = "submitted"
                        return {
                            "success": True,
                            "status": status,
                            "message": "Sharecode odeslan na csstats.gg ke zpracovani (~2-5 min)",
                        }
                    elif r.status == 409:
                        return {"success": True, "status": "already_exists",
                                "message": "Tento zapas uz je na csstats.gg"}
                    else:
                        log.warning("[CSStats] Upload HTTP %s: %s", r.status, text[:200])
                        return {"success": False, "status": "error", "message": f"HTTP {r.status}"}
        except Exception as e:
            log.error("[CSStats] Upload chyba: %s", e)
            return {"success": False, "status": "error", "message": str(e)}

    async def get_player(self, steam_id: str) -> Optional[Dict[str, Any]]:
        """Stáhne základní stats hráče z csstats.gg."""
        url = self.PLAYER_URL.format(steam_id=steam_id)
        try:
            async with aiohttp.ClientSession(headers={
                **_HEADERS, "Accept": "text/html,application/xhtml+xml"
            }) as s:
                async with s.get(url, timeout=_TIMEOUT) as r:
                    if r.status != 200:
                        return None
                    html = await r.text()
                    return self._parse_player_page(html, steam_id)
        except Exception as e:
            log.error("[CSStats] Player chyba: %s", e)
            return None

    def _parse_player_page(self, html: str, steam_id: str) -> Optional[Dict[str, Any]]:
        """Parser pro csstats.gg player stránku."""
        def find_num(patterns: list, default="N/A"):
            for p in patterns:
                m = re.search(p, html, re.DOTALL)
                if m:
                    val = m.group(1).replace(",", "").strip()
                    if val:
                        return val
            return default

        # csstats.gg zobrazuje stats v různých formátech — zkusíme více patterns
        kd       = find_num([r'"kd"[^>]*>([\d.]+)', r'K/D.*?>([\d.]+)<'])
        wr       = find_num([r'"wr"[^>]*>([\d.]+)', r'Win Rate.*?>([\d.]+)%'])
        hs       = find_num([r'"hs"[^>]*>([\d.]+)', r'HS.*?>([\d.]+)%'])
        matches  = find_num([r'"matches"[^>]*>([\d,]+)', r'Matches.*?>([\d,]+)<'])
        wins     = find_num([r'"wins"[^>]*>([\d,]+)', r'Wins.*?>([\d,]+)<'])
        rating   = find_num([r'"rating"[^>]*>([\d.]+)', r'Rating.*?>([\d.]+)<'])
        adr      = find_num([r'"adr"[^>]*>([\d.]+)', r'ADR.*?>([\d.]+)<'])
        premier  = find_num([r'Premier.*?(\d{4,6})', r'CS Rating.*?(\d{4,6})'])

        # Pokud nenašli nic smysluplného, vrátíme None
        if kd == "N/A" and matches == "N/A" and rating == "N/A":
            return None

        return {
            "source":      "csstats",
            "kd":          kd,
            "win_rate":    wr,
            "hs_pct":      hs,
            "matches":     matches,
            "wins":        wins,
            "rating":      rating,
            "adr":         adr,
            "premier":     premier,
            "profile_url": f"https://csstats.gg/player/{steam_id}",
        }


# ════════════════════════════════════════════════════════════════
#  3. FACEIT  —  https://open.faceit.com/data/v4
# ════════════════════════════════════════════════════════════════

class FACEITApi:
    """
    FACEIT Open Data API.
    Klíč ZDARMA: https://developers.faceit.com/ → Apps → API Keys
    Nastav jako FACEIT_API_KEY v .env
    """
    BASE = "https://open.faceit.com/data/v4"

    def __init__(self):
        self.api_key = os.getenv("FACEIT_API_KEY", "")
        self._auth_headers = {
            **_HEADERS,
            "Authorization": f"Bearer {self.api_key}",
        }

    async def get_player_by_steam(self, steam_id: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            log.debug("[FACEIT] FACEIT_API_KEY neni nastaven")
            return None

        url = f"{self.BASE}/players?game=cs2&game_player_id={steam_id}"
        try:
            async with aiohttp.ClientSession(headers=self._auth_headers) as s:
                async with s.get(url, timeout=_TIMEOUT) as r:
                    if r.status == 404:
                        return None   # hráč nemá FACEIT
                    if r.status == 401:
                        log.warning("[FACEIT] Neplatny API klic!")
                        return None
                    if r.status != 200:
                        log.warning("[FACEIT] HTTP %s", r.status)
                        return None
                    player = await r.json(content_type=None)
                    return await self._enrich(s, player, steam_id)
        except Exception as e:
            log.error("[FACEIT] Chyba: %s", e)
            return None

    async def _enrich(self, session: aiohttp.ClientSession,
                       player: Dict, steam_id: str) -> Dict[str, Any]:
        player_id = player.get("player_id", "")
        game_info = player.get("games", {}).get("cs2", {})

        lifetime = {}
        segments = []
        try:
            async with session.get(
                f"{self.BASE}/players/{player_id}/stats/cs2", timeout=_TIMEOUT
            ) as r:
                if r.status == 200:
                    raw = await r.json(content_type=None)
                    lifetime = raw.get("lifetime", {})
                    segments = raw.get("segments", [])
        except Exception:
            pass

        # Zpracuj segmenty (per-mapa statistiky)
        map_stats = {}
        for seg in segments[:5]:
            if seg.get("type") == "Map":
                label = seg.get("label", "?").replace("de_", "")
                s_stats = seg.get("stats", {})
                map_stats[label] = {
                    "win_rate": s_stats.get("Win Rate %", "?"),
                    "kd":       s_stats.get("Average K/D Ratio", "?"),
                    "matches":  s_stats.get("Matches", "?"),
                }

        return {
            "source":          "faceit",
            "player_id":       player_id,
            "nickname":        player.get("nickname", "N/A"),
            "level":           game_info.get("skill_level", "N/A"),
            "elo":             game_info.get("faceit_elo", "N/A"),
            "country":         player.get("country", "N/A"),
            "avatar":          player.get("avatar", ""),
            "profile_url":     player.get("faceit_url", "").replace("{lang}", "en"),
            # Lifetime stats
            "total_matches":   _int(lifetime.get("Matches")),
            "win_rate":        lifetime.get("Win Rate %", "N/A"),
            "avg_kd":          lifetime.get("Average K/D Ratio", "N/A"),
            "avg_hs_pct":      lifetime.get("Average Headshots %", "N/A"),
            "longest_streak":  lifetime.get("Longest Win Streak", "N/A"),
            "current_streak":  lifetime.get("Current Win Streak", "N/A"),
            "total_wins":      lifetime.get("Wins", "N/A"),
            # Map stats
            "map_stats":       map_stats,
        }

    async def get_recent_matches(self, player_id: str, limit: int = 5) -> List[Dict]:
        if not self.api_key or not player_id:
            return []
        url = f"{self.BASE}/players/{player_id}/history?game=cs2&limit={limit}"
        try:
            async with aiohttp.ClientSession(headers=self._auth_headers) as s:
                async with s.get(url, timeout=_TIMEOUT) as r:
                    if r.status != 200:
                        return []
                    data = await r.json(content_type=None)
                    return [
                        {
                            "match_id":   m.get("match_id"),
                            "map":        m.get("voting", {}).get("map", {}).get("pick", ["?"])[0] if m.get("voting") else "?",
                            "result":     "WIN" if m.get("results", {}).get("winner") == m.get("teams", {}).get("faction1", {}).get("faction_id") else "LOSS",
                            "finished":   m.get("finished_at"),
                        }
                        for m in data.get("items", [])
                    ]
        except Exception as e:
            log.error("[FACEIT] Recent matches chyba: %s", e)
            return []


# ════════════════════════════════════════════════════════════════
#  AGREGÁTOR  —  stáhne vše paralelně
# ════════════════════════════════════════════════════════════════

class ExternalStatsAggregator:

    def __init__(self):
        self.leetify  = LeetifyAPI()
        self.csstats  = CSStatsAPI()
        self.faceit   = FACEITApi()

    async def fetch_all(self, steam_id: str) -> Dict[str, Any]:
        log.info("[External] Paralelni stazeni dat pro %s...", steam_id)

        leetify_task  = self.leetify.get_profile(steam_id)
        csstats_task  = self.csstats.get_player(steam_id)
        faceit_task   = self.faceit.get_player_by_steam(steam_id)

        results = await asyncio.gather(
            leetify_task, csstats_task, faceit_task,
            return_exceptions=True
        )

        out: Dict[str, Any] = {}
        labels = ["leetify", "csstats", "faceit"]
        for label, result in zip(labels, results):
            if isinstance(result, Exception):
                log.warning("[External] %s selhal: %s", label, result)
            elif result:
                out[label] = result
                log.info("[External] %s: OK", label)

        return out

    async def upload_sharecode_all(self, sharecode: str) -> Dict[str, Any]:
        """Nahraje sharecode na csstats.gg."""
        return await self.csstats.upload_sharecode(sharecode)

    # ── Discord embed helpers ──────────────────────────────────

    def build_embed_fields(self, data: Dict[str, Any]) -> List[tuple]:
        """Vrátí seznam (name, value, inline) pro Discord embed."""
        fields = []

        # ── LEETIFY ──────────────────────────────────────────
        if "leetify" in data:
            l = data["leetify"]
            rank_str = f" | Premier: `{l['premier_rank']}`" if l.get("premier_rank") else ""

            # Ratings s vizuálními indikátory
            def rating_bar(val):
                if val == "N/A": return "N/A"
                try:
                    v = float(val)
                    filled = min(10, max(0, round(v)))
                    return "█" * filled + "░" * (10 - filled) + f" `{val}`"
                except Exception:
                    return str(val)

            fields.append((
                "Leetify",
                (
                    f"Rating: **{l.get('leetify_rating')}**{rank_str}\n"
                    f"Sledovano zapasu: `{l.get('games_tracked')}`\n"
                    f"\n**Ratings (skala 0-10):**\n"
                    f"Aim:          {rating_bar(l.get('aim_rating'))}\n"
                    f"Utility:      {rating_bar(l.get('utility_rating'))}\n"
                    f"Positioning:  {rating_bar(l.get('positioning_rating'))}\n"
                    f"Clutch:       {rating_bar(l.get('clutch_rating'))}\n"
                    f"\n**Pokrocile metriky:**\n"
                    f"Crosshair placement (preaim): **{l.get('preaim_pct')}%**\n"
                    f"Opening duel WR: **{l.get('opening_duel_wr')}%**\n"
                    f"CT rating: `{l.get('ct_rating')}` | T rating: `{l.get('t_rating')}`\n"
                    f"Trade kill ratio: `{l.get('trade_kill_ratio')}`\n"
                    f"Flash success: `{l.get('flash_success_rate')}%`\n"
                    f"[Otevrit profil]({l.get('profile_url')})"
                ),
                False
            ))

        # ── CSSTATS.GG ───────────────────────────────────────
        if "csstats" in data:
            c = data["csstats"]
            fields.append((
                "csstats.gg",
                (
                    f"Rating: **{c.get('rating', 'N/A')}** | K/D: **{c.get('kd', 'N/A')}**\n"
                    f"Win Rate: `{c.get('win_rate', 'N/A')}%` | HS: `{c.get('hs_pct', 'N/A')}%`\n"
                    f"ADR: `{c.get('adr', 'N/A')}` | Zapasy: `{c.get('matches', 'N/A')}`\n"
                    + (f"Premier: `{c['premier']}`\n" if c.get('premier') and c['premier'] != 'N/A' else "")
                    + f"[Otevrit profil]({c.get('profile_url')})"
                ),
                False
            ))

        # ── FACEIT ───────────────────────────────────────────
        if "faceit" in data:
            f = data["faceit"]
            lvl    = f.get("level", "N/A")
            elo    = f.get("elo", "N/A")
            emoji  = _faceit_emoji(lvl)

            map_lines = ""
            if f.get("map_stats"):
                lines = []
                for mname, ms in list(f["map_stats"].items())[:4]:
                    lines.append(f"`{mname}`: {ms['win_rate']}% WR | KD: {ms['kd']}")
                map_lines = "\n**Per-mapa:**\n" + "\n".join(lines)

            fields.append((
                "FACEIT",
                (
                    f"{emoji} Level **{lvl}** | ELO: **{elo}**\n"
                    f"Hrac: [{f.get('nickname')}]({f.get('profile_url', '#')})\n"
                    f"Win Rate: `{f.get('win_rate', 'N/A')}%` | K/D: `{f.get('avg_kd', 'N/A')}`\n"
                    f"HS%: `{f.get('avg_hs_pct', 'N/A')}%` | Zapasy: `{f.get('total_matches', 'N/A')}`\n"
                    f"Nejdelsi serie: `{f.get('longest_streak', 'N/A')}` vyhry"
                    + map_lines
                ),
                False
            ))

        if not fields:
            fields.append(("Zadna externa data", (
                "Nepodařilo se načíst data.\n"
                "Možné příčiny:\n"
                "Profil je soukromý\n"
                "Hráč nemá FACEIT účet\n"
                "API dočasně nedostupné"
            ), False))

        return fields

    def build_leetify_match_fields(self, matches: List[Dict]) -> str:
        """Formátuje Leetify match historii jako string."""
        if not matches:
            return "Zadne zapasy k zobrazeni."
        lines = []
        for m in matches:
            outcome = m.get("outcome", "?")
            o_emoji = "W" if "win" in str(outcome).lower() else ("L" if "loss" in str(outcome).lower() else "?")
            map_short = str(m.get("map_name", "?")).replace("de_", "").upper()
            lines.append(
                f"**{o_emoji}** {map_short} — "
                f"{m.get('kills','?')}/{m.get('deaths','?')}/{m.get('assists','?')} "
                f"Rating: `{m.get('rating','?')}` "
                f"KAST: `{m.get('kast','?')}%` "
                f"Preaim: `{m.get('preaim','?')}`"
            )
        return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────

def _r(val) -> str:
    """Zaokrouhlí float na 1 des. místo nebo vrátí 'N/A'."""
    if val is None:
        return "N/A"
    try:
        return str(round(float(val), 1))
    except Exception:
        return str(val)

def _pct(val) -> str:
    """Převede 0-1 float na procenta, nebo vrátí 'N/A'."""
    if val is None:
        return "N/A"
    try:
        f = float(val)
        return str(round(f * 100 if f <= 1.0 else f, 1))
    except Exception:
        return str(val)

def _int(val) -> int:
    try:
        return int(val)
    except Exception:
        return 0

def _faceit_emoji(level) -> str:
    try:
        lvl = int(level)
    except (TypeError, ValueError):
        return "?"
    return {1:"⬜",2:"⬜",3:"🟡",4:"🟡",5:"🟠",6:"🟠",7:"🔴",8:"🔴",9:"🔴",10:"💜"}.get(lvl,"❓")
