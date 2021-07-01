import asyncio
import json

import aiohttp
import discord
from discord.ext import commands

import core
from core.bot import CustomBot
from core.config import twitter_bearer_token
from core.context import CustomContext

__all__ = ("setup",)

API_URL = "https://api.twitter.com"


class TwitterStreamer:
    def __init__(self, bot: CustomBot):
        self.bot = bot
        self.session = None

    async def start(self):
        url = (
            API_URL
            + "/2/tweets/search/stream?tweet.fields=created_at&expansions=author_id&user.fields=created_at"
        )

        # https://developer.twitter.com/en/docs/twitter-api/v1/tweets/filter-realtime/guides/connecting
        stall_timeout = 90
        network_error_wait = network_error_wait_step = 0.25
        network_error_wait_max = 16
        http_error_wait = http_error_wait_start = 5
        http_error_wait_max = 320
        http_420_error_wait_start = 60

        if self.session is None or self.session.closed:
            headers = dict(self.bot.session.headers) | {"Authorization": f"Bearer {twitter_bearer_token}"}
            self.session = aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(sock_read=stall_timeout)
            )

        try:
            while True:
                try:
                    async with self.session.get(url) as response:
                        if response.ok:
                            async for line in response.content:
                                line = line.strip()
                                if line:
                                    await self.on_data(line)
                        else:
                            if response.status == 420 and http_error_wait < http_420_error_wait_start:
                                http_error_wait = http_420_error_wait_start

                            await asyncio.sleep(http_error_wait)

                            http_error_wait *= 2
                            if response.status != 420 and http_error_wait > http_error_wait_max:
                                http_error_wait = http_error_wait_max

                except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError):
                    await asyncio.sleep(network_error_wait)

                    network_error_wait += network_error_wait_step
                    network_error_wait = min(network_error_wait, network_error_wait_max)
        except asyncio.CancelledError:
            return
        finally:
            await self.session.close()

    async def on_data(self, data: bytes):
        data = json.loads(data)
        print(data)


class Twitter(commands.Cog):
    def __init__(self, bot: CustomBot):
        self.bot = bot
        self.handler = TwitterStreamer(bot)
        self.bot.loop.create_task(self.handler.start())


def setup(bot: CustomBot):
    bot.add_cog(Twitter(bot))
