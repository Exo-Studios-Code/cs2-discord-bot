"""
Progress cog - Sledování pokroku, týdenní DM reporty, grafy.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
import os
import json
import asyncio
from datetime import datetime, timedelta
from utils.cs2_api import SteamAPI, calculate_rating, get_rank_from_rating
from utils.ai_analyzer import AIAnalyzer
from utils.embeds import build_progress_embed, COLORS

log = logging.getLogger("CS2Bot.Progress")


class ProgressCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.steam_api = SteamAPI(os.getenv("STEAM_API_KEY", ""))
        self.ai = AIAnalyzer()
        self.weekly_report.start()

    def cog_unload(self):
        self.weekly_report.cancel()

    # ─── TÝDENNÍ REPORT ─────────────────────────────────────────

    @tasks.loop(hours=168)  # každých 7 dní
    async def weekly_report(self):
        """Pošle týdenní progress report do DM každému uživateli."""
        users = await self.bot.db.get_all_users()
        log.info(f"📊 Odesílám týdenní reporty pro {len(users)} uživatelů...")

        for user in users:
            if not user["dm_notifications"]:
                continue
            try:
                await self._send_weekly_report(user)
                await asyncio.sleep(3)
            except Exception as e:
                log.error(f"Chyba při odesílání týdenního reportu: {e}")

    @weekly_report.before_loop
    async def before_weekly(self):
        await self.bot.wait_until_ready()
        # Spusť v neděli večer
        now = datetime.now()
        days_until_sunday = (6 - now.weekday()) % 7
        target = now.replace(hour=20, minute=0, second=0) + timedelta(days=days_until_sunday)
        wait_secs = (target - now).total_seconds()
        if wait_secs < 0:
            wait_secs += 7 * 86400
        log.info(f"📅 Týdenní report za {wait_secs/3600:.1f}h")
        await asyncio.sleep(max(0, wait_secs))

    async def _send_weekly_report(self, user: dict):
        """Sestaví a pošle kompletní týdenní report do DM."""
        discord_id = user["discord_id"]
        discord_user = await self.bot.fetch_user(int(discord_id))
        if not discord_user:
            return

        # Aktuální statistiky
        cs2_stats = await self.steam_api.get_cs2_stats(user["steam_id"])
        player = await self.steam_api.get_player_summary(user["steam_id"])
        player_name = player.get("personaname", "Hráč") if player else "Hráč"

        if cs2_stats:
            await self.bot.db.save_snapshot(discord_id, cs2_stats)

        snapshots = await self.bot.db.get_snapshots(discord_id, limit=5)
        matches = await self.bot.db.get_match_history(discord_id, limit=20)

        # Zápasy z tohoto týdne
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        weekly_matches = [m for m in matches if str(m["match_date"]) > week_ago]

        # Sestav report
        embeds = await self._build_weekly_embeds(
            cs2_stats, player, player_name, snapshots, weekly_matches, discord_id
        )

        try:
            for embed in embeds:
                await discord_user.send(embed=embed)
                await asyncio.sleep(0.5)
            log.info(f"✅ Týdenní report odeslán: {discord_id}")
        except discord.Forbidden:
            log.warning(f"Nemohu poslat DM: {discord_id}")

    async def _build_weekly_embeds(self, cs2_stats, player, player_name,
                                    snapshots, weekly_matches, discord_id) -> list:
        embeds = []
        rating = calculate_rating(cs2_stats) if cs2_stats else 0
        rank_name, rank_emoji = get_rank_from_rating(rating)

        # 1. Hlavní report embed
        main_embed = discord.Embed(
            title=f"📊 Týdenní CS2 Report — {player_name}",
            description=(
                f"**{rank_emoji} {rank_name}** | Rating: `{rating}`\n\n"
                f"Zápasů tento týden: **{len(weekly_matches)}**"
            ),
            color=COLORS["info"],
            timestamp=datetime.utcnow()
        )

        if player and player.get("avatarfull"):
            main_embed.set_thumbnail(url=player["avatarfull"])

        if cs2_stats:
            main_embed.add_field(
                name="📈 Aktuální statistiky",
                value=(
                    f"K/D: **{cs2_stats.get('kd_ratio')}**\n"
                    f"Win Rate: **{cs2_stats.get('win_rate')}%**\n"
                    f"HS Rate: **{cs2_stats.get('hs_rate')}%**\n"
                    f"ADR: **{cs2_stats.get('adr')}**"
                ),
                inline=True
            )

        if weekly_matches:
            wins = sum(1 for m in weekly_matches if m["result"] == "WIN")
            losses = len(weekly_matches) - wins
            avg_kd = round(
                sum(float(m["kd_ratio"]) for m in weekly_matches) / len(weekly_matches), 2
            )
            main_embed.add_field(
                name="🎮 Tento týden",
                value=(
                    f"✅ Výhry: **{wins}**\n"
                    f"❌ Prohry: **{losses}**\n"
                    f"Průměr K/D: **{avg_kd}**"
                ),
                inline=True
            )

        main_embed.set_footer(text="CS2 Bot • Týdenní report")
        embeds.append(main_embed)

        # 2. Pokrok embed
        if len(snapshots) >= 2:
            progress_embed = build_progress_embed([dict(s) for s in snapshots])
            progress_embed.title = "📈 Tvůj pokrok za posledních 30 dní"
            embeds.append(progress_embed)

        # 3. AI Progress analýza
        if len(snapshots) >= 2 and cs2_stats:
            ai_embed = discord.Embed(
                title="🤖 AI Hodnocení pokroku",
                color=COLORS["ai"]
            )
            analysis = await self.ai.analyze_progress(
                [dict(s) for s in snapshots], cs2_stats
            )
            ai_embed.description = analysis[:4096]
            ai_embed.set_footer(text="Google Gemini AI • CS2 Bot")
            embeds.append(ai_embed)

        # 4. Historie zápasů tohoto týdne
        if weekly_matches:
            history_lines = []
            for m in weekly_matches[:8]:
                r_emoji = "✅" if m["result"] == "WIN" else "❌"
                kd = round(float(m["kills"]) / float(m["deaths"]), 2) if m["deaths"] > 0 else m["kills"]
                map_short = str(m["map_name"]).replace("de_", "").replace("cs_", "")
                history_lines.append(
                    f"{r_emoji} **{map_short.upper()}** — {m['kills']}/{m['deaths']}/{m['assists']} (KD: {kd})"
                )

            history_embed = discord.Embed(
                title="📜 Zápasy tento týden",
                description="\n".join(history_lines),
                color=COLORS["info"]
            )
            embeds.append(history_embed)

        return embeds

    # ─── SLASH PŘÍKAZY ───────────────────────────────────────────

    @app_commands.command(name="progress", description="Zobraz svůj pokrok a vývoj statistik v čase")
    async def progress(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("❌ Nejsi zaregistrován. Použij `/setup`.")
            return

        # Ulož aktuální snapshot
        cs2_stats = await self.steam_api.get_cs2_stats(user["steam_id"])
        if cs2_stats:
            await self.bot.db.save_snapshot(str(interaction.user.id), cs2_stats)

        snapshots = await self.bot.db.get_snapshots(str(interaction.user.id), limit=10)

        if not snapshots:
            await interaction.followup.send(
                "❌ Žádná historická data.\nPočkej den a použij `/stats` pro první snapshot."
            )
            return

        embed = build_progress_embed([dict(s) for s in snapshots])
        view = ProgressView(
            [dict(s) for s in snapshots], cs2_stats or {}, self.ai,
            str(interaction.user.id), self.bot
        )
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="snapshot", description="Ulož aktuální statistiky jako referenční bod")
    async def snapshot(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("❌ Nejsi zaregistrován. Použij `/setup`.", ephemeral=True)
            return

        cs2_stats = await self.steam_api.get_cs2_stats(user["steam_id"])
        if not cs2_stats:
            await interaction.followup.send("❌ Nepodařilo se načíst statistiky.", ephemeral=True)
            return

        await self.bot.db.save_snapshot(str(interaction.user.id), cs2_stats)

        embed = discord.Embed(
            title="✅ Snapshot uložen!",
            description=(
                f"K/D: `{cs2_stats.get('kd_ratio')}`\n"
                f"Win Rate: `{cs2_stats.get('win_rate')}%`\n"
                f"HS Rate: `{cs2_stats.get('hs_rate')}%`\n"
                f"Datum: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`"
            ),
            color=COLORS["win"]
        )
        embed.set_footer(text="Použij /progress pro zobrazení vývoje")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="weeklyreport", description="Pošli si týdenní report do DM okamžitě")
    async def weeklyreport(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("❌ Nejsi zaregistrován. Použij `/setup`.", ephemeral=True)
            return

        await interaction.followup.send("📬 Generuji a odesílám report do DM...", ephemeral=True)
        await self._send_weekly_report(dict(user))
        await interaction.followup.send("✅ Report odeslán do DM!", ephemeral=True)

    @app_commands.command(name="goals", description="Nastav si herní cíle a sleduj jejich plnění")
    @app_commands.describe(
        kd_goal="Cílové K/D ratio (např. 1.5)",
        winrate_goal="Cílový win rate v % (např. 55)",
        hs_goal="Cílová headshot rate v % (např. 40)"
    )
    async def goals(self, interaction: discord.Interaction,
                    kd_goal: float = None,
                    winrate_goal: float = None,
                    hs_goal: float = None):
        await interaction.response.defer(ephemeral=True)

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("❌ Nejsi zaregistrován.", ephemeral=True)
            return

        cs2_stats = await self.steam_api.get_cs2_stats(user["steam_id"])

        embed = discord.Embed(
            title="🎯 Tvoje herní cíle",
            color=COLORS["info"]
        )

        def goal_field(name, current, goal, suffix=""):
            if goal is None:
                return f"❓ Nenastaveno (aktuální: `{current}{suffix}`)"
            pct = min(100, round(float(current) / float(goal) * 100))
            bar_filled = int(pct / 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            status = "✅" if float(current) >= float(goal) else "🔄"
            return f"{status} Cíl: `{goal}{suffix}` | Nyní: `{current}{suffix}`\n`[{bar}]` {pct}%"

        if cs2_stats:
            embed.add_field(
                name="📊 K/D Ratio",
                value=goal_field("K/D", cs2_stats.get("kd_ratio", 0), kd_goal),
                inline=False
            )
            embed.add_field(
                name="🏆 Win Rate",
                value=goal_field("Win Rate", cs2_stats.get("win_rate", 0), winrate_goal, "%"),
                inline=False
            )
            embed.add_field(
                name="🎯 Headshot Rate",
                value=goal_field("HS Rate", cs2_stats.get("hs_rate", 0), hs_goal, "%"),
                inline=False
            )

        embed.set_footer(text="Cíle se resetují po každém volání příkazu")
        await interaction.followup.send(embed=embed, ephemeral=True)


class ProgressView(discord.ui.View):
    """Interaktivní view pro progress."""

    def __init__(self, snapshots: list, current_stats: dict,
                 ai: AIAnalyzer, discord_id: str, bot):
        super().__init__(timeout=120)
        self.snapshots = snapshots
        self.current_stats = current_stats
        self.ai = ai
        self.discord_id = discord_id
        self.bot = bot

    @discord.ui.button(label="📈 Graf pokroku", style=discord.ButtonStyle.primary)
    async def show_graph(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = self._build_text_graph()
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🤖 AI Hodnocení", style=discord.ButtonStyle.secondary)
    async def ai_eval(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        loading = discord.Embed(title="🤖 Analyzuji pokrok...", color=COLORS["ai"])
        await interaction.edit_original_response(embed=loading, view=self)

        analysis = await self.ai.analyze_progress(self.snapshots, self.current_stats)
        embed = discord.Embed(
            title="🤖 AI Hodnocení pokroku",
            description=analysis[:4096],
            color=COLORS["ai"]
        )
        embed.set_footer(text="Google Gemini AI • CS2 Bot")
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="📊 Přehled", style=discord.ButtonStyle.secondary)
    async def overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = build_progress_embed(self.snapshots)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="📬 Pošli do DM", style=discord.ButtonStyle.success)
    async def send_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            embed = build_progress_embed(self.snapshots)
            await interaction.user.send(embed=embed)
            await interaction.followup.send("✅ Odesláno do DM!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Nemohu poslat DM.", ephemeral=True)

    def _build_text_graph(self) -> discord.Embed:
        """ASCII-style textový graf K/D v čase."""
        embed = discord.Embed(
            title="📈 Vývoj K/D v čase",
            color=COLORS["win"]
        )

        if len(self.snapshots) < 2:
            embed.description = "Nedostatek dat pro graf."
            return embed

        kd_values = [float(s["kd_ratio"]) for s in reversed(self.snapshots)]
        dates = [str(s["snapshot_date"])[:10] for s in reversed(self.snapshots)]

        max_kd = max(kd_values)
        min_kd = min(kd_values)
        height = 8
        width = len(kd_values)

        lines = []
        for row in range(height, -1, -1):
            line = ""
            threshold = min_kd + (max_kd - min_kd) * row / height
            for val in kd_values:
                if val >= threshold:
                    line += "█ "
                else:
                    line += "░ "
            y_label = f"{threshold:.2f}"
            lines.append(f"`{y_label:5}` |{line}")

        lines.append(f"`{'':5}` +" + "──" * width)

        trend = "📈 Rostoucí" if kd_values[-1] > kd_values[0] else ("📉 Klesající" if kd_values[-1] < kd_values[0] else "➡️ Stabilní")

        embed.description = (
            f"**Trend: {trend}**\n"
            f"Min: `{min_kd}` | Max: `{max_kd}` | Aktuální: `{kd_values[-1]}`\n\n"
            + "\n".join(lines[:12])
        )
        embed.set_footer(text=f"Od {dates[0]} do {dates[-1]}")
        return embed


async def setup(bot):
    await bot.add_cog(ProgressCog(bot))
