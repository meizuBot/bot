import logging
from asyncio import AbstractEventLoop, Event
from collections import Counter, deque
from random import SystemRandom
from statistics import mean
from typing import List, Union

import discord
from aiohttp import ClientSession
from discord.ext import commands

import config
from web import ipc

log = logging.getLogger("bot")
logging.basicConfig(level=logging.INFO)

__all__ = ("CustomBot",)


@ipc.route(name="test")
async def test(text):
    return "this is a cool thing: {}".format(text)


@ipc.route(name="stats")
async def cool(bot):
    return {
        "users": format(sum(1 for i in bot.users if not i.bot), ","),
        "guilds": format(len(bot.guilds), ","),
    }


def get_prefix(bot: "CustomBot", message: discord.Message) -> Union[List[str], str]:
    return commands.when_mentioned_or(*config.prefix)(bot, message)


class Extra:
    def __init__(self):
        self.message_latencies = deque(maxlen=500)
        self.socket_stats = Counter()
        self.command_stats = Counter()

    @property
    def message_latency(self):
        return 1000 * mean(lat.total_seconds() for lat in self.message_latencies)


class CustomBot(commands.Bot):
    loop: AbstractEventLoop

    def __init__(self, loop: AbstractEventLoop) -> None:
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            command_prefix=get_prefix,
            skip_after_prefix=True,
            case_insensitive=True,
            intents=intents,
            max_messages=750,
            owner_id=809587169520910346,
            loop=loop,
        )

        self._BotBase__cogs = commands.core._CaseInsensitiveDict()

        self.loop.create_task(self.__prep())
        self.prepped = Event()

        self.random = SystemRandom()
        self.extra = Extra()
        self.start_time = None

        self.context = commands.Context

    async def __prep(self):
        self.session = ClientSession(
            headers={"User-Agent": "Walrus (https://github.com/ppotatoo/bot-rewrite)"}
        )
        await self.wait_until_ready()
        async with self.pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO public.guilds (id) VALUES ($1) ON CONFLICT DO NOTHING",
                tuple((g.id,) for g in self.guilds),
            )
        self.prepped.set()
        log.info("Completed preperation.")

    def load_extensions(self):
        extensions = [
            "core.context",
            "extensions.help",
            "extensions.osu",
            "extensions.errorhandler",
            "extensions.interactions",
            "extensions.reminders",
            "extensions.background",
            "extensions.general",
            "extensions.owner",
            "extensions.casino",
            "extensions.useful",
            "extensions.giveaways",
        ]
        for ext in extensions:
            self.load_extension(ext)
        self.load_extension("jishaku")
        log.info("Loaded extensions")

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=cls or self.context)

    async def login(self, token: str):
        await super().login(token)
        self.start_time = discord.utils.utcnow()

    def run(self, *args, **kwargs):
        self.load_extensions()
        super().run(*args, **kwargs)

    async def close(self):
        await self.session.close()
        await self.pool.close()
        await super().close()

    async def on_ready(self):
        log.info("Connected to Discord.")

    @staticmethod
    def embed(**kwargs):
        color = kwargs.pop("color", discord.Color.blurple())
        return discord.Embed(**kwargs, color=color)

    async def paste(self, data: str, url="https://mystb.in"):
        async with self.session.post(url + "/documents", data=bytes(str(data), "utf-8")) as r:
            res = await r.json()
        key = res["key"]
        return url + f"/{key}"

    async def getch_user(self, user_id: int) -> discord.User:
        user = self.get_user(user_id)
        if user is None:
            user = await self.fetch_user(user_id)
        return user
