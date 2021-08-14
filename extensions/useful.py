import discord
from discord.ext import commands
from discord.http import Route

import core
from utils import checks

__all__ = ("setup",)


voice_games = {
    "youtube": "755600276941176913",
    "poker": "755827207812677713",
    "betrayal": "773336526917861400",
    "fishing": "814288819477020702",
    "chess": "832012586023256104",
}


class GameConverter(commands.Converter):
    async def convert(self, ctx: core.Context, argument: str):
        game = voice_games.get(argument.lower().strip())
        if game is None:
            raise commands.BadArgument("Invalid voice game specified.")
        return game


class Useful(commands.Cog):
    def __init__(self, bot: core.Bot):
        self.bot = bot

    @core.command(
        aliases=("vcgame", "voicechatgame", "interactivegame"),
        examples=voice_games.keys(),
        params={"game": "The game you want to play."},
        returns="An invite link for the channel.",
    )
    @checks.can_run(create_instant_invite=True)
    async def vc_game(self, ctx: core.Context, game: GameConverter, channel: discord.VoiceChannel = None):
        """Creates an invite link for an interactive game in a Voice Channel"""
        json = {
            "max_age": 86400,
            "max_uses": 0,
            "target_application_id": game,
            "target_type": 2,
            "temporary": False,
            "validate": None,
        }
        if channel is None:
            voice_state = ctx.author.voice
            if voice_state is None:
                raise commands.BadArgument("You are not in a voice channel and you did not specify a channel.")
            channel = voice_state.channel
        data = await self.bot.http.request(Route("POST", "/channels/" + str(channel.id) + "/invites"), json=json)
        if data.get("guild") is None or data.get("message") is not None:
            return await ctx.send("Something went wrong when creating the invite.")
        await ctx.send("https://discord.com/invite/" + data["code"])


def setup(bot: core.Bot):
    bot.add_cog(Useful(bot))
