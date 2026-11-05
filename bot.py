"""
CS2 Discord Bot - Hlavní soubor
Sleduje CS2 statistiky, analyzuje zápasy pomocí AI a posílá reporty do DM.
"""

import discord
from discord.ext import commands, tasks
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv
from utils.database import Database

load_dotenv()

# ── Logging: UTF-8 fix pro Windows CP1250 ──────────────────────
def _make_stream_handler() -> logging.StreamHandler:
    """Vrátí StreamHandler s UTF-8, funguje i na Windows."""
    if sys.platform == "win32":
        import io
        stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    else:
        stream = sys.stdout
    h = logging.StreamHandler(stream)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    return h

_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.addHandler(_make_stream_handler())
_root.addHandler(
    logging.FileHandler("bot.log", encoding="utf-8")
)
log = logging.getLogger("CS2Bot")

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

class CS2Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="CS2 zápasy 🔫"
            )
        )
        self.db = Database()

    async def setup_hook(self):
        await self.db.init()
        # Načti všechny cogs
        cogs = ["cogs.setup", "cogs.stats", "cogs.matches", "cogs.ai_analysis", "cogs.progress", "cogs.help"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f"✅ Načten cog: {cog}")
            except Exception as e:
                log.error(f"❌ Chyba při načítání {cog}: {e}")

        # Synchronizuj slash příkazy
        synced = await self.tree.sync()
        log.info(f"✅ Synchronizováno {len(synced)} příkazů")

    async def on_ready(self):
        log.info(f"🤖 Bot {self.user} je online!")
        log.info(f"📊 Připojen k {len(self.guilds)} serverům")

    async def on_application_command_error(self, interaction: discord.Interaction, error: Exception):
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"❌ Chyba: {str(error)}", ephemeral=True
            )
        log.error(f"Příkazová chyba: {error}", exc_info=True)

def main():
    bot = CS2Bot()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        log.critical("❌ DISCORD_TOKEN není nastaven v .env!")
        return
    bot.run(token, log_handler=None)

if __name__ == "__main__":
    main()
