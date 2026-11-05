"""
Embed builder - Vytváří bohaté Discord embedy pro CS2 data.
"""

import discord
from typing import Dict, Any, List, Optional
from datetime import datetime


COLORS = {
    "win":     0x00FF7F,   # zelená
    "loss":    0xFF4444,   # červená
    "draw":    0xFFAA00,   # oranžová
    "info":    0x5865F2,   # Discord blurple
    "ai":      0x8A2BE2,   # fialová
    "stats":   0x00BFFF,   # modrá
    "warning": 0xFFD700,   # žlutá
    "cs2":     0xFF6B35,   # CS2 oranžová
}

MAP_EMOJIS = {
    "de_dust2":    "🏜️",
    "de_mirage":   "🌆",
    "de_inferno":  "🔥",
    "de_nuke":     "☢️",
    "de_overpass": "🌉",
    "de_ancient":  "🏛️",
    "de_vertigo":  "🏗️",
    "de_anubis":   "🐍",
    "de_cache":    "📦",
    "de_train":    "🚂",
}

WEAPON_EMOJIS = {
    "ak47":   "🔴",
    "m4a1":   "🟢",
    "awp":    "🎯",
    "deagle": "🔫",
    "glock":  "⚪",
    "p250":   "🔵",
    "famas":  "🟡",
    "aug":    "🟠",
    "sg556":  "🔶",
}


def build_stats_embed(stats: Dict[str, Any], player: Dict[str, Any],
                       rating: float, rank_info: tuple) -> discord.Embed:
    """Hlavní embed se všemi statistikami."""
    rank_name, rank_emoji = rank_info
    kd = stats.get("kd_ratio", 0)
    color = COLORS["win"] if kd >= 1.0 else COLORS["loss"]

    embed = discord.Embed(
        title=f"🎮 CS2 Statistiky — {player.get('personaname', 'Neznámý hráč')}",
        description=(
            f"**Steam:** [{player.get('personaname')}](https://steamcommunity.com/profiles/{player.get('steamid')})\n"
            f"**Odhadovaný rank:** {rank_emoji} {rank_name}\n"
            f"**Rating:** `{rating}`"
        ),
        color=color,
        timestamp=datetime.utcnow()
    )

    if player.get("avatarfull"):
        embed.set_thumbnail(url=player["avatarfull"])

    # Hlavní statistiky
    embed.add_field(
        name="⚔️ Boj",
        value=(
            f"🔫 Zabití: **{stats.get('total_kills', 0):,}**\n"
            f"💀 Smrtí: **{stats.get('total_deaths', 0):,}**\n"
            f"🤝 Asistence: N/A\n"
            f"📊 K/D: **{kd}**"
        ),
        inline=True
    )

    embed.add_field(
        name="🏆 Výsledky",
        value=(
            f"🎮 Zápasy: **{stats.get('total_matches', 0):,}**\n"
            f"✅ Výhry: **{stats.get('total_wins', 0):,}**\n"
            f"📈 Win Rate: **{stats.get('win_rate', 0)}%**\n"
            f"⭐ MVPs: **{stats.get('total_mvps', 0):,}**"
        ),
        inline=True
    )

    embed.add_field(
        name="🎯 Přesnost",
        value=(
            f"💥 Headshoty: **{stats.get('total_hs', 0):,}**\n"
            f"🎯 HS Rate: **{stats.get('hs_rate', 0)}%**\n"
            f"🔲 Přesnost: **{stats.get('accuracy', 0)}%**\n"
            f"💢 ADR: **{stats.get('adr', 0)}**"
        ),
        inline=True
    )

    # Hodiny a zbraň
    fav_weapon = stats.get("favorite_weapon", "N/A")
    weapon_emoji = WEAPON_EMOJIS.get(fav_weapon, "🔫")
    best_map = stats.get("best_map", "N/A")
    map_emoji = MAP_EMOJIS.get(f"de_{best_map}" if not best_map.startswith("de_") else best_map, "🗺️")

    embed.add_field(
        name="📌 Ostatní",
        value=(
            f"⏱️ Odehráno: **{stats.get('hours_played', 0)}h**\n"
            f"{weapon_emoji} Oblíbená zbraň: **{fav_weapon.upper()}**\n"
            f"{map_emoji} Nejlepší mapa: **{best_map}**"
        ),
        inline=True
    )

    embed.set_footer(text="CS2 Bot • Steam API", icon_url="https://i.imgur.com/AfFp7pu.png")
    return embed


