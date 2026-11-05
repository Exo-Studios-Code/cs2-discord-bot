"""
Matches cog - Sledování zápasů, sharecode polling, DM notifikace, externí data.
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
import os
import asyncio
from utils.cs2_api import SteamAPI, validate_sharecode, decode_sharecode
from utils.ai_analyzer import AIAnalyzer
from utils.external_apis import ExternalStatsAggregator
from utils.embeds import (
    build_match_embed, build_history_embed,
    build_dm_match_notification, COLORS
)

log = logging.getLogger("CS2Bot.Matches")


# ════════════════════════════════════════════════════════════════
#  VIEWS
# ════════════════════════════════════════════════════════════════

class MatchDetailView(discord.ui.View):
    """Interaktivní tlačítka pro detail jednoho zápasu."""

    def __init__(self, match_data: dict, player_name: str, ai: AIAnalyzer,
                 steam_id: str = ""):
        super().__init__(timeout=180)
        self.match_data  = match_data
        self.player_name = player_name
        self.ai          = ai
        self.steam_id    = steam_id
        self._ai_cache   = None
        self._ext        = ExternalStatsAggregator()

    def _active(self, target: discord.ui.Button):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.style = (
                    discord.ButtonStyle.primary
                    if item == target
                    else discord.ButtonStyle.secondary
                )

    @discord.ui.button(label="Prehled", style=discord.ButtonStyle.primary, emoji="📊")
    async def overview(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        self._active(btn)
        await interaction.edit_original_response(
            embed=build_match_embed(self.match_data, self.player_name), view=self
        )

    @discord.ui.button(label="AI Analyza", style=discord.ButtonStyle.secondary, emoji="🤖")
    async def ai_btn(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        if not self._ai_cache:
            loading = discord.Embed(
                title="Generuji AI analyzu...",
                description="Analyzuji tvuj vykon pomoci Gemini...",
                color=COLORS["ai"]
            )
            await interaction.edit_original_response(embed=loading, view=self)
            self._ai_cache = await self.ai.analyze_match(self.match_data, self.player_name)

        embed = discord.Embed(
            title=f"AI Analyza — {self.match_data.get('map_name','?')}",
            description=self._ai_cache[:4096],
            color=COLORS["ai"]
        )
        embed.set_footer(text="Google Gemini AI")
        self._active(btn)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Sharecode", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def sharecode_btn(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        sc = self.match_data.get("sharecode", "N/A")
        embed = discord.Embed(title="Match Sharecode", color=COLORS["info"])
        embed.add_field(name="Kod", value=f"```\n{sc}\n```", inline=False)
        embed.set_footer(text="Zkopiruj a vloz do CS2 → Watch → Replay")
        self._active(btn)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Odeslat na csstats", style=discord.ButtonStyle.secondary, emoji="📤")
    async def upload_csstats(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        sc = self.match_data.get("sharecode")
        if not sc or sc == "N/A":
            await interaction.followup.send("Tento zapas nema platny sharecode.", ephemeral=True)
            return

        loading = discord.Embed(title="Odesilam na csstats.gg...", color=COLORS["info"])
        await interaction.edit_original_response(embed=loading, view=self)

        result = await self._ext.upload_sharecode_all(sc)
        color  = COLORS["win"] if result["success"] else COLORS["loss"]
        embed  = discord.Embed(
            title="csstats.gg upload",
            description=result["message"],
            color=color
        )
        if result["success"]:
            embed.add_field(
                name="Odkaz",
                value=f"[Zobrazit na csstats.gg](https://csstats.gg/player/{self.steam_id})",
                inline=False
            )
        await interaction.edit_original_response(embed=embed, view=self)


class HistoryView(discord.ui.View):
    """Stránkované zobrazení match historie."""

    def __init__(self, matches: list, player_name: str):
        super().__init__(timeout=120)
        self.matches     = matches
        self.player_name = player_name
        self.page        = 0
        self.per_page    = 5

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        self.page = max(0, self.page - 1)
        await interaction.edit_original_response(embed=self._embed(), view=self)

    @discord.ui.button(label="Souhrn", style=discord.ButtonStyle.primary, emoji="📊")
    async def summary_btn(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        embed = build_history_embed(self.matches, self.player_name)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        max_p = max(0, (len(self.matches) - 1) // self.per_page)
        self.page = min(max_p, self.page + 1)
        await interaction.edit_original_response(embed=self._embed(), view=self)

    def _embed(self) -> discord.Embed:
        start  = self.page * self.per_page
        items  = self.matches[start : start + self.per_page]
        total  = max(1, (len(self.matches) + self.per_page - 1) // self.per_page)

        embed = discord.Embed(
            title=f"Historie zapasu — {self.player_name} ({self.page+1}/{total})",
            color=COLORS["info"]
        )
        for m in items:
            result    = m.get("result", "?")
            r_label   = "WIN" if result == "WIN" else ("LOSS" if result == "LOSS" else "DRAW")
            kills     = m.get("kills", 0)
            deaths    = m.get("deaths", 1)
            kd        = round(float(kills) / max(float(deaths), 1), 2)
            map_short = str(m.get("map_name","?")).replace("de_","").replace("cs_","").upper()

            embed.add_field(
                name=f"{r_label} | {map_short}",
                value=(
                    f"K/D/A: **{kills}/{deaths}/{m.get('assists',0)}** "
                    f"(KD: {kd}) | MVPs: {m.get('mvps',0)} | HS: {m.get('hs_kills',0)}"
                ),
                inline=False
            )
        if not items:
            embed.description = "Zadne zapasy."
        return embed


class ExternalView(discord.ui.View):
    """View pro zobrazení externích statistik s AI analýzou."""

    def __init__(self, data: dict, steam_id: str, ai: AIAnalyzer,
                 player_name: str, agg: ExternalStatsAggregator):
        super().__init__(timeout=300)
        self.data        = data
        self.steam_id    = steam_id
        self.ai          = ai
        self.player_name = player_name
        self.agg         = agg

    @discord.ui.button(label="Prehled", style=discord.ButtonStyle.primary, emoji="📊")
    async def show_overview(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        embed = _build_external_embed(self.data, self.player_name)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Leetify zapasy", style=discord.ButtonStyle.secondary, emoji="🎮")
    async def leetify_matches(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        loading = discord.Embed(title="Nacinam Leetify zapasy...", color=COLORS["info"])
        await interaction.edit_original_response(embed=loading, view=self)

        matches = await ExternalStatsAggregator().leetify.get_matches(self.steam_id, limit=10)
        embed   = discord.Embed(
            title=f"Leetify — posledni zapasy",
            color=COLORS["cs2"]
        )
        if matches:
            embed.description = self.agg.build_leetify_match_fields(matches)
            embed.set_footer(text="Data: Leetify | Zahrnuje preaim (crosshair placement) a KAST")
        else:
            embed.description = "Zadne Leetify zapasy nenalezeny."
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="AI Analyza", style=discord.ButtonStyle.secondary, emoji="🤖")
    async def ai_external(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        loading = discord.Embed(title="Analyzuji externa data...", color=COLORS["ai"])
        await interaction.edit_original_response(embed=loading, view=self)

        analysis = await self.ai.analyze_external_data(self.player_name, self.data)
        embed = discord.Embed(
            title="AI Analyza externich dat",
            description=analysis[:4096],
            color=COLORS["ai"]
        )
        embed.set_footer(text="Google Gemini AI | Leetify + FACEIT + csstats.gg")
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Obnovit", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        loading = discord.Embed(title="Obnova dat ze vsech zdroju...", color=COLORS["info"])
        await interaction.edit_original_response(embed=loading, view=self)
        self.data = await ExternalStatsAggregator().fetch_all(self.steam_id)
        embed = _build_external_embed(self.data, self.player_name)
        embed.set_footer(text="Data obnovena")
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Poslat do DM", style=discord.ButtonStyle.success, emoji="📬")
    async def send_dm(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        try:
            embed = _build_external_embed(self.data, self.player_name)
            await interaction.user.send(embed=embed)
            await interaction.followup.send("Odeslano do DM!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("Nelze odeslat DM — povol DM od botu.", ephemeral=True)


class QuickMatchDMView(discord.ui.View):
    """Rychlé akce v DM notifikaci po zápase."""

    def __init__(self, match_data: dict, player_name: str, ai: AIAnalyzer, steam_id: str):
        super().__init__(timeout=600)
        self.match_data  = match_data
        self.player_name = player_name
        self.ai          = ai
        self.steam_id    = steam_id

    @discord.ui.button(label="Detail zapasu", style=discord.ButtonStyle.primary, emoji="🔍")
    async def detail(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        embed = build_match_embed(self.match_data, self.player_name)
        view  = MatchDetailView(self.match_data, self.player_name, self.ai, self.steam_id)
        await interaction.followup.send(embed=embed, view=view)

    @discord.ui.button(label="Kompletni AI analyza", style=discord.ButtonStyle.secondary, emoji="🤖")
    async def full_ai(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        loading = discord.Embed(title="Analyzuji...", color=COLORS["ai"])
        msg     = await interaction.followup.send(embed=loading)
        analysis = await self.ai.analyze_match(self.match_data, self.player_name)
        embed = discord.Embed(
            title="Kompletni AI Analyza",
            description=analysis[:4096],
            color=COLORS["ai"]
        )
        await msg.edit(embed=embed)

    @discord.ui.button(label="Odeslat na csstats", style=discord.ButtonStyle.secondary, emoji="📤")
    async def upload(self, interaction: discord.Interaction, btn: discord.ui.Button):
        await interaction.response.defer()
        sc = self.match_data.get("sharecode")
        if not sc:
            await interaction.followup.send("Sharecode neni dostupny.", ephemeral=True)
            return
        result = await ExternalStatsAggregator().upload_sharecode_all(sc)
        await interaction.followup.send(result["message"], ephemeral=True)


# ════════════════════════════════════════════════════════════════
#  COG
# ════════════════════════════════════════════════════════════════

class MatchesCog(commands.Cog):
    def __init__(self, bot):
        self.bot   = bot
        self.steam = SteamAPI(os.getenv("STEAM_API_KEY", ""))
        self.ai    = AIAnalyzer()
        self.agg   = ExternalStatsAggregator()
        self.match_poller.start()
        log.info("[Matches] Match poller spusten (interval 15 min)")

    def cog_unload(self):
        self.match_poller.cancel()

    # ─── AUTOMATICKÝ POLLING ─────────────────────────────────

    @tasks.loop(minutes=15)
    async def match_poller(self):
        users = await self.bot.db.get_all_users()
        if not users:
            return
        log.info("[Matches] Polling pro %d uzivatelu...", len(users))
        for user in users:
            try:
                await self._check_new_matches(dict(user))
                await asyncio.sleep(2)
            except Exception as e:
                log.error("[Matches] Chyba pollingu %s: %s", user["discord_id"], e)

    @match_poller.before_loop
    async def before_poller(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(30)

    async def _check_new_matches(self, user: dict) -> bool:
        discord_id = user["discord_id"]
        steam_id   = user["steam_id"]
        auth_token = user.get("match_auth_token", "")
        last_code  = user.get("last_sharecode", "")

        if not auth_token or not last_code:
            return False

        new_code = await self.steam.get_next_match_code(steam_id, auth_token, last_code)
        if not new_code or new_code in ("n/a", last_code):
            return False

        log.info("[Matches] Novy zapas pro %s: %s", discord_id, new_code)

        try:
            match_id, _, _ = decode_sharecode(new_code)
        except Exception:
            match_id = 0

        match_data = {
            "sharecode": new_code,
            "match_id":  str(match_id),
            "map_name":  "Neznama",
            "result":    "N/A",
            "score_ct":  0, "score_t": 0,
            "kills":     0, "deaths": 0, "assists": 0,
            "hs_kills":  0, "mvps": 0, "score": 0,
            "adr":       0.0, "kd_ratio": 0.0,
        }

        await self.bot.db.save_match(discord_id, match_data)
        await self.bot.db.update_last_sharecode(discord_id, new_code)

        # Upload na csstats.gg automaticky
        asyncio.create_task(self.agg.upload_sharecode_all(new_code))

        if user.get("dm_notifications"):
            await self._send_match_dm(discord_id, match_data, steam_id)

        return True

    async def _send_match_dm(self, discord_id: str, match_data: dict, steam_id: str):
        try:
            discord_user = await self.bot.fetch_user(int(discord_id))
            if not discord_user:
                return
            ai_summary = await self.ai.analyze_match(match_data, discord_user.display_name)
            embed = build_dm_match_notification(match_data, ai_summary)
            view  = QuickMatchDMView(match_data, discord_user.display_name, self.ai, steam_id)
            await discord_user.send(embed=embed, view=view)
            log.info("[Matches] DM odeslano: %s", discord_id)
        except discord.Forbidden:
            log.warning("[Matches] DM zakazano pro %s", discord_id)
        except Exception as e:
            log.error("[Matches] DM chyba: %s", e)

    # ─── SLASH PŘÍKAZY ───────────────────────────────────────

    @app_commands.command(name="match", description="Detail posledniho nebo konkretniho zapasu")
    @app_commands.describe(sharecode="Volitelny sharecode (CSGO-XXXXX-...)")
    async def match_cmd(self, interaction: discord.Interaction, sharecode: str = None):
        await interaction.response.defer()

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("Nejsi zaregistrovan. Pouzij /setup.")
            return

        if sharecode:
            if not validate_sharecode(sharecode):
                await interaction.followup.send("Neplatny sharecode format.")
                return
            match = await self.bot.db.get_match_by_sharecode(sharecode)
        else:
            matches = await self.bot.db.get_match_history(str(interaction.user.id), limit=1)
            match   = matches[0] if matches else None

        if not match:
            await interaction.followup.send(
                "Zapas nenalezen.\n"
                "Zkus `/forcepoll` pro nacteni novych zapasu,\n"
                "nebo zadej sharecode z CS2 (Watch → Tvoje zapasy → Sdilet)."
            )
            return

        player      = await self.steam.get_player_summary(user["steam_id"])
        player_name = player.get("personaname", "Hrac") if player else "Hrac"
        match_dict  = dict(match)

        embed = build_match_embed(match_dict, player_name)
        view  = MatchDetailView(match_dict, player_name, self.ai, user["steam_id"])
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="history", description="Historie poslednich zapasu")
    @app_commands.describe(count="Pocet zapasu k zobrazeni (1-20)")
    async def history(self, interaction: discord.Interaction, count: int = 10):
        await interaction.response.defer()

        count = max(1, min(count, 20))
        user  = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("Nejsi zaregistrovan. Pouzij /setup.")
            return

        matches     = await self.bot.db.get_match_history(str(interaction.user.id), limit=count)
        player      = await self.steam.get_player_summary(user["steam_id"])
        player_name = player.get("personaname", "Hrac") if player else "Hrac"
        match_list  = [dict(m) for m in matches]

        embed = build_history_embed(match_list, player_name)
        view  = HistoryView(match_list, player_name)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="forcepoll", description="Zkontroluj nové zapasy ihned")
    async def forcepoll(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("Nejsi zaregistrovan. Pouzij /setup.", ephemeral=True)
            return

        user_dict = dict(user)

        # Informativní status embed
        status = discord.Embed(
            title="Hledam nove zapasy...",
            color=COLORS["info"]
        )
        status.add_field(name="Steam ID",        value=f"`{user_dict['steam_id']}`", inline=True)
        status.add_field(name="Posledni kod",
                         value=f"`{user_dict.get('last_sharecode') or 'neni'}`",
                         inline=True)
        status.add_field(name="Status",          value="Dotazuji Steam API...", inline=False)
        msg = await interaction.followup.send(embed=status, ephemeral=True)

        found = await self._check_new_matches(user_dict)

        if found:
            result = discord.Embed(
                title="Novy zapas nalezen!",
                color=COLORS["win"]
            )
            result.add_field(
                name="Co se stalo",
                value=(
                    "Zapas byl ulozen do databaze.\n"
                    "AI analyza odeslana do DM (pokud jsou zapnute notifikace).\n"
                    "Sharecode odeslan na csstats.gg ke zpracovani."
                ),
                inline=False
            )
            result.add_field(
                name="Dalsi kroky",
                value="Pouzij `/match` pro detail\nPouzij `/history` pro seznam zapasu",
                inline=False
            )
        else:
            result = discord.Embed(
                title="Zadny novy zapas",
                color=COLORS["warning"]
            )
            result.add_field(
                name="Proc to muze byt",
                value=(
                    "Valve servery zpracovavaji demos s 15-30 min zpozdenim.\n"
                    "Mozna mas nespravny Match Auth Token nebo Sharecode."
                ),
                inline=False
            )
            result.add_field(
                name="Co zkusit",
                value=(
                    "Otevri CS2 → Watch → Tvoje zapasy → klikni Sdilet → zkopiruj kod.\n"
                    "Pak zadej `/updatecode <kod>`."
                ),
                inline=False
            )

        await msg.edit(embed=result)

    @app_commands.command(name="updatecode", description="Aktualizuj posledni match sharecode")
    @app_commands.describe(sharecode="Sharecode z CS2 (CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX)")
    async def updatecode(self, interaction: discord.Interaction, sharecode: str):
        await interaction.response.defer(ephemeral=True)

        if not validate_sharecode(sharecode):
            await interaction.followup.send(
                "Neplatny format. Spravny format:\n`CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`",
                ephemeral=True
            )
            return

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("Nejsi zaregistrovan.", ephemeral=True)
            return

        old = user["last_sharecode"] or "neni"
        await self.bot.db.update_last_sharecode(str(interaction.user.id), sharecode)

        embed = discord.Embed(title="Sharecode aktualizovan", color=COLORS["win"])
        embed.add_field(name="Stary", value=f"`{old}`", inline=False)
        embed.add_field(name="Novy",  value=f"`{sharecode}`", inline=False)
        embed.set_footer(text="Pouzij /forcepoll pro okamzitou kontrolu")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="external",
        description="Statistiky z Leetify (preaim/crosshair%), FACEIT a csstats.gg"
    )
    async def external(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("Nejsi zaregistrovan. Pouzij /setup.")
            return

        loading = discord.Embed(
            title="Stahuji externa data...",
            description=(
                "Leetify (preaim, aim rating, clutch, utility...)\n"
                "FACEIT (level, ELO, per-mapa stats...)\n"
                "csstats.gg (rating, ADR, KAST...)\n\n"
                "Muze trvat az 15 sekund."
            ),
            color=COLORS["info"]
        )
        msg = await interaction.followup.send(embed=loading)

        data   = await self.agg.fetch_all(user["steam_id"])
        player = await self.steam.get_player_summary(user["steam_id"])
        pname  = player.get("personaname", "Hrac") if player else "Hrac"

        embed = _build_external_embed(data, pname)
        if player and player.get("avatarfull"):
            embed.set_thumbnail(url=player["avatarfull"])

        view = ExternalView(data, user["steam_id"], self.ai, pname, self.agg)
        await msg.edit(embed=embed, view=view)

    @app_commands.command(
        name="leetify",
        description="Detailni Leetify statistiky vcetne preaim (crosshair placement) a zapasy"
    )
    async def leetify_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user = await self.bot.db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send("Nejsi zaregistrovan. Pouzij /setup.")
            return

        loading = discord.Embed(title="Nacitam Leetify...", color=COLORS["info"])
        msg = await interaction.followup.send(embed=loading)

        profile, matches = await asyncio.gather(
            self.agg.leetify.get_profile(user["steam_id"]),
            self.agg.leetify.get_matches(user["steam_id"], limit=10)
        )
        player = await self.steam.get_player_summary(user["steam_id"])
        pname  = player.get("personaname", "Hrac") if player else "Hrac"

        if not profile:
            no_data = discord.Embed(
                title="Leetify — zadna data",
                description=(
                    "Profil nenalezen na Leetify.\n\n"
                    "Mozne priciny:\n"
                    "Profil je soukromy na Steamu\n"
                    "Hrac jeste nikdy nehral zapas po registraci na Leetify\n\n"
                    "Registruj se zdarma na https://leetify.com"
                ),
                color=COLORS["warning"]
            )
            await msg.edit(embed=no_data)
            return

        embed = discord.Embed(
            title=f"Leetify — {pname}",
            color=0x7B61FF  # Leetify fialova
        )
        if player and player.get("avatarfull"):
            embed.set_thumbnail(url=player["avatarfull"])

        # Profil sekce
        def bar(val):
            try:
                v = float(val)
                filled = min(10, max(0, round(v)))
                return "█" * filled + "░" * (10 - filled)
            except Exception:
                return "N/A"

        embed.add_field(
            name="Ratings (0-10, prumer = 5.0)",
            value=(
                f"**Leetify Rating: {profile.get('leetify_rating')}**\n"
                f"Aim:          `{bar(profile.get('aim_rating'))}` {profile.get('aim_rating')}\n"
                f"Utility:      `{bar(profile.get('utility_rating'))}` {profile.get('utility_rating')}\n"
                f"Positioning:  `{bar(profile.get('positioning_rating'))}` {profile.get('positioning_rating')}\n"
                f"Clutch:       `{bar(profile.get('clutch_rating'))}` {profile.get('clutch_rating')}\n"
            ),
            inline=False
        )
        embed.add_field(
            name="Pokrocile metriky",
            value=(
                f"**Crosshair placement (preaim):** `{profile.get('preaim_pct')}%`\n"
                f"Opening duel WR: `{profile.get('opening_duel_wr')}%`\n"
                f"CT rating: `{profile.get('ct_rating')}` | T rating: `{profile.get('t_rating')}`\n"
                f"Trade kill ratio: `{profile.get('trade_kill_ratio')}`\n"
                f"Flash success: `{profile.get('flash_success_rate')}%`\n"
                f"Utility dmg/round: `{profile.get('utility_damage_per_round')}`\n"
                f"Enemies flashed/round: `{profile.get('enemies_flashed_per_round')}`"
            ),
            inline=False
        )
        if profile.get("premier_rank"):
            embed.add_field(
                name="Rank",
                value=f"Premier: **{profile['premier_rank']}**",
                inline=True
            )
        embed.add_field(
            name="Sledovano",
            value=f"`{profile.get('games_tracked')}` zapasu",
            inline=True
        )

        # Match history
        if matches:
            embed.add_field(
                name="Posledni zapasy",
                value=self.agg.build_leetify_match_fields(matches),
                inline=False
            )

        embed.set_footer(text="Data: Leetify | leetify.com")
        embed.add_field(
            name="Odkaz",
            value=f"[Otevrit na Leetify]({profile.get('profile_url')})",
            inline=False
        )

        await msg.edit(embed=embed)


# ── Helpers ────────────────────────────────────────────────────

def _build_external_embed(data: dict, player_name: str) -> discord.Embed:
    agg = ExternalStatsAggregator()
    embed = discord.Embed(
        title=f"Externa data — {player_name}",
        color=COLORS["cs2"]
    )
    sources_found = list(data.keys())
    embed.description = (
        f"Zdroje: `{'`, `'.join(sources_found) if sources_found else 'zadne'}`\n"
        f"Pouzij tlacitka pro AI analyzu nebo obnoveni."
    )
    for name, value, inline in agg.build_embed_fields(data):
        embed.add_field(name=name, value=value[:1024], inline=inline)
    embed.set_footer(text="Leetify | FACEIT | csstats.gg")
    return embed


async def setup(bot):
    await bot.add_cog(MatchesCog(bot))
