import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import NamedTuple, Union

import aiohttp
from discord import ButtonStyle, Embed, Interaction, ui
from discord.ext import commands
from humanize import precisedelta

import core
from config import osu
from utils import MENTION_REGEX
from utils.buttons import StopButton
from utils.decos import wait_until_ready

EMOJIS = {
    "Main": "<:osu:850783495386300416>",
    "Socials": "<:socials:851127959758176256>",
    "Scores": "<:catshrug:851131304736194600>",
}

log = logging.getLogger(__name__)


class OsuButton(ui.Button["OsuProfileView"]):
    def __init__(self, label: str):
        super().__init__(label=label, emoji=EMOJIS[label], style=ButtonStyle.blurple)

    async def callback(self, interaction: Interaction):
        self.view.embed.description = self.view.data[self.label]
        await interaction.response.edit_message(embed=self.view.embed)


class OsuProfileView(ui.View):
    embed: Embed

    def __init__(self, ctx: core.Context, messages: dict):
        super().__init__()
        self.ctx = ctx
        self.data = messages

        for i in EMOJIS:
            self.add_item(OsuButton(label=i))
        self.add_item(StopButton())

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(f"This view is owned by {self.ctx.author}.", ephemeral=True)
            return False
        return True

    def construct_embed(self):
        self.embed = self.ctx.bot.embed(
            title=f"{self.data['username']}'s osu! profile",
            description=self.data["Main"],
            url=self.data["url"],
        )
        self.embed.set_footer(text=self.data["footer"])
        self.embed.set_thumbnail(url=self.data["avatar_url"])

    async def start(self):
        self.construct_embed()
        await self.ctx.send(embed=self.embed, view=self)


API_URL = "https://osu.ppy.sh/api/v2"
OSU_PROFILE_REGEX = re.compile(r"https?://osu\.ppy\.sh/users/(?P<id>[0-9]+)")

OsuConverterResponse = NamedTuple("ConverterResponse", [("search", Union[int, str]), ("type", str)])


class OsuUserConverter(commands.Converter):
    async def convert(self, ctx: "core.Context", argument) -> OsuConverterResponse:
        if argument is None:
            _id = await ctx.bot.pool.fetchval(
                "SELECT id FROM users.games WHERE game = 'osu' AND snowflake = $1", ctx.author.id
            )
            if _id is None:
                raise commands.BadArgument("You are not registered.")
            return OsuConverterResponse(search=_id, type="id")
        if url_match := OSU_PROFILE_REGEX.match(argument.strip("<>")):
            return OsuConverterResponse(search=str(url_match["id"]), type="id")
        if mention_match := MENTION_REGEX.fullmatch(argument):
            snowflake = int(mention_match["id"])
            _id = await ctx.bot.pool.fetchval(
                "SELECT id FROM users.games WHERE game = 'osu' AND snowflake = $1", snowflake
            )
            if _id is None:
                raise commands.BadArgument(
                    "That user is not registered." if _id != ctx.author.id else "You are not registered."
                )
            return OsuConverterResponse(search=_id, type="id")

        return OsuConverterResponse(search=argument, type="username")


