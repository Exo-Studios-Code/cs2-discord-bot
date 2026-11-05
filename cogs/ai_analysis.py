"""
AI Analysis cog - Kompletní AI analýzy pomocí Google Gemini.
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from utils.cs2_api import SteamAPI, calculate_rating, get_rank_from_rating
from utils.ai_analyzer import AIAnalyzer
from utils.embeds import COLORS

log = logging.getLogger("CS2Bot.AI")


class AIAnalysisCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.steam_api = SteamAPI(os.getenv("STEAM_API_KEY", ""))
        self.ai = AIAnalyzer()

    @app_commands.command(name="analyze", description="Kompletní AI analýza tvých statistik pomocí Google Gemini")
    async def analyze(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("❌ Nejsi zaregistrován. Použij `/setup`.")
            return

        # Loading embed
        loading = discord.Embed(
            title="🤖 AI Analýza v průběhu...",
            description=(
                "⏳ Načítám tvoje statistiky...\n"
                "🧠 Analyzuji pomocí Google Gemini...\n"
                "📊 Připravuji výsledky..."
            ),
            color=COLORS["ai"]
        )
        msg = await interaction.followup.send(embed=loading)

        # Načti data
        player = await self.steam_api.get_player_summary(user["steam_id"])
        cs2_stats = await self.steam_api.get_cs2_stats(user["steam_id"])

        if not cs2_stats:
            await msg.edit(embed=discord.Embed(
                title="❌ Chyba",
                description="Nepodařilo se načíst statistiky. Zkontroluj nastavení soukromí Steam profilu.",
                color=COLORS["loss"]
            ))
            return

        player_name = player.get("personaname", "Hráč") if player else "Hráč"
        analysis = await self.ai.analyze_overall_stats(cs2_stats, player_name)

        # Rozdel dlouhou analýzu do více embedů
        embeds = self._split_analysis_to_embeds(analysis, player_name, player)

        await msg.edit(embed=embeds[0], view=AIAnalysisView(embeds, player, cs2_stats, self.ai))

    @app_commands.command(name="improve", description="AI doporučení pro zlepšení na konkrétní oblast")
    @app_commands.describe(area="Oblast pro zlepšení")
    @app_commands.choices(area=[
        app_commands.Choice(name="🎯 Aim & Přesnost", value="aim"),
        app_commands.Choice(name="🗺️ Map Awareness", value="maps"),
        app_commands.Choice(name="💰 Economy & Nákupy", value="economy"),
        app_commands.Choice(name="🤝 Týmová hra", value="teamplay"),
        app_commands.Choice(name="🧠 Mentalita & Tilt", value="mental"),
        app_commands.Choice(name="📍 Positioning", value="positioning"),
        app_commands.Choice(name="🔫 Utility (granáty)", value="utility"),
    ])
    async def improve(self, interaction: discord.Interaction, area: str):
        await interaction.response.defer()

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("❌ Nejsi zaregistrován. Použij `/setup`.")
            return

        cs2_stats = await self.steam_api.get_cs2_stats(user["steam_id"])
        player = await self.steam_api.get_player_summary(user["steam_id"])
        player_name = player.get("personaname", "Hráč") if player else "Hráč"

        loading = discord.Embed(
            title=f"🤖 Generuji rady pro oblast: {area}...",
            color=COLORS["ai"]
        )
        msg = await interaction.followup.send(embed=loading)

        area_prompts = {
            "aim": "aim, crosshair placement, recoil control a přesnost střelby",
            "maps": "map awareness, callouts, rotace a čtení hry",
            "economy": "ekonomiku, správné nakupování, eco rounds a force buy",
            "teamplay": "týmovou komunikaci, supportování spoluhráčů a trade frags",
            "mental": "mentální stabilitu, zvládání tiltu, comebacky a focus",
            "positioning": "positioning, angles, peak timing a use of cover",
            "utility": "granáty, smoke, flash, molotov a jejich efektivní použití"
        }

        area_text = area_prompts.get(area, area)

        if self.ai.available:
            stats_summary = ""
            if cs2_stats:
                stats_summary = f"""
Statistiky hráče:
- K/D: {cs2_stats.get('kd_ratio')}
- Win Rate: {cs2_stats.get('win_rate')}%
- HS Rate: {cs2_stats.get('hs_rate')}%
- ADR: {cs2_stats.get('adr')}
- Oblíbená zbraň: {cs2_stats.get('favorite_weapon')}
"""
            prompt = f"""Jsi profesionální CS2 kouč. Hráč "{player_name}" chce zlepšit: {area_text}.

{stats_summary}

Poskytni detailní, akční rady v češtině:

1. 🔍 **Analýza současného stavu** (co data říkají o této oblasti)
2. 📚 **Základy** (co musí vědět)
3. 🎯 **5 konkrétních cvičení/technik**
4. ⚙️ **Nastavení & konfigurace** (pokud relevantní)
5. 📺 **Jak trénovat** (konkrétní routine)
6. ⚠️ **Nejčastější chyby** k vyhnuti
7. ✅ **30-denní plán** zlepšení

