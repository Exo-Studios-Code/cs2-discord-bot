"""
Setup cog - Registrace hráče, nastavení tokenů, konfigurace.
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from utils.cs2_api import SteamAPI, validate_steam64, validate_sharecode, steam64_from_steamid3
from utils.ai_analyzer import AIAnalyzer

log = logging.getLogger("CS2Bot.Setup")


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.steam_api = SteamAPI(os.getenv("STEAM_API_KEY", ""))
        self.ai = AIAnalyzer()

    @app_commands.command(name="setup", description="Zaregistruj svůj Steam účet a CS2 tokeny")
    @app_commands.describe(
        steam_id="Tvoje Steam64 ID (17 číslic) nebo SteamID3 [U:1:XXXXXXXX]",
        match_auth_token="Match authentication token z CS2 (Nastavení → Sdílení zápasů)",
        last_sharecode="Poslední sharecode zápasu (CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX)"
    )
    async def setup(self, interaction: discord.Interaction,
                    steam_id: str,
                    match_auth_token: str,
                    last_sharecode: str):
        await interaction.response.defer(ephemeral=True)

        # Konvertuj SteamID3 pokud potřeba
        if steam_id.startswith("[U:") or steam_id.startswith("U:"):
            converted = steam64_from_steamid3(steam_id)
            if not converted:
                await interaction.followup.send(
                    "❌ Neplatný SteamID3 formát. Použij `[U:1:XXXXXXXX]`.", ephemeral=True
                )
                return
            steam_id = converted

        # Validace Steam64
        if not validate_steam64(steam_id):
            await interaction.followup.send(
                "❌ Neplatné Steam64 ID. Musí být 17číselné číslo začínající `7656119...`\n"
                "💡 Svůj Steam64 ID najdeš na: https://steamid.io",
                ephemeral=True
            )
            return

        # Validace sharecode
        if not validate_sharecode(last_sharecode):
            await interaction.followup.send(
                "❌ Neplatný sharecode. Formát: `CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`\n"
                "💡 V CS2: Nastavení → Sdílení zápasů → Zkopírovat kód",
                ephemeral=True
            )
            return

        # Ověř Steam profil
        player = await self.steam_api.get_player_summary(steam_id)
        if not player:
            await interaction.followup.send(
                "❌ Steam profil nenalezen nebo je soukromý.\n"
                "💡 Ujisti se, že máš **veřejný profil** na Steamu.",
                ephemeral=True
            )
            return

        # Ulož do databáze
        success = await self.bot.db.register_user(
            discord_id=str(interaction.user.id),
            steam_id=steam_id,
            match_auth_token=match_auth_token,
            sharecode=last_sharecode
        )

        if not success:
            await interaction.followup.send("❌ Chyba při ukládání. Zkus to znovu.", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Registrace úspěšná!",
            description=f"Ahoj **{player.get('personaname')}**! Tvůj účet byl propojen.",
            color=0x00FF7F
        )
        embed.set_thumbnail(url=player.get("avatarfull"))
        embed.add_field(name="🆔 Steam ID", value=f"`{steam_id}`", inline=True)
        embed.add_field(name="🔑 Auth Token", value="`*****` (uložen)", inline=True)
        embed.add_field(name="🎮 Poslední kód", value=f"`{last_sharecode[:15]}...`", inline=False)
        embed.add_field(
            name="📋 Dostupné příkazy",
            value=(
                "`/stats` - Tvoje statistiky\n"
                "`/match` - Analýza posledního zápasu\n"
                "`/history` - Historie zápasů\n"
                "`/progress` - Tvůj pokrok\n"
                "`/analyze` - AI analýza\n"
                "`/notifications` - Zapnout/vypnout DM notifikace"
            ),
            inline=False
        )
        embed.set_footer(text="Bot bude automaticky sledovat nové zápasy každých 15 minut")

        await interaction.followup.send(embed=embed, ephemeral=True)
        log.info(f"Nový uživatel zaregistrován: {interaction.user} → Steam {steam_id}")

    @app_commands.command(name="notifications", description="Zapnout/vypnout DM notifikace po zápasech")
    async def notifications(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send(
                "❌ Nejsi zaregistrován. Použij `/setup`.", ephemeral=True
            )
            return

        new_state = await self.bot.db.toggle_notifications(str(interaction.user.id))

        embed = discord.Embed(
            title="🔔 Notifikace",
            description=f"DM notifikace jsou nyní: **{'✅ ZAPNUTY' if new_state else '❌ VYPNUTY'}**",
            color=0x00FF7F if new_state else 0xFF4444
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="unregister", description="Odstraň svůj účet z bota")
    async def unregister(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Confirm view
        view = ConfirmView()
        await interaction.followup.send(
            "⚠️ **Opravdu chceš smazat všechna svá data?**\nTato akce je nevratná.",
            view=view,
            ephemeral=True
        )
        await view.wait()

        if view.confirmed:
            async with self.bot.db.db.execute(
                "DELETE FROM users WHERE discord_id = ?", (str(interaction.user.id),)
            ):
                pass
            await self.bot.db.db.execute(
                "DELETE FROM match_history WHERE discord_id = ?", (str(interaction.user.id),)
            )
            await self.bot.db.db.execute(
                "DELETE FROM player_snapshots WHERE discord_id = ?", (str(interaction.user.id),)
            )
            await self.bot.db.db.commit()
            await interaction.followup.send("✅ Tvůj účet byl odstraněn.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Zrušeno.", ephemeral=True)

    @app_commands.command(name="profile", description="Zobraz svůj propojený Steam profil")
    async def profile(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("❌ Nejsi zaregistrován. Použij `/setup`.", ephemeral=True)
            return

        player = await self.steam_api.get_player_summary(user["steam_id"])

        embed = discord.Embed(
            title="👤 Tvůj profil",
            color=0x5865F2
        )
        if player:
            embed.description = f"**[{player.get('personaname')}](https://steamcommunity.com/profiles/{user['steam_id']})**"
            embed.set_thumbnail(url=player.get("avatarfull"))

        embed.add_field(name="🆔 Steam ID", value=f"`{user['steam_id']}`", inline=True)
        embed.add_field(name="📅 Registrován", value=str(user["registered_at"])[:10], inline=True)
        embed.add_field(
            name="🔔 Notifikace",
            value="✅ Zapnuty" if user["dm_notifications"] else "❌ Vypnuty",
            inline=True
        )
        embed.add_field(
            name="📊 Posledně zkontrolováno",
            value=str(user["last_check"] or "Nikdy")[:16],
            inline=True
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.confirmed = False

    @discord.ui.button(label="✅ Ano, smazat", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="❌ Zrušit", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()


async def setup(bot):
    await bot.add_cog(SetupCog(bot))