class Osu(commands.Cog):
    def __init__(self, bot: core.Bot):
        self.bot = bot
        self.emoji = "<:osu:850783495386300416>"
        self.show_subcommands = True

        self.headers = {"Authorization": None}

        bot.loop.create_task(self.acquire_bearer_token())

    @wait_until_ready()
    async def acquire_bearer_token(self):
        url = "https://osu.ppy.sh/oauth/token"
        data = {
            "client_id": osu.client_id,
            "client_secret": osu.client_secret,
            "grant_type": "client_credentials",
            "scope": "public",
        }
        while not self.bot.is_closed():
            async with self.bot.session.post(url, json=data) as r:
                try:
                    data = await r.json()
                except aiohttp.ContentTypeError:
                    log.warning(f"OSU api responded with text/html: {await r.json()}")
            self.headers["Authorization"] = "Bearer " + data["access_token"]
            await asyncio.sleep(data["expires_in"])

    async def get_user(self, search: OsuConverterResponse) -> dict:
        url = API_URL + f"/users/{search.search}/osu?key={search.type}"
        async with self.bot.session.get(url, headers=self.headers) as r:
            if r.status == 404:
                raise commands.BadArgument("Could not find anything from that query.")
            data = await r.json()
        return data

    @core.group(usage="<subcommand>")
    async def osu(self, ctx: core.Context):
        """If you do not invoke a subcommand, this command sends help."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @osu.command(
        name="profile",
        examples=("whitecat", "https://osu.ppy.sh/u/4504101", "@ppotatoo#9688"),
        params={
            "query": "The profile you want to look up, this can be a username, profile link, or a user. "
            "Leave blank to view your own stats."
        },
        returns="An interactive view that showcases an osu! user's profile.",
    )
    async def osu_profile(self, ctx: core.Context, query: str = None):
        """A command to view someone's osu! profile.
        You can view the user's stats and socials through an interactive button menu.
        """
        data = await self.get_user(await OsuUserConverter().convert(ctx, query))

        stats = data.get("statistics", {})
        username = data.get("username")
        join = datetime.fromisoformat(data.get("join_date")).strftime("%b %d %Y")
        plays_with = data.get("playstyle") or ["This user has not set what they play with."]
        ranks = stats.get("grade_counts")
        time_played = precisedelta(
            timedelta(seconds=stats.get("play_time") or 0),
            suppress=["months", "years", "days"],
            format="%0.0f",
            minimum_unit="minutes",
        )
        _global = stats["global_rank"] or 0
        _country = stats.get("rank", {})["country"] or 0
        data = {
            "username": username,
            "url": "https://osu.ppy.sh/users/" + str(data.get("id")),
            "avatar_url": data.get("avatar_url", "https://osu.ppy.sh/images/layout/avatar-guest.png"),
            "footer": f"{username} started playing osu! on {join}",
            "Main": (
                f"**PP:** `{stats.get('pp')}`\n"
                f"**Global Rank:** `{_global:,d}`\n"
                f"**Country Rank:** :flag_{data.get('country_code').lower()}: `{_country:,d}`\n"
                f"**Replays Watched by Others:** `{stats.get('replays_watched_by_others', 0):,d}`\n"
                f"**First Place Ranks:** `{data.get('scores_first_count'):,d}`\n"
                f"**Average Accuracy:** `{(stats.get('hit_accuracy', 0) / 100):.2%}`\n"
                f"**Plays With:** `{', '.join(i.capitalize() for i in plays_with)}`\n"
                f"**Play Time:** `{time_played}`"
            ),
            "Socials": (
                f"**Discord:** `{data.get('discord') or 'This user has not set their Discord'}`\n"
                f"**Website:** `{data.get('website') or 'This user has not set their website'}`\n"
                f"**Twitter:** `{data.get('twitter') or 'This user has not set their Twitter'}`\n"
                f"**Occupation:** `{data.get('occupation') or 'This user has not set their occupation'}`\n"
                f"**Location:** `{data.get('location') or 'This user has not set their location'}`\n"
                f"**Forum Posts:** `{data.get('post_count', 0):,d}`"
            ),
            "Scores": (
                f"**SS Ranks:** `{ranks.get('ss', 0):,d}`\n"
                f"**S Ranks:** `{ranks.get('s', 0):,d}`\n"
                f"**A Ranks:** `{ranks.get('a', 0):,d}`\n"
                f"**Total Score:** `{stats.get('total_score', 0):,d}`\n"
                f"**Ranked Score:** `{stats.get('ranked_score', 0):,d}`\n"
                f"**Play Count:** `{stats.get('play_count', 0):,d}`\n"
                f"**Total Hits:** `{stats.get('total_hits', 0):,d}`\n"
                f"**Maximum Combo:** `{stats.get('maximum_combo', 0):,d}`"
            ),
        }
        view = OsuProfileView(ctx, data)
        await view.start()

    @osu.command(
        name="register",
        examples=(
            "whitecat",
            "https://osu.ppy.sh/u/4504101",
        ),
        params={"query": "The user you want to register yourself to."},
        returns="Confirmation that you got registered.",
    )
    async def osu_register(self, ctx: core.Context, *, query: OsuUserConverter):
        """Simple command that registers you to an osu! profile
        Two users can have the same profile.
        """
        data = await self.get_user(query)

        await self.bot.pool.register_user("osu", ctx.author.id, str(data["id"]))
        await ctx.send("Registered you into the database.")


def setup(bot: core.Bot):
    bot.add_cog(Osu(bot))
