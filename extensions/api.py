from discord.ext import commands, tasks
import core
import discord
import json
from utils.time import utcnow
from config import gist
import logging

log = logging.getLogger(__file__)

class BackendAPI(commands.Cog):
    def __init__(self, bot: core.CustomBot):
        self.bot = bot
        self.headers = {"Authorization": f"token {gist.token}", "User-Agent": "ppotatoo", "Accept": "application/vnd.github.v3+json"}
        self.gist_update.start()

    def cog_unload(self):
        self.gist_update.stop()

    @tasks.loop(minutes=30)
    async def gist_update(self):
        content = json.dumps(await self.generate_data())
        description = f"Last updated at {utcnow()}"
        data = {
            "description": description,
            "files": {
                "data.json": {
                    "content": content
                }
            }
        }
        url = "https://api.github.com/gists/" + gist.id
        async with self.bot.session.patch(url, json=data, headers=self.headers) as resp:
            log.info("Posted stats to gist.")

    @gist_update.before_loop
    async def wait(self):
        await self.bot.wait_until_ready()

    def generate_subcommands(command: core.Group):
        ...

    async def generate_data(self) -> dict:
        bot = self.bot
        data = {
            "stats": {
                "guilds": 0,
                "members": 0,
                "total_commands": len(tuple(bot.walk_commands())),
                "total_commands_run": await self.bot.pool.fetchval("SELECT COUNT(*) FROM stats.commands"),
                "text_channels": 0,
                "voice_channels": 0,
            },
            "socket": dict(await self.bot.pool.fetch("SELECT * FROM stats.socket")),
            "commands": {}
        }
        for guild in bot.guilds:
            data["stats"]["guilds"] +=1
            if guild.unavailable:
                continue
            
            data["stats"]["members"] += guild.member_count
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    data["stats"]["text_channels"] += 1
                elif isinstance(channel, discord.VoiceChannel):
                    data["stats"]["voice_channels"] += 1

        return data

    
def setup(bot: core.CustomBot):
    bot.add_cog(BackendAPI(bot))