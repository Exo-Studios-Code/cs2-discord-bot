"""
Help cog - Kompletní nápověda a onboarding.
"""

import discord
from discord.ext import commands
from discord import app_commands
from utils.embeds import COLORS


class HelpView(discord.ui.View):
    """Interaktivní help menu."""

    def __init__(self):
        super().__init__(timeout=120)
        self.page = "main"

    @discord.ui.select(
        placeholder="📂 Vyber kategorii...",
        options=[
            discord.SelectOption(label="🏠 Hlavní menu", value="main", emoji="🏠"),
            discord.SelectOption(label="⚙️ Nastavení", value="setup", emoji="⚙️"),
            discord.SelectOption(label="📊 Statistiky", value="stats", emoji="📊"),
            discord.SelectOption(label="🎮 Zápasy", value="matches", emoji="🎮"),
            discord.SelectOption(label="🤖 AI Analýza", value="ai", emoji="🤖"),
            discord.SelectOption(label="📈 Pokrok", value="progress", emoji="📈"),
            discord.SelectOption(label="❓ Jak na to", value="howto", emoji="❓"),
        ]
    )
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        self.page = select.values[0]
        embed = build_help_embed(self.page)
        await interaction.edit_original_response(embed=embed, view=self)


def build_help_embed(page: str) -> discord.Embed:
    pages = {
        "main": (
            "🤖 CS2 Discord Bot — Nápověda",
            COLORS["cs2"],
            (
                "Tvůj osobní CS2 asistent! Sleduje statistiky, analyzuje zápasy a posílá "
                "reporty přímo do DM.\n\n"
                "**Rychlý start:**\n"
                "1️⃣ `/setup` — Propoj Steam účet\n"
                "2️⃣ `/stats` — Zobraz statistiky\n"
                "3️⃣ `/analyze` — AI analýza\n"
                "4️⃣ `/progress` — Sleduj pokrok\n\n"
                "Vyber kategorii z menu níže pro více info."
            )
        ),
        "setup": (
            "⚙️ Nastavení — Příkazy",
            COLORS["info"],
            (
                "**`/setup`** `<steam_id>` `<match_auth_token>` `<last_sharecode>`\n"
                "Zaregistruje tvůj Steam účet. Potřebuješ:\n"
                "• **Steam64 ID** — najdeš na steamid.io\n"
                "• **Match Auth Token** — CS2 → Nastavení → Sdílení zápasů → Token\n"
                "• **Sharecode** — poslední kód zápasu z CS2\n\n"
                "**`/profile`**\n"
                "Zobrazí tvůj propojený profil.\n\n"
                "**`/notifications`**\n"
                "Zapne/vypne DM notifikace po každém zápase.\n\n"
                "**`/unregister`**\n"
                "Smaže všechna tvoje data z bota.\n\n"
                "**`/updatecode`** `<sharecode>`\n"
                "Ručně aktualizuje poslední match sharecode."
            )
        ),
        "stats": (
            "📊 Statistiky — Příkazy",
            COLORS["stats"],
            (
                "**`/stats`**\n"
                "Kompletní statistiky s interaktivními tlačítky:\n"
                "• 📊 Přehled — hlavní stats\n"
                "• 🗺️ Mapy — statistiky per mapa\n"
                "• 🔫 Zbraně — kills per zbraň\n"
                "• 📜 Historie — posledních 20 zápasů\n"
                "• 📈 Pokrok — vývoj v čase\n\n"
                "**`/quickstats`**\n"
                "Rychlý přehled klíčových čísel + AI tip.\n\n"
                "**`/compare`**\n"
                "Porovnání tvých stats s průměrem CS2 komunity."
            )
        ),
        "matches": (
            "🎮 Zápasy — Příkazy",
            COLORS["win"],
            (
                "**`/match`** `[sharecode]`\n"
                "Detail posledního (nebo konkrétního) zápasu.\n"
                "Interaktivní tlačítka:\n"
                "• 📊 Přehled — základní stats\n"
                "• 🤖 AI Analýza — Gemini rozbor\n"
                "• 📋 Sharecode — kód pro replay\n\n"
                "**`/history`** `[count]`\n"
                "Historie posledních zápasů (max 20) s stránkováním.\n\n"
                "**`/forcepoll`**\n"
                "Ručně spustí kontrolu nových zápasů.\n\n"
                "🔄 **Automatické sledování** každých 15 minut.\n"
                "📬 **DM notifikace** po každém novém zápasu (pokud zapnuty)."
            )
        ),
        "ai": (
            "🤖 AI Analýza — Příkazy",
            COLORS["ai"],
            (
                "Powered by **Google Gemini AI**.\n\n"
                "**`/analyze`**\n"
                "Kompletní AI analýza všech tvých statistik.\n"
                "Obsahuje: silné/slabé stránky, doporučení, herní styl, odhadovaný rank.\n\n"
                "**`/improve`** `<oblast>`\n"
                "Personalizované rady pro konkrétní oblast:\n"
                "• 🎯 Aim & Přesnost\n"
                "• 🗺️ Map Awareness\n"
                "• 💰 Economy & Nákupy\n"
                "• 🤝 Týmová hra\n"
                "• 🧠 Mentalita & Tilt\n"
                "• 📍 Positioning\n"
                "• 🔫 Utility (granáty)\n\n"
                "**`/compare`**\n"
                "Porovnání s průměrem + odhadovaný rank."
            )
        ),
        "progress": (
            "📈 Pokrok — Příkazy",
            COLORS["win"],
            (
                "**`/progress`**\n"
                "Interaktivní zobrazení pokroku v čase.\n"
                "• 📈 ASCII graf K/D vývoje\n"
                "• 🤖 AI hodnocení pokroku\n"
                "• 📬 Odeslání do DM\n\n"
                "**`/snapshot`**\n"
                "Ručně uloží aktuální statistiky jako referenční bod.\n"
                "*(Bot ukládá automaticky při každém `/stats`)*\n\n"
                "**`/weeklyreport`**\n"
                "Odešle kompletní týdenní report do DM okamžitě.\n"
                "*(Automaticky každou neděli večer)*\n\n"
                "**`/goals`** `[kd]` `[winrate]` `[hs]`\n"
                "Nastav si cíle a sleduj jejich plnění s progress barem."
            )
        ),
        "howto": (
            "❓ Jak na to — Průvodce",
            COLORS["warning"],
            (
                "**1. Najdi svůj Steam64 ID**\n"
                "Jdi na https://steamid.io a vlož URL svého Steam profilu.\n\n"
                "**2. Získej Match Auth Token**\n"
                "CS2 → Hlavní menu → Nastavení (ozubené kolo) → Sdílení zápasů\n"
                "→ Zkopíruj **Authentication Token** (vypadá jako: `XXXXXXXX`)\n\n"
                "**3. Získej poslední Sharecode**\n"
                "V CS2 → Hlavní menu → Watch → Tvoje zápasy → Sdílet\n"
                "Kód vypadá jako: `CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`\n\n"
                "**4. Nastav veřejný profil na Steamu**\n"
                "Steam → Profil → Upravit profil → Ochrana soukromí\n"
                "→ Herní detaily: **Veřejné**\n\n"
                "**5. Zaregistruj se**\n"
                "Spusť `/setup` s těmito třemi informacemi a jsi hotov! 🎉\n\n"
                "📝 **Tip:** Bot kontroluje nové zápasy každých 15 minut automaticky."
            )
        )
    }

    title, color, description = pages.get(page, pages["main"])
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="CS2 Bot • Nápověda | github.com/tvuj-repo")
    return embed


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Zobraz nápovědu a seznam všech příkazů")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = build_help_embed("main")
        view = HelpView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="ping", description="Zkontroluj odezvu bota")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = COLORS["win"] if latency < 100 else (COLORS["warning"] if latency < 200 else COLORS["loss"])
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{latency}ms**",
            color=color
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="status", description="Stav bota a statistiky")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        all_users = await self.bot.db.get_all_users()

        embed = discord.Embed(
            title="⚙️ Stav CS2 Bota",
            color=COLORS["info"]
        )
        embed.add_field(name="🤖 Bot", value=f"`{self.bot.user}`", inline=True)
        embed.add_field(name="📡 Latency", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="🌐 Servery", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="👥 Registrovaní", value=f"`{len(all_users)}`", inline=True)
        embed.add_field(name="🔄 Polling", value="`každých 15 min`", inline=True)
        embed.add_field(name="📬 Týdenní report", value="`Neděle 20:00`", inline=True)
        embed.set_footer(text="CS2 Bot • Verze 1.0.0")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
