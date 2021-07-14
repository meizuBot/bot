from typing import Dict, Union
from discord.ext import commands, tasks
import core
import discord
import json
from utils.time import utcnow
from config import gist
import logging
from aiohttp import web

log = logging.getLogger(__name__)

class APIHandler:
    def __init__(self, bot: core.CustomBot) -> None:
        self.bot = bot
        self.json = JSONHandler(self.bot)

        self.app = web.Application()
        self.runner = web.AppRunner(self.app, access_log=log)
        self.site = None
        self.bot.loop.create_task(self.run())

    def generate_routes(self) -> tuple:
        prefix = "/api"
        return (
            web.get(f"{prefix}/all", handler=self.all),
            web.get(f"{prefix}/command/{{command}}", handler=self.command),
            web.get(f"{prefix}/stats", handler=self.stats),
            web.get(f"{prefix}/socket", handler=self.socket),
            web.get(f"{prefix}/cogs", handler=self.cogs),
        )

    async def all(self, request):
        return web.json_response(await self.json.generate_all())

    async def command(self, request):
        command = self.bot.get_command(request.match_info["command"])
        if command is None:
            return web.json_response({"message": "Command not found", "code": 404}, status=404)
        return web.json_response(self.json.generate_command(command))

    async def socket(self, request):
        return web.json_response(await self.json.generate_socket())

    async def stats(self, request):
        return web.json_response(await self.json.generate_stats())

    async def cogs(self, request):
        return web.json_response(self.json.generate_cogs())

    async def run(self):
        self.app.add_routes(self.generate_routes())

        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "localhost", 8080)
        await self.site.start()

        log.info("Backend JSON API started up.")



class JSONHandler:
    def __init__(self, bot: core.CustomBot) -> None:
        self.bot = bot

    async def generate_stats(self) -> Dict[str, int]:
        data = {
            "guilds": 0,
            "unique_users": len(self.bot.users),
            "total_members": 0,
            "total_commands": len(tuple(i for i in self.bot.walk_commands() if i.cog is not None and not i.cog.qualified_name == "Jishaku")),
            "total_commands_run": await self.bot.pool.fetchval("SELECT COUNT(*) FROM stats.commands"),
            "text_channels": 0,
            "voice_channels": 0
        }
        for guild in self.bot.guilds:
            data["guilds"] +=1
            if guild.unavailable:
                continue
            
            data["total_members"] += guild.member_count
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    data["text_channels"] += 1
                elif isinstance(channel, discord.VoiceChannel):
                    data["voice_channels"] += 1

        return data

    async def generate_socket(self) -> Dict[str, int]:
        return dict(await self.bot.pool.fetch("SELECT * FROM stats.socket"))

    def generate_command(self, command: commands.Command) -> dict:
        data = {
            "name": command.name,
            "qualified_name": command.qualified_name,
            "aliases": command.aliases,
            "description": command.description,
            "signature": command.signature,
            "parent_name": command.full_parent_name,
            # extra stuff here
            "cooldown": getattr(command, "cooldown", None),
            "returns": getattr(command, "returns", None),
            "params": getattr(command, "params_", None),

            "subcommands": self.generate_subcommands(command)
        }
        examples = getattr(command, "examples", None)
        if examples:
            if examples[0] is not None:
                data["examples"] = examples
            else:
                data["examples"] = []
        return data

    def generate_subcommands(self, command: Union):
        if not isinstance(command, commands.Group):
            return {}
        if command.commands == set():
            return {}
        data = {}
        for cmd in command.commands:
            data[cmd.name] = self.generate_command(cmd)

        return data

    def generate_cogs(self):
        data = {}
        for cog_name, cog in self.bot.cogs.items():
            if getattr(cog, "emoji", None) is None:
                continue
            cdata = {
                "description": cog.description,
                "commands": {}
            }
            for command in cog.get_commands():
                cdata["commands"][command.name] = self.generate_command(command)
            data[cog_name] = cdata

        return data

    async def generate_all(self):
        return {
            "stats": await self.generate_stats(),
            "socket": await self.generate_socket(),
            "cogs": self.generate_cogs()
        }


class BackendAPI(commands.Cog):
    def __init__(self, bot: core.CustomBot):
        self.bot = bot
        self.headers = {"Authorization": f"token {gist.token}", "User-Agent": "ppotatoo", "Accept": "application/vnd.github.v3+json"}
        self.gist_update.start()

        self.api = APIHandler(self.bot)

    def cog_unload(self):
        self.gist_update.stop()

    @tasks.loop(minutes=30)
    async def gist_update(self):
        content = json.dumps(await self.api.json.generate_all(), indent=4)
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

    
def setup(bot: core.CustomBot):
    bot.add_cog(BackendAPI(bot))