def build_match_embed(match: Dict[str, Any], player_name: str = "Hráč") -> discord.Embed:
    """Embed pro konkrétní zápas."""
    result = match.get("result", "?").upper()
    kills  = match.get("kills", 0)
    deaths = match.get("deaths", 0)
    assists = match.get("assists", 0)
    map_name = match.get("map_name", "Neznámá mapa")

    color = COLORS["win"] if result == "WIN" else (COLORS["loss"] if result == "LOSS" else COLORS["draw"])
    result_emoji = "🏆" if result == "WIN" else ("💀" if result == "LOSS" else "🤝")
    map_emoji = MAP_EMOJIS.get(map_name, "🗺️")

    embed = discord.Embed(
        title=f"{result_emoji} {result} — {map_emoji} {map_name}",
        description=(
            f"**Skóre:** `{match.get('score_ct', 0)} CT — {match.get('score_t', 0)} T`\n"
            f"**Hráč:** {player_name}"
        ),
        color=color,
        timestamp=datetime.utcnow()
    )

    kd = round(kills / deaths, 2) if deaths > 0 else kills
    embed.add_field(
        name="⚔️ Výkon",
        value=(
            f"🔫 K/D/A: **{kills}/{deaths}/{assists}**\n"
            f"📊 K/D Ratio: **{kd}**\n"
            f"💥 Headshoty: **{match.get('hs_kills', 0)}**\n"
            f"⭐ MVPs: **{match.get('mvps', 0)}**"
        ),
        inline=True
    )

    embed.add_field(
        name="📊 Pokročilé",
        value=(
            f"💢 ADR: **{match.get('adr', 'N/A')}**\n"
            f"🏅 Skóre: **{match.get('score', 0)}**\n"
            f"🎯 HS Rate: **{round(match.get('hs_kills', 0) / kills * 100, 1) if kills > 0 else 0}%**"
        ),
        inline=True
    )

    if match.get("sharecode"):
        embed.add_field(
            name="🔗 Match Info",
            value=f"`{match['sharecode']}`",
            inline=False
        )

    embed.set_footer(text="CS2 Bot • Zápas")
    return embed


def build_history_embed(matches: List[Any], player_name: str) -> discord.Embed:
    """Embed se seznamem posledních zápasů."""
    embed = discord.Embed(
        title=f"📜 Historie zápasů — {player_name}",
        color=COLORS["info"],
        timestamp=datetime.utcnow()
    )

    if not matches:
        embed.description = "❌ Žádné zápasy nenalezeny."
        return embed

    # Souhrn
    wins   = sum(1 for m in matches if m["result"] == "WIN")
    losses = sum(1 for m in matches if m["result"] == "LOSS")
    draws  = len(matches) - wins - losses
    avg_kd = round(sum(m["kd_ratio"] for m in matches) / len(matches), 2)

    embed.description = (
        f"**Poslední {len(matches)} zápasů**\n"
        f"✅ {wins}W  ❌ {losses}L  🤝 {draws}D  |  Průměr K/D: **{avg_kd}**"
    )

    # Zápasy jako pole
    match_lines = []
    for m in matches[:10]:
        r_emoji = "✅" if m["result"] == "WIN" else ("❌" if m["result"] == "LOSS" else "🤝")
        map_short = str(m["map_name"]).replace("de_", "").replace("cs_", "")
        kd = round(float(m["kills"]) / float(m["deaths"]), 2) if m["deaths"] > 0 else m["kills"]
        match_lines.append(
            f"{r_emoji} **{map_short.upper()}** — {m['kills']}/{m['deaths']}/{m['assists']} (KD: {kd})"
        )

    embed.add_field(
        name="🎮 Zápasy",
        value="\n".join(match_lines) if match_lines else "Žádné záznamy",
        inline=False
    )

    embed.set_footer(text="CS2 Bot • Historie")
    return embed