Buď konkrétní, praktický, použij příklady z CS2."""

            try:
                response = self.ai.model.generate_content(prompt)
                analysis = response.text
            except Exception as e:
                analysis = f"❌ AI dočasně nedostupná: {e}\n\n💡 Základní tip: Procvičuj každý den alespoň 30 minut deathmatch."
        else:
            analysis = (
                f"**Tipy pro {area}** (bez AI)\n\n"
                "Nastav `GOOGLE_AI_KEY` v `.env` pro personalizované AI rady!\n\n"
                "💡 Obecná rada: Pravidelný trénink v dedikovaných aim mapách jako `aim_botz` nebo `training_aim_csgo2` ti výrazně pomůže."
            )

        embed = discord.Embed(
            title=f"🎓 Rady pro zlepšení: {area.upper()}",
            description=analysis[:4096],
            color=COLORS["ai"]
        )
        if player and player.get("avatarfull"):
            embed.set_thumbnail(url=player["avatarfull"])
        embed.set_footer(text=f"Personalizováno pro {player_name} • CS2 Bot AI")

        await msg.edit(embed=embed)

    @app_commands.command(name="compare", description="Porovnej se s průměrnými hráči CS2")
    async def compare(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("❌ Nejsi zaregistrován. Použij `/setup`.")
            return

        cs2_stats = await self.steam_api.get_cs2_stats(user["steam_id"])
        if not cs2_stats:
            await interaction.followup.send("❌ Nepodařilo se načíst statistiky.")
            return

        # Průměrné hodnoty CS2 hráčů (přibližné)
        AVERAGES = {
            "kd_ratio": 1.0,
            "win_rate": 50.0,
            "hs_rate": 35.0,
            "accuracy": 22.0,
            "adr": 70.0,
        }

        def compare_val(key, label, suffix=""):
            my_val = cs2_stats.get(key, 0)
            avg_val = AVERAGES[key]
            diff = round(float(my_val) - avg_val, 2)
            if diff > 0:
                emoji = "🟢"
                diff_str = f"+{diff}"
            elif diff < 0:
                emoji = "🔴"
                diff_str = str(diff)
            else:
                emoji = "🟡"
                diff_str = "±0"
            return f"{emoji} **{label}**: `{my_val}{suffix}` (průměr: `{avg_val}{suffix}`, {diff_str})"

        rating = calculate_rating(cs2_stats)
        rank_name, rank_emoji = get_rank_from_rating(rating)

        embed = discord.Embed(
            title="📊 Tvoje statistiky vs. Průměr CS2",
            color=COLORS["info"]
        )
        embed.add_field(
            name="📈 Porovnání",
            value="\n".join([
                compare_val("kd_ratio", "K/D Ratio"),
                compare_val("win_rate", "Win Rate", "%"),
                compare_val("hs_rate", "Headshot Rate", "%"),
                compare_val("accuracy", "Přesnost", "%"),
                compare_val("adr", "ADR"),
            ]),
            inline=False
        )
        embed.add_field(
            name="🏆 Tvůj odhadovaný rank",
            value=f"{rank_emoji} **{rank_name}** (Rating: `{rating}`)",
            inline=False
        )
        embed.set_footer(text="Průměry jsou přibližné hodnoty CS2 komunity")
        await interaction.followup.send(embed=embed)

    def _split_analysis_to_embeds(self, analysis: str, player_name: str, player: dict) -> list:
        """Rozdělí dlouhou AI analýzu do více embedů."""
        embeds = []
        chunks = []
        current = ""

        for line in analysis.split("\n"):
            if len(current) + len(line) + 1 > 3800:
                chunks.append(current)
                current = line
            else:
                current += "\n" + line if current else line

        if current:
            chunks.append(current)

        for i, chunk in enumerate(chunks or [analysis[:4096]]):
            e = discord.Embed(
                title=f"🤖 AI Analýza — {player_name}" + (f" (část {i+1}/{len(chunks)})" if len(chunks) > 1 else ""),
                description=chunk,
                color=COLORS["ai"]
            )
            if i == 0 and player and player.get("avatarfull"):
                e.set_thumbnail(url=player["avatarfull"])
            e.set_footer(text="Google Gemini AI • CS2 Bot")
            embeds.append(e)

        return embeds if embeds else [discord.Embed(title="❌ Analýza prázdná", color=COLORS["warning"])]


class AIAnalysisView(discord.ui.View):
    """Navigace v AI analýze + akce."""

    def __init__(self, embeds: list, player: dict, stats: dict, ai: AIAnalyzer):
        super().__init__(timeout=300)
        self.embeds = embeds
        self.player = player
        self.stats = stats
        self.ai = ai
        self.page = 0

    @discord.ui.button(label="⬅️ Předchozí", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.page = max(0, self.page - 1)
        await interaction.edit_original_response(embed=self.embeds[self.page], view=self)

    @discord.ui.button(label="➡️ Další", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.page = min(len(self.embeds) - 1, self.page + 1)
        await interaction.edit_original_response(embed=self.embeds[self.page], view=self)

    @discord.ui.button(label="💡 Rychlý tip", style=discord.ButtonStyle.primary)
    async def quick_tip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        tip = await self.ai.quick_tip(self.stats)
        embed = discord.Embed(title="💡 Tip dne", description=tip, color=COLORS["ai"])
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="📬 Pošli do DM", style=discord.ButtonStyle.success)
    async def send_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            for e in self.embeds:
                await interaction.user.send(embed=e)
            await interaction.followup.send("✅ Analýza odeslána do DM!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Nemohu poslat DM. Povol přijímání zpráv od botů.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(AIAnalysisCog(bot))
