"""
Stats cog - Zobrazení kompletních statistik hráče s interaktivními tlačítky.
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from utils.cs2_api import SteamAPI, calculate_rating, get_rank_from_rating
from utils.ai_analyzer import AIAnalyzer
from utils.embeds import (
    build_stats_embed, build_history_embed, build_progress_embed,
    COLORS, MAP_EMOJIS, WEAPON_EMOJIS
)

log = logging.getLogger("CS2Bot.Stats")


class StatsView(discord.ui.View):
    """Interaktivní View s tlačítky pro přepínání statistik."""

    def __init__(self, cog, discord_id: str, steam_id: str,
                 stats: dict, player: dict, matches: list, snapshots: list):
        super().__init__(timeout=120)
        self.cog = cog
        self.discord_id = discord_id
        self.steam_id = steam_id
        self.stats = stats
        self.player = player
        self.matches = matches
        self.snapshots = snapshots
        self.current_page = "overview"

    @discord.ui.button(label="📊 Přehled", style=discord.ButtonStyle.primary, custom_id="overview")
    async def overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        rating = calculate_rating(self.stats)
        rank_info = get_rank_from_rating(rating)
        embed = build_stats_embed(self.stats, self.player, rating, rank_info)
        self._highlight_button(button)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🗺️ Mapy", style=discord.ButtonStyle.secondary, custom_id="maps")
    async def maps(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = self._build_maps_embed()
        self._highlight_button(button)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🔫 Zbraně", style=discord.ButtonStyle.secondary, custom_id="weapons")
    async def weapons(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = self._build_weapons_embed()
        self._highlight_button(button)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="📜 Historie", style=discord.ButtonStyle.secondary, custom_id="history")
    async def history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = build_history_embed(
            [dict(m) for m in self.matches],
            self.player.get("personaname", "Hráč")
        )
        self._highlight_button(button)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="📈 Pokrok", style=discord.ButtonStyle.secondary, custom_id="progress")
    async def progress(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = build_progress_embed([dict(s) for s in self.snapshots])
        self._highlight_button(button)
        await interaction.edit_original_response(embed=embed, view=self)

    def _highlight_button(self, active_button: discord.ui.Button):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.style = (
                    discord.ButtonStyle.primary
                    if item == active_button
                    else discord.ButtonStyle.secondary
                )

    def _build_maps_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🗺️ Statistiky map — {self.player.get('personaname', 'Hráč')}",
            color=COLORS["stats"]
        )
        map_wins = self.stats.get("map_wins", {})
        if not map_wins:
            embed.description = "❌ Žádná data o mapách."
            return embed

        sorted_maps = sorted(map_wins.items(), key=lambda x: x[1], reverse=True)
        lines = []
        for i, (map_name, wins) in enumerate(sorted_maps[:10], 1):
            full_name = f"de_{map_name}" if not map_name.startswith("de_") else map_name
            emoji = MAP_EMOJIS.get(full_name, "🗺️")
            medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"{i}."))
            lines.append(f"{medal} {emoji} **{map_name.upper()}** — {wins:,} výher")

        embed.description = "\n".join(lines)
        embed.set_footer(text="Seřazeno podle počtu výher")
        return embed

    def _build_weapons_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🔫 Statistiky zbraní — {self.player.get('personaname', 'Hráč')}",
            color=COLORS["cs2"]
        )
        weapon_kills = self.stats.get("weapon_kills", {})
        if not weapon_kills:
            embed.description = "❌ Žádná data o zbraních."
            return embed

        sorted_weapons = sorted(weapon_kills.items(), key=lambda x: x[1], reverse=True)
        total = sum(weapon_kills.values())

        lines = []
        for i, (weapon, kills) in enumerate(sorted_weapons[:12], 1):
            emoji = WEAPON_EMOJIS.get(weapon, "🔫")
            pct = round(kills / total * 100, 1) if total > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else f"`{i}.`"))
            lines.append(f"{medal} {emoji} **{weapon.upper()}** — {kills:,} killů ({pct}%)\n`{bar}`")

        embed.description = "\n".join(lines)
        embed.set_footer(text="Z celkových kill statistik")
        return embed


class StatsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.steam_api = SteamAPI(os.getenv("STEAM_API_KEY", ""))
        self.ai = AIAnalyzer()

    async def _get_registered_user(self, interaction: discord.Interaction):
        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send(
                "❌ Nejsi zaregistrován!\n💡 Použij `/setup` pro propojení Steam účtu.",
                ephemeral=True
            )
            return None
        return user

    @app_commands.command(name="stats", description="Zobraz své kompletní CS2 statistiky s interaktivními tlačítky")
    async def stats(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user = await self._get_registered_user(interaction)
        if not user:
            return

        # Načti data paralelně
        import asyncio
        player_task = self.steam_api.get_player_summary(user["steam_id"])
        cs2_task    = self.steam_api.get_cs2_stats(user["steam_id"])
        matches_task = self.bot.db.get_match_history(str(interaction.user.id), limit=20)
        snapshots_task = self.bot.db.get_snapshots(str(interaction.user.id))

        player, cs2_stats, matches, snapshots = await asyncio.gather(
            player_task, cs2_task, matches_task, snapshots_task
        )

        if not cs2_stats:
            await interaction.followup.send(
                "❌ Nepodařilo se načíst CS2 statistiky.\n"
                "💡 Ujisti se, že máš **veřejný profil** a **veřejné herní detaily** na Steamu.",
                ephemeral=False
            )
            return

        # Ulož snapshot pro sledování pokroku
        await self.bot.db.save_snapshot(str(interaction.user.id), cs2_stats)

        rating = calculate_rating(cs2_stats)
        rank_info = get_rank_from_rating(rating)
        embed = build_stats_embed(cs2_stats, player or {}, rating, rank_info)

        view = StatsView(
            cog=self,
            discord_id=str(interaction.user.id),
            steam_id=user["steam_id"],
            stats=cs2_stats,
            player=player or {},
            matches=matches,
            snapshots=snapshots
        )

        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="quickstats", description="Rychlý přehled klíčových statistik")
    async def quickstats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = await self._get_registered_user(interaction)
        if not user:
            return

        cs2_stats = await self.steam_api.get_cs2_stats(user["steam_id"])
        player = await self.steam_api.get_player_summary(user["steam_id"])

        if not cs2_stats:
            await interaction.followup.send("❌ Nepodařilo se načíst statistiky.", ephemeral=True)
            return

        rating = calculate_rating(cs2_stats)
        rank_name, rank_emoji = get_rank_from_rating(rating)
        tip = await self.ai.quick_tip(cs2_stats)

        embed = discord.Embed(
            title=f"⚡ Rychlý přehled — {player.get('personaname', 'Hráč') if player else 'Hráč'}",
            color=COLORS["info"]
        )
        embed.add_field(name="📊 K/D", value=f"`{cs2_stats.get('kd_ratio')}`", inline=True)
        embed.add_field(name="🏆 Win Rate", value=f"`{cs2_stats.get('win_rate')}%`", inline=True)
        embed.add_field(name="🎯 HS Rate", value=f"`{cs2_stats.get('hs_rate')}%`", inline=True)
        embed.add_field(name="💢 ADR", value=f"`{cs2_stats.get('adr')}`", inline=True)
        embed.add_field(name="🎮 Zápasy", value=f"`{cs2_stats.get('total_matches'):,}`", inline=True)
        embed.add_field(name="⭐ Rating", value=f"`{rating}` {rank_emoji}", inline=True)
        embed.add_field(name=tip[:50], value=tip[50:] if len(tip) > 50 else "\u200b", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(StatsCog(bot))