def build_progress_embed(snapshots: List[Any]) -> discord.Embed:
    """Embed zobrazující pokrok hráče."""
    embed = discord.Embed(
        title="📈 Tvůj pokrok v CS2",
        color=COLORS["win"],
        timestamp=datetime.utcnow()
    )

    if len(snapshots) < 2:
        embed.description = "⚠️ Potřebuji alespoň 2 záznamy pro zobrazení pokroku.\nPřijď znovu za pár dní!"
        return embed

    newest = snapshots[0]
    oldest = snapshots[-1]

    def arrow(new, old):
        diff = float(new) - float(old)
        if diff > 0:   return f"🔼 +{round(diff, 2)}"
        if diff < 0:   return f"🔽 {round(diff, 2)}"
        return "➡️ 0"

    embed.add_field(
        name=f"📅 Od: {str(oldest['snapshot_date'])[:10]}",
        value=(
            f"K/D: `{oldest['kd_ratio']}`\n"
            f"Win Rate: `{oldest['win_rate']}%`\n"
            f"HS Rate: `{oldest['hs_rate']}%`\n"
            f"Zápasy: `{oldest['total_matches']}`"
        ),
        inline=True
    )

    embed.add_field(
        name=f"📅 Nyní: {str(newest['snapshot_date'])[:10]}",
        value=(
            f"K/D: `{newest['kd_ratio']}`\n"
            f"Win Rate: `{newest['win_rate']}%`\n"
            f"HS Rate: `{newest['hs_rate']}%`\n"
            f"Zápasy: `{newest['total_matches']}`"
        ),
        inline=True
    )

    embed.add_field(
        name="📊 Změna",
        value=(
            f"K/D: {arrow(newest['kd_ratio'], oldest['kd_ratio'])}\n"
            f"Win Rate: {arrow(newest['win_rate'], oldest['win_rate'])}%\n"
            f"HS Rate: {arrow(newest['hs_rate'], oldest['hs_rate'])}%\n"
            f"Nové zápasy: `+{int(newest['total_matches']) - int(oldest['total_matches'])}`"
        ),
        inline=True
    )

    embed.set_footer(text="CS2 Bot • Pokrok")
    return embed


def build_dm_match_notification(match: Dict, ai_summary: str = None) -> discord.Embed:
    """DM notifikace o novém zápasu."""
    result = match.get("result", "?")
    color = COLORS["win"] if result == "WIN" else COLORS["loss"]
    emoji = "🏆" if result == "WIN" else "💀"

    embed = discord.Embed(
        title=f"{emoji} Nový zápas zaznamenán!",
        color=color,
        timestamp=datetime.utcnow()
    )

    embed.add_field(
        name="📊 Výsledek",
        value=(
            f"Mapa: **{match.get('map_name', 'N/A')}**\n"
            f"Výsledek: **{result}**\n"
            f"K/D/A: **{match.get('kills', 0)}/{match.get('deaths', 0)}/{match.get('assists', 0)}**"
        ),
        inline=False
    )

    if ai_summary:
        # Zkrátit AI analýzu na 800 znaků pro DM preview
        preview = ai_summary[:800] + "..." if len(ai_summary) > 800 else ai_summary
        embed.add_field(
            name="🤖 AI Analýza",
            value=preview,
            inline=False
        )

    embed.set_footer(text="Použij /match pro detailní analýzu")
    return embed